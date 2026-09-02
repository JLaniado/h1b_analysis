# H-1B / PERM Analysis for MBA Recruiting Strategy

Analysis of DOL OFLC disclosure data (H-1B/LCA and PERM) to help Tepper School of Business
international MBA students target employers and role functions with realistic odds of visa
sponsorship. End goal is a public dashboard; this repo currently holds the data-exploration
phase.

## Data sources

Raw quarterly disclosure files from the [DOL OFLC Performance Data page](https://www.dol.gov/agencies/eta/foreign-labor/performance):

- `data/raw/LCA_Disclosure_Data_FY2026_Q3.csv` — H-1B / E-3 / H-1B1 Labor Condition Applications
- `data/raw/PERM_Disclosure_Data_FY2026_Q3.csv` — PERM labor certifications (green card sponsorship)

Both files are large (400MB+ / 230MB+) and are **not committed to git** — see `.gitignore`.
Drop fresh quarterly exports into `data/raw/` with the same filenames to reproduce.

Two quirks worth knowing before touching the raw CSVs (documented in `src/data_loader.py`):

1. Cell values can contain embedded newlines, so pandas' C engine needs `low_memory=False`
   (pyarrow's engine outright rejects these files).
2. Each quarterly file is pre-allocated for the full fiscal year — only the first N rows have
   data, the rest are fully blank rows. The loaders drop rows with a blank `CASE_NUMBER`.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m ipykernel install --user --name h1b_analysis --display-name "h1b_analysis"
```

## Structure

- `src/data_loader.py` — robust loaders for the LCA/PERM CSVs
- `src/mba_occupations.py` — heuristic for classifying occupations as MBA "core" / "adjacent" /
  "excluded" (see caveats in that file — neither disclosure extract has a real minimum-degree
  field, so this is a SOC-code + title proxy, not ground truth)
- `notebooks/01_data_loading_and_eda.py` — general EDA: data quality, case status/certification
  rates, top occupations, filing trends over time, wages, geography, top employers
- `notebooks/02_mba_relevant_analysis.py` — narrows to MBA-relevant roles: certification rates by
  tier, top employers ranked by MBA-relevant volume *and* mix, wage premium, geography
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

Exploration phase. Headline findings so far live in notebook 02; open questions for next steps
are listed at the bottom of that notebook (better MBA-relevance signal, LCA↔PERM employer
matching to find who does both H-1B *and* green card sponsorship for business roles, NAICS
industry rollups).
