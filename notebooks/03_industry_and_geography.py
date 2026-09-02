# %% [markdown]
# # 03 — Industry & Geography
#
# Two more targeting dimensions beyond occupation and employer: **which industries** sponsor
# MBA-relevant roles, and **where geographically**. Both cross-cut with wage, so a student can
# answer "if I want a Financial Analyst role in Finance & Insurance, where does that pay best and
# who's hiring the most?" in one pass.

# %%
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

sys.path.insert(0, str(Path.cwd().parent / "src"))
from data_loader import load_lca, load_perm, annual_wage  # noqa: E402
from mba_occupations import classify_mba_relevance  # noqa: E402
from employer_canonicalization import add_canonical_employer  # noqa: E402
from naics_sectors import naics_sector  # noqa: E402

sns.set_theme(style="whitegrid")
plt.rcParams["figure.figsize"] = (10, 5)

PROCESSED_DIR = Path.cwd().parent / "data" / "processed"
FIG_DIR = Path.cwd().parent / "outputs" / "figures"

# %%
lca = load_lca()
perm = load_perm()

lca["MBA_TIER"] = classify_mba_relevance(lca["SOC_CODE"], lca["SOC_TITLE"])
perm["MBA_TIER"] = classify_mba_relevance(perm["PWD_SOC_CODE"], perm["PWD_SOC_TITLE"])

lca = add_canonical_employer(lca, "EMPLOYER_NAME", "EMPLOYER_CANONICAL")
perm = add_canonical_employer(perm, "EMP_BUSINESS_NAME", "EMPLOYER_CANONICAL")

lca["NAICS_SECTOR"] = naics_sector(lca["NAICS_CODE"])
perm["NAICS_SECTOR"] = naics_sector(perm["EMP_NAICS"])

lca["ANNUAL_WAGE_FROM"] = annual_wage(lca["WAGE_RATE_OF_PAY_FROM"], lca["WAGE_UNIT_OF_PAY"])

lca_mba = lca[lca["MBA_TIER"] != "excluded"].copy()
perm_mba = perm[perm["MBA_TIER"] != "excluded"].copy()

# %% [markdown]
# ## Which industries sponsor the most MBA-relevant roles?

# %%
lca_sector_counts = lca_mba["NAICS_SECTOR"].value_counts()
perm_sector_counts = perm_mba["NAICS_SECTOR"].value_counts()

fig, axes = plt.subplots(1, 2, figsize=(14, 7))
lca_sector_counts.head(15).sort_values().plot.barh(ax=axes[0], color="#4C72B0")
axes[0].set_title("MBA-relevant LCA filings by industry sector")
perm_sector_counts.head(15).sort_values().plot.barh(ax=axes[1], color="#DD8452")
axes[1].set_title("MBA-relevant PERM filings by industry sector")
plt.tight_layout()
plt.savefig(FIG_DIR / "03_mba_by_sector.png", dpi=150)
plt.show()

# %% [markdown]
# ## Certification rate and wage by sector

# %%
def sector_scorecard(df, decided_statuses, denied_status, wage_col=None):
    decided = df[df["CASE_STATUS"].isin(decided_statuses)]
    cert_rate = decided.groupby("NAICS_SECTOR")["CASE_STATUS"].apply(lambda s: (s != denied_status).mean())
    volume = df.groupby("NAICS_SECTOR").size()
    out = pd.DataFrame({"filings": volume, "cert_rate": cert_rate})
    if wage_col:
        wage = df[(df[wage_col] > 20_000) & (df[wage_col] < 500_000)].groupby("NAICS_SECTOR")[wage_col].median()
        out["median_annual_wage"] = wage
    return out.sort_values("filings", ascending=False)


lca_sector_scorecard = sector_scorecard(
    lca_mba, ["Certified", "Certified - Withdrawn", "Denied"], "Denied", "ANNUAL_WAGE_FROM"
)
lca_sector_scorecard.head(15)

# %%
perm_sector_scorecard = sector_scorecard(
    perm_mba, ["Certified", "Certified - Expired", "Denied"], "Denied"
)
perm_sector_scorecard.head(15)

# %% [markdown]
# ## Occupation x industry cross-tab
#
# Coarse (2-digit) NAICS sectors miss the finance-vs-fintech-vs-consulting distinction that
# matters to a finance/risk background — cross-tabbing occupation against sector at least shows
# *which* sectors hire *which* MBA-relevant functions, so a student can spot e.g. "Financial Risk
# Specialists cluster in Finance & Insurance, but also show up meaningfully in Professional
# Services (consulting)."

# %%
cross_tab_lca = pd.crosstab(lca_mba["SOC_TITLE"], lca_mba["NAICS_SECTOR"])
top_occupations = lca_mba["SOC_TITLE"].value_counts().head(15).index
cross_tab_lca.loc[top_occupations].loc[:, cross_tab_lca.loc[top_occupations].sum().sort_values(ascending=False).head(8).index]

# %% [markdown]
# ## Geography: where should a student look, for a given industry/occupation?
#
# State-level concentration and median wage, for MBA-relevant roles overall — filter this same
# query down to a specific occupation/industry when using it interactively.

# %%
def geo_scorecard(df, state_col, wage_col=None):
    volume = df.groupby(state_col).size().rename("filings")
    out = volume.to_frame()
    if wage_col:
        wage = df[(df[wage_col] > 20_000) & (df[wage_col] < 500_000)].groupby(state_col)[wage_col].median()
        out["median_annual_wage"] = wage
    return out.sort_values("filings", ascending=False)


lca_geo = geo_scorecard(lca_mba, "WORKSITE_STATE", "ANNUAL_WAGE_FROM")
lca_geo.head(15)

# %%
perm_geo = geo_scorecard(perm_mba, "PRIMARY_WORKSITE_STATE")
perm_geo.head(15)

# %%
fig, ax = plt.subplots(figsize=(9, 4))
top10 = lca_geo.head(10)
ax2 = ax.twinx()
top10["filings"].plot.bar(ax=ax, color="#4C72B0", position=1, width=0.4)
top10["median_annual_wage"].plot(ax=ax2, color="#DD8452", marker="o", linestyle="none")
ax.set_ylabel("MBA-relevant filings")
ax2.set_ylabel("Median annual wage (USD)")
ax.set_title("Top 10 states: MBA-relevant LCA volume vs. median wage")
plt.tight_layout()
plt.savefig(FIG_DIR / "03_geo_volume_vs_wage.png", dpi=150)
plt.show()

# %% [markdown]
# County-level detail is available (`WORKSITE_COUNTY` / `PRIMARY_WORKSITE_COUNTY`) for drilling
# into specific metro areas once a state is picked — not expanded here to keep this notebook
# readable, but ready for the interactive dashboard to use directly.

# %% [markdown]
# ## Wage benchmarking: occupation x wage level x location
#
# `PW_WAGE_LEVEL` (I-IV) is DOL's own classification of how much experience/responsibility a role
# calls for — the closest available proxy to "years of experience needed" since no applicant-level
# field exists. Level I/II roles are the entry-friendlier target for someone a few years out of
# undergrad plus an MBA; Level III/IV skew toward more senior hires.

# %%
wage_level_by_occupation = (
    lca_mba.groupby(["SOC_TITLE", "PW_WAGE_LEVEL"]).size().unstack(fill_value=0)
)
wage_level_by_occupation["total"] = wage_level_by_occupation.sum(axis=1)
wage_level_by_occupation.sort_values("total", ascending=False).drop(columns="total").head(20)

# %%
fig, ax = plt.subplots(figsize=(10, 7))
top15 = wage_level_by_occupation.sort_values("total", ascending=False).head(15).drop(columns="total")
top15_share = top15.div(top15.sum(axis=1), axis=0)
top15_share[["I", "II", "III", "IV"]].plot.barh(stacked=True, ax=ax, colormap="viridis")
ax.set_title("Wage-level mix by occupation (I=entry ... IV=expert)")
ax.set_xlabel("Share of filings")
plt.tight_layout()
plt.savefig(FIG_DIR / "03_wage_level_mix.png", dpi=150)
plt.show()

# %% [markdown]
# ## Save dashboard-ready aggregates

# %%
lca_sector_scorecard.reset_index().to_csv(PROCESSED_DIR / "lca_sector_scorecard.csv", index=False)
perm_sector_scorecard.reset_index().to_csv(PROCESSED_DIR / "perm_sector_scorecard.csv", index=False)
lca_geo.reset_index().to_csv(PROCESSED_DIR / "lca_state_scorecard.csv", index=False)
perm_geo.reset_index().to_csv(PROCESSED_DIR / "perm_state_scorecard.csv", index=False)
wage_level_by_occupation.reset_index().to_csv(PROCESSED_DIR / "lca_wage_level_by_occupation.csv", index=False)

print("Saved industry/geography aggregates to", PROCESSED_DIR)

# %% [markdown]
# ## Notes
#
# - NAICS sector is only 2-digit here (`src/naics_sectors.py`) — coarse enough that "fintech"
#   gets split across Finance & Insurance (52), Information (51, if the company is
#   software-classified), and Professional Services (54, if consulting-adjacent). Employer-name
#   keyword search (notebook 05) is the practical workaround for finer industry targeting.
# - Wage-level mix is a solid proxy for seniority *expected by the role*, but doesn't tell us
#   what a specific *employer's* bar is for a given level — two employers both filing "Level II
#   Financial Analyst" may have very different actual hiring bars.
