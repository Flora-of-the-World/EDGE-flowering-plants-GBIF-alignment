"""
Build a single, complete EDGE × GBIF deliverable for the FotW website team.

Inputs
------
  edge_taxonomy_resolved.csv   — 335,497 EDGE rows, each with GBIF resolution

Output (single combined file)
-----------------------------
  edge_taxonomy_complete.csv
    All 335,497 EDGE rows (record_type = "edge_original")
    + N new rows for accepted names whose binomial is NOT itself in EDGE
      (record_type = "gbif_accepted_new") — one row per unique accepted_gbif_id,
      with `synonym_edge_keys` listing the EDGE synonym keys that pointed here.

For convenience, the new accepted-name rows are also written to a separate file:
  edge_new_accepted_names.csv

Mirrors the FotW pipeline:
    taxon_DB_updated.csv          ↔ edge_taxonomy_resolved.csv     (existing)
    fotw_new_accepted_names.csv   ↔ edge_new_accepted_names.csv    (new)
    [combined view]               ↔ edge_taxonomy_complete.csv     (NEW)

For new accepted-name rows, GBIF-derived fields (taxonID, scientificName, genus,
specificEpithet, gbif_status, accepted_*) are filled from the synonym's GBIF
resolution. EDGE source columns (Family, Order, edge.med, EDGE.List, …) are
left blank — those species were not scored in the Forest et al. study, so no
score exists for them. The `synonym_edge_keys` column links each new accepted
name back to the EDGE-scored synonyms it absorbs.

Usage
-----
    python3 build_edge_complete.py
"""

import csv
import os
import sys
from collections import defaultdict

csv.field_size_limit(sys.maxsize)

BASE     = os.path.dirname(os.path.abspath(__file__))
IN_CSV   = os.path.join(BASE, "edge_taxonomy_resolved.csv")
OUT_FULL = os.path.join(BASE, "edge_taxonomy_complete.csv")
OUT_NEW  = os.path.join(BASE, "edge_new_accepted_names.csv")

# Status values that imply "the EDGE name is NOT the accepted name; an accepted
# name exists elsewhere via GBIF". Note: GBIF returns SYNONYM and finer-grained
# variants like HETEROTYPIC_SYNONYM / HOMOTYPIC_SYNONYM / PROPARTE_SYNONYM.
SYNONYM_STATUSES = {
    "SYNONYM", "HETEROTYPIC_SYNONYM", "HOMOTYPIC_SYNONYM",
    "PROPARTE_SYNONYM", "MISAPPLIED",
}


def main():
    # Read the resolved EDGE table once into memory
    print(f"Reading {os.path.basename(IN_CSV)} …")
    with open(IN_CSV, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        in_fields = reader.fieldnames
        rows = list(reader)
    print(f"  {len(rows):,} EDGE rows")

    # ── Build the EDGE species key set (original taxonIDs = Genus_epithet) ──
    edge_keys = {r["taxonID"] for r in rows if r["taxonID"]}

    # ── Collect new accepted names from synonym resolutions ─────────────────
    # Group by accepted_gbif_id (deduplicate when multiple EDGE synonyms point
    # to the same accepted GBIF taxon).
    new_accepted = {}                          # gbif_id -> aggregated row
    synonym_links = defaultdict(list)          # gbif_id -> [edge_keys ...]

    for r in rows:
        status = r["gbif_status"].strip().upper()
        if status not in SYNONYM_STATUSES:
            continue
        acc_name = r["accepted_name"].strip()
        acc_id   = r["accepted_gbif_id"].strip()
        if not acc_name or not acc_id:
            continue

        parts = acc_name.split()
        if len(parts) < 2:
            continue
        acc_key = f"{parts[0]}_{parts[1]}"

        # If the accepted name is itself an EDGE-scored species, no new row needed
        if acc_key in edge_keys:
            continue

        synonym_links[acc_id].append(r["taxonID"])

        if acc_id in new_accepted:
            continue

        new_accepted[acc_id] = {
            "taxonID"             : acc_key,
            "scientificName"      : acc_name,
            "genus"               : parts[0],
            "specificEpithet"     : parts[1],
            "infraspecificEpithet": "",
            "scientificNameID"    : "",
            "gbif_id"             : acc_id,
            "lookup_method"       : "inferred_from_synonym",
            "gbif_status"         : "ACCEPTED",
            "gbif_confidence"     : "",
            "accepted_name"       : acc_name,
            "accepted_gbif_id"    : acc_id,
            "accepted_gbif_url"   : r["accepted_gbif_url"].strip(),
            "error"               : "",
        }

    print(f"  New accepted names found (before homonym collapse): {len(new_accepted):,}  "
          f"(from {sum(len(v) for v in synonym_links.values()):,} EDGE synonym rows)")

    # ── Collapse GBIF homonyms ─────────────────────────────────────────────
    # Some accepted binomials exist as multiple distinct GBIF taxa (homonyms,
    # or GBIF's own duplicate records). Group by binomial (acc_key) and pick a
    # canonical GBIF id per binomial: the one with the most incoming synonym
    # pointers, tie-break by lowest GBIF key (older = more canonical).
    by_acc_key = defaultdict(list)
    for gid, info in new_accepted.items():
        by_acc_key[info["taxonID"]].append(gid)

    collapsed_new       = {}      # canonical gbif_id -> aggregated info
    collapsed_links     = defaultdict(list)
    dropped_gbif_ids    = []      # for reporting

    for acc_key, gids in by_acc_key.items():
        if len(gids) == 1:
            gid = gids[0]
            collapsed_new[gid]   = new_accepted[gid]
            collapsed_links[gid] = synonym_links[gid]
            continue
        # Pick canonical: most synonym pointers, then lowest gbif_id
        canonical = sorted(
            gids,
            key=lambda g: (-len(synonym_links[g]), int(g) if g.isdigit() else g),
        )[0]
        collapsed_new[canonical] = new_accepted[canonical]
        # Merge synonym_edge_keys from all variants
        merged_synonyms = []
        merged_other_ids = []
        for g in gids:
            merged_synonyms.extend(synonym_links[g])
            if g != canonical:
                merged_other_ids.append(g)
                dropped_gbif_ids.append((acc_key, g))
        # Dedupe while preserving order
        seen = set()
        collapsed_links[canonical] = [k for k in merged_synonyms
                                       if not (k in seen or seen.add(k))]
        # Annotate the canonical record with the dropped homonyms
        collapsed_new[canonical]["error"] = (
            f"merged_homonyms:{','.join(merged_other_ids)}"
            if merged_other_ids else ""
        )

    new_accepted  = collapsed_new
    synonym_links = collapsed_links

    print(f"  Homonym collapse: dropped {len(dropped_gbif_ids):,} duplicate GBIF entries")
    print(f"  New accepted names (final, deduplicated): {len(new_accepted):,}")

    # ── Build output schema ─────────────────────────────────────────────────
    # Combined file gets two extra columns: record_type + synonym_edge_keys
    out_fields = ["record_type"] + in_fields + ["synonym_edge_keys"]

    # EDGE source columns (everything in in_fields not in the GBIF block) are
    # blank for new accepted-name rows.

    # ── Write the combined file ─────────────────────────────────────────────
    print(f"Writing {os.path.basename(OUT_FULL)} …")
    with open(OUT_FULL, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=out_fields, extrasaction="ignore")
        writer.writeheader()

        # Existing EDGE rows verbatim
        for r in rows:
            out = {f: r.get(f, "") for f in in_fields}
            out["record_type"]        = "edge_original"
            out["synonym_edge_keys"]  = ""
            writer.writerow(out)

        # New accepted-name rows
        for acc_id, info in new_accepted.items():
            out = {f: "" for f in in_fields}
            out.update(info)
            out["record_type"]        = "gbif_accepted_new"
            out["synonym_edge_keys"]  = ";".join(synonym_links[acc_id])
            writer.writerow(out)

    # ── Write a separate file with only the new accepted names ─────────────
    print(f"Writing {os.path.basename(OUT_NEW)} …")
    with open(OUT_NEW, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=out_fields, extrasaction="ignore")
        writer.writeheader()
        for acc_id, info in new_accepted.items():
            out = {f: "" for f in in_fields}
            out.update(info)
            out["record_type"]        = "gbif_accepted_new"
            out["synonym_edge_keys"]  = ";".join(synonym_links[acc_id])
            writer.writerow(out)

    # ── Summary ─────────────────────────────────────────────────────────────
    total = len(rows) + len(new_accepted)
    print()
    print("=" * 60)
    print(f"  Original EDGE rows           : {len(rows):>8,}")
    print(f"  New accepted-name rows added : {len(new_accepted):>8,}")
    print(f"  Combined total               : {total:>8,}")
    print("=" * 60)
    print(f"  Combined file : {OUT_FULL}")
    print(f"  New-only file : {OUT_NEW}")


if __name__ == "__main__":
    main()
