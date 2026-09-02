# %% [markdown]
# # 01 — Data Loading & Exploratory Analysis
#
# First pass over the DOL disclosure data for FY2026 Q3:
# - `data/raw/LCA_Disclosure_Data_FY2026_Q3.csv` — H-1B (and E-3/H-1B1) Labor Condition Applications
# - `data/raw/PERM_Disclosure_Data_FY2026_Q3.csv` — PERM labor certifications (green card sponsorship)
#
# Goal here is just to understand shape, quality, and headline distributions before we narrow in
# on MBA-relevant roles in notebook 02.

# %%
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

sys.path.insert(0, str(Path.cwd().parent / "src"))
from data_loader import load_lca, load_perm, annual_wage  # noqa: E402

sns.set_theme(style="whitegrid")
plt.rcParams["figure.figsize"] = (10, 5)

PROCESSED_DIR = Path.cwd().parent / "data" / "processed"
FIG_DIR = Path.cwd().parent / "outputs" / "figures"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
FIG_DIR.mkdir(parents=True, exist_ok=True)

# %% [markdown]
# ## Load both files
#
# Both CSVs are pre-allocated to the full fiscal year, so most rows are blank placeholders —
# `load_lca`/`load_perm` (see `src/data_loader.py`) drop those and parse dates for us.

# %%
lca = load_lca()
perm = load_perm()

print(f"LCA (H-1B/E-3/H-1B1) records: {len(lca):,}")
print(f"PERM records: {len(perm):,}")

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
# ## Top sponsoring employers

# %%
lca["EMPLOYER_NAME"].value_counts().head(20)

# %%
perm["EMP_BUSINESS_NAME"].value_counts().head(20)

# %% [markdown]
# ## Save lightweight summaries for reuse
#
# These are small aggregate CSVs (not the raw data) so they're safe to commit and reuse
# directly in the dashboard later.

# %%
lca["SOC_TITLE"].value_counts().rename("filings").to_csv(PROCESSED_DIR / "lca_top_occupations.csv")
perm["PWD_SOC_TITLE"].value_counts().rename("filings").to_csv(PROCESSED_DIR / "perm_top_occupations.csv")
lca["EMPLOYER_NAME"].value_counts().rename("filings").head(200).to_csv(PROCESSED_DIR / "lca_top_employers.csv")
perm["EMP_BUSINESS_NAME"].value_counts().rename("filings").head(200).to_csv(PROCESSED_DIR / "perm_top_employers.csv")

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
