"""
Fetch taxon UUIDs from Flora of the World for the 197 EDGE.List species
documented in FotW.

Strategy
--------
The FotW search page (floraoftheworld.org/search?q=<genus>+<epithet>) returns
a "View Taxon" button whose href is /taxons/<UUID>. We parse that UUID for
each species. Only 197 requests are needed.

The script is resumable: already-fetched species are skipped on re-runs.

Output
------
fotw_taxon_uuids.csv  —  species_key, genus, epithet, taxon_uuid, taxon_url

Usage
-----
    python3 fetch_fotw_taxon_uuids.py [--workers N] [--delay SECONDS]
"""

import csv
import os
import re
import time
import argparse
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE         = os.path.dirname(os.path.abspath(__file__))
EDGE_CSV     = os.path.join(BASE, "Forest_etal_EDGEangio_tableS1_EDGEspp_RL&Pred.csv")
FOTW_CSV     = os.path.join(BASE, "..", "FotW_DB", "occurrences.csv")
CACHE_CSV    = os.path.join(BASE, "fotw_taxon_uuids.csv")

FOTW_SEARCH  = "https://floraoftheworld.org/search?q={genus}+{epithet}"
FOTW_TAXON   = "https://floraoftheworld.org/taxons/{uuid}"

# Matches the "View Taxon" button href in the search page HTML
TAXON_HREF_RE = re.compile(r'href="/taxons/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"')

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; EDGE-FotW-research-bot/1.0; "
        "Boise State University; contact: sven.buerki@boisestate.edu)"
    ),
    "Accept": "text/html,application/xhtml+xml",
}

# ── Build target species list: EDGE.List species that are in FotW ─────────────
def build_targets(edge_csv, fotw_csv):
    # EDGE.List species
    edge_list = {}
    with open(edge_csv, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row["EDGE.List"].strip('"') == "y":
                key = row["Species"].strip().strip('"')
                edge_list[key] = {
                    "genus":   key.split("_")[0],
                    "epithet": "_".join(key.split("_")[1:]),
                }

    # Unique FotW taxa
    fotw_taxa = set()
    with open(fotw_csv, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            g, e = row["genus"].strip(), row["specificEpithet"].strip()
            if g and e:
                fotw_taxa.add(f"{g}_{e}")

    # Intersection
    targets = {k: v for k, v in edge_list.items() if k in fotw_taxa}
    return targets

# ── Load cache ────────────────────────────────────────────────────────────────
def load_cache(cache_csv):
    done = set()
    if os.path.exists(cache_csv):
        with open(cache_csv, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                done.add(row["species_key"])
    return done

# ── Fetch taxon UUID for one species ─────────────────────────────────────────
def fetch_uuid(species_key, genus, epithet, delay):
    time.sleep(delay)
    url = FOTW_SEARCH.format(genus=genus, epithet=epithet)
    try:
        req = Request(url, headers=HEADERS)
        with urlopen(req, timeout=30) as resp:
            html = resp.read().decode("utf-8", errors="replace")
        matches = TAXON_HREF_RE.findall(html)
        uuid = matches[0] if matches else ""
        return species_key, genus, epithet, uuid, ""
    except (HTTPError, URLError, Exception) as exc:
        return species_key, genus, epithet, "", f"ERROR: {exc}"

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int,   default=4,
                        help="Concurrent workers (default: 4)")
    parser.add_argument("--delay",   type=float, default=1.0,
                        help="Pause per worker between requests in seconds (default: 1.0)")
    args = parser.parse_args()

    print("Building target species list (EDGE.List ∩ FotW) …")
    targets = build_targets(EDGE_CSV, FOTW_CSV)
    print(f"  {len(targets)} species to process")

    cached = load_cache(CACHE_CSV)
    todo   = {k: v for k, v in targets.items() if k not in cached}
    print(f"  {len(cached)} already cached, {len(todo)} remaining\n")

    if not todo:
        print("Nothing to do.")
        return

    write_header = not os.path.exists(CACHE_CSV)
    fh     = open(CACHE_CSV, "a", newline="", encoding="utf-8")
    writer = csv.DictWriter(fh, fieldnames=[
        "species_key", "genus", "epithet", "taxon_uuid", "taxon_url", "error"
    ])
    if write_header:
        writer.writeheader()

    done = errors = 0
    total = len(todo)
    t0 = time.time()
    est = total * args.delay / args.workers / 60
    print(f"Fetching {total} search pages  "
          f"({args.workers} workers · {args.delay}s delay · ~{est:.1f} min)\n")

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(fetch_uuid, k, v["genus"], v["epithet"], args.delay): k
            for k, v in todo.items()
        }
        for future in as_completed(futures):
            species_key, genus, epithet, uuid, error = future.result()
            taxon_url = FOTW_TAXON.format(uuid=uuid) if uuid else ""

            writer.writerow({
                "species_key": species_key,
                "genus":       genus,
                "epithet":     epithet,
                "taxon_uuid":  uuid,
                "taxon_url":   taxon_url,
                "error":       error,
            })
            fh.flush()

            done += 1
            if error:
                errors += 1
            elapsed = time.time() - t0
            rate    = done / elapsed if elapsed else 0
            eta     = (total - done) / rate if rate else 0
            status  = error if error else (uuid[:8] + "…" if uuid else "no match")
            print(f"  [{done:>3}/{total}]  {species_key:<45}  {status}"
                  f"  |  ETA {eta/60:.1f}min", end="\r", flush=True)

    fh.close()
    print(f"\n\nDone in {(time.time()-t0)/60:.1f} min.")
    print(f"  Fetched : {done}")
    print(f"  Errors  : {errors}")
    print(f"  Output  : {CACHE_CSV}")

if __name__ == "__main__":
    main()
