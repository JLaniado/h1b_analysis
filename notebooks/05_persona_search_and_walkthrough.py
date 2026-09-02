# %% [markdown]
# # 05 — Persona Search & Walkthrough
#
# Proves the tooling generalizes: given a student's background (as free-text keywords, not a
# fixed category), produce a concrete shortlist of occupations, employers, and locations. Runs
# the example persona from the original ask — 4 years experience across data science, business
# analytics, fintech, credit risk, and risk management — plus two differing backgrounds
# (marketing/brand, supply chain/operations) to confirm this isn't persona-specific plumbing.

# %%
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path.cwd().parent / "src"))
from data_loader import load_lca, load_perm, annual_wage  # noqa: E402
from mba_occupations import classify_mba_relevance  # noqa: E402
from employer_canonicalization import add_canonical_employer  # noqa: E402
from naics_sectors import naics_sector  # noqa: E402
from occupation_search import search_occupations, summarize_occupation_search, PERSONA_KEYWORDS  # noqa: E402

PROCESSED_DIR = Path.cwd().parent / "data" / "processed"

# %%
lca = load_lca()
perm = load_perm()

lca["MBA_TIER"] = classify_mba_relevance(lca["SOC_CODE"], lca["SOC_TITLE"])
perm["MBA_TIER"] = classify_mba_relevance(perm["PWD_SOC_CODE"], perm["PWD_SOC_TITLE"])

lca = add_canonical_employer(lca, "EMPLOYER_NAME", "EMPLOYER_CANONICAL")
perm = add_canonical_employer(perm, "EMP_BUSINESS_NAME", "EMPLOYER_CANONICAL")

lca["NAICS_SECTOR"] = naics_sector(lca["NAICS_CODE"])
lca["ANNUAL_WAGE_FROM"] = annual_wage(lca["WAGE_RATE_OF_PAY_FROM"], lca["WAGE_UNIT_OF_PAY"])
lca["IS_NEW_POSITION"] = lca["NEW_EMPLOYMENT"].fillna(0) > 0

# %% [markdown]
# ## Reusable persona report
#
# Given a keyword list, this answers: how big is this market, is it growing, which employers,
# which locations, what wage/seniority level should this student expect.

# %%
def persona_report(keywords: list[str], label: str):
    print(f"\n{'='*70}\nPERSONA: {label}\nKeywords: {keywords}\n{'='*70}")

    mask = search_occupations(lca, keywords, ["SOC_TITLE", "JOB_TITLE"])
    matched = lca[mask]
    summary = summarize_occupation_search(lca, mask)
    print(f"\nMatched LCA filings: {summary['matched_filings']:,} ({summary['share_of_total']:.2%} of all LCA)")
    print("MBA-tier breakdown:", summary["tier_breakdown"])

    if len(matched) == 0:
        print("No matches — widen keywords.")
        return None

    yoy = matched[matched["FISCAL_QUARTER"] <= 3].groupby("FISCAL_YEAR").size()
    print("\nFilings by fiscal year (Q1-Q3 only, for fair YoY):")
    print(yoy)

    print("\nTop occupations matched:")
    print(matched["SOC_TITLE"].value_counts().head(10))

    print("\nTop industries:")
    print(matched["NAICS_SECTOR"].value_counts().head(8))

    print("\nTop employers (min 3 matched filings):")
    emp = matched.groupby("EMPLOYER_CANONICAL").size()
    print(emp[emp >= 3].sort_values(ascending=False).head(15))

    print("\nTop states:")
    print(matched["WORKSITE_STATE"].value_counts().head(10))

    wage = matched[(matched["ANNUAL_WAGE_FROM"] > 20_000) & (matched["ANNUAL_WAGE_FROM"] < 500_000)]
    print(f"\nAnnual wage: median ${wage['ANNUAL_WAGE_FROM'].median():,.0f}, "
          f"25th-75th pct ${wage['ANNUAL_WAGE_FROM'].quantile(0.25):,.0f}-"
          f"${wage['ANNUAL_WAGE_FROM'].quantile(0.75):,.0f}")

    print("\nWage-level mix (I=entry ... IV=expert) — a proxy for seniority typically expected:")
    print(matched["PW_WAGE_LEVEL"].value_counts(normalize=True).sort_index())

    new_share = matched["IS_NEW_POSITION"].mean()
    print(f"\nShare of matched filings that are genuinely new positions: {new_share:.1%}")

    return matched


# %% [markdown]
# ## Persona 1: the original example — data science, business analytics, fintech, credit risk,
# risk management, 4 years experience

# %%
persona1_keywords = PERSONA_KEYWORDS["finance_risk_fintech"]
persona1_matched = persona_report(persona1_keywords, "Finance / Risk / Fintech background")

# %% [markdown]
# **Reading this persona's results**: a strong wage-level skew toward II/III (not pure entry
# level) is expected for a candidate with 4 years' experience — Level I roles here would actually
# be a poor fit (they're calibrated for a fresh grad with far less experience), so this student
# should specifically look for Level II-III filings, not just any match. Cross-reference the top
# employers list here against notebook 04's employer scorecard (certification rate, mix, new vs.
# renewal share) before treating any single employer as a strong lead.

# %% [markdown]
# ## Persona 2: marketing / brand management background

# %%
persona2_matched = persona_report(PERSONA_KEYWORDS["marketing_brand"], "Marketing / Brand background")

# %% [markdown]
# ## Persona 3: supply chain / operations background

# %%
persona3_matched = persona_report(PERSONA_KEYWORDS["supply_chain_ops"], "Supply Chain / Operations background")

# %% [markdown]
# ## Does the tooling generalize? Sanity check
#
# Each persona should surface a *different* dominant industry/occupation mix — if they all
# converged on the same top employers/industries, that would suggest the keyword search isn't
# actually discriminating between backgrounds.

# %%
for matched, label in [(persona1_matched, "Finance/Risk"), (persona2_matched, "Marketing"), (persona3_matched, "Supply Chain")]:
    if matched is not None:
        top_sector = matched["NAICS_SECTOR"].value_counts().idxmax()
        top_occupation = matched["SOC_TITLE"].value_counts().idxmax()
        print(f"{label}: top sector = {top_sector!r}, top occupation = {top_occupation!r}")

# %% [markdown]
# ## Save the finance/risk persona's shortlist as a concrete dashboard-ready example

# %%
if persona1_matched is not None:
    shortlist = (
        persona1_matched[persona1_matched["PW_WAGE_LEVEL"].isin(["II", "III"])]
        .groupby("EMPLOYER_CANONICAL")
        .agg(matched_filings=("CASE_NUMBER", "count"), median_wage=("ANNUAL_WAGE_FROM", "median"))
        .query("matched_filings >= 2")
        .sort_values("matched_filings", ascending=False)
    )
    shortlist.reset_index().to_csv(PROCESSED_DIR / "persona_finance_risk_shortlist.csv", index=False)
    print(f"Saved {len(shortlist)} employers to persona_finance_risk_shortlist.csv")

# %% [markdown]
# ## Notes
#
# - `PERSONA_KEYWORDS` in `src/occupation_search.py` is a starting point, not an exhaustive
#   taxonomy — the actual dashboard should let a student type free-text keywords directly rather
#   than being limited to these three examples.
# - This notebook only searches LCA; the same `search_occupations` function works identically
#   against the PERM dataframe (with `PWD_SOC_TITLE`/`JOB_TITLE` as the title columns) for
#   green-card-stage targeting.
