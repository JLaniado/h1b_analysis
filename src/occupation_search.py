"""
Keyword-based occupation search — a flexible complement to the fixed
core/adjacent/excluded tiers in `mba_occupations.py`.

The tier system is a coarse, defensible default for "how much of the market
is MBA-relevant overall," but it's a blunt instrument for one specific
student asking "what should *I* target given *my* background." A candidate
with a data science / credit risk / fintech background, for example, might
reasonably target "Data Scientists" or "Financial Risk Specialists" even
though our tiers classify Data Scientists as excluded (SOC/title heuristics
can't tell a business-facing data scientist from a pure ML-research one).

This module lets a student (or the dashboard) search SOC_TITLE/JOB_TITLE by
keyword directly, and ships a few example persona -> keyword-set mappings as
a starting point, not an exhaustive taxonomy.
"""

import pandas as pd

# Example persona keyword sets — a starting point for the dashboard's
# "pick a background" shortcut, not a closed list. Free-text search via
# `search_occupations` covers anything not listed here.
PERSONA_KEYWORDS = {
    "finance_risk_fintech": [
        "credit risk", "risk management", "risk analyst", "financial risk",
        "financial analyst", "financial and investment analyst", "data scientist",
        "business intelligence", "quantitative analyst", "management analyst",
    ],
    "marketing_brand": [
        "marketing manager", "market research", "brand", "marketing specialist",
        "public relations", "product marketing",
    ],
    "supply_chain_ops": [
        "supply chain", "logistician", "logistics analyst", "operations manager",
        "operations research analyst", "purchasing manager", "industrial production manager",
    ],
    "product_tech_adjacent": [
        "product manager", "technical program manager", "information technology project manager",
        "business intelligence analyst", "project management specialist",
    ],
}


def search_occupations(df: pd.DataFrame, keywords: list[str], title_cols: list[str]) -> pd.Series:
    """Boolean mask: rows whose title column(s) contain any of `keywords` (case-insensitive).

    df: LCA or PERM dataframe.
    keywords: list of substrings to match, e.g. ["credit risk", "financial analyst"].
    title_cols: which column(s) to search, e.g. ["SOC_TITLE"] or ["SOC_TITLE", "JOB_TITLE"].
    """
    pattern = "|".join(k.replace(" ", r"\s+") for k in keywords)
    mask = pd.Series(False, index=df.index)
    for col in title_cols:
        if col in df.columns:
            mask = mask | df[col].fillna("").str.contains(pattern, case=False, regex=True)
    return mask


def summarize_occupation_search(df: pd.DataFrame, mask: pd.Series, tier_col: str = "MBA_TIER") -> dict:
    """Quick headline stats for a keyword-search result set, for display/sanity-check."""
    matched = df[mask]
    out = {
        "matched_filings": len(matched),
        "share_of_total": len(matched) / len(df) if len(df) else 0.0,
    }
    if tier_col in df.columns:
        out["tier_breakdown"] = matched[tier_col].value_counts().to_dict()
    return out
