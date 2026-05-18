"""
Generate EDGE_FotW_report.md from EDGE_FotW_matched_species_gbif.csv.

Produces the same rich format as the original report (ED stats, per-threat
breakdown, Top 50 EDGE, Top 20 ED, full EDGE.List table) but sourced from
the GBIF-normalised match pipeline.
"""

import csv
import os
import statistics
from collections import defaultdict

BASE     = os.path.dirname(os.path.abspath(__file__))
MATCH_CSV = os.path.join(BASE, "EDGE_FotW_matched_species_gbif.csv")
EDGE_CSV  = os.path.join(BASE, "Forest_etal_EDGEangio_tableS1_EDGEspp_RL&Pred.csv")
OCC_CSV   = os.path.join(BASE, "..", "FotW_DB", "occurrences.csv")
OUT_MD    = os.path.join(BASE, "EDGE_FotW_report.md")

# ── Load matched species ───────────────────────────────────────────────────────
matched = []
with open(MATCH_CSV, newline="", encoding="utf-8") as fh:
    for row in csv.DictReader(fh):
        row["_ed"]   = float(row["ed_med"])
        row["_edge"] = float(row["edge_med"])
        row["_tbl"]  = float(row["tbl_med"])
        row["_pext"] = float(row["pext_med"])
        row["_rank"] = int(row["EDGE_rank"])
        row["_n"]    = int(row["n_fotw_records"])
        matched.append(row)

matched.sort(key=lambda r: r["_rank"])
edge_list = [m for m in matched if m["EDGE_List"] == "y"]

# ── Load full EDGE dataset for context stats ───────────────────────────────────
edge_threat_counts  = defaultdict(int)
edge_total          = 0
edge_list_total     = 9945   # known constant
ed_total_all        = 0.0

with open(EDGE_CSV, newline="", encoding="utf-8") as fh:
    for row in csv.DictReader(fh):
        edge_total += 1
        t = row["threat"].strip()
        edge_threat_counts[t] += 1
        try:
            ed_total_all += float(row["ed.med"])
        except ValueError:
            pass

# ── Count unique FotW taxa from occurrences ────────────────────────────────────
fotw_unique = set()
with open(OCC_CSV, newline="", encoding="utf-8") as fh:
    for row in csv.DictReader(fh):
        g = row["genus"].strip()
        e = row["specificEpithet"].strip()
        if g and e:
            fotw_unique.add(f"{g}_{e}")
n_fotw_unique = len(fotw_unique)

# ── Compute stats ──────────────────────────────────────────────────────────────
ed_values   = [m["_ed"]   for m in matched]
edge_values = [m["_edge"] for m in matched]

ed_sum    = sum(ed_values)
ed_mean   = statistics.mean(ed_values)
ed_median = statistics.median(ed_values)
ed_max    = max(ed_values)

edge_mean   = statistics.mean(edge_values)
edge_median = statistics.median(edge_values)
edge_max    = max(edge_values)

best  = matched[0]
worst = matched[-1]

# Per-threat breakdown for matched species
THREAT_ORDER = ["CR", "EN", "VU", "NT", "LC", "DD", "EW", "EX", "thr", "not"]
THREAT_DESC  = {
    "CR": "Critically Endangered",
    "EN": "Endangered",
    "VU": "Vulnerable",
    "NT": "Near Threatened",
    "LC": "Least Concern",
    "DD": "Data Deficient",
    "EW": "Extinct in the Wild",
    "EX": "Extinct",
    "thr": "Threatened (predicted)",
    "not": "Not threatened (predicted)",
}

threat_data = defaultdict(lambda: {"n": 0, "ed": 0.0, "edge_vals": []})
for m in matched:
    t = m["threat"]
    threat_data[t]["n"] += 1
    threat_data[t]["ed"] += m["_ed"]
    threat_data[t]["edge_vals"].append(m["_edge"])

# Match method breakdown
method_counts = defaultdict(int)
for m in matched:
    method_counts[m["match_method"]] += 1

# ── Top 20 most ED species ─────────────────────────────────────────────────────
top20_ed = sorted(matched, key=lambda r: r["_ed"], reverse=True)[:20]

# ── Write report ───────────────────────────────────────────────────────────────
match_rate    = 100 * len(matched) / edge_total
ed_pct        = 100 * ed_sum / ed_total_all
el_direct     = method_counts["direct"] + method_counts["fotw_synonym"]
el_syn        = method_counts["edge_synonym"]

with open(OUT_MD, "w", encoding="utf-8") as fh:
    def w(line=""): fh.write(line + "\n")

    w("# EDGE Flowering Plants × Flora of the World — Match Report")
    w()
    w(f"*Forest et al. (Science) EDGE dataset · FotW occurrence database · 2026-05-01 · GBIF-normalised pipeline*")
    w()
    w("---")
    w()
    w("## Executive Summary")
    w()
    w("| Metric | Value |")
    w("|---|---|")
    w(f"| Total EDGE flowering plant species | {edge_total:,} |")
    w(f"| Unique species in FotW database | {n_fotw_unique:,} |")
    w(f"| **EDGE species with FotW occurrence** | **{len(matched):,}** |")
    w(f"| Match rate | {match_rate:.2f}% |")
    w(f"| EDGE.List species (priority list) | {edge_list_total:,} |")
    w(f"| EDGE.List species in FotW | **{len(edge_list):,} ({100*len(edge_list)/edge_list_total:.1f}%)** |")
    w()
    w("### Match method breakdown")
    w()
    w("| Method | Count | Description |")
    w("|--------|------:|-------------|")
    w(f"| direct | {method_counts['direct']:,} | FotW name = EDGE name (same GBIF backbone name) |")
    w(f"| fotw_synonym | {method_counts['fotw_synonym']:,} | FotW carried a synonym; GBIF accepted name = EDGE name |")
    w(f"| edge_synonym | {method_counts['edge_synonym']:,} | EDGE carried a synonym; GBIF accepted name is in FotW |")
    w()
    w("---")
    w()
    w("## Evolutionary Distinctiveness (ED) in FotW")
    w()
    w("| Metric | Value |")
    w("|---|---|")
    w(f"| Total ED across all EDGE species (Myr) | {ed_total_all:,.1f} |")
    w(f"| ED represented by FotW species (Myr) | {ed_sum:,.1f} |")
    w(f"| % of total angiosperm ED in FotW | {ed_pct:.2f}% |")
    w(f"| Mean ED — matched species (Myr) | {ed_mean:.2f} |")
    w(f"| Median ED — matched species (Myr) | {ed_median:.2f} |")
    w(f"| Max ED — matched species (Myr) | {ed_max:.2f} |")
    w()
    w("---")
    w()
    w("## EDGE Score Statistics (matched species)")
    w()
    w("| Metric | Value |")
    w("|---|---|")
    w(f"| Mean EDGE score | {edge_mean:.2f} |")
    w(f"| Median EDGE score | {edge_median:.2f} |")
    w(f"| Max EDGE score | {edge_max:.2f} |")
    w(f"| Best EDGE rank in FotW | #{best['_rank']} |")
    w(f"| Worst EDGE rank in FotW | #{worst['_rank']:,} |")
    w()
    w("---")
    w()
    w("## IUCN Threat Status")
    w()
    w("### Matched species in FotW")
    w()
    w("| Status | Description | # species | % of matched | Total ED (Myr) | Mean EDGE |")
    w("|---|---|---:|---:|---:|---:|")
    for t in THREAT_ORDER:
        d = threat_data.get(t)
        if not d or d["n"] == 0:
            continue
        pct      = 100 * d["n"] / len(matched)
        mean_e   = sum(d["edge_vals"]) / len(d["edge_vals"])
        desc     = THREAT_DESC.get(t, t)
        w(f"| {t} | {desc} | {d['n']} | {pct:.1f}% | {d['ed']:,.1f} | {mean_e:.2f} |")
    w()
    w("### Full EDGE dataset (for context)")
    w()
    w("| Status | Description | # species | % of total |")
    w("|---|---|---:|---:|")
    for t in THREAT_ORDER:
        n = edge_threat_counts.get(t, 0)
        if n == 0:
            continue
        pct  = 100 * n / edge_total
        desc = THREAT_DESC.get(t, t)
        w(f"| {t} | {desc} | {n:,} | {pct:.1f}% |")
    w()
    w("---")
    w()
    w("## Top 50 EDGE Species in FotW")
    w()
    w("| Rank | Species | Family | Threat | EDGE score | ED (Myr) | Tbl (Myr) | P(ext) | EDGE List | FotW records |")
    w("|---:|---|---|:---:|---:|---:|---:|---:|:---:|---:|")
    for m in matched[:50]:
        url  = m.get("taxon_url", "")
        name = f"[*{m['species']}*]({url})" if url else f"*{m['species']}*"
        el   = "Yes" if m["EDGE_List"] == "y" else "—"
        w(f"| {m['_rank']:,} | {name} | {m['family']} | {m['threat']} "
          f"| {m['_edge']:.2f} | {m['_ed']:.2f} | {m['_tbl']:.2f} "
          f"| {m['_pext']:.3f} | {el} | {m['_n']} |")
    w()
    w("---")
    w()
    w("## Top 20 Most Evolutionarily Distinct (ED) Species in FotW")
    w()
    w("| ED (Myr) | Species | Family | Threat | EDGE rank | EDGE score |")
    w("|---:|---|---|:---:|---:|---:|")
    for m in top20_ed:
        url  = m.get("taxon_url", "")
        name = f"[*{m['species']}*]({url})" if url else f"*{m['species']}*"
        w(f"| {m['_ed']:.2f} | {name} | {m['family']} | {m['threat']} "
          f"| {m['_rank']:,} | {m['_edge']:.2f} |")
    w()
    w("---")
    w()
    w(f"## EDGE.List Priority Species in FotW ({len(edge_list)} species)")
    w()
    w("Species on the EDGE.List combine high evolutionary distinctiveness with high extinction risk — the global conservation priority list.")
    w()
    w("| Rank | Species | Family | Threat | EDGE score | ED (Myr) | P(ext) | FotW records |")
    w("|---:|---|---|:---:|---:|---:|---:|---:|")
    for m in sorted(edge_list, key=lambda r: r["_rank"]):
        url  = m.get("taxon_url", "")
        name = f"[*{m['species']}*]({url})" if url else f"*{m['species']}*"
        w(f"| {m['_rank']:,} | {name} | {m['family']} | {m['threat']} "
          f"| {m['_edge']:.2f} | {m['_ed']:.2f} | {m['_pext']:.3f} | {m['_n']} |")
    w()

print(f"Written: {OUT_MD}")
