# Data Dictionary — Forest et al. EDGE Angiosperm Dataset

**File:** `Forest_etal_EDGEangio_tableS1_EDGEspp_RL&Pred.csv`  
**Source:** Forest et al. (*Science*, 2025) — Supplementary Table S1  
**Rows:** 335,497 (one per flowering plant species)  
**Columns:** 22

---

## Background: How EDGE scores are calculated

**EDGE** stands for **Evolutionarily Distinct and Globally Endangered**. It is a composite conservation metric that prioritises species which are both:

- **Evolutionarily Distinct (ED):** they sit on long, isolated branches of the tree of life and have few or no close relatives. Losing them would erase a disproportionately large chunk of evolutionary history.
- **Globally Endangered:** they face a high probability of extinction in the near future.

Because the underlying phylogenetic tree is uncertain, all scores are computed across **200 posterior MCMC samples** of the angiosperm phylogeny. Most numeric columns therefore report the **median** across those 200 samples (suffix `.med`), giving a robust central estimate that reflects phylogenetic uncertainty.

---

## Column Reference

### Taxonomy

| Column | Type | Description |
|--------|------|-------------|
| `Species` | string | Binomial species name with an underscore separator (e.g. `Gomortega_keule`). Matches the World Flora Online / GBIF backbone taxonomy where possible. |
| `Family` | string | APG IV angiosperm family. |
| `Order` | string | APG IV angiosperm order. |

---

### EDGE ranking

| Column | Type | Description |
|--------|------|-------------|
| `EDGE.rank` | integer | Global rank of the species by EDGE score, from 1 (highest priority) to 335,497. Rank 1 is the species combining the greatest evolutionary distinctiveness with the highest extinction risk. |
| `edge.med` | float | **Median EDGE score** across 200 phylogenetic posterior draws. EDGE is calculated as: `EDGE = ln(ED) + GE × ln(2)`, where GE is the IUCN-derived extinction probability (see `pext.med`). Higher = greater conservation priority. Range: 0 – 54.9. |

---

### Evolutionary Distinctiveness (ED)

| Column | Type | Description |
|--------|------|-------------|
| `ed.med` | float | **Median ED score** (millions of years, Myr). Measures how isolated a species is on the phylogenetic tree, calculated as the Fair Proportion metric: each branch length is divided equally among all descendent species. A species with no close relatives and a long stem branch will have a high ED. Range: 0.0001 – 139.4 Myr. |
| `tbl.med` | float | **Median terminal branch length** (Myr). The length of the branch leading directly to the species (its unique evolutionary contribution not shared with any other species). For species with no close relatives this equals `ed.med`; for species nested within large genera it is lower. Range: 0.0001 – 139.4 Myr. |

---

### Extinction probability

| Column | Type | Description |
|--------|------|-------------|
| `pext.med` | float | **Median probability of extinction** within 100 years, derived from the IUCN Red List category (or modelled prediction). Ranges from ~0.04 (Least Concern) to 1.0 (Critically Endangered / Extinct in the Wild). Used as the GE term in the EDGE formula. |
| `threat` | string | The IUCN Red List category used to derive `pext.med`, or a predicted status for species not formally assessed. See values below. |
| `RL.ERP` | string | Source of the threat assessment: `RL` = IUCN Red List (formally assessed, ~49,800 species); `ERP` = Expert Review Panel (modelled prediction, ~285,700 species). |
| `thr.or.not` | string | Binary threat classification used in list assignments: `thr` = threatened (CR / EN / VU / EW / EX, or predicted threatened); `not` = not threatened (NT / LC, or predicted not threatened). |

**`threat` values:**

| Value | Meaning | `pext.med` approx. |
|-------|---------|-------------------|
| `CR` | Critically Endangered (IUCN) | ~0.97 |
| `EN` | Endangered (IUCN) | ~0.50 |
| `VU` | Vulnerable (IUCN) | ~0.24 |
| `NT` | Near Threatened (IUCN) | ~0.13 |
| `LC` | Least Concern (IUCN) | ~0.06 |
| `EW` | Extinct in the Wild (IUCN) | ~0.97 |
| `EX` | Extinct (IUCN) | 1.0 |
| `thr` | Predicted threatened (ERP model, no RL assessment) | variable |
| `not` | Predicted not threatened (ERP model, no RL assessment) | variable |

---

### Statistical robustness columns

These columns summarise how consistently a species ranks above the dataset-wide median EDGE score across the 200 MCMC phylogenetic draws.

| Column | Type | Description |
|--------|------|-------------|
| `above.med.tot` | integer | Number of MCMC draws (out of 200) in which the species' EDGE score exceeded the overall median EDGE score for that draw. Range: 0 – 200. |
| `above.med.perc` | float | `above.med.tot / 200`. The proportion of draws in which the species scored above median. Range: 0 – 1. |
| `above.med` | string (`y`/`n`) | Binary flag: `y` if `above.med.perc ≥ 0.95` (i.e. the species scored above the median in at least 95% of draws — a robust, statistically stable result). This is one of the two criteria for EDGE.List membership. |
| `total.thr.draws` | integer | Number of MCMC draws (out of 200) in which the species was classified as threatened. For RL-assessed species this is always 0 or 200 (deterministic); for ERP-modelled species it reflects model uncertainty. |
| `perc.thr.draws` | float | `total.thr.draws / 200`. Proportion of draws in which the species was classified as threatened. |

---

### Taxonomic backbone

| Column | Type | Description |
|--------|------|-------------|
| `in.backbone` | string (`y`/`n`) | Whether the species name is present in the World Flora Online (WFO) / GBIF taxonomic backbone used to construct the phylogeny. `y` = name matched; `n` = name not matched (species may be valid but unresolved synonyms, recently described, or from a regional checklist not yet integrated). ~68,000 species are in the backbone; ~267,000 are not. |

---

### EDGE priority lists

#### EDGE rank vs. EDGE.List — an important distinction

`EDGE.rank` and `EDGE.List` are related but answer different questions:

- **`EDGE.rank`** ranks *all* 335,497 species by their EDGE score. It is a continuous global ranking that combines evolutionary distinctiveness and extinction probability. Every species has a rank, from #1 (highest combined score) to #335,497.

- **`EDGE.List`** is a binary filter applied on top of the ranking. It selects only species that are *both* threatened *and* robustly above the median EDGE score. It is the actionable conservation priority list.

A species can therefore have a **high EDGE rank** (i.e. a good score) but still be **off the EDGE.List** if it is not threatened. The classic example is *Amborella trichopoda* — the sister lineage to all other flowering plants, with the highest ED in the dataset (139.4 Myr). It ranks #1,140 globally, placing it in the top 0.3% of all angiosperms by EDGE score. Yet it is Least Concern, so it does not qualify for the EDGE.List.

Conversely, a species with moderate ED but Critically Endangered status can rank very high and make the EDGE.List, because the high extinction probability amplifies its EDGE score.

| Species | ED (Myr) | Threat | EDGE rank | EDGE.List |
|---------|--------:|:------:|----------:|:---------:|
| *Amborella trichopoda* | 139.4 | LC | #1,140 | No |
| *Amorphophallus lewallei* | 50.9 | CR | **#2** | **Yes** |

In short: **EDGE rank = where a species sits among all flowering plants. EDGE.List = is it both distinctive enough AND threatened enough to be a global conservation priority.**

---

The EDGE.List and related flags categorise species into conservation and research action tiers. A species appears on at most one list.

**The two criteria for all list assignments are:**
1. `thr.or.not = "thr"` — the species is threatened (formally or predicted)
2. `above.med = "y"` — its EDGE score is robustly above the dataset median (in ≥ 95% of draws)

| Column | Type | # species | Description |
|--------|------|----------:|-------------|
| `EDGE.List` | `y`/`n` | 9,945 | **Core EDGE priority list.** Species that are both threatened AND have a robustly above-median EDGE score. These are the global priority species for conservation investment. |
| `EDGE.Borderline` | `y`/`n` | 32,424 | Species that meet the EDGE.List criteria but with lower statistical confidence (e.g. `above.med.perc` between 0.50 and 0.95, or threat status uncertain). Worth monitoring but evidence is weaker. |
| `EDGE.Research` | `y`/`n` | 5,797 | EDGE.List species for which data are critically lacking — prioritised for targeted fieldwork, Red List assessment, or phylogenetic sampling. |
| `EDGE.Watch` | `y`/`n` | 2,170 | EDGE.List species whose status is improving or stabilising but still require active monitoring to prevent relapse. |

---

### Useful plants

| Column | Type | Description |
|--------|------|-------------|
| `useful.plant` | `y`/`n` | Whether the species has a documented economic or cultural use (food, medicine, timber, fibre, etc.) according to the Plants of the World Online useful plants database. ~34,400 species flagged. Can be used to highlight co-benefits of EDGE conservation. |

---

## Key relationships between columns

```
EDGE.List = "y"
    ↔  thr.or.not = "thr"   (threatened formally or by prediction)
    AND above.med = "y"      (above.med.perc ≥ 0.95)

above.med = "y"
    ↔  above.med.perc ≥ 0.95
    ↔  above.med.tot ≥ 190

thr.or.not = "thr"
    ↔  threat ∈ {CR, EN, VU, EW, EX}  (if RL-assessed)
    OR perc.thr.draws > 0.5            (if ERP-modelled)
```

---

## Dataset composition

| Category | Count | % of total |
|----------|------:|----------:|
| Total species | 335,497 | 100% |
| Formally IUCN-assessed (`RL.ERP = "RL"`) | 49,800 | 14.8% |
| ERP-modelled only (`RL.ERP = "ERP"`) | 285,697 | 85.2% |
| In taxonomic backbone (`in.backbone = "y"`) | 68,146 | 20.3% |
| Threatened (CR/EN/VU/EW/EX) — RL-assessed | 20,242 | 6.0% |
| EDGE.List priority species | 9,945 | 3.0% |
| Useful plants | 34,398 | 10.3% |
