# %% [markdown]
# # 01 — Data Loading & Exploratory Analysis
#
# First pass over the DOL disclosure data, now spanning full FY2025 plus FY2026 through Q3:
# - LCA (H-1B/E-3/H-1B1) Labor Condition Applications
# - PERM labor certifications (green card sponsorship)
#
# Raw sources arrive inconsistently (one cumulative CSV for FY2026, four separate quarterly
# XLSX exports for FY2025) — `src/consolidate_raw.py` normalizes all of that into
# `data/interim/{lca,perm}_master.csv` once, tagged with a derived `FISCAL_YEAR`/`FISCAL_QUARTER`.
# Run `python src/consolidate_raw.py` after dropping new raw exports into `data/raw/` to rebuild
# those before running this notebook.
#
# Goal here is just to understand shape, quality, and headline distributions (now with a
# year-over-year lens) before we narrow in on MBA-relevant roles in notebook 02.
#
# **Note on a fixed data bug**: one source file (`LCA_Disclosure_Data_FY2025_Q2.xlsx`, ~13% of
# LCA data) exported nearly every text cell wrapped as a literal Excel "keep as text" string
# (`="541511"` instead of `541511`), which silently corrupted `SOC_CODE` for that whole quarter
# and broke MBA-tier classification for those rows. `consolidate_raw.py` now strips this on
# ingestion — if you're comparing against an earlier run of this notebook, the FY2025 numbers
# (and anything YoY) will have shifted slightly as a result.

# %%
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

sys.path.insert(0, str(Path.cwd().parent / "src"))
from data_loader import load_lca, load_perm, annual_wage  # noqa: E402
from employer_canonicalization import add_canonical_employer  # noqa: E402

sns.set_theme(style="whitegrid")
plt.rcParams["figure.figsize"] = (10, 5)

PROCESSED_DIR = Path.cwd().parent / "data" / "processed"
FIG_DIR = Path.cwd().parent / "outputs" / "figures"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
FIG_DIR.mkdir(parents=True, exist_ok=True)

# %% [markdown]
# ## Load both consolidated master files

# %%
lca = load_lca()
perm = load_perm()

print(f"LCA (H-1B/E-3/H-1B1) records: {len(lca):,}")
print(f"PERM records: {len(perm):,}")

# %% [markdown]
# ### Coverage by fiscal year/quarter
#
# Fiscal year and quarter are derived from `DECISION_DATE` (falling back to `RECEIVED_DATE` for
# undecided cases) using the federal fiscal calendar, not trusted from source filenames — DOL's
# own file naming isn't a reliable signal (a "FY2026 Q3" file can be a Q1-Q3 cumulative export).

# %%
lca.groupby(["FISCAL_YEAR", "FISCAL_QUARTER"]).size().unstack(fill_value=0)

# %%
perm.groupby(["FISCAL_YEAR", "FISCAL_QUARTER"]).size().unstack(fill_value=0)

# %% [markdown]
# ## Employer name canonicalization
#
# Raw employer names are fragmented by casing/punctuation/legal-suffix noise — e.g. "Hire IT
# People, Inc" / "Hire IT People, Inc." / "HIRE IT PEOPLE INC" all show up as different strings
# for the same employer, which understates their true filing volume in any employer-level
# ranking. `add_canonical_employer` (see `src/employer_canonicalization.py`) collapses these
# safely — it does *not* attempt to merge distinct legal subsidiaries under one brand (e.g.
# "Amazon Web Services, Inc." vs "Amazon.com Services LLC" stay separate), since that's a
# harder problem where naive matching produces false merges (a real risk here: "Apple American
# Group LLC" is an Applebee's franchisee, not Apple Inc.).

# %%
lca_raw_employers = lca["EMPLOYER_NAME"].nunique()
lca = add_canonical_employer(lca, "EMPLOYER_NAME", "EMPLOYER_CANONICAL")
perm_raw_employers = perm["EMP_BUSINESS_NAME"].nunique()
perm = add_canonical_employer(perm, "EMP_BUSINESS_NAME", "EMPLOYER_CANONICAL")

print(f"LCA employers: {lca_raw_employers:,} raw names -> {lca['EMPLOYER_CANONICAL'].nunique():,} canonical")
print(f"PERM employers: {perm_raw_employers:,} raw names -> {perm['EMPLOYER_CANONICAL'].nunique():,} canonical")

# %%
lca.info()

# %%
perm.info()

# %% [markdown]
# ## Data quality: missingness

# %%
missing_lca = (lca.isna().mean() * 100).round(1).sort_values(ascending=False)
missing_lca[missing_lca > 0]

# %%
missing_perm = (perm.isna().mean() * 100).round(1).sort_values(ascending=False)
missing_perm[missing_perm > 0]

# %% [markdown]
# ## Case status: how often do filings actually get certified?
#
# This is the headline number international students care about — of the cases DOL has
# decided, what fraction were certified vs denied/withdrawn?

# %%
fig, axes = plt.subplots(1, 2, figsize=(14, 5))

lca["CASE_STATUS"].value_counts().plot.bar(ax=axes[0], color="#4C72B0")
axes[0].set_title("LCA (H-1B) case status")
axes[0].set_ylabel("Filings")

perm["CASE_STATUS"].value_counts(dropna=False).plot.bar(ax=axes[1], color="#DD8452")
axes[1].set_title("PERM case status")
axes[1].set_ylabel("Filings")

plt.tight_layout()
plt.savefig(FIG_DIR / "01_case_status.png", dpi=150)
plt.show()

# %%
lca_decided = lca[lca["CASE_STATUS"].isin(["Certified", "Certified - Withdrawn", "Denied"])]
lca_cert_rate = (lca_decided["CASE_STATUS"] != "Denied").mean()
print(f"LCA certification rate (of decided cases): {lca_cert_rate:.1%}")

perm_decided = perm[perm["CASE_STATUS"].isin(["Certified", "Certified - Expired", "Denied"])]
perm_cert_rate = (perm_decided["CASE_STATUS"] != "Denied").mean()
print(f"PERM certification rate (of decided cases): {perm_cert_rate:.1%}")

# %% [markdown]
# LCA (H-1B) approval rates are famously high — the real bottleneck for H-1B is the annual
# lottery/cap, which never shows up in this data at all (only *filed* LCAs, and most LCAs are
# filed only after an employer already won a cap slot or the role is cap-exempt). PERM denial
# rates, by contrast, are a more direct signal of employer/role risk since there's no lottery.

# %% [markdown]
# ## Visa class breakdown (LCA)

# %%
lca["VISA_CLASS"].value_counts()

# %% [markdown]
# ## Top occupations by filing volume

# %%
top_soc_lca = lca["SOC_TITLE"].value_counts().head(20)
top_soc_lca

# %%
fig, ax = plt.subplots(figsize=(10, 7))
top_soc_lca.sort_values().plot.barh(ax=ax, color="#4C72B0")
ax.set_title("Top 20 SOC occupations by LCA (H-1B) filing volume")
ax.set_xlabel("Filings")
plt.tight_layout()
plt.savefig(FIG_DIR / "01_top_soc_lca.png", dpi=150)
plt.show()

# %%
top_soc_perm = perm["PWD_SOC_TITLE"].value_counts().head(20)
top_soc_perm

# %% [markdown]
# ## Filing volume over time

# %%
monthly_lca = lca.set_index("RECEIVED_DATE").resample("ME").size()
monthly_perm = perm.set_index("RECEIVED_DATE").resample("ME").size()

fig, ax = plt.subplots()
monthly_lca.plot(ax=ax, label="LCA (H-1B)", marker="o")
monthly_perm.plot(ax=ax, label="PERM", marker="o")
ax.set_title("Monthly filings received")
ax.set_ylabel("Filings")
ax.legend()
plt.tight_layout()
plt.savefig(FIG_DIR / "01_monthly_filings.png", dpi=150)
plt.show()

# %% [markdown]
# ### Year-over-year: is sponsorship growing or shrinking?
#
# FY2026 is partial (through Q3) — compare it to the *same* Q1-Q3 window in FY2025, not full-year
# FY2025, or a shrinking year will look like growth just from missing Q4.

# %%
def yoy_by_quarter(df, label):
    g = df[df["FISCAL_QUARTER"] <= 3].groupby(["FISCAL_YEAR", "FISCAL_QUARTER"]).size().unstack(0, fill_value=0)
    print(f"\n{label} — filings by quarter, FY2025 vs FY2026 (Q1-Q3 only):")
    print(g)
    if 2025 in g.columns and 2026 in g.columns:
        pct_change = (g[2026].sum() / g[2025].sum() - 1) * 100
        print(f"FY2026 Q1-Q3 vs FY2025 Q1-Q3: {pct_change:+.1f}%")
    return g


lca_yoy = yoy_by_quarter(lca, "LCA (H-1B)")
perm_yoy = yoy_by_quarter(perm, "PERM")

fig, axes = plt.subplots(1, 2, figsize=(12, 5))
lca_yoy.plot.bar(ax=axes[0])
axes[0].set_title("LCA filings by quarter: FY2025 vs FY2026")
axes[0].set_ylabel("Filings")
perm_yoy.plot.bar(ax=axes[1])
axes[1].set_title("PERM filings by quarter: FY2025 vs FY2026")
axes[1].set_ylabel("Filings")
plt.tight_layout()
plt.savefig(FIG_DIR / "01_yoy_quarterly.png", dpi=150)
plt.show()

# %% [markdown]
# ### Seasonality: does filing volume track the H-1B cap cycle?
#
# The H-1B annual lottery registration window falls in March, with selected registrants filing
# petitions (and the LCA that must precede them) mostly April-June. If that cycle drives LCA
# volume, we'd expect a visible spring bump. PERM has no lottery, so no reason to expect the same
# pattern — a useful contrast.

# %%
lca_by_month = lca["RECEIVED_DATE"].dt.month.value_counts().sort_index()
perm_by_month = perm["RECEIVED_DATE"].dt.month.value_counts().sort_index()
month_labels = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

fig, axes = plt.subplots(1, 2, figsize=(14, 5))
lca_by_month.reindex(range(1, 13), fill_value=0).plot.bar(ax=axes[0], color="#4C72B0")
axes[0].set_xticklabels(month_labels, rotation=45)
axes[0].set_title("LCA filings received by calendar month (all years combined)")
perm_by_month.reindex(range(1, 13), fill_value=0).plot.bar(ax=axes[1], color="#DD8452")
axes[1].set_xticklabels(month_labels, rotation=45)
axes[1].set_title("PERM filings received by calendar month (all years combined)")
plt.tight_layout()
plt.savefig(FIG_DIR / "01_seasonality.png", dpi=150)
plt.show()

# %% [markdown]
# ## Wages
#
# Normalize everything to an annualized figure so hourly/weekly/monthly roles are comparable.

# %%
lca["ANNUAL_WAGE_FROM"] = annual_wage(lca["WAGE_RATE_OF_PAY_FROM"], lca["WAGE_UNIT_OF_PAY"])
lca_wage = lca[(lca["ANNUAL_WAGE_FROM"] > 20_000) & (lca["ANNUAL_WAGE_FROM"] < 500_000)]

fig, ax = plt.subplots()
sns.histplot(lca_wage["ANNUAL_WAGE_FROM"], bins=60, ax=ax, color="#4C72B0")
ax.set_title("LCA annualized offered wage distribution")
ax.set_xlabel("Annual wage (USD)")
plt.tight_layout()
plt.savefig(FIG_DIR / "01_wage_distribution.png", dpi=150)
plt.show()

print(lca_wage["ANNUAL_WAGE_FROM"].describe())

# %% [markdown]
# ## Geography: where are sponsoring employers located?

# %%
top_states_lca = lca["WORKSITE_STATE"].value_counts().head(15)
top_states_perm = perm["PRIMARY_WORKSITE_STATE"].value_counts().head(15)

fig, axes = plt.subplots(1, 2, figsize=(14, 5))
top_states_lca.sort_values().plot.barh(ax=axes[0], color="#4C72B0")
axes[0].set_title("Top worksite states — LCA (H-1B)")
top_states_perm.sort_values().plot.barh(ax=axes[1], color="#DD8452")
axes[1].set_title("Top worksite states — PERM")
plt.tight_layout()
plt.savefig(FIG_DIR / "01_top_states.png", dpi=150)
plt.show()

# %% [markdown]
# ## Top sponsoring employers (canonical names)

# %%
lca["EMPLOYER_CANONICAL"].value_counts().head(20)

# %%
perm["EMPLOYER_CANONICAL"].value_counts().head(20)

# %% [markdown]
# ## Save lightweight summaries for reuse
#
# These are small aggregate CSVs (not the raw data) so they're safe to commit and reuse
# directly in the dashboard later.

# %%
lca["SOC_TITLE"].value_counts().rename("filings").to_csv(PROCESSED_DIR / "lca_top_occupations.csv")
perm["PWD_SOC_TITLE"].value_counts().rename("filings").to_csv(PROCESSED_DIR / "perm_top_occupations.csv")
lca["EMPLOYER_CANONICAL"].value_counts().rename("filings").head(200).to_csv(PROCESSED_DIR / "lca_top_employers.csv")
perm["EMPLOYER_CANONICAL"].value_counts().rename("filings").head(200).to_csv(PROCESSED_DIR / "perm_top_employers.csv")

print("Saved summary CSVs to", PROCESSED_DIR)

# %% [markdown]
# ## Open questions heading into notebook 02
#
# 1. Neither file exposes a "minimum degree required" field — how do we approximate
#    "MBA-reachable" roles from SOC code / job title alone? (see `src/mba_occupations.py`)
# 2. Which employers sponsor MBA-relevant roles specifically, not just tech roles in general?
# 3. Do certification/denial rates differ meaningfully by occupation tier or employer?
# 4. Where geographically do MBA-relevant sponsorships concentrate vs. the overall market?
# 5. What's the wage premium (or discount) for MBA-relevant roles vs. the broader population?
# 6. Employer names are now canonicalized for casing/punctuation/legal-suffix noise — but
#    distinct legal subsidiaries of the same brand (Amazon Web Services vs Amazon.com Services
#    LLC) still show up separately. Worth a manually-curated brand rollup for just the top ~50-100
#    employers that matter most for the dashboard leaderboard.
