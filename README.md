# H-1B / PERM Analysis for MBA Recruiting Strategy

Analysis of DOL OFLC disclosure data (H-1B/LCA and PERM) to help Tepper School of Business
international MBA students target employers and role functions with realistic odds of visa
sponsorship, plus an interactive explorer built on top of it.

**[Open the Sponsorship Explorer dashboard →](https://jlaniado.github.io/h1b_analysis/)**
Filter H-1B and PERM filings by occupation keyword, industry, state, and wage level; see a
ranked employer leaderboard with certification rate, real-new-position share, and H-1B→green-card
pipeline status. (Also available as a [Claude Artifact](https://claude.ai/code/artifact/3e07185f-f13a-4454-bfe6-5bb776429ef6) — same page, private link.)

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
  employer name strings into one canonical name per employer. Build the mapping across *all*
  datasets at once (`build_canonical_map(lca[...], perm[...])`), not one map per dataset — doing
  it separately lets the same company settle on a different display spelling in each (e.g.
  "Apple Inc." in LCA vs "APPLE INC." in PERM), which then never merges when compared or combined.
- `src/employer_brand_rollup.py` — manually-reviewed rollup of distinct legal subsidiaries to one
  brand label (e.g. "Amazon Web Services, Inc." + "Amazon.com Services LLC" -> "Amazon"), applied
  on top of `employer_canonicalization`. Every group was built by hand-reviewing the top ~400
  employers by volume — the module's docstring lists specific look-alike names that were
  deliberately *excluded* (e.g. "Apple American Group LLC" is an Applebee's franchisee, not Apple
  Inc.; "The Citadel" is a military college, not the hedge fund) so a future edit doesn't
  accidentally add them back in.
- `src/mba_occupations.py` — heuristic for classifying occupations as MBA "core" / "adjacent" /
  "excluded" (see caveats in that file — neither disclosure extract has a real minimum-degree
  field, so this is a SOC-code + title proxy, not ground truth)
- `src/occupation_search.py` — flexible keyword search over SOC/job titles, for targeting by a
  student's actual background rather than being boxed into the core/adjacent/excluded tiers
- `src/naics_sectors.py` — 2-digit NAICS code -> sector name lookup (neither raw dataset ships
  human-readable industry names)
- `src/employer_matching.py` — matches employers across LCA and PERM (by the same cleaned/
  suffix-stripped key as canonicalization) to see who sponsors *both* H-1B and green cards
- `src/build_dashboard_data.py` / `src/build_dashboard_html.py` — build the interactive dashboard
  (see Dashboard section below)
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
- `data/processed/` — small aggregate CSVs saved from the notebooks (safe to commit)
- `outputs/figures/` — PNG charts saved from the notebooks

## Dashboard

The Sponsorship Explorer (linked above) is a static, client-side-filtered page — no backend, so
it's just a link to share. It's built in three steps, each re-runnable independently:

1. `python src/build_dashboard_data.py` — aggregates the LCA/PERM master data into a compact,
   dictionary-encoded JSON "cube" at the grain (occupation, employer, state, industry sector,
   wage level), restricted to the ~150 highest-volume occupations and employers with 3+ filings
   (covers 81% of MBA-relevant LCA filings, 57% of PERM — the long tail is dropped to keep the
   page small enough to embed client-side). Writes `outputs/dashboard_data.json`.
2. `python src/build_dashboard_html.py` — injects that JSON into `outputs/dashboard_template.html`
   (the actual page source — edit this file for any markup/style/logic change, not either
   generated output) to produce two files: `outputs/dashboard.html` (a fragment, for Claude
   Artifact publishing, which wraps the page itself) and `docs/index.html` (a complete standalone
   document with its own `<!DOCTYPE>`/`<head>`/charset, since GitHub Pages does no such wrapping —
   opening a fragment directly in a browser mis-guesses the encoding and mangles non-ASCII
   characters).
3. Publish `outputs/dashboard.html` as a Claude Artifact, and push `docs/index.html` to have
   GitHub Pages pick it up automatically (Pages is configured to serve from `main` / `/docs`).

External assets (Google Fonts, [Chart.js](https://www.chartjs.org/) from cdnjs) are loaded from a
CDN — if you change the pinned Chart.js version in the template, verify the exact
`https://cdnjs.cloudflare.com/ajax/libs/Chart.js/<version>/chart.umd.min.js` URL actually resolves
(`curl -I` it) before publishing. An earlier version of this dashboard pinned a version that
didn't exist on cdnjs, which 404'd silently in most consoles and looked like a network/ad-blocker
issue rather than a typo'd version number.

The page is deliberately scoped to occupations in the core/adjacent MBA tiers — a search for a
more technical title like "Data Scientists" or "Software Developers" won't return results, since
including those (very high-volume, very high cardinality) occupations would blow the data cube
past a size a static page can embed. This is called out directly in the page's own copy so it
doesn't read as a bug.

**Coverage**: because of that sampling, the static page covers 184,015 of 1,023,639 total LCA
records (**18.0%**) and 25,134 of 259,489 total PERM records (**9.7%**) — see `app.py` below for
the full-data alternative.

## Local dashboard (full data)

`app.py` is a [Streamlit](https://streamlit.io/) app with no sampling: it loads the complete
consolidated master data directly and filters/aggregates live with pandas, so it has no
embed-size constraint to work around. Compared to the static page, it covers:

- **Every record** in both datasets, not a ~150-occupation/3+-filing sample.
- **Every MBA tier, including "excluded"** — technical titles like Data Scientists or Software
  Developers are searchable (toggle the tier filter), which the static page can't offer at all.
- **Free-text job-title search**, not just standardized SOC/occupation titles — "credit risk" and
  "data scientist" work here even though they don't match any SOC title string directly.

Run it with:

```bash
source .venv/bin/activate
pip install -r requirements.txt  # first time only
streamlit run app.py
```

Open `http://localhost:8501` once the server starts (`.streamlit/config.toml` runs it headless —
see below for why). First load takes a few seconds while it reads and prepares the full master
CSVs (cached after that — subsequent filter changes are instant). This isn't deployed anywhere;
it's meant to run on your own machine.

**Known macOS crash and why it's disabled by default**: `streamlit run` normally auto-opens your
browser, which forks a subprocess to run `/usr/bin/open`. On some macOS versions this crashes —
macOS reports it as "Python quit unexpectedly" with a SIGSEGV, and the crash log shows `*** 
multi-threaded process forked ***` / `subprocess_fork_exec` — because forking a multi-threaded
process (which Streamlit's server is) races with a fork-handler Apple's Network framework
registers, and that handler isn't safe to run before the subsequent `exec`. `.streamlit/config.toml`
sets `headless = true` to skip the auto-open entirely and sidestep it; open the URL yourself
instead. If you ever pass a config flag that re-enables the browser auto-open, you may hit this
again.

## Status

Exploration and analysis-layer phase complete, now covering full FY2025 + FY2026 through Q3, with
both a notebook-based analysis layer (notebooks 02-05) and a shareable interactive dashboard on
top of it, answering the core recruiting-strategy questions (occupation fit, employer targeting,
industry, geography, timing) generically rather than for one fixed persona.

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

- **Employer consolidation**: canonicalization now builds one shared mapping across LCA and PERM
  together (previously each dataset picked its own display spelling independently, so the same
  company could show up unmerged when compared — e.g. "Apple Inc." vs "APPLE INC."), plus a
  manually-reviewed brand rollup (`src/employer_brand_rollup.py`) for 20 major employers whose
  filings were split across multiple legal subsidiaries — Amazon, Goldman Sachs, Deloitte, PwC,
  Citigroup, Capital One, Wells Fargo, Morgan Stanley, Bank of America, Deutsche Bank, Visa,
  Mastercard, Dell, Samsung, HCL, Capgemini, Wipro, Fidelity Investments, TikTok, CVS Health, and
  Citadel. Amazon alone went from its largest single entity showing ~29,600 filings to ~43,400
  once its subsidiaries were combined.

Open questions/next steps: a better MBA-relevance signal than SOC/title regex if a cleaner
minimum-education proxy is worth integrating, and — deferred by design this round — choosing and
building the actual interactive dashboard technology on top of this analysis layer (since
resolved: see the Dashboard and Local dashboard sections above).
