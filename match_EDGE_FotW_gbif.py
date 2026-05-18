"""
EDGE × FotW match using GBIF-normalised FotW taxonomy.

Strategy
--------
Phase 1 — FotW → GBIF → EDGE  (no network calls; uses pre-resolved taxonomy)
  FotW taxon names are resolved to their GBIF-accepted names via
  FotW_DB/fotw_taxonomy_resolved.csv (produced by resolve_fotw_taxonomy.py).
  The GBIF-accepted names are matched against the EDGE dataset.

  This is the primary match. It catches:
    - Direct matches (FotW name = EDGE name, both on current GBIF backbone)
    - FotW synonym cases (FotW carries an old name; GBIF accepted name = EDGE name)

Phase 2 — EDGE.List → GBIF → FotW  (network calls; ~10 min for ~9,700 queries)
  For EDGE.List species that remain unmatched after Phase 1, the EDGE name is
  queried against GBIF. If GBIF returns a different accepted name and that name
  is present in FotW, a match is recorded.

  This is necessary because the EDGE dataset was built on a snapshot of the GBIF
  backbone that predates the current one. Some EDGE names are now considered
  synonyms by GBIF, whose current accepted name appears in FotW under the updated
  name. Phase 1 alone misses these cases because FotW (after GBIF normalisation)
  carries the current accepted name, while EDGE still uses the outdated synonym.

  Example: EDGE has Aneulophus_congoensis; GBIF now treats this as a synonym of
  Aneulophus_africanus; FotW has Aneulophus_africanus. Phase 1 finds no match
  (FotW's accepted name is not in EDGE). Phase 2 queries GBIF for the EDGE name,
  gets Aneulophus_africanus as the accepted name, and finds it in FotW.

match_method column in output
------------------------------
  direct               FotW name = EDGE name (same string on both sides)
  fotw_synonym         FotW name was a GBIF synonym; accepted name = EDGE name
  edge_synonym         EDGE name was a GBIF synonym; accepted name is in FotW
                       (found by Phase 2)

Inputs
------
  ../FotW_DB/fotw_taxonomy_resolved.csv  — GBIF-resolved FotW taxonomy
  ../FotW_DB/occurrences.csv             — FotW occurrence records (for counts)
  Forest_etal_EDGEangio_tableS1_...csv   — EDGE dataset
  fotw_taxon_uuids.csv                   — existing FotW taxon UUIDs

Outputs
-------
  EDGE_FotW_matched_species_gbif.csv     — matched species (one row per species)
  EDGE_FotW_report_gbif.md               — Markdown report

Usage
-----
    # Run both phases (recommended):
    python3 match_EDGE_FotW_gbif.py

    # Phase 1 only (fast, no network):
    python3 match_EDGE_FotW_gbif.py --phase 1

    # Control Phase 2 network load:
    python3 match_EDGE_FotW_gbif.py --workers 8 --delay 0.3
"""

import argparse
import csv
import json
import os
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE       = os.path.dirname(os.path.abspath(__file__))
EDGE_CSV   = os.path.join(BASE, "Forest_etal_EDGEangio_tableS1_EDGEspp_RL&Pred.csv")
RESOLVED   = os.path.join(BASE, "..", "FotW_DB", "fotw_taxonomy_resolved.csv")
OCC_CSV    = os.path.join(BASE, "..", "FotW_DB", "occurrences.csv")
UUID_CSV   = os.path.join(BASE, "fotw_taxon_uuids.csv")
OUT_CSV    = os.path.join(BASE, "EDGE_FotW_matched_species_gbif.csv")
OUT_MD     = os.path.join(BASE, "EDGE_FotW_report_gbif.md")

GBIF_MATCH_URL = (
    "https://api.gbif.org/v1/species/match"
    "?kingdom=Plantae&verbose=false&name={name}"
)
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; EDGE-FotW-research-bot/1.0; "
        "Boise State University; contact: sven.buerki@boisestate.edu)"
    ),
    "Accept": "application/json",
}

OUT_FIELDS = [
    "EDGE_rank", "species", "family", "order",
    "edge_med", "ed_med", "tbl_med", "pext_med",
    "threat", "RL_ERP",
    "EDGE_List", "EDGE_Borderline", "EDGE_Research", "EDGE_Watch",
    "fotw_original_name", "fotw_gbif_status", "fotw_taxon_id",
    "match_method", "n_fotw_records", "taxon_url",
]

# ── Loaders ───────────────────────────────────────────────────────────────────
def load_edge(path):
    """Returns edge_meta (all species) and edge_list_keys (EDGE.List only)."""
    edge_meta      = {}
    edge_list_keys = set()
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            key = row["Species"].strip().strip('"').replace(" ", "_")
            edge_meta[key] = row
            if row["EDGE.List"].strip('"') == "y":
                edge_list_keys.add(key)
    return edge_meta, edge_list_keys

def load_resolved_taxonomy(path):
    """
    Returns:
      resolved  — dict  original_key → {accepted_key, gbif_status, taxon_id, …}
      fotw_accepted_index — dict  accepted_key → {taxon_id, orig_key, gbif_status}
        (for Phase 2 reverse lookups)
    """
    resolved            = {}
    fotw_accepted_index = {}
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            g = row["genus"].strip()
            e = row["specificEpithet"].strip()
            if not (g and e):
                continue
            orig_key = f"{g}_{e}"
            acc      = row["accepted_name"].strip()
            parts    = acc.split()
            acc_key  = f"{parts[0]}_{parts[1]}" if len(parts) >= 2 else orig_key

            entry = {
                "accepted_key"     : acc_key,
                "gbif_status"      : row["gbif_status"],
                "taxon_id"         : row["taxonID"],
                "accepted_gbif_url": row["accepted_gbif_url"],
            }
            resolved[orig_key] = entry

            # Index by accepted key (keep first / highest-occurrence entry;
            # duplicates are resolved later in build_matches)
            if acc_key not in fotw_accepted_index:
                fotw_accepted_index[acc_key] = {
                    "taxon_id"  : row["taxonID"],
                    "orig_key"  : orig_key,
                    "gbif_status": row["gbif_status"],
                }

    return resolved, fotw_accepted_index

def load_occurrence_counts(path):
    counts = defaultdict(int)
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            g = row["genus"].strip()
            e = row["specificEpithet"].strip()
            if g and e:
                counts[f"{g}_{e}"] += 1
    return dict(counts)

def load_uuids(path):
    uuids = {}
    if not os.path.exists(path):
        return uuids
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            key = row["species_key"].strip()
            url = row.get("taxon_url", "").strip()
            if key and url:
                uuids[key] = url
    return uuids

# ── Match helpers ─────────────────────────────────────────────────────────────
def make_match_row(edge_key, edge_meta, fotw_orig_key, fotw_gbif_status,
                   fotw_taxon_id, n_occ, match_method, existing_uuids):
    edge_row  = edge_meta[edge_key]
    taxon_url = existing_uuids.get(edge_key, "")
    if not taxon_url and fotw_taxon_id:
        taxon_url = f"https://floraoftheworld.org/taxons/{fotw_taxon_id}"
    return {
        "_edge_key"         : edge_key,
        "EDGE_rank"         : int(edge_row["EDGE.rank"]),
        "species"           : edge_key.replace("_", " "),
        "family"            : edge_row["Family"].strip(),
        "order"             : edge_row["Order"].strip(),
        "edge_med"          : edge_row["edge.med"].strip(),
        "ed_med"            : edge_row["ed.med"].strip(),
        "tbl_med"           : edge_row["tbl.med"].strip(),
        "pext_med"          : edge_row["pext.med"].strip(),
        "threat"            : edge_row["threat"].strip(),
        "RL_ERP"            : edge_row["RL.ERP"].strip(),
        "EDGE_List"         : edge_row["EDGE.List"].strip('"'),
        "EDGE_Borderline"   : edge_row["EDGE.Borderline"].strip('"'),
        "EDGE_Research"     : edge_row["EDGE.Research"].strip('"'),
        "EDGE_Watch"        : edge_row["EDGE.Watch"].strip('"'),
        "fotw_original_name": fotw_orig_key.replace("_", " "),
        "fotw_gbif_status"  : fotw_gbif_status,
        "fotw_taxon_id"     : fotw_taxon_id,
        "match_method"      : match_method,
        "n_fotw_records"    : n_occ,
        "taxon_url"         : taxon_url,
    }

# ── Phase 1 ───────────────────────────────────────────────────────────────────
def phase1_match(edge_meta, resolved, occ_counts, existing_uuids):
    """
    FotW → GBIF → EDGE.
    No network calls; uses pre-resolved taxonomy.
    Returns matched list and set of matched EDGE keys.
    """
    all_fotw_keys  = set(resolved.keys()) | set(occ_counts.keys())
    matched        = []
    seen_edge_keys = set()

    for orig_key in all_fotw_keys:
        res = resolved.get(orig_key)
        if res:
            acc_key     = res["accepted_key"]
            gbif_status = res["gbif_status"]
            taxon_id    = res["taxon_id"]
        else:
            acc_key     = orig_key   # occurrence-only: no GBIF resolution
            gbif_status = "unknown"
            taxon_id    = ""

        if gbif_status == "DOUBTFUL":
            continue
        if acc_key not in edge_meta:
            continue

        n_occ = occ_counts.get(orig_key, 0)

        # Deduplicate: multiple FotW synonyms may resolve to the same accepted name.
        # Keep the entry with the most occurrence records.
        if acc_key in seen_edge_keys:
            for m in matched:
                if m["_edge_key"] == acc_key and n_occ > m["n_fotw_records"]:
                    m["n_fotw_records"]     = n_occ
                    m["fotw_original_name"] = orig_key.replace("_", " ")
                    m["fotw_gbif_status"]   = gbif_status
                    m["fotw_taxon_id"]      = taxon_id
                    break
            continue

        seen_edge_keys.add(acc_key)
        method = "direct" if acc_key == orig_key else "fotw_synonym"
        matched.append(make_match_row(
            acc_key, edge_meta, orig_key, gbif_status,
            taxon_id, n_occ, method, existing_uuids,
        ))

    return matched, seen_edge_keys

# ── Phase 2 ───────────────────────────────────────────────────────────────────
def gbif_match_name(edge_key, delay):
    """Query GBIF name-match for one EDGE Genus_epithet key."""
    time.sleep(delay)
    name = edge_key.replace("_", " ")
    url  = GBIF_MATCH_URL.format(name=name.replace(" ", "%20"))
    try:
        req  = Request(url, headers=HEADERS)
        with urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if data.get("matchType") == "NONE":
            return edge_key, "", 0, ""
        species_full = data.get("species", "")
        parts        = species_full.split()
        acc_key      = f"{parts[0]}_{parts[1]}" if len(parts) >= 2 else ""
        confidence   = data.get("confidence", 0)
        return edge_key, acc_key, confidence, ""
    except (HTTPError, URLError, Exception) as exc:
        return edge_key, "", 0, str(exc)

def phase2_match(unmatched_edge_list, edge_meta, fotw_accepted_index,
                 occ_counts, existing_uuids, workers, delay, min_conf):
    """
    EDGE.List → GBIF → FotW.
    Queries GBIF for each unmatched EDGE.List species; checks if the returned
    accepted name is present in FotW's GBIF-normalised taxonomy.
    """
    total    = len(unmatched_edge_list)
    new_hits = []
    done = errors = 0
    t0   = time.time()

    print(f"\nPhase 2: {total:,} EDGE.List queries "
          f"({workers} workers · {delay}s delay · "
          f"~{total * delay / workers / 60:.0f} min)\n")

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(gbif_match_name, k, delay): k
            for k in unmatched_edge_list
        }
        for future in as_completed(futures):
            edge_key, acc_key, conf, err = future.result()
            done += 1
            if err:
                errors += 1

            hit = False
            if acc_key and acc_key != edge_key and conf >= min_conf:
                fotw_info = fotw_accepted_index.get(acc_key)
                if fotw_info:
                    taxon_id    = fotw_info["taxon_id"]
                    orig_key    = fotw_info["orig_key"]
                    gbif_status = fotw_info["gbif_status"]
                    n_occ       = occ_counts.get(orig_key, 0)
                    new_hits.append(make_match_row(
                        edge_key, edge_meta, orig_key, gbif_status,
                        taxon_id, n_occ, "edge_synonym", existing_uuids,
                    ))
                    hit = True

            elapsed = time.time() - t0
            rate    = done / elapsed if elapsed else 0
            eta     = (total - done) / rate if rate else 0
            flag    = " *** HIT ***" if hit else ""
            print(
                f"  [{done:>5}/{total}]  {edge_key:<45}  "
                f"→ {acc_key or '(none)':<40}  conf={conf:>3}"
                f"{flag}  |  ETA {eta/60:.1f}min",
                end="\r", flush=True,
            )

    print(f"\n  Phase 2 done — {len(new_hits)} new matches, {errors} errors")
    return new_hits

# ── Report ────────────────────────────────────────────────────────────────────
def write_report(matched, out_path):
    edge_list      = [m for m in matched if m["EDGE_List"] == "y"]
    total_edge     = 9945
    total_all      = 335497
    ed_total_fotw  = sum(float(m["ed_med"]) for m in matched)
    ed_total_edge  = 113173.0

    threat_order  = ["CR", "EN", "VU", "NT", "LC", "DD", "EW", "EX", "thr", "not"]
    threat_counts = defaultdict(int)
    method_counts = defaultdict(int)
    for m in matched:
        method_counts[m["match_method"]] += 1
    for m in edge_list:
        threat_counts[m["threat"]] += 1

    with open(out_path, "w", encoding="utf-8") as fh:
        def w(line=""): fh.write(line + "\n")

        w("# EDGE × Flora of the World — Match Report (GBIF-normalised)")
        w()
        w("*Generated from `match_EDGE_FotW_gbif.py`.*")
        w()
        w("---")
        w()
        w("## Executive Summary")
        w()
        w("| Metric | Value |")
        w("|--------|-------|")
        w(f"| EDGE species matched in FotW | {len(matched):,} / {total_all:,} ({100*len(matched)/total_all:.2f}%) |")
        w(f"| EDGE.List species in FotW | **{len(edge_list):,} / {total_edge:,} ({100*len(edge_list)/total_edge:.1f}%)** |")
        w(f"| EDGE.List ED documented in FotW | {ed_total_fotw:,.0f} / {ed_total_edge:,.0f} Myr ({100*ed_total_fotw/ed_total_edge:.1f}%) |")
        w(f"| Best EDGE rank in FotW | #{matched[0]['EDGE_rank']} (*{matched[0]['species']}*, {matched[0]['threat']}) |")
        w()
        w("### Match method breakdown")
        w()
        w("| Method | Count | Description |")
        w("|--------|------:|-------------|")
        w(f"| direct | {method_counts['direct']:,} | FotW name = EDGE name (same GBIF backbone name) |")
        w(f"| fotw_synonym | {method_counts['fotw_synonym']:,} | FotW carried a synonym; GBIF accepted name = EDGE name |")
        w(f"| edge_synonym | {method_counts['edge_synonym']:,} | EDGE carried a synonym; GBIF accepted name is in FotW |")
        w()
        w("> **Note on edge_synonym matches:** The EDGE dataset was built on a snapshot of the GBIF")
        w("> backbone. Some EDGE names have since been synonymised by GBIF; the current accepted name")
        w("> appears in FotW under the updated name. These matches are found by Phase 2, which queries")
        w("> GBIF for each unmatched EDGE.List species and checks whether the returned accepted name is")
        w("> present in FotW.")
        w()
        w("---")
        w()
        w("## IUCN Threat Status of EDGE.List Species in FotW")
        w()
        w("| Threat | Count |")
        w("|--------|------:|")
        for t in threat_order:
            if threat_counts[t]:
                w(f"| {t} | {threat_counts[t]} |")
        w()
        w("---")
        w()
        w("## Top 50 EDGE Species in FotW")
        w()
        w("| EDGE rank | Species | Family | Threat | ED (Myr) | EDGE score | Method | Records | EDGE.List |")
        w("|----------:|---------|--------|:------:|---------:|-----------:|--------|--------:|:---------:|")
        for m in matched[:50]:
            el   = "**yes**" if m["EDGE_List"] == "y" else "no"
            url  = m["taxon_url"]
            name = f"[{m['species']}]({url})" if url else f"*{m['species']}*"
            w(f"| {m['EDGE_rank']} | {name} | {m['family']} | {m['threat']} "
              f"| {float(m['ed_med']):.1f} | {float(m['edge_med']):.4f} "
              f"| {m['match_method']} | {m['n_fotw_records']} | {el} |")
        w()
        w("---")
        w()
        w(f"## EDGE.List Priority Species in FotW ({len(edge_list)} species)")
        w()
        w("| EDGE rank | Species | Family | Threat | ED (Myr) | EDGE score | FotW name | Method | Records |")
        w("|----------:|---------|--------|:------:|---------:|-----------:|-----------|--------|--------:|")
        for m in sorted(edge_list, key=lambda r: r["EDGE_rank"]):
            url      = m["taxon_url"]
            name     = f"[{m['species']}]({url})" if url else f"*{m['species']}*"
            orig     = m["fotw_original_name"]
            orig_note = f"*{orig}*" if orig != m["species"] else "—"
            w(f"| {m['EDGE_rank']} | {name} | {m['family']} | {m['threat']} "
              f"| {float(m['ed_med']):.1f} | {float(m['edge_med']):.4f} "
              f"| {orig_note} | {m['match_method']} | {m['n_fotw_records']} |")

    print(f"Report written to {out_path}")

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--phase", choices=["1", "2", "both"], default="both",
                        help="Which phase(s) to run (default: both)")
    parser.add_argument("--workers",  type=int,   default=8,
                        help="Concurrent workers for Phase 2 (default: 8)")
    parser.add_argument("--delay",    type=float, default=0.3,
                        help="Pause per worker between Phase 2 requests (default: 0.3s)")
    parser.add_argument("--min-conf", type=int,   default=80,
                        help="Minimum GBIF confidence for Phase 2 hits (default: 80)")
    args = parser.parse_args()

    print("Loading EDGE data …")
    edge_meta, edge_list_keys = load_edge(EDGE_CSV)
    print(f"  {len(edge_meta):,} total EDGE species  |  {len(edge_list_keys):,} EDGE.List species")

    print("Loading resolved FotW taxonomy …")
    resolved, fotw_accepted_index = load_resolved_taxonomy(RESOLVED)
    print(f"  {len(resolved):,} taxa with GBIF resolution")
    print(f"  {len(fotw_accepted_index):,} unique GBIF accepted names in FotW")

    print("Loading FotW occurrence counts …")
    occ_counts = load_occurrence_counts(OCC_CSV)
    print(f"  {len(occ_counts):,} unique FotW taxa in occurrences")

    print("Loading existing FotW taxon UUIDs …")
    existing_uuids = load_uuids(UUID_CSV)
    print(f"  {len(existing_uuids):,} existing URLs loaded")

    # ── Phase 1 ───────────────────────────────────────────────────────────────
    matched        = []
    matched_keys   = set()

    if args.phase in ("1", "both"):
        print("\nPhase 1: FotW → GBIF → EDGE (no network) …")
        matched, matched_keys = phase1_match(
            edge_meta, resolved, occ_counts, existing_uuids,
        )
        el1 = sum(1 for m in matched if m["EDGE_List"] == "y")
        print(f"  Phase 1 done — {len(matched):,} total matches  |  {el1:,} EDGE.List")

    # ── Phase 2 ───────────────────────────────────────────────────────────────
    if args.phase in ("2", "both"):
        unmatched = [k for k in edge_list_keys if k not in matched_keys]
        new_hits  = phase2_match(
            unmatched, edge_meta, fotw_accepted_index,
            occ_counts, existing_uuids,
            args.workers, args.delay, args.min_conf,
        )
        matched.extend(new_hits)
        matched_keys |= {m["_edge_key"] for m in new_hits}

    matched.sort(key=lambda r: r["EDGE_rank"])

    edge_list_matched = [m for m in matched if m["EDGE_List"] == "y"]
    method_counts     = defaultdict(int)
    for m in matched:
        method_counts[m["match_method"]] += 1

    print(f"\n{'='*65}")
    print(f"  Total EDGE species matched in FotW : {len(matched):,}")
    print(f"  EDGE.List species matched          : {len(edge_list_matched):,}")
    print(f"  Match methods:")
    print(f"    direct               : {method_counts['direct']:,}")
    print(f"    fotw_synonym         : {method_counts['fotw_synonym']:,}")
    print(f"    edge_synonym (Ph.2)  : {method_counts['edge_synonym']:,}")
    print(f"{'='*65}\n")

    print(f"Writing {OUT_CSV} …")
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=OUT_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(matched)

    print(f"Writing {OUT_MD} …")
    write_report(matched, OUT_MD)

    print("\nDone.")

if __name__ == "__main__":
    main()
