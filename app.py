"""
Sponsorship Explorer — local, full-data version.

The published static dashboard (docs/index.html) only covers 18% of LCA
records and 9.7% of PERM records — it's a pre-aggregated sample (top ~150
occupations, employers with 3+ filings, core/adjacent MBA tiers only)
because a static page has to embed all its data client-side and stay small
enough to load in a browser.

This app has no such constraint: it loads the full consolidated master data
directly and filters/aggregates live with pandas, so it covers every
record, every employer, every tier (including "excluded" — e.g. Data
Scientists, Software Developers), and searches actual free-text job titles
in addition to standardized SOC/occupation titles.

Run: streamlit run app.py
"""

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from data_loader import load_lca, load_perm, annual_wage  # noqa: E402
from mba_occupations import classify_mba_relevance  # noqa: E402
from employer_canonicalization import add_canonical_employer, build_canonical_map  # noqa: E402
from employer_brand_rollup import apply_brand_rollup  # noqa: E402
from naics_sectors import naics_sector  # noqa: E402

st.set_page_config(page_title="Sponsorship Explorer (local, full data)", layout="wide")

DECIDED_LCA = {"Certified", "Certified - Withdrawn", "Denied"}
DECIDED_PERM = {"Certified", "Certified - Expired", "Denied"}


@st.cache_data(show_spinner="Loading and preparing full LCA + PERM data (first run only)...")
def load_data():
    lca = load_lca()
    perm = load_perm()

    # Build ONE shared canonical mapping across both datasets so the same
    # employer settles on one display spelling in both (canonicalizing each
    # dataset independently can pick a different most-common raw variant in
    # each, e.g. "Apple Inc." in LCA vs "APPLE INC." in PERM, which then
    # never merges).
    employer_mapping = build_canonical_map(lca["EMPLOYER_NAME"], perm["EMP_BUSINESS_NAME"])

    lca["MBA_TIER"] = classify_mba_relevance(lca["SOC_CODE"], lca["SOC_TITLE"])
    lca = add_canonical_employer(lca, "EMPLOYER_NAME", "EMPLOYER_CANONICAL", mapping=employer_mapping)
    lca["EMPLOYER_CANONICAL"] = apply_brand_rollup(lca["EMPLOYER_CANONICAL"])
    lca["NAICS_SECTOR"] = naics_sector(lca["NAICS_CODE"])
    lca["ANNUAL_WAGE"] = annual_wage(lca["WAGE_RATE_OF_PAY_FROM"], lca["WAGE_UNIT_OF_PAY"])
    lca["ANNUAL_WAGE"] = lca["ANNUAL_WAGE"].where(
        (lca["ANNUAL_WAGE"] > 20_000) & (lca["ANNUAL_WAGE"] < 500_000)
    )
    lca["IS_NEW_POSITION"] = lca["NEW_EMPLOYMENT"].fillna(0) > 0
    lca["WAGE_LEVEL"] = lca["PW_WAGE_LEVEL"].fillna("Unspecified")
    lca["DECIDED"] = lca["CASE_STATUS"].isin(DECIDED_LCA)
    lca["CERTIFIED"] = lca["DECIDED"] & (lca["CASE_STATUS"] != "Denied")

    perm["MBA_TIER"] = classify_mba_relevance(perm["PWD_SOC_CODE"], perm["PWD_SOC_TITLE"])
    perm = add_canonical_employer(perm, "EMP_BUSINESS_NAME", "EMPLOYER_CANONICAL", mapping=employer_mapping)
    perm["EMPLOYER_CANONICAL"] = apply_brand_rollup(perm["EMPLOYER_CANONICAL"])
    perm["NAICS_SECTOR"] = naics_sector(perm["EMP_NAICS"])
    perm_mult = {"Hour": 2080, "Week": 52, "Bi-Weekly": 26, "Month": 12, "Year": 1}
    perm["ANNUAL_WAGE"] = perm["JOB_OPP_WAGE_FROM"] * perm["JOB_OPP_WAGE_PER"].map(perm_mult)
    perm["ANNUAL_WAGE"] = perm["ANNUAL_WAGE"].where(
        (perm["ANNUAL_WAGE"] > 20_000) & (perm["ANNUAL_WAGE"] < 500_000)
    )
    perm["IS_EXTERNAL_HIRE"] = perm["OTHER_REQ_IS_FW_CURRENTLY_WRK"] == "N"
    perm["DECIDED"] = perm["CASE_STATUS"].isin(DECIDED_PERM)
    perm["CERTIFIED"] = perm["DECIDED"] & (perm["CASE_STATUS"] != "Denied")

    return lca, perm


def yoy_table(df, tier_col="MBA_TIER"):
    q13 = df[df["FISCAL_QUARTER"] <= 3]
    g = q13.groupby(["FISCAL_YEAR", tier_col]).size().unstack(fill_value=0)
    rows = []
    for tier in ["core", "adjacent", "excluded"]:
        if tier in g.columns and 2025 in g.index and 2026 in g.index and g.loc[2025, tier] > 0:
            pct = (g.loc[2026, tier] / g.loc[2025, tier] - 1) * 100
            rows.append({"Tier": tier, "FY25 Q1-3": int(g.loc[2025, tier]),
                         "FY26 Q1-3": int(g.loc[2026, tier]), "Change": f"{pct:+.1f}%"})
    return pd.DataFrame(rows)


lca, perm = load_data()

st.title("Sponsorship Explorer — local, full data")
st.caption(
    "Every record, every tier, every employer — no sampling. "
    f"LCA: {len(lca):,} total records. PERM: {len(perm):,} total records. "
    "Compare to the published static dashboard, which covers 18.0% of LCA and 9.7% of PERM."
)

with st.sidebar:
    st.header("Filters")
    dataset = st.radio("Dataset", ["H-1B (LCA)", "Green card (PERM)"], horizontal=True)
    df = lca if dataset == "H-1B (LCA)" else perm
    title_cols = ["SOC_TITLE", "JOB_TITLE"] if dataset == "H-1B (LCA)" else ["PWD_SOC_TITLE", "JOB_TITLE"]

    keyword = st.text_input(
        "Keyword (matches standardized occupation title AND free-text job title)",
        placeholder="e.g. credit risk, data scientist, product manager…",
    )
    st.caption("Unlike the static dashboard, this searches actual job titles too — "
               "so \"credit risk\" and \"data scientist\" work here.")

    tiers = st.multiselect(
        "MBA-relevance tier", ["core", "adjacent", "excluded"],
        default=["core", "adjacent"],
        help="'excluded' covers technical/other titles outside the MBA heuristic (e.g. Data "
             "Scientists, Software Developers) — include it to search your own background "
             "regardless of the taxonomy.",
    )

    states_available = sorted(df["WORKSITE_STATE" if dataset == "H-1B (LCA)" else "PRIMARY_WORKSITE_STATE"].dropna().unique())
    states_sel = st.multiselect("Worksite state", states_available)

    sectors_available = sorted(df["NAICS_SECTOR"].dropna().unique())
    sectors_sel = st.multiselect("Industry sector", sectors_available)

    if dataset == "H-1B (LCA)":
        wage_levels_sel = st.multiselect("Wage level (I=entry … IV=expert)", ["I", "II", "III", "IV", "Unspecified"])
    else:
        wage_levels_sel = []

    min_employer_filings = st.slider("Min. filings to show an employer in the leaderboard", 1, 50, 3)

mask = df["MBA_TIER"].isin(tiers)
if keyword:
    kw_mask = pd.Series(False, index=df.index)
    for col in title_cols:
        kw_mask = kw_mask | df[col].fillna("").str.contains(keyword, case=False, regex=False)
    mask &= kw_mask
state_col = "WORKSITE_STATE" if dataset == "H-1B (LCA)" else "PRIMARY_WORKSITE_STATE"
if states_sel:
    mask &= df[state_col].isin(states_sel)
if sectors_sel:
    mask &= df["NAICS_SECTOR"].isin(sectors_sel)
if wage_levels_sel:
    mask &= df["WAGE_LEVEL"].isin(wage_levels_sel)

filtered = df[mask]

# ---- KPIs ----
c1, c2, c3, c4 = st.columns(4)
c1.metric("Matched filings", f"{len(filtered):,}")
decided = filtered["DECIDED"].sum()
cert_rate = filtered["CERTIFIED"].sum() / decided if decided else None
c2.metric("Certification rate", f"{cert_rate:.1%}" if cert_rate is not None else "—",
          help=f"of {decided:,} decided cases")
wage_valid = filtered["ANNUAL_WAGE"].dropna()
c3.metric("Avg. annual wage", f"${wage_valid.mean():,.0f}" if len(wage_valid) else "—",
          help=f"from {len(wage_valid):,} filings with wage data")
if dataset == "H-1B (LCA)":
    extra_share = filtered["IS_NEW_POSITION"].mean() if len(filtered) else None
    c4.metric("Genuinely new positions", f"{extra_share:.1%}" if extra_share is not None else "—",
              help="vs. renewals/transfers")
else:
    extra_share = filtered["IS_EXTERNAL_HIRE"].mean() if len(filtered) else None
    c4.metric("External-hire share", f"{extra_share:.1%}" if extra_share is not None else "—",
              help="not already employed there")

st.divider()

# ---- YoY (fixed, not filtered) ----
st.subheader("Is sponsorship growing or shrinking?")
st.caption("Q1–Q3 of each fiscal year, all tiers — not affected by the filters above.")
yc1, yc2 = st.columns(2)
yc1.write("**LCA (H-1B)**")
yc1.dataframe(yoy_table(lca), hide_index=True, use_container_width=True)
yc2.write("**PERM**")
yc2.dataframe(yoy_table(perm), hide_index=True, use_container_width=True)

st.divider()

# ---- Charts ----
occ_col = "SOC_TITLE" if dataset == "H-1B (LCA)" else "PWD_SOC_TITLE"
col_a, col_b = st.columns(2)
with col_a:
    st.subheader("Top occupations")
    top_occ = filtered[occ_col].value_counts().head(15).sort_values()
    if len(top_occ):
        fig = px.bar(top_occ, orientation="h", labels={"value": "Filings", "index": ""})
        fig.update_layout(showlegend=False, height=420)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No matches — widen your filters.")

with col_b:
    st.subheader("Top industries")
    top_sector = filtered["NAICS_SECTOR"].value_counts().head(12).sort_values()
    if len(top_sector):
        fig = px.bar(top_sector, orientation="h", labels={"value": "Filings", "index": ""})
        fig.update_layout(showlegend=False, height=420)
        st.plotly_chart(fig, use_container_width=True)

col_c, col_d = st.columns(2)
with col_c:
    st.subheader("Top states")
    top_state = filtered[state_col].value_counts().head(12).sort_values()
    if len(top_state):
        fig = px.bar(top_state, orientation="h", labels={"value": "Filings", "index": ""})
        fig.update_layout(showlegend=False, height=380)
        st.plotly_chart(fig, use_container_width=True)

with col_d:
    if dataset == "H-1B (LCA)":
        st.subheader("Wage-level mix")
        wl = filtered["WAGE_LEVEL"].value_counts().reindex(["I", "II", "III", "IV", "Unspecified"], fill_value=0)
        fig = px.bar(wl, labels={"value": "Filings", "index": ""})
        fig.update_layout(showlegend=False, height=380)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.subheader("Existing employee vs. external hire")
        share = filtered["IS_EXTERNAL_HIRE"].value_counts().rename({True: "External hire", False: "Already employed there"})
        fig = px.pie(values=share.values, names=share.index)
        fig.update_layout(height=380)
        st.plotly_chart(fig, use_container_width=True)

st.divider()

# ---- Employer leaderboard ----
st.subheader("Employer leaderboard")
st.caption("Ranked by matched filings. Mix = that employer's overall share of filings (any tier) "
           "that are MBA-relevant. Click a column header to sort.")

if dataset == "H-1B (LCA)":
    emp_all_totals = df.groupby("EMPLOYER_CANONICAL").size()
    emp_mba_totals = df[df["MBA_TIER"] != "excluded"].groupby("EMPLOYER_CANONICAL").size()
    g = filtered.groupby("EMPLOYER_CANONICAL").agg(
        Filings=("CASE_NUMBER", "count"),
        Certified=("CERTIFIED", "sum"),
        Decided=("DECIDED", "sum"),
        **{"New position share": ("IS_NEW_POSITION", "mean")},
        **{"Avg wage": ("ANNUAL_WAGE", "mean")},
        **{"Willful violator": ("WILLFUL_VIOLATOR", lambda s: (s == "Y").any())},
        **{"H-1B dependent": ("H_1B_DEPENDENT", lambda s: (s == "Y").any())},
    )
else:
    emp_all_totals = df.groupby("EMPLOYER_CANONICAL").size()
    emp_mba_totals = df[df["MBA_TIER"] != "excluded"].groupby("EMPLOYER_CANONICAL").size()
    g = filtered.groupby("EMPLOYER_CANONICAL").agg(
        Filings=("CASE_NUMBER", "count"),
        Certified=("CERTIFIED", "sum"),
        Decided=("DECIDED", "sum"),
        **{"External hire share": ("IS_EXTERNAL_HIRE", "mean")},
        **{"Avg wage": ("ANNUAL_WAGE", "mean")},
    )

g = g[g["Filings"] >= min_employer_filings]
g["Cert rate"] = g["Certified"] / g["Decided"].replace(0, pd.NA)
g["MBA mix"] = (emp_mba_totals / emp_all_totals).reindex(g.index)
g = g.sort_values("Filings", ascending=False).drop(columns=["Certified", "Decided"])

display_cols = ["Filings", "MBA mix", "Cert rate"]
display_cols += ["New position share"] if "New position share" in g.columns else ["External hire share"]
display_cols += ["Avg wage"]
if "Willful violator" in g.columns:
    display_cols += ["Willful violator", "H-1B dependent"]

st.dataframe(
    g[display_cols].head(300),
    use_container_width=True,
    height=500,
    column_config={
        "MBA mix": st.column_config.ProgressColumn(min_value=0, max_value=1, format="%.0f%%"),
        "Cert rate": st.column_config.ProgressColumn(min_value=0, max_value=1, format="%.0f%%"),
        "New position share": st.column_config.ProgressColumn(min_value=0, max_value=1, format="%.0f%%"),
        "External hire share": st.column_config.ProgressColumn(min_value=0, max_value=1, format="%.0f%%"),
        "Avg wage": st.column_config.NumberColumn(format="$%d"),
    },
)

st.divider()
with st.expander("Reading this responsibly"):
    st.markdown("""
- **PERM ≠ "will sponsor an outside hire."** Most PERM filings are green-card conversions for
  someone *already* employed there.
- **"New position" (H-1B) filters out renewals/transfers.**
- **Wage level is a role proxy, not an employer's actual bar.**
- **MBA-relevance tiers are a heuristic** (SOC code + title matching) — include "excluded" above
  and search your own keywords if your background is non-obvious (e.g. data science, engineering).
- **Employer names are canonicalized** for casing/punctuation, but distinct legal subsidiaries of
  the same brand (e.g. separate Amazon entities) are not merged.
- Wage figures are means (not medians) of annualized pay.
""")
