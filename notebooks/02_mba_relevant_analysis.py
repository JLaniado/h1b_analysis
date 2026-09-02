# %% [markdown]
# # 02 — MBA-Relevant Occupation Analysis
#
# Narrowing the full H-1B/PERM dataset down to roles an MBA graduate can realistically target,
# and starting to answer the recruiting-strategy questions: which employers, which functions,
# which locations give an international MBA the best odds of sponsorship.
#
# **Important caveat**: neither disclosure file includes a minimum-degree-required field (PERM's
# public extract only has `OCCUPATION_TYPE`: Professional / Non-professional / College-University
# Teacher — it drops the more detailed education fields DOL collects internally). So "MBA-relevant"
# here is a SOC-code + title heuristic (see `src/mba_occupations.py`), not a hard filter on actual
# degree requirements. Treat tier splits as directional, not exact.

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

# %% [markdown]
# ## How much of the market is actually MBA-relevant?

# %%
lca_tier_counts = lca["MBA_TIER"].value_counts()
perm_tier_counts = perm["MBA_TIER"].value_counts()

fig, axes = plt.subplots(1, 2, figsize=(12, 5))
lca_tier_counts.plot.pie(ax=axes[0], autopct="%1.0f%%", ylabel="", colors=["#C44E52", "#4C72B0", "#DD8452"])
axes[0].set_title("LCA (H-1B) filings by MBA-relevance tier")
perm_tier_counts.plot.pie(ax=axes[1], autopct="%1.0f%%", ylabel="", colors=["#C44E52", "#4C72B0", "#DD8452"])
axes[1].set_title("PERM filings by MBA-relevance tier")
plt.tight_layout()
plt.savefig(FIG_DIR / "02_mba_tier_share.png", dpi=150)
plt.show()

print("LCA:\n", lca_tier_counts, "\n")
print("PERM:\n", perm_tier_counts)

# %%
lca_mba = lca[lca["MBA_TIER"] != "excluded"].copy()
perm_mba = perm[perm["MBA_TIER"] != "excluded"].copy()
print(f"MBA-relevant LCA filings: {len(lca_mba):,} ({len(lca_mba) / len(lca):.1%} of all)")
print(f"MBA-relevant PERM filings: {len(perm_mba):,} ({len(perm_mba) / len(perm):.1%} of all)")

# %% [markdown]
# ## Certification rate: does it differ by tier?
#
# If core/adjacent roles get certified at a similar (or better) rate than the broader market,
# that's reassuring — it means the bottleneck for MBAs isn't the process, it's finding
# employers who file for these roles at all.

# %%
def cert_rate_by_tier(df, decided_statuses, denied_status="Denied"):
    decided = df[df["CASE_STATUS"].isin(decided_statuses)]
    return decided.groupby("MBA_TIER")["CASE_STATUS"].apply(lambda s: (s != denied_status).mean())


lca_cert_by_tier = cert_rate_by_tier(lca, ["Certified", "Certified - Withdrawn", "Denied"])
perm_cert_by_tier = cert_rate_by_tier(perm, ["Certified", "Certified - Expired", "Denied"])

fig, axes = plt.subplots(1, 2, figsize=(12, 5))
lca_cert_by_tier.reindex(["core", "adjacent", "excluded"]).plot.bar(ax=axes[0], color="#4C72B0")
axes[0].set_title("LCA certification rate by tier")
axes[0].set_ylim(0, 1)
perm_cert_by_tier.reindex(["core", "adjacent", "excluded"]).plot.bar(ax=axes[1], color="#DD8452")
axes[1].set_title("PERM certification rate by tier")
axes[1].set_ylim(0, 1)
plt.tight_layout()
plt.savefig(FIG_DIR / "02_cert_rate_by_tier.png", dpi=150)
plt.show()

# %% [markdown]
# ## Which functions within "core" and "adjacent" see the most volume?

# %%
fig, ax = plt.subplots(figsize=(10, 8))
lca_mba["SOC_TITLE"].value_counts().head(25).sort_values().plot.barh(ax=ax, color="#4C72B0")
ax.set_title("MBA-relevant LCA filings by occupation")
plt.tight_layout()
plt.savefig(FIG_DIR / "02_mba_occupations_lca.png", dpi=150)
plt.show()

# %%
fig, ax = plt.subplots(figsize=(10, 8))
perm_mba["PWD_SOC_TITLE"].value_counts().head(25).sort_values().plot.barh(ax=ax, color="#DD8452")
ax.set_title("MBA-relevant PERM filings by occupation")
plt.tight_layout()
plt.savefig(FIG_DIR / "02_mba_occupations_perm.png", dpi=150)
plt.show()

# %% [markdown]
# ## Top employers sponsoring MBA-relevant roles
#
# This is the recruiting-strategy payload: which companies are actually filing for business/
# management-track roles (as opposed to being a huge H-1B filer purely on the engineering side).

# %%
top_employers_lca_mba = lca_mba["EMPLOYER_CANONICAL"].value_counts().head(30)
top_employers_lca_mba

# %%
top_employers_perm_mba = perm_mba["EMPLOYER_CANONICAL"].value_counts().head(30)
top_employers_perm_mba

# %% [markdown]
# ### "MBA-focused" employers: high share of MBA-relevant filings, not just high volume
#
# A employer with 5 total filings, all core-MBA roles, is a better lead than one with 500
# filings where only 2% are business-track. Rank by volume *and* mix.

# %%
def employer_mba_mix(df, employer_col, min_filings=10):
    g = df.groupby(employer_col)["MBA_TIER"].agg(
        total="count",
        mba_relevant=lambda s: (s != "excluded").sum(),
    )
    g["mba_share"] = g["mba_relevant"] / g["total"]
    return g[g["total"] >= min_filings].sort_values(["mba_share", "total"], ascending=False)


lca_employer_mix = employer_mba_mix(lca, "EMPLOYER_CANONICAL")
lca_employer_mix.head(25)

# %%
perm_employer_mix = employer_mba_mix(perm, "EMPLOYER_CANONICAL")
perm_employer_mix.head(25)

# %% [markdown]
# ## Wage premium for MBA-relevant roles

# %%
lca["ANNUAL_WAGE_FROM"] = annual_wage(lca["WAGE_RATE_OF_PAY_FROM"], lca["WAGE_UNIT_OF_PAY"])
lca_wage = lca[(lca["ANNUAL_WAGE_FROM"] > 20_000) & (lca["ANNUAL_WAGE_FROM"] < 500_000)]

fig, ax = plt.subplots()
sns.boxplot(data=lca_wage, x="MBA_TIER", y="ANNUAL_WAGE_FROM", order=["core", "adjacent", "excluded"], ax=ax)
ax.set_title("Annualized offered wage by MBA-relevance tier (LCA)")
plt.tight_layout()
plt.savefig(FIG_DIR / "02_wage_by_tier.png", dpi=150)
plt.show()

lca_wage.groupby("MBA_TIER")["ANNUAL_WAGE_FROM"].describe()

# %% [markdown]
# ## Geographic concentration of MBA-relevant sponsorship

# %%
fig, ax = plt.subplots(figsize=(10, 7))
lca_mba["WORKSITE_STATE"].value_counts().head(20).sort_values().plot.barh(ax=ax, color="#4C72B0")
ax.set_title("MBA-relevant LCA filings by worksite state")
plt.tight_layout()
plt.savefig(FIG_DIR / "02_mba_states.png", dpi=150)
plt.show()

# %% [markdown]
# ## Save dashboard-ready aggregates

# %%
lca_employer_mix.reset_index().to_csv(PROCESSED_DIR / "lca_employer_mba_mix.csv", index=False)
perm_employer_mix.reset_index().to_csv(PROCESSED_DIR / "perm_employer_mba_mix.csv", index=False)
lca_mba["SOC_TITLE"].value_counts().rename("filings").to_csv(PROCESSED_DIR / "lca_mba_occupations.csv")
perm_mba["PWD_SOC_TITLE"].value_counts().rename("filings").to_csv(PROCESSED_DIR / "perm_mba_occupations.csv")
lca_mba["WORKSITE_STATE"].value_counts().rename("filings").to_csv(PROCESSED_DIR / "lca_mba_states.csv")

print("Saved MBA-focused aggregates to", PROCESSED_DIR)

# %% [markdown]
# ## Notes for next session
#
# - Need a better MBA-relevance signal than SOC/title regex — worth checking whether the DOL
#   PERM *case-level* disclosure (not this summary extract) exposes minimum education fields we
#   could join in, or whether O*NET's "typical education" lookup by SOC code is a cleaner proxy.
# - Employer names are canonicalized for casing/punctuation/legal-suffix noise (see
#   `src/employer_canonicalization.py`), but distinct legal subsidiaries of the same brand (e.g.
#   Amazon Web Services, Inc. vs Amazon.com Services LLC) are intentionally left separate — that
#   needs a manually-curated brand alias list, scoped to just the top employers on the dashboard
#   leaderboard, rather than automated fuzzy matching (which produces false merges, e.g. "Apple
#   American Group LLC" is an Applebee's franchisee, not Apple Inc.).
# - Should link LCA employer names to PERM employer names (fuzzy match — names aren't identical
#   across the two systems) to see which employers do *both* H-1B and green card sponsorship for
#   business roles, since that end-to-end path is what students actually care about.
# - Consider NAICS industry rollups on top of the occupation tiers (e.g. consulting/finance/tech
#   sector cuts) for the dashboard's employer targeting view.
