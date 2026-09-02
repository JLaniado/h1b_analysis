# H-1B / PERM Analysis for MBA Recruiting Strategy

Analysis of DOL OFLC disclosure data (H-1B/LCA and PERM) to help Tepper School of Business
international MBA students target employers and role functions with realistic odds of visa
sponsorship. End goal is a public dashboard; this repo currently holds the data-exploration
phase.

## Data sources

Disclosure files from the [DOL OFLC Performance Data page](https://www.dol.gov/agencies/eta/foreign-labor/performance),
covering full FY2025 plus FY2026 through Q3. DOL's own export format is inconsistent release to
release — some fiscal years ship as one cumulative CSV, others as four separate quarterly XLSX
files — so `data/raw/` holds whatever DOL actually handed us:

- `LCA_Disclosure_Data_FY2025_Q{1,2,3,4}.xlsx` + `LCA_Disclosure_Data_FY2026_Q3.csv` — H-1B / E-3 /
  H-1B1 Labor Condition Applications
- `PERM_Disclosure_Data_FY2025_Q4.xlsx` (a cumulative full-FY2025 export, despite the "Q4" name) +
  `PERM_Disclosure_Data_FY2026_Q3.csv` — PERM labor certifications (green card sponsorship)
- `*_Record_Layout_*.pdf`, `*_Selected_Statistics_*.pdf` — DOL's own column documentation and
  aggregate stats reports (used to cross-check our own record counts — e.g. DOL's FY26 Q3 selected
  stats report lists "Total Determinations Processed: 437,496" for LCA, which matches exactly)

None of this is committed to git — files run 80MB-450MB each — see `.gitignore`. Drop fresh
exports into `data/raw/` (add new filenames to `LCA_SOURCES`/`PERM_SOURCES` in
`src/consolidate_raw.py`) to extend.

**`python src/consolidate_raw.py` turns all of that into two clean, structured files:**
`data/interim/lca_master.csv` and `data/interim/perm_master.csv`. It handles, once, so nothing
downstream has to:

1. Reading both CSV and XLSX sources uniformly.
2. Dropping blank template rows — every source file, CSV or XLSX, is pre-allocated to a fixed row
   count with only the first N rows populated.
3. A column-name inconsistency across vintages (`H-1B_DEPENDENT` vs `H_1B_DEPENDENT`).
4. Normalizing all dates to ISO (`YYYY-MM-DD`).
5. Deriving `FISCAL_YEAR`/`FISCAL_QUARTER` from `DECISION_DATE` (federal fiscal calendar) rather
   than trusting the filename — verified against DOL's own quarterly breakdowns that the FY2025
   XLSX exports are cleanly disjoint by decision quarter, but the logic also de-dupes safely
   (latest source wins) in case a future release turns out to be cumulative/overlapping instead.
6. Tagging every row with `SOURCE_FILE` for traceability.

Also gitignored (`data/interim/`, multiple hundred MB) — regenerate with the command above any
time `data/raw/` changes. `src/data_loader.py` reads from these master files, not from `data/raw/`
directly, and pandas' C engine still needs `low_memory=False` on read since some cell values
contain embedded newlines (pyarrow's engine outright rejects these files on that).

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m ipykernel install --user --name h1b_analysis --display-name "h1b_analysis"
```

## Structure

- `src/consolidate_raw.py` — builds `data/interim/{lca,perm}_master.csv` from the mixed raw
  sources (see Data sources above)
- `src/data_loader.py` — loaders for the consolidated master CSVs
- `src/employer_canonicalization.py` — collapses casing/punctuation/legal-suffix duplicate
  employer name strings into one canonical name per employer (does *not* merge distinct legal
  subsidiaries of the same brand — see caveats in that file)
- `src/mba_occupations.py` — heuristic for classifying occupations as MBA "core" / "adjacent" /
  "excluded" (see caveats in that file — neither disclosure extract has a real minimum-degree
  field, so this is a SOC-code + title proxy, not ground truth)
- `notebooks/01_data_loading_and_eda.py` — general EDA: data quality, case status/certification
  rates, top occupations, filing trends over time and year-over-year, wages, geography, top
  employers
- `notebooks/02_mba_relevant_analysis.py` — narrows to MBA-relevant roles: certification rates by
  tier, year-over-year growth by tier, top employers ranked by MBA-relevant volume *and* mix,
  wage premium, geography
- `.ipynb` counterparts of both are generated with [jupytext](https://jupytext.readthedocs.io/)
  and executed — re-run with:
  ```bash
  jupytext --to notebook notebooks/*.py
  jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.kernel_name=h1b_analysis notebooks/*.ipynb
  ```
  (Edit the `.py` files, not the `.ipynb` files directly, then regenerate — keeps diffs readable.)
- `data/processed/` — small aggregate CSVs saved from the notebooks (safe to commit, meant to
  seed the eventual dashboard)
- `outputs/figures/` — PNG charts saved from the notebooks

## Status

Exploration phase, now covering full FY2025 + FY2026 through Q3. Headline findings so far live in
notebook 02 — notably, core MBA-relevant filings grew year-over-year (Q1-Q3 FY2025 vs FY2026: LCA
core +34%, PERM core +24%) even as the broader (mostly engineering) filing pool shrank. Open
questions for next steps are listed at the bottom of that notebook (better MBA-relevance signal,
LCA↔PERM employer matching to find who does both H-1B *and* green card sponsorship for business
roles, NAICS industry rollups, a curated brand-alias layer on top of employer canonicalization).
