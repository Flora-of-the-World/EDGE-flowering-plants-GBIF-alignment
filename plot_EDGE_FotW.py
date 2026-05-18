"""
Plots focused on EDGE.List priority species (threatened + evolutionarily
distinct; n = 9,945) and their representation in Flora of the World (FotW).

The 229 EDGE.List species documented in FotW are the primary subject
(197 exact-name matches + 32 additional matches via GBIF synonym resolution).
Other FotW species are shown only for context where relevant.

Figures (saved to ./figures/)
------------------------------
1. Coverage         — How many of the 9,945 EDGE.List species are in FotW
                      and what ED they represent (two paired bar panels)
2. Threat breakdown — IUCN status of the 229 FotW EDGE.List species
3. Top 25 species   — Top 25 FotW EDGE.List species by EDGE score
4. Top families     — Families with most EDGE.List species in FotW
5. Top 20 by ED     — Most evolutionarily distinct EDGE.List species in FotW
"""

import csv
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.ticker as mticker
import numpy as np
from collections import defaultdict, Counter

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE        = os.path.dirname(os.path.abspath(__file__))
EDGE_CSV    = os.path.join(BASE, "Forest_etal_EDGEangio_tableS1_EDGEspp_RL&Pred.csv")
MATCHED_CSV = os.path.join(BASE, "EDGE_FotW_matched_species.csv")
FIG_DIR     = os.path.join(BASE, "figures")
os.makedirs(FIG_DIR, exist_ok=True)

# ── Colours ───────────────────────────────────────────────────────────────────
C_FOTW    = "#1A6B9A"
C_MISSING = "#E0E0E0"

THREAT_COLOR = {
    "CR":  "#B5121B",
    "EN":  "#E8620A",
    "VU":  "#F5A623",
    "NT":  "#7BC67E",
    "LC":  "#2E8B57",
    "EW":  "#8B008B",
    "thr": "#A8A8A8",
    "not": "#D8D8D8",
}
THREAT_LABEL = {
    "CR":  "Critically Endangered (CR)",
    "EN":  "Endangered (EN)",
    "VU":  "Vulnerable (VU)",
    "NT":  "Near Threatened (NT)",
    "LC":  "Least Concern (LC)",
    "EW":  "Extinct in the Wild (EW)",
    "thr": "Threatened — predicted",
    "not": "Not threatened — predicted",
}
THREAT_ORDER = ["CR", "EN", "VU", "NT", "LC", "EW", "thr", "not"]

plt.rcParams.update({
    "font.family":      "DejaVu Sans",
    "font.size":        11,
    "axes.spines.top":  False,
    "axes.spines.right":False,
    "figure.dpi":       150,
})

# ── Load & match ──────────────────────────────────────────────────────────────
# Full EDGE dataset — needed for coverage denominator (9,945 EDGE.List species)
print("Loading EDGE data …")
edge = {}
with open(EDGE_CSV, newline="", encoding="utf-8") as fh:
    for row in csv.DictReader(fh):
        key = row["Species"].strip().strip('"')
        edge[key] = {
            "name":      key.replace("_", " "),
            "rank":      int(row["EDGE.rank"]),
            "family":    row["Family"].strip('"'),
            "edge_med":  float(row["edge.med"]),
            "ed_med":    float(row["ed.med"]),
            "pext_med":  float(row["pext.med"]),
            "threat":    row["threat"].strip('"'),
            "EDGE_List": row["EDGE.List"].strip('"'),
        }

# Matched species — includes exact matches + synonym-resolved additions
print("Loading matched species (exact + synonym) …")
fotw_el   = []
all_fotw  = []
with open(MATCHED_CSV, newline="", encoding="utf-8") as fh:
    for row in csv.DictReader(fh):
        sp = {
            "name":      row["species"],
            "rank":      int(row["EDGE_rank"]),
            "family":    row["family"],
            "edge_med":  float(row["edge_med"]),
            "ed_med":    float(row["ed_med"]),
            "pext_med":  float(row["pext_med"]),
            "threat":    row["threat"],
            "EDGE_List": row["EDGE_List"],
        }
        all_fotw.append(sp)
        if row["EDGE_List"] == "y":
            fotw_el.append(sp)

fotw_el_s   = sorted(fotw_el, key=lambda x: x["rank"])

# Coverage denominators from full EDGE dataset
edge_list   = [v for v in edge.values() if v["EDGE_List"] == "y"]
n_el        = len(edge_list)
n_fotw_el   = len(fotw_el)
n_missing   = n_el - n_fotw_el

ed_el_total = sum(v["ed_med"] for v in edge_list)
ed_fotw_el  = sum(v["ed_med"] for v in fotw_el)
ed_missing  = ed_el_total - ed_fotw_el

print(f"  EDGE.List total        : {n_el:,}")
print(f"  EDGE.List in FotW      : {n_fotw_el:,} ({n_fotw_el/n_el*100:.1f}%)")
print(f"  ED in FotW (EDGE.List) : {ed_fotw_el:,.0f} / {ed_el_total:,.0f} Myr "
      f"({ed_fotw_el/ed_el_total*100:.1f}%)\n")

def save(fig, name):
    path = os.path.join(FIG_DIR, name)
    fig.savefig(path, bbox_inches="tight", dpi=200)
    plt.close(fig)
    print(f"  Saved figures/{name}")

def threat_legend(ax, threats, **kwargs):
    patches = [mpatches.Patch(color=THREAT_COLOR[t], label=THREAT_LABEL[t])
               for t in THREAT_ORDER if t in threats]
    ax.legend(handles=patches, frameon=False, fontsize=9, **kwargs)


# ═══════════════════════════════════════════════════════════════════════════════
# Fig 1 — Coverage: species count + ED represented
# Two side-by-side panels sharing the same FotW-vs-missing framing
# ═══════════════════════════════════════════════════════════════════════════════
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 5.5))

# ── Panel A: species count ──
bars_sp = [n_fotw_el, n_missing]
ax1.bar([0], [n_fotw_el], color=C_FOTW,    width=0.5, label=f"In FotW ({n_fotw_el:,})")
ax1.bar([0], [n_missing],  bottom=[n_fotw_el], color=C_MISSING, width=0.5,
        label=f"Not in FotW ({n_missing:,})")

ax1.text(0, n_el * 1.04, f"{n_el:,} species", ha="center", fontweight="bold", fontsize=12)
ax1.text(0, n_fotw_el / 2,
         f"{n_fotw_el:,}\n({n_fotw_el/n_el*100:.1f}%)",
         ha="center", va="center", color="white", fontsize=11, fontweight="bold")

ax1.set_xticks([0])
ax1.set_xticklabels(["EDGE.List\nspecies"], fontsize=12)
ax1.set_ylabel("Number of species")
ax1.set_title("Species documented\nin Flora of the World", fontweight="bold", fontsize=12)
ax1.set_ylim(0, n_el * 1.18)
ax1.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{int(v):,}"))
ax1.legend(frameon=False, fontsize=10, loc="upper right")

# ── Panel B: ED (Myr) ──
ax2.bar([0], [ed_fotw_el], color=C_FOTW,   width=0.5, label=f"In FotW ({ed_fotw_el:,.0f} Myr)")
ax2.bar([0], [ed_missing],  bottom=[ed_fotw_el], color=C_MISSING, width=0.5,
        label=f"Not in FotW ({ed_missing:,.0f} Myr)")

ax2.text(0, ed_el_total * 1.04, f"{ed_el_total:,.0f} Myr", ha="center",
         fontweight="bold", fontsize=12)
ax2.text(0, ed_fotw_el / 2,
         f"{ed_fotw_el:,.0f} Myr\n({ed_fotw_el/ed_el_total*100:.1f}%)",
         ha="center", va="center", color="white", fontsize=10, fontweight="bold")

ax2.set_xticks([0])
ax2.set_xticklabels(["EDGE.List\nspecies"], fontsize=12)
ax2.set_ylabel("Evolutionary Distinctiveness (Myr)")
ax2.set_title("Evolutionary history documented\nin Flora of the World", fontweight="bold", fontsize=12)
ax2.set_ylim(0, ed_el_total * 1.18)
ax2.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v/1000:.0f}k"))
ax2.legend(frameon=False, fontsize=10, loc="upper right")

fig.suptitle("Coverage of EDGE.List Priority Species in Flora of the World",
             fontweight="bold", fontsize=14, y=1.02)
plt.tight_layout()
save(fig, "fig1_EDGE_list_coverage.png")


# ═══════════════════════════════════════════════════════════════════════════════
# Fig 2 — Threat breakdown of the 197 FotW EDGE.List species
# ═══════════════════════════════════════════════════════════════════════════════
threat_counts = Counter(sp["threat"] for sp in fotw_el)
threat_ed     = defaultdict(float)
for sp in fotw_el:
    threat_ed[sp["threat"]] += sp["ed_med"]

categories = [t for t in THREAT_ORDER if threat_counts[t] > 0]
counts  = [threat_counts[t] for t in categories]
ed_vals = [threat_ed[t] for t in categories]
colors  = [THREAT_COLOR[t] for t in categories]

fig, (ax_l, ax_r) = plt.subplots(1, 2, figsize=(12, 5))

# Left: species count
y = np.arange(len(categories))
ax_l.barh(y, counts, color=colors, edgecolor="white", linewidth=0.4, height=0.6)
for i, (c, t) in enumerate(zip(counts, categories)):
    ax_l.text(c + 0.5, i, f"{c}  ({c/n_fotw_el*100:.1f}%)", va="center", fontsize=9.5)
ax_l.set_yticks(y)
ax_l.set_yticklabels([THREAT_LABEL[t] for t in categories], fontsize=10)
ax_l.set_xlabel("Number of species")
ax_l.set_title("Species count", fontweight="bold")
ax_l.set_xlim(0, max(counts) * 1.45)

# Right: ED
ax_r.barh(y, ed_vals, color=colors, edgecolor="white", linewidth=0.4, height=0.6)
for i, (ed, t) in enumerate(zip(ed_vals, categories)):
    ax_r.text(ed + 0.3, i, f"{ed:,.0f} Myr  ({ed/ed_fotw_el*100:.1f}%)",
              va="center", fontsize=9.5)
ax_r.set_yticks(y)
ax_r.set_yticklabels([])
ax_r.set_xlabel("Evolutionary Distinctiveness (Myr)")
ax_r.set_title("ED represented (Myr)", fontweight="bold")
ax_r.set_xlim(0, max(ed_vals) * 1.5)

fig.suptitle(
    f"IUCN Threat Status of {n_fotw_el} EDGE.List Species in Flora of the World",
    fontweight="bold", fontsize=13, y=1.02,
)
plt.tight_layout()
save(fig, "fig2_threat_breakdown.png")


# ═══════════════════════════════════════════════════════════════════════════════
# Fig 3 — Top 25 FotW EDGE.List species by EDGE score
# ═══════════════════════════════════════════════════════════════════════════════
top25 = fotw_el_s[:25]
fig, ax = plt.subplots(figsize=(10, 8.5))

names  = [f"#{sp['rank']}  {sp['name']}" for sp in top25]
scores = [sp["edge_med"] for sp in top25]
colors = [THREAT_COLOR.get(sp["threat"], "#999") for sp in top25]
y = np.arange(len(top25))

ax.barh(y, scores, color=colors, edgecolor="white", linewidth=0.4, height=0.7)
for i, sp in enumerate(top25):
    ax.text(scores[i] + 0.3, i,
            f"{sp['threat']}  ·  {sp['family']}",
            va="center", fontsize=8.5, color="#444")

ax.set_yticks(y)
ax.set_yticklabels(names, fontsize=9.5)
ax.invert_yaxis()
ax.set_xlabel("EDGE score", fontsize=11)
ax.set_title(f"Top 25 EDGE.List Species Documented in Flora of the World\n"
             f"(ranked among {n_el:,} global EDGE priority species)",
             fontweight="bold", pad=12, fontsize=12)
threat_legend(ax, {sp["threat"] for sp in top25}, loc="lower right")
plt.tight_layout()
save(fig, "fig3_top25_EDGE_list_species.png")


# ═══════════════════════════════════════════════════════════════════════════════
# Fig 4 — Families with most EDGE.List species in FotW
# ═══════════════════════════════════════════════════════════════════════════════
fam_threat = defaultdict(lambda: defaultdict(int))
for sp in fotw_el:
    fam_threat[sp["family"]][sp["threat"]] += 1

fam_totals   = {f: sum(d.values()) for f, d in fam_threat.items()}
top_families = sorted(fam_totals, key=lambda f: fam_totals[f], reverse=True)[:15]

fig, ax = plt.subplots(figsize=(9, 6))
y     = np.arange(len(top_families))
lefts = np.zeros(len(top_families))

for t in THREAT_ORDER:
    vals = np.array([fam_threat[f].get(t, 0) for f in top_families], dtype=float)
    if vals.sum() == 0:
        continue
    ax.barh(y, vals, left=lefts, color=THREAT_COLOR[t],
            edgecolor="white", linewidth=0.3, height=0.6, label=THREAT_LABEL[t])
    lefts += vals

for i, f in enumerate(top_families):
    tot = fam_totals[f]
    ax.text(tot + 0.1, i, str(tot), va="center", fontsize=9.5)

ax.set_yticks(y)
ax.set_yticklabels(top_families, fontstyle="italic", fontsize=10)
ax.invert_yaxis()
ax.set_xlabel("Number of EDGE.List species in FotW")
ax.set_title(f"Families with Most EDGE.List Species in FotW\n"
             f"({n_fotw_el} species across "
             f"{len(fam_totals)} families)",
             fontweight="bold", pad=12, fontsize=12)
ax.set_xlim(0, max(fam_totals[f] for f in top_families) * 1.2)

handles = [mpatches.Patch(color=THREAT_COLOR[t], label=THREAT_LABEL[t])
           for t in THREAT_ORDER if any(fam_threat[f].get(t,0) for f in top_families)]
ax.legend(handles=handles, frameon=False, fontsize=8.5,
          loc="lower right", title="IUCN status", title_fontsize=9)
plt.tight_layout()
save(fig, "fig4_top_families.png")


# ═══════════════════════════════════════════════════════════════════════════════
# Fig 5 — Top 20 most evolutionarily distinct EDGE.List species in FotW
# ═══════════════════════════════════════════════════════════════════════════════
top_ed = sorted(fotw_el, key=lambda x: x["ed_med"], reverse=True)[:20]
fig, ax = plt.subplots(figsize=(10, 7))

names   = [f"{sp['name']}  (#{sp['rank']})" for sp in top_ed]
ed_vals = [sp["ed_med"] for sp in top_ed]
colors  = [THREAT_COLOR.get(sp["threat"], "#999") for sp in top_ed]
y = np.arange(len(top_ed))

ax.barh(y, ed_vals, color=colors, edgecolor="white", linewidth=0.4, height=0.65)
for i, sp in enumerate(top_ed):
    ax.text(ed_vals[i] + 0.3, i,
            f"{sp['ed_med']:.1f} Myr  ·  {sp['threat']}",
            va="center", fontsize=8.5, color="#444")

ax.set_yticks(y)
ax.set_yticklabels(names, fontstyle="italic", fontsize=9.5)
ax.invert_yaxis()
ax.set_xlabel("Evolutionary Distinctiveness (Myr)", fontsize=11)
ax.set_title("Top 20 Most Evolutionarily Distinct EDGE.List Species in FotW",
             fontweight="bold", pad=12, fontsize=12)
threat_legend(ax, {sp["threat"] for sp in top_ed}, loc="lower right")
plt.tight_layout()
save(fig, "fig5_top20_ED_species.png")

# ═══════════════════════════════════════════════════════════════════════════════
# Fig 6 — Top 20 most evolutionarily distinct species in FotW (all, regardless
#          of EDGE.List status) — *Amborella trichopoda* leads at 139.4 Myr
# ═══════════════════════════════════════════════════════════════════════════════
top_ed_all = sorted(all_fotw, key=lambda x: x["ed_med"], reverse=True)[:20]

fig, ax = plt.subplots(figsize=(10, 7))

names   = [f"{sp['name']}  (#{sp['rank']})" for sp in top_ed_all]
ed_vals = [sp["ed_med"] for sp in top_ed_all]
colors  = [THREAT_COLOR.get(sp["threat"], "#999") for sp in top_ed_all]
y = np.arange(len(top_ed_all))

bars = ax.barh(y, ed_vals, color=colors, edgecolor="white", linewidth=0.4, height=0.65)

# Mark EDGE.List species with a star
for i, sp in enumerate(top_ed_all):
    star = " ★" if sp["EDGE_List"] == "y" else ""
    ax.text(ed_vals[i] + 0.3, i,
            f"{sp['ed_med']:.1f} Myr  ·  {sp['threat']}{star}",
            va="center", fontsize=8.5, color="#444")

ax.set_yticks(y)
ax.set_yticklabels(names, fontstyle="italic", fontsize=9.5)
ax.invert_yaxis()
ax.set_xlabel("Evolutionary Distinctiveness (Myr)", fontsize=11)
ax.set_title("Top 20 Most Evolutionarily Distinct Species in FotW\n"
             "(all species — ★ = on EDGE.List)",
             fontweight="bold", pad=12, fontsize=12)
threat_legend(ax, {sp["threat"] for sp in top_ed_all}, loc="lower right")
plt.tight_layout()
save(fig, "fig6_top20_ED_all_species.png")

print("\nAll figures saved to figures/")
