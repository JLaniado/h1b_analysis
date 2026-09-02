"""
Build a single compact JSON data cube for the static client-side dashboard.

Why a custom build step instead of just shipping the notebook CSVs: the
dashboard needs to cross-filter (occupation x employer x state x industry x
wage level) interactively in the browser with no backend, which means the
underlying fact table has to be small enough to embed directly in the page
and fast enough to re-aggregate on every filter change in JS. This produces
a dictionary-encoded fact table (integer indices into lookup arrays instead
of repeated strings) at the grain (occupation, employer, state, sector,
wage level) — bounded to the top occupations and employers with enough
filings to be meaningful, which keeps the file in the low single-digit MB
range while still covering the large majority of MBA-relevant filings.

Run: python src/build_dashboard_data.py
Output: outputs/dashboard_data.json
"""

import json
from pathlib import Path

import pandas as pd

from data_loader import load_lca, load_perm, annual_wage
from mba_occupations import classify_mba_relevance
from employer_canonicalization import add_canonical_employer, build_canonical_map
from employer_brand_rollup import apply_brand_rollup
from naics_sectors import naics_sector
from employer_matching import match_employers

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "outputs" / "dashboard_data.json"

TOP_N_OCCUPATIONS = 150
MIN_EMPLOYER_FILINGS = 3
DECIDED_LCA = {"Certified", "Certified - Withdrawn", "Denied"}
DECIDED_PERM = {"Certified", "Certified - Expired", "Denied"}


def _wage_annualized_perm(df: pd.DataFrame) -> pd.Series:
    multipliers = {"Hour": 2080, "Week": 52, "Bi-Weekly": 26, "Month": 12, "Year": 1}
    mult = df["JOB_OPP_WAGE_PER"].map(multipliers)
    return df["JOB_OPP_WAGE_FROM"] * mult


def _prep_lca(employer_mapping: pd.Series) -> pd.DataFrame:
    lca = load_lca()
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
    lca["STATE"] = lca["WORKSITE_STATE"]
    lca["OCC_TITLE"] = lca["SOC_TITLE"]
    return lca


def _prep_perm(employer_mapping: pd.Series) -> pd.DataFrame:
    perm = load_perm()
    perm["MBA_TIER"] = classify_mba_relevance(perm["PWD_SOC_CODE"], perm["PWD_SOC_TITLE"])
    perm = add_canonical_employer(perm, "EMP_BUSINESS_NAME", "EMPLOYER_CANONICAL", mapping=employer_mapping)
    perm["EMPLOYER_CANONICAL"] = apply_brand_rollup(perm["EMPLOYER_CANONICAL"])
    perm["NAICS_SECTOR"] = naics_sector(perm["EMP_NAICS"])
    perm["ANNUAL_WAGE"] = _wage_annualized_perm(perm)
    perm["ANNUAL_WAGE"] = perm["ANNUAL_WAGE"].where(
        (perm["ANNUAL_WAGE"] > 20_000) & (perm["ANNUAL_WAGE"] < 500_000)
    )
    perm["IS_EXTERNAL_HIRE"] = perm["OTHER_REQ_IS_FW_CURRENTLY_WRK"] == "N"
    perm["STATE"] = perm["PRIMARY_WORKSITE_STATE"]
    perm["OCC_TITLE"] = perm["PWD_SOC_TITLE"]
    return perm


def _build_lookups(df: pd.DataFrame):
    occ_counts = df["OCC_TITLE"].value_counts()
    top_occ = occ_counts.head(TOP_N_OCCUPATIONS).index.tolist()
    occ_tier = df.drop_duplicates("OCC_TITLE").set_index("OCC_TITLE")["MBA_TIER"]

    emp_counts = df["EMPLOYER_CANONICAL"].value_counts()
    top_emp = emp_counts[emp_counts >= MIN_EMPLOYER_FILINGS].index.tolist()

    states = sorted(df["STATE"].dropna().unique().tolist())
    sectors = sorted(df["NAICS_SECTOR"].dropna().unique().tolist())

    return {
        "occupations": top_occ,
        "occupation_tiers": [occ_tier.get(o, "adjacent") for o in top_occ],
        "employers": top_emp,
        "states": states,
        "sectors": sectors,
    }


def _bucket_other(series: pd.Series, allowed: list) -> pd.Series:
    allowed_set = set(allowed)
    return series.where(series.isin(allowed_set), other="Other")


def build_lca_cube(lca: pd.DataFrame, lookups: dict) -> list:
    occ_idx = {name: i for i, name in enumerate(lookups["occupations"])}
    emp_idx = {name: i for i, name in enumerate(lookups["employers"])}
    state_idx = {name: i for i, name in enumerate(lookups["states"])}
    sector_idx = {name: i for i, name in enumerate(lookups["sectors"])}
    wage_levels = ["I", "II", "III", "IV", "Unspecified"]
    wage_idx = {name: i for i, name in enumerate(wage_levels)}

    sub = lca[lca["OCC_TITLE"].isin(occ_idx) & lca["EMPLOYER_CANONICAL"].isin(emp_idx)].copy()
    sub["decided"] = sub["CASE_STATUS"].isin(DECIDED_LCA)
    sub["certified"] = sub["decided"] & (sub["CASE_STATUS"] != "Denied")

    g = sub.groupby(["OCC_TITLE", "EMPLOYER_CANONICAL", "STATE", "NAICS_SECTOR", "WAGE_LEVEL"], observed=True).agg(
        filings=("CASE_NUMBER", "count"),
        new_pos=("IS_NEW_POSITION", "sum"),
        certified=("certified", "sum"),
        decided=("decided", "sum"),
        wage_sum=("ANNUAL_WAGE", "sum"),
        wage_n=("ANNUAL_WAGE", "count"),
    ).reset_index()

    rows = []
    for r in g.itertuples(index=False):
        rows.append([
            occ_idx[r.OCC_TITLE], emp_idx[r.EMPLOYER_CANONICAL], state_idx.get(r.STATE, -1),
            sector_idx.get(r.NAICS_SECTOR, -1), wage_idx.get(r.WAGE_LEVEL, 4),
            int(r.filings), int(r.new_pos), int(r.certified), int(r.decided),
            round(float(r.wage_sum), 0), int(r.wage_n),
        ])
    return rows, wage_levels


def build_perm_cube(perm: pd.DataFrame, lookups: dict) -> list:
    occ_idx = {name: i for i, name in enumerate(lookups["occupations"])}
    emp_idx = {name: i for i, name in enumerate(lookups["employers"])}
    state_idx = {name: i for i, name in enumerate(lookups["states"])}
    sector_idx = {name: i for i, name in enumerate(lookups["sectors"])}

    sub = perm[perm["OCC_TITLE"].isin(occ_idx) & perm["EMPLOYER_CANONICAL"].isin(emp_idx)].copy()
    sub["decided"] = sub["CASE_STATUS"].isin(DECIDED_PERM)
    sub["certified"] = sub["decided"] & (sub["CASE_STATUS"] != "Denied")

    g = sub.groupby(["OCC_TITLE", "EMPLOYER_CANONICAL", "STATE", "NAICS_SECTOR"], observed=True).agg(
        filings=("CASE_NUMBER", "count"),
        external_hire=("IS_EXTERNAL_HIRE", "sum"),
        certified=("certified", "sum"),
        decided=("decided", "sum"),
        wage_sum=("ANNUAL_WAGE", "sum"),
        wage_n=("ANNUAL_WAGE", "count"),
    ).reset_index()

    rows = []
    for r in g.itertuples(index=False):
        rows.append([
            occ_idx[r.OCC_TITLE], emp_idx[r.EMPLOYER_CANONICAL], state_idx.get(r.STATE, -1),
            sector_idx.get(r.NAICS_SECTOR, -1),
            int(r.filings), int(r.external_hire), int(r.certified), int(r.decided),
            round(float(r.wage_sum), 0), int(r.wage_n),
        ])
    return rows


def build_employer_meta(lca_full: pd.DataFrame, perm_full: pd.DataFrame, lca_mba: pd.DataFrame,
                         perm_mba: pd.DataFrame, lca_lookups: dict, perm_lookups: dict) -> dict:
    pipeline = match_employers(lca_mba, perm_mba)
    both = set(pipeline.loc[pipeline["sponsors_both"], "lca_canonical_name"].dropna()) | \
        set(pipeline.loc[pipeline["sponsors_both"], "perm_canonical_name"].dropna())

    lca_flags = lca_full.groupby("EMPLOYER_CANONICAL").agg(
        willful_violator=("WILLFUL_VIOLATOR", lambda s: bool((s == "Y").any())),
        h1b_dependent=("H_1B_DEPENDENT", lambda s: bool((s == "Y").any())),
    )
    perm_size = perm_full.groupby("EMPLOYER_CANONICAL")["EMP_NUM_PAYROLL"].median()

    lca_total = lca_full.groupby("EMPLOYER_CANONICAL").size()
    lca_mba_count = lca_mba.groupby("EMPLOYER_CANONICAL").size()
    perm_total = perm_full.groupby("EMPLOYER_CANONICAL").size()
    perm_mba_count = perm_mba.groupby("EMPLOYER_CANONICAL").size()

    all_employers = sorted(set(lca_lookups["employers"]) | set(perm_lookups["employers"]))
    meta = {}
    for emp in all_employers:
        lca_tot = int(lca_total.get(emp, 0))
        perm_tot = int(perm_total.get(emp, 0))
        meta[emp] = {
            "both_pipelines": emp in both,
            "willful_violator": bool(lca_flags["willful_violator"].get(emp, False)),
            "h1b_dependent": bool(lca_flags["h1b_dependent"].get(emp, False)),
            "median_payroll": (
                None if pd.isna(perm_size.get(emp, float("nan"))) else int(perm_size.get(emp))
            ),
            "lca_mba_share": (
                None if lca_tot == 0 else round(int(lca_mba_count.get(emp, 0)) / lca_tot, 3)
            ),
            "perm_mba_share": (
                None if perm_tot == 0 else round(int(perm_mba_count.get(emp, 0)) / perm_tot, 3)
            ),
        }
    return meta


def main():
    # A cheap names-only pass so both datasets settle on ONE shared canonical
    # spelling per employer — canonicalizing each dataset independently lets
    # the same company end up displayed differently in each (e.g. "Apple
    # Inc." in LCA vs "APPLE INC." in PERM), which then never merges.
    lca_names = load_lca(usecols=["EMPLOYER_NAME"])["EMPLOYER_NAME"]
    perm_names = load_perm(usecols=["EMP_BUSINESS_NAME"])["EMP_BUSINESS_NAME"]
    employer_mapping = build_canonical_map(lca_names, perm_names)

    lca_full = _prep_lca(employer_mapping)
    perm_full = _prep_perm(employer_mapping)
    lca = lca_full[lca_full["MBA_TIER"] != "excluded"].copy()
    perm = perm_full[perm_full["MBA_TIER"] != "excluded"].copy()

    lca_lookups = _build_lookups(lca)
    perm_lookups = _build_lookups(perm)

    lca_rows, wage_levels = build_lca_cube(lca, lca_lookups)
    perm_rows = build_perm_cube(perm, perm_lookups)

    employer_meta = build_employer_meta(lca_full, perm_full, lca, perm, lca_lookups, perm_lookups)

    def yoy(df, tier_col="MBA_TIER"):
        q13 = df[df["FISCAL_QUARTER"] <= 3]
        g = q13.groupby(["FISCAL_YEAR", tier_col]).size().unstack(fill_value=0)
        out = {}
        for tier in ["core", "adjacent"]:
            if tier in g.columns and 2025 in g.index and 2026 in g.index and g.loc[2025, tier] > 0:
                out[tier] = {
                    "fy2025_q1_3": int(g.loc[2025, tier]),
                    "fy2026_q1_3": int(g.loc[2026, tier]),
                    "pct_change": round((g.loc[2026, tier] / g.loc[2025, tier] - 1) * 100, 1),
                }
        return out

    data = {
        "meta": {
            "lca_mba_total": int(len(lca)),
            "perm_mba_total": int(len(perm)),
            "lca_cube_coverage": round(sum(r[5] for r in lca_rows) / len(lca), 3),
            "perm_cube_coverage": round(sum(r[4] for r in perm_rows) / len(perm), 3),
        },
        "yoy": {"lca": yoy(lca), "perm": yoy(perm)},
        "lca": {
            "lookups": lca_lookups,
            "wage_levels": wage_levels,
            "facts": lca_rows,
            "fact_fields": ["occ", "emp", "state", "sector", "wage_level", "filings", "new_pos", "certified", "decided", "wage_sum", "wage_n"],
        },
        "perm": {
            "lookups": perm_lookups,
            "facts": perm_rows,
            "fact_fields": ["occ", "emp", "state", "sector", "filings", "external_hire", "certified", "decided", "wage_sum", "wage_n"],
        },
        "employer_meta": employer_meta,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(data, f, separators=(",", ":"))

    size_mb = OUTPUT_PATH.stat().st_size / 1e6
    print(f"Wrote {OUTPUT_PATH} ({size_mb:.2f} MB)")
    print(f"LCA facts: {len(lca_rows):,} rows, coverage {data['meta']['lca_cube_coverage']:.1%}")
    print(f"PERM facts: {len(perm_rows):,} rows, coverage {data['meta']['perm_cube_coverage']:.1%}")


if __name__ == "__main__":
    main()
