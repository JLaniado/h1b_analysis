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
7. Stripping a literal `="value"` Excel "keep as text" wrapper that one entire source
   (`LCA_Disclosure_Data_FY2025_Q2.xlsx`, ~13% of LCA data) exports on nearly every text cell —
   this silently corrupted `SOC_CODE` for that whole quarter and broke MBA-tier classification
   for those rows before the fix.

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
- `src/occupation_search.py` — flexible keyword search over SOC/job titles, for targeting by a
  student's actual background rather than being boxed into the core/adjacent/excluded tiers
- `src/naics_sectors.py` — 2-digit NAICS code -> sector name lookup (neither raw dataset ships
  human-readable industry names)
- `src/employer_matching.py` — matches employers across LCA and PERM (by the same cleaned/
  suffix-stripped key as canonicalization) to see who sponsors *both* H-1B and green cards
- `notebooks/01_data_loading_and_eda.py` — general EDA: data quality, case status/certification
  rates, top occupations, filing trends over time and year-over-year, seasonality, wages,
  geography, top employers
- `notebooks/02_mba_relevant_analysis.py` — narrows to MBA-relevant roles: certification rates by
  tier, year-over-year growth by tier, the "real hiring signal" question (new positions vs.
  renewals/transfers for LCA, existing-employee vs. external hire for PERM), top employers ranked
  by MBA-relevant volume *and* mix, wage premium, geography
- `notebooks/03_industry_and_geography.py` — NAICS sector rollups, occupation x industry
  cross-tab, state-level geography with wage, and wage-level (I-IV) mix by occupation as a proxy
  for the seniority a role expects (no applicant-experience field exists, so this is the closest
  available signal)
- `notebooks/04_employer_leaderboard_and_pipeline.py` — full employer scorecard (volume, mix,
  certification rate, new-position share, DOL risk flags, company size where PERM has it) plus
  the LCA↔PERM pipeline view
- `notebooks/05_persona_search_and_walkthrough.py` — runs `occupation_search.py` end-to-end for
  three different student backgrounds (finance/risk/fintech, marketing/brand, supply chain/ops)
  to prove the tooling generalizes rather than being tuned to one persona
- `.ipynb` counterparts of all five are generated with [jupytext](https://jupytext.readthedocs.io/)
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

Exploration phase, now covering full FY2025 + FY2026 through Q3, with an analysis layer answering
the core recruiting-strategy questions (occupation fit, employer targeting, industry, geography,
timing) generically rather than for one fixed persona — see notebooks 02-05.

Headline findings:
- **Real hiring signal matters more than excluding withdrawn/denied cases.** Only ~35-39% of
  MBA-relevant LCA filings are genuinely new positions (`NEW_EMPLOYMENT > 0`) rather than
  extensions/transfers of existing employees; only ~14% of MBA-relevant PERM filings are for a
  worker not already employed there (`OTHER_REQ_IS_FW_CURRENTLY_WRK`) — most PERM sponsorship is
  green-card conversion for existing H-1B staff, not an offer to an external candidate.
- **Corrected year-over-year picture** (after fixing the FY2025-Q2 data bug — see Data sources):
  MBA-core LCA filings are roughly flat YoY (Q1-Q3 FY2025 vs FY2026: -1.8%, previously
  mis-reported as +34% before the bug fix), while PERM core filings are up +24%. Adjacent-tier
  LCA filings are down -13.2%.
- 8,885 employers show MBA-relevant activity in *both* LCA and PERM (a full visa-to-green-card
  pathway), out of ~45K MBA-relevant LCA filers — most H-1B business-role sponsors show no
  matched PERM presence, worth double-checking rather than treating as confirmed "no path."

Open questions/next steps: a curated brand-alias layer on top of employer canonicalization (e.g.
Amazon Web Services vs. Amazon.com Services LLC), a better MBA-relevance signal than SOC/title
regex if a cleaner minimum-education proxy is worth integrating, and — deferred by design this
round — choosing and building the actual interactive dashboard technology on top of this
analysis layer.
