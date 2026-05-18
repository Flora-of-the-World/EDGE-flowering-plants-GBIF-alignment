# EDGE Flowering Plants × Flora of the World — Documentation

## Overview

This folder contains the data and scripts to cross-match the **EDGE flowering plant dataset** (Forest et al., *Science*) with the **Flora of the World (FotW) occurrence database**, in order to identify which EDGE-scored species are documented on FotW and to produce conservation-relevant statistics for a press release.

---

## Matching strategy

The core challenge is that EDGE and FotW may use different accepted names for the same species — one dataset may follow a newer synonymy, use a different spelling, or apply a different circumscription. A naïve string match will therefore undercount the true overlap.

Our strategy is to **normalise FotW taxonomy to the GBIF backbone first, then match against EDGE**.

This is preferable to bidirectional on-the-fly synonym resolution because:

1. **GBIF is the shared backbone.** The EDGE dataset is built on GBIF taxonomy. By aligning FotW names to GBIF accepted names, both datasets speak the same language before any comparison is made.
2. **FotW taxonomy is under our control.** We can fix name discrepancies in FotW directly (and have done so for the names identified during earlier synonym resolution). This means the alignment is a one-time operation that improves the underlying database, not a workaround applied at query time.
3. **Cleaner and more reproducible.** Once FotW names are resolved to GBIF accepted names, the EDGE match becomes a simple exact-key lookup with no ambiguity.

### Pipeline overview

```
FotW taxonomy DB                        EDGE dataset (GBIF backbone)
        │                                          │
        ▼                                          ▼
[Step 1] Resolve FotW names           [Step 4a] Resolve EDGE names
         to GBIF accepted names                to GBIF accepted names
         (resolve_fotw_taxonomy.py)            (resolve_edge_taxonomy.py)
        │                                          │
        ▼                                          ▼
 FotW GBIF-normalised names           EDGE GBIF-normalised + new
        │                              accepted-name records
        │                              (build_edge_complete.py)
        ├──────────────────────────────────────────┤
        ▼                                          ▼
[Step 2] Exact match on              Joinable on accepted_gbif_id
         GBIF accepted name           for FotW website integration
         (match_EDGE_FotW_gbif.py)    (EDGE score embedding on
        │                              FotW taxon pages)
        ▼
[Step 3] Retrieve FotW taxon
         UUIDs for EDGE.List species
         (fetch_fotw_taxon_uuids.py)
```

Steps 1–3 produce the matched species list and FotW links used in the *Science* press release. Step 4 (the EDGE-side GBIF alignment) produces the FotW website deliverable: a single combined file that lets FotW import EDGE scores and resolve future taxon additions against the EDGE dataset.

---

## Files

### Scripts

| File | Location | Description |
|------|----------|-------------|
| [`resolve_fotw_taxonomy.py`](../FotW_DB/resolve_fotw_taxonomy.py) | `../FotW_DB/` | **Step 1.** Resolves all FotW taxon names against the GBIF backbone. Determines accepted/synonym status; for synonyms, retrieves the accepted name and its GBIF ID. |
| [`match_EDGE_FotW_gbif.py`](match_EDGE_FotW_gbif.py) | `EDGE_flowering_plants/` | **Step 2.** Exact-name match between GBIF-normalised FotW taxa and the EDGE dataset. |
| [`fetch_fotw_taxon_uuids.py`](fetch_fotw_taxon_uuids.py) | `EDGE_flowering_plants/` | **Step 3.** Retrieves FotW taxon page UUIDs for matched EDGE.List species. |
| [`resolve_edge_taxonomy.py`](resolve_edge_taxonomy.py) | `EDGE_flowering_plants/` | **Step 4a.** Resolves all 335,497 EDGE species names against the GBIF backbone. Mirrors `resolve_fotw_taxonomy.py`. Resumable; supports `--scope list \| priority \| all`. |
| [`build_edge_complete.py`](build_edge_complete.py) | `EDGE_flowering_plants/` | **Step 4b.** Builds the combined deliverable for the FotW website team: all EDGE rows + new accepted-name records inferred from synonym resolution. Collapses GBIF homonyms into canonical records. |
| [`generate_main_report.py`](generate_main_report.py) | `EDGE_flowering_plants/` | Generates `EDGE_FotW_report.md` / `.pdf` for the press article. |
| [`generate_press_article.py`](generate_press_article.py) | `EDGE_flowering_plants/` | Generates `EDGE_FotW_press_article.docx` BSU press article draft. |
| [`plot_EDGE_FotW.py`](plot_EDGE_FotW.py) | `EDGE_flowering_plants/` | Generates figures from the matched species data. |

### Input data (not bundled — see links)

| File | Source | Description |
|------|--------|-------------|
| `Forest_etal_EDGEangio_tableS1_EDGEspp_RL&Pred.csv` | [Zenodo `10.5281/zenodo.17273037`](https://doi.org/10.5281/zenodo.17273037) | Source EDGE dataset (Forest et al., *Science*, 2025). 335,497 flowering plant species with EDGE scores, ED, threat status, and EDGE.List flags. |
| `taxon_DB_01May2026.csv` | [`FotW-taxonomy-GBIF-alignment`](https://github.com/Flora-of-the-World/FotW-taxonomy-GBIF-alignment) | FotW taxonomy DB export (12,838 taxa). Contains FotW taxon UUIDs and GBIF/CoL IDs in `scientificNameID`. |
| `fotw_taxonomy_resolved.csv` | [`FotW-taxonomy-GBIF-alignment`](https://github.com/Flora-of-the-World/FotW-taxonomy-GBIF-alignment) | GBIF-resolved FotW taxonomy. Used by Steps 2 and 3 as the FotW-side join input. |
| `occurrences.csv` | FotW Foundation (private export) | FotW occurrence records, used by Step 2 for documentation counts and Step 3 for taxon-page lookups. |

### Output bundled with this repository

| File | Description |
|------|-------------|
| [`edge_taxonomy_complete.csv.gz`](edge_taxonomy_complete.csv.gz) | **Primary deliverable.** 340,042 rows: 335,497 EDGE originals + 4,545 inferred accepted-name records. 38 columns (`record_type` + 14 GBIF + 22 EDGE-source + `synonym_edge_keys`). Compressed with gzip (~23 MB; decompresses to ~99 MB). |
| [`EDGE_CSV_data_dictionary.md`](EDGE_CSV_data_dictionary.md) | Reference documentation for all 22 source EDGE columns (`Species`, `EDGE.rank`, `edge.med`, `ed.med`, `threat`, `EDGE.List`, …). |

### Other outputs (reproducible by running the scripts)

| File | Produced by | Description |
|------|-------------|-------------|
| `edge_taxonomy_resolved.csv` | `resolve_edge_taxonomy.py --scope all` | Intermediate file. All 335,497 EDGE species with GBIF resolution (36 columns). Schema column-compatible with `fotw_taxonomy_resolved.csv`. |
| `edge_new_accepted_names.csv` | `build_edge_complete.py` | Subset of the deliverable: 4,545 inferred accepted-name records only. |
| `EDGE_FotW_matched_species_gbif.csv` | `match_EDGE_FotW_gbif.py` | 10,902 EDGE species matched against FotW with metadata and taxon URLs. |
| `fotw_taxon_uuids.csv` | `fetch_fotw_taxon_uuids.py` | FotW taxon UUIDs and URLs for EDGE.List species in FotW. |
| `EDGE_FotW_report.md` / `.pdf` | `generate_main_report.py` | Full report with statistics and clickable FotW links. |
| `figures/` | `plot_EDGE_FotW.py` | Coverage, threat breakdown, top species, families, ED plots. |

### Reading the bundled deliverable

```python
import pandas as pd
df = pd.read_csv("edge_taxonomy_complete.csv.gz")   # pandas reads .gz transparently
```

```r
df <- read.csv(gzfile("edge_taxonomy_complete.csv.gz"))
```

```bash
gunzip -c edge_taxonomy_complete.csv.gz | head
```

---

## Step 1 — Resolve FotW taxonomy to GBIF (`resolve_fotw_taxonomy.py`)

Located in `../FotW_DB/`. Run from that directory:

```bash
cd ../FotW_DB
python3 resolve_fotw_taxonomy.py [--workers N] [--delay SECONDS]
```

### How it works

For each of the 12,838 FotW taxa:

- **If a GBIF species ID is available** (`scientificNameID` contains `gbif.org/species/{id}`): queries `/v1/species/{id}` directly. This is the most reliable method — no name-matching ambiguity.
- **Otherwise** (CoL ID or no ID): queries `/v1/species/match?kingdom=Plantae&name=Genus+epithet`. Matches with confidence < 80 are flagged.

GBIF returns `taxonomicStatus` (`ACCEPTED`, `SYNONYM`, `DOUBTFUL`) and, for synonyms, the accepted name and its GBIF key. The script writes all results to `fotw_taxonomy_resolved.csv`.

**Coverage of the 12,838 FotW taxa:**

| Lookup method | Count |
|---|---|
| GBIF ID (direct) | 8,798 |
| CoL ID or no ID (name-match fallback) | 4,040 |

The script is resumable — already-resolved taxon IDs are skipped on re-run.

### Output — `fotw_taxonomy_resolved.csv`

| Column | Description |
|--------|-------------|
| `taxonID` | FotW taxon UUID |
| `scientificName` | Original FotW name |
| `genus`, `specificEpithet`, `infraspecificEpithet` | Name components |
| `scientificNameID` | Original GBIF or CoL URL from FotW DB |
| `gbif_id` | Extracted numeric GBIF species key |
| `lookup_method` | `gbif_id` or `name_match` |
| `gbif_status` | `ACCEPTED`, `SYNONYM`, `DOUBTFUL`, `NO_MATCH`, or `ERROR` |
| `gbif_confidence` | Confidence score (name-match only) |
| `accepted_name` | GBIF-accepted binomial |
| `accepted_gbif_id` | GBIF key of the accepted name |
| `accepted_gbif_url` | `https://gbif.org/species/{accepted_gbif_id}` |
| `error` | Error message if lookup failed |

---

## Step 2 — Match FotW against EDGE (`match_EDGE_FotW_gbif.py`)

```bash
cd EDGE_flowering_plants
python3 match_EDGE_FotW_gbif.py                        # both phases (recommended)
python3 match_EDGE_FotW_gbif.py --phase 1              # Phase 1 only, no network
python3 match_EDGE_FotW_gbif.py --workers 8 --delay 0.3  # tune Phase 2 load
```

### The GBIF backbone version mismatch problem

Although both FotW (after Step 1 normalisation) and EDGE use the GBIF backbone, they do not use the **same version** of it. The EDGE dataset was built on a GBIF snapshot that predates the current one. Some names that EDGE treats as accepted have since been synonymised by GBIF.

This creates a one-sided blind spot:

| Dataset | Name used | GBIF current status |
|---------|-----------|---------------------|
| EDGE | *Aneulophus congoensis* | SYNONYM of *A. africanus* |
| FotW (normalised) | *Aneulophus africanus* | ACCEPTED |

After Step 1, FotW correctly carries *Aneulophus africanus*. But this name does not appear in EDGE (which has *Aneulophus congoensis*), so a Phase 1-only match produces no hit. The problem is on the EDGE side: its names are frozen at an older GBIF version.

### Two-phase solution

**Phase 1 — FotW → GBIF → EDGE** (no network calls; uses pre-resolved taxonomy from Step 1)

For every FotW taxon, the GBIF-accepted name is looked up from `fotw_taxonomy_resolved.csv` and checked against the EDGE dataset. Catches:
- *direct* — FotW name = EDGE name (same current GBIF accepted name on both sides)
- *fotw_synonym* — FotW carried an old name; its GBIF accepted name = EDGE name

**Phase 2 — EDGE.List → GBIF → FotW** (~9,700 network queries; ~10 min)

For each EDGE.List species not yet matched, the EDGE name is queried against GBIF. If GBIF returns a different accepted name and that name is present in FotW's normalised taxonomy, a match is recorded. These are labelled *edge_synonym* matches.

Together, the two phases ensure that name-version differences on either side of the GBIF snapshot boundary do not cause missed matches.

### Output — `EDGE_FotW_matched_species_gbif.csv`

Columns: `EDGE_rank`, `species`, `family`, `order`, `edge_med`, `ed_med`, `tbl_med`, `pext_med`, `threat`, `RL_ERP`, `EDGE_List`, `EDGE_Borderline`, `EDGE_Research`, `EDGE_Watch`, `fotw_original_name`, `fotw_gbif_status`, `fotw_taxon_id`, `match_method`, `n_fotw_records`, `taxon_url`

The `match_method` column records how each species was found:

| Value | Meaning |
|-------|---------|
| `direct` | FotW name = EDGE name |
| `fotw_synonym` | FotW name was a GBIF synonym; accepted name = EDGE name |
| `edge_synonym` | EDGE name was a GBIF synonym; accepted name is in FotW (Phase 2) |

---

## Step 3 — Retrieve FotW taxon UUIDs ([`fetch_fotw_taxon_uuids.py`](fetch_fotw_taxon_uuids.py))

```bash
python3 fetch_fotw_taxon_uuids.py [--workers N] [--delay SECONDS]
```

For each EDGE.List species matched in FotW, queries the FotW search page and parses the taxon page UUID from the HTML. Resumable. Output: `fotw_taxon_uuids.csv` with columns `species_key`, `genus`, `epithet`, `taxon_uuid`, `taxon_url`.

All EDGE.List species in FotW have complete UUID entries (2 were supplied manually: *Nasa aequatoriana* and *Tecunumania stothertiae*).

---

## Step 4 — EDGE taxonomy GBIF alignment & FotW deliverables

This is the EDGE-side counterpart to Step 1. It produces a single combined file that lets the FotW website team (i) import EDGE scores onto existing FotW taxon pages and (ii) resolve any future FotW taxon addition against the EDGE dataset via the GBIF backbone.

### Step 4a — Resolve EDGE names against GBIF ([`resolve_edge_taxonomy.py`](resolve_edge_taxonomy.py))

```bash
python3 resolve_edge_taxonomy.py --scope all          # full 335,497-row table (~17 h)
python3 resolve_edge_taxonomy.py --scope priority     # list+borderline+research+watch (~28 min)
python3 resolve_edge_taxonomy.py --scope list         # EDGE.List only (~6 min)
```

For each EDGE species, queries `/v1/species/match?kingdom=Plantae&name=Genus epithet` against the current GBIF backbone. Mirrors `resolve_fotw_taxonomy.py` (same 14 GBIF-derived columns, identical names and order). Resumable — already-resolved species are skipped on re-run.

**Output — `edge_taxonomy_resolved.csv`** (36 columns):

| Block | Columns |
|---|---|
| GBIF-derived (14 — same schema as `fotw_taxonomy_resolved.csv`) | `taxonID`, `scientificName`, `genus`, `specificEpithet`, `infraspecificEpithet`, `scientificNameID`, `gbif_id`, `lookup_method`, `gbif_status`, `gbif_confidence`, `accepted_name`, `accepted_gbif_id`, `accepted_gbif_url`, `error` |
| EDGE source (22, verbatim from input) | `Species`, `EDGE.rank`, `Family`, `Order`, `edge.med`, `ed.med`, `tbl.med`, `above.med.tot`, `above.med.perc`, `pext.med`, `total.thr.draws`, `perc.thr.draws`, `threat`, `RL.ERP`, `thr.or.not`, `in.backbone`, `above.med`, `EDGE.List`, `EDGE.Borderline`, `EDGE.Research`, `EDGE.Watch`, `useful.plant` |

**Resolution results (335,497 rows):**

| GBIF status | Count | % |
|---|---:|---:|
| ACCEPTED | 326,159 | 97.22% |
| SYNONYM | 9,051 | 2.70% |
| HETEROTYPIC_SYNONYM | 6 | 0.00% |
| DOUBTFUL | 19 | 0.01% |
| NO_MATCH | 0 | 0% |
| ERROR (transient GBIF timeouts; retryable) | 262 | 0.08% |

All synonyms have `accepted_name` and `accepted_gbif_id` populated.

### Step 4b — Build the combined deliverable ([`build_edge_complete.py`](build_edge_complete.py))

```bash
python3 build_edge_complete.py
```

Reads `edge_taxonomy_resolved.csv` and produces:

1. **`edge_taxonomy_complete.csv`** — the primary deliverable. Single combined file containing:
   - All 335,497 EDGE rows tagged `record_type = edge_original`
   - 4,545 new accepted-name records tagged `record_type = gbif_accepted_new`, generated when an EDGE synonym resolves to a GBIF-accepted binomial that is **not itself** in the EDGE Species list. Each new row carries `synonym_edge_keys` — a semicolon-separated list of the EDGE synonym(s) that point to that accepted name.
2. **`edge_new_accepted_names.csv`** — the 4,545 new rows only, for review.

**GBIF homonym handling:** some accepted binomials exist as multiple GBIF taxa (homonyms, or GBIF's own duplicate records — e.g. *Morella salicifolia* has 5 distinct GBIF keys). The script collapses these into one canonical record per binomial, picked by (a) most synonym pointers, (b) tie-break by lowest GBIF key. The dropped homonym GBIF ids are preserved on the canonical row in the `error` column (`merged_homonyms:<id1>,<id2>,...`). 64 GBIF entries collapsed into 45 canonical winners.

**Combined file integrity:**

| Check | Result |
|---|---:|
| Total rows | 340,042 |
| Duplicate `taxonID` | 0 |
| Duplicate `scientificName` | 0 |
| Source EDGE table duplicate `Species` | 0 |
| Groups sharing `accepted_gbif_id` (synonym↔accepted links, **not** duplicates) | 7,356 |

**Schema (38 columns):** `record_type` + the 36 columns of `edge_taxonomy_resolved.csv` + `synonym_edge_keys`.

**How to join with FotW:**

```
FotW (fotw_taxonomy_resolved.csv).accepted_gbif_id
    ↔
EDGE (edge_taxonomy_complete.csv).accepted_gbif_id
```

The two files share 10,299 unique `accepted_gbif_id` values; 10,902 EDGE rows have a FotW match, including **231 EDGE.List priority species** (up from 229 with the older direct-name pipeline — the gain comes from deeper synonym resolution applied to every EDGE row).

---

## What to display on the FotW taxon page

Of the 22 EDGE source columns, only a subset is meaningful for end users — many are MCMC sampling statistics that justify the methodology but don't belong on a public page. The recommendations below are organised by display priority. The full column glossary is in [`EDGE_CSV_data_dictionary.md`](EDGE_CSV_data_dictionary.md).

### Tier 1 — show on the taxon page (initial release)

| Column | Suggested label / UI treatment | Meaning |
|---|---|---|
| `is_edge_species` *(derived boolean)* | No badge — gates the entire EDGE panel | Computed during import: true if a matching row was found in `edge_taxonomy_complete.csv` when joining on `accepted_gbif_id` (either `record_type = edge_original`, or `record_type = gbif_accepted_new` with a resolvable `synonym_edge_keys` link). Use this as the master gate for whether the EDGE panel is rendered at all. |
| `is_edge_list_priority` *(derived boolean)* | Badge: **"EDGE Priority Species"** | Computed during import: true if `EDGE.List = "y"`. Member of the global priority list of 9,945 species that are both threatened AND robustly above the median EDGE score. The single most actionable flag on the page. |
| `EDGE.rank` | *"EDGE rank: #N of 335,497"* | Global rank by combined EDGE score. #1 is the top priority overall. Rank #1,140 = top 0.3%. Useful for context even when not on the priority list. |
| `edge.med` | *"EDGE score: X.XX"* | The composite metric itself (range 0–54.9). Higher = greater conservation priority. Best paired with the rank for interpretation. |
| `ed.med` | *"Evolutionary Distinctiveness: X Myr"* | How isolated this species is on the flowering-plant tree of life, in millions of years. Long branches with few close relatives = high ED (max 139.4 Myr for *Amborella trichopoda*). |
| `threat` | IUCN-style tag (CR / EN / VU / NT / LC / EW / EX) with the standard IUCN colour coding; or *"Predicted: threatened / not threatened"* when from the expert panel | Either the IUCN Red List category or a modelled equivalent. Always pair with `RL.ERP` so the attribution is honest. |
| `RL.ERP` | Small tag next to threat: *"IUCN-assessed"* (RL) or *"Modelled — Expert Review Panel"* (ERP) | Distinguishes formal IUCN assessments (49,800 species) from model predictions (285,700 species). Critical for honest presentation — predicted threat is not the same as assessed. |

### Available but deferred to a future release

These columns carry meaningful information and can be added to the EDGE panel in a future iteration, but are not part of the initial design.

- `pext.med` — modelled probability of extinction within 100 years (the GE term in the EDGE formula, ~0.04 for LC, ~0.97 for CR).
- `useful.plant` — has a documented economic or cultural use per Plants of the World Online (~34,400 species). Good candidate for a "documented human use" icon.
- `EDGE.Borderline` — meets EDGE.List criteria with lower statistical confidence (50–95% of phylogenetic draws above median).
- `EDGE.Research` — EDGE.List species lacking adequate data; flagged for targeted fieldwork or Red List assessment.
- `EDGE.Watch` — EDGE.List species whose status is improving or stabilising but still require active monitoring.

### Do not display (internal / methodological)

These columns underpin the analysis but are not user-relevant. Keep them in the database for reproducibility, but do not surface them on taxon pages.

- `tbl.med` — terminal branch length (Myr). Technical phylogenetics; redundant with `ed.med` for most users.
- `above.med` — statistical robustness flag (above-median in ≥ 95% of draws). Methodological — already baked into `EDGE.List` membership.
- `above.med.tot` — internal MCMC counter (draws above median).
- `above.med.perc` — internal MCMC counter (proportion of draws above median).
- `total.thr.draws` — internal MCMC counter (draws classified as threatened).
- `perc.thr.draws` — internal MCMC counter (proportion of draws classified as threatened).
- `thr.or.not` — binary derived from `threat`; redundant for display.
- `in.backbone` — whether the EDGE name was on the WFO/GBIF backbone snapshot used to build the phylogeny. Internal metadata.

### Design hints

- Use the official IUCN palette for the threat tag (CR red, EN orange-red, VU orange, NT amber, LC green, EW/EX black). For ERP-predicted species, use a desaturated version of the same colour to signal lower certainty.
- Where `RL.ERP = RL`, link the threat tag to the species' IUCN Red List page. Doable now via the IUCN Red List API v4; an enrichment step can attach the IUCN URL for the ~49,800 RL-assessed species.
- For `is_edge_list_priority = true` species, consider a dedicated EDGE panel near the top of the page. For non-priority species with a notably high `EDGE.rank` (say top 10,000), a smaller inline note keeps context without implying priority.
- `ed.med` is the most intuitive metric for a general audience (*"this species sits on a 50-million-year branch with no close relatives"*) — worth a one-line plain-language gloss next to the number.

---

## Input data details

### EDGE dataset columns

| Column | Description |
|--------|-------------|
| `Species` | Binomial name with underscore separator (e.g. `Gomortega_keule`) |
| `EDGE.rank` | Global EDGE rank among all 335,497 species (1 = highest) |
| `Family` / `Order` | Taxonomic placement |
| `edge.med` | Median EDGE score |
| `ed.med` | Median Evolutionary Distinctiveness (millions of years) |
| `tbl.med` | Median terminal branch length (millions of years) |
| `pext.med` | Median probability of extinction |
| `threat` | IUCN Red List category or predicted status (`thr` / `not`) |
| `RL.ERP` | Assessment source: `RL` = IUCN Red List, `ERP` = Expert Review Panel |
| `EDGE.List` | `y` if on EDGE priority list (threatened + robustly above-median EDGE score) |
| `EDGE.Borderline` | `y` if borderline EDGE.List candidate |
| `EDGE.Research` | `y` if flagged for research priority |
| `EDGE.Watch` | `y` if flagged for monitoring |

> **EDGE rank vs. EDGE.List**
>
> `EDGE.rank` sorts *all* 335,497 species by EDGE score. `EDGE.List` is a binary filter: only species that are *both* threatened *and* robustly above the median EDGE score (≥ 95% of phylogenetic draws). A species can rank highly but be off the EDGE.List if it is not threatened — e.g. *Amborella trichopoda* (ED = 139.4 Myr, LC, rank #1,140, not on EDGE.List) vs. *Amorphophallus lewallei* (ED = 50.9 Myr, CR, rank #2, EDGE.List).

### FotW occurrence database columns

| Column | Description |
|--------|-------------|
| `genus` | Genus name |
| `specificEpithet` | Species epithet |
| `family` | Family name |
| `occurrenceID` | UUID of the occurrence record |
| `country`, `stateProvince`, `county`, `locality` | Geographic provenance |
| `decimalLatitude`, `decimalLongitude` | Coordinates |
| `eventDate` | Collection or observation date |
| `recordedBy` | Collector name (one row per collector) |

---

## Key results (current)

### EDGE × FotW matching

| Metric | Value |
|--------|-------|
| EDGE species matched in FotW | 10,902 / 335,497 (3.25%) |
| EDGE.List species in FotW | **231 / 9,945 (2.32%)** |
| Unique GBIF accepted ids shared (EDGE ∩ FotW) | 10,299 |
| Best EDGE rank in FotW | #2 (*Amorphophallus lewallei*, CR) |
| EW EDGE.List species in FotW | 4 (*Franklinia alatamaha*, *Brugmansia suaveolens*, *B. vulcanicola*, *B. sanguinea*) |

### EDGE × GBIF resolution (Step 4)

| Metric | Value |
|--------|-------|
| EDGE rows resolved against GBIF | 335,497 (100%) |
| ACCEPTED | 326,159 (97.22%) |
| SYNONYM (incl. HETEROTYPIC) | 9,057 (2.70%) |
| DOUBTFUL | 19 |
| ERROR (retryable) | 262 (0.08%) |
| New accepted-name records created | 4,545 |
| **Combined deliverable rows** | **340,042** |

---

## Planned next steps

1. ~~GBIF taxonomy alignment of FotW~~ — DONE; deposited at [Flora-of-the-World/FotW-taxonomy-GBIF-alignment](https://github.com/Flora-of-the-World/FotW-taxonomy-GBIF-alignment).
2. ~~EDGE-side GBIF taxonomy alignment~~ — DONE 2026-05-18; produces `edge_taxonomy_complete.csv`.
3. FotW website team to import `edge_taxonomy_complete.csv`: update existing taxon pages with EDGE scores (join on `accepted_gbif_id`), and add the 4,545 new accepted-name records.
4. EDGE score integration on FotW taxon pages — embed `edge.med`, `ed.med`, `threat`, and `EDGE.List` flag.
5. *(Optional)* Retry the 262 ERROR rows from Step 4a — delete those rows from `edge_taxonomy_resolved.csv` and re-run `resolve_edge_taxonomy.py --scope all` (resumable).
6. Press release species selection — shortlist the most compelling EDGE.List species in FotW.

---

## Citation

If you use this repository, please cite both the source publication and the underlying dataset.

**Publication**

> Forest, F., Brown, R., Buerki, S., Colville, J. F., Moat, J., Nic Lughadha, E., Owen, N. R., Raimondo, D. C., Rivers, M., Rosindell, J., Walker, B. E., Bachman, S. P., Pipins, S., Gumbs, R., Brown, M. J. M. (2025). High risk of extinction across the flowering plant tree of life. *Science*. <https://doi.org/10.1126/science.adz0773>

**Dataset**

> Forest, F., Brown, R., Buerki, S., Colville, J. F., Moat, J., Nic Lughadha, E., Owen, N. R., Raimondo, D. C., Rivers, M., Rosindell, J., Walker, B. E., Bachman, S. P., Pipins, S., Gumbs, R., Brown, M. J. M. (2025). *High risk of extinction across the flowering plant tree of life — codes.* Zenodo. <https://doi.org/10.5281/zenodo.17273037>

The source EDGE table redistributed in this repository (`Forest_etal_EDGEangio_tableS1_EDGEspp_RL&Pred.csv`) is Supplementary Table S1 of the publication above and is also available through the Zenodo deposit.

---

## License

This repository is released under the [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/legalcode) license. The full legal code is included in the [LICENSE](LICENSE) file.

You are free to share and adapt the material — including the code, the GBIF-resolved EDGE taxonomy outputs, and the combined deliverable — for any purpose, including commercially, provided that you give appropriate credit to the source publication and dataset cited above, indicate any changes made, and do not suggest endorsement by the authors of either work.

---

## Maintainer

Flora of the World Foundation, Boise, ID, USA — <https://floraoftheworld.org>
