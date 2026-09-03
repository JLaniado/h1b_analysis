"""
Loaders for the consolidated DOL OFLC disclosure data (LCA/H-1B and PERM).

Reads from data/interim/lca_master.csv.gz and data/interim/perm_master.csv.gz
(gzip-compressed — pandas reads these natively, no decompression step
needed), which are built by `src/consolidate_raw.py` from the mixed raw
sources in data/raw/ (some fiscal years arrive as one cumulative CSV, others
as four separate quarterly XLSX exports — see that module's docstring). Run
`python src/consolidate_raw.py` after adding new raw exports to regenerate
the master files before using these loaders.

If the master files aren't present locally (a fresh clone, a cloud deploy),
they're fetched automatically from this repo's GitHub Release — see
`src/fetch_master_data.py`.

The master files already have blank template rows dropped and dates
normalized to ISO (YYYY-MM-DD), so loading here is a plain, fast read.
"""

from pathlib import Path

import pandas as pd

from fetch_master_data import ensure_master_data

INTERIM_DIR = Path(__file__).resolve().parent.parent / "data" / "interim"
LCA_PATH = INTERIM_DIR / "lca_master.csv.gz"
PERM_PATH = INTERIM_DIR / "perm_master.csv.gz"

# Columns we actually need for MBA-focused sponsorship analysis. The full
# files have ~98 (LCA) / ~137 (PERM) columns, most of it recruiting-process
# and attorney/POC contact detail that we don't need in memory.
LCA_USECOLS = [
    "CASE_NUMBER",
    "CASE_STATUS",
    "RECEIVED_DATE",
    "DECISION_DATE",
    "FISCAL_YEAR",
    "FISCAL_QUARTER",
    "VISA_CLASS",
    "JOB_TITLE",
    "SOC_CODE",
    "SOC_TITLE",
    "FULL_TIME_POSITION",
    "TOTAL_WORKER_POSITIONS",
    "NEW_EMPLOYMENT",
    "CONTINUED_EMPLOYMENT",
    "CHANGE_EMPLOYER",
    "NEW_CONCURRENT_EMPLOYMENT",
    "EMPLOYER_NAME",
    "EMPLOYER_CITY",
    "EMPLOYER_STATE",
    "EMPLOYER_COUNTRY",
    "NAICS_CODE",
    "WORKSITE_CITY",
    "WORKSITE_COUNTY",
    "WORKSITE_STATE",
    "WAGE_RATE_OF_PAY_FROM",
    "WAGE_RATE_OF_PAY_TO",
    "WAGE_UNIT_OF_PAY",
    "PREVAILING_WAGE",
    "PW_UNIT_OF_PAY",
    "PW_WAGE_LEVEL",
    "H_1B_DEPENDENT",
    "WILLFUL_VIOLATOR",
]

PERM_USECOLS = [
    "CASE_NUMBER",
    "CASE_STATUS",
    "RECEIVED_DATE",
    "DECISION_DATE",
    "FISCAL_YEAR",
    "FISCAL_QUARTER",
    "OCCUPATION_TYPE",
    "EMP_BUSINESS_NAME",
    "EMP_CITY",
    "EMP_STATE",
    "EMP_COUNTRY",
    "EMP_NAICS",
    "EMP_NUM_PAYROLL",
    "EMP_YEAR_COMMENCED",
    "PWD_SOC_CODE",
    "PWD_SOC_TITLE",
    "JOB_TITLE",
    "JOB_OPP_WAGE_FROM",
    "JOB_OPP_WAGE_TO",
    "JOB_OPP_WAGE_PER",
    "PRIMARY_WORKSITE_CITY",
    "PRIMARY_WORKSITE_COUNTY",
    "PRIMARY_WORKSITE_STATE",
    "OTHER_REQ_IS_FW_CURRENTLY_WRK",
]


def _read_master(path: Path, usecols: list[str]) -> pd.DataFrame:
    if not path.exists():
        ensure_master_data()
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found and couldn't be auto-downloaded. "
            f"Run `python src/consolidate_raw.py` to build it from data/raw/."
        )
    return pd.read_csv(path, usecols=usecols, low_memory=False, compression="gzip")


def _parse_dates(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    for col in cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], format="%Y-%m-%d", errors="coerce")
    return df


def load_lca(path: Path = LCA_PATH, usecols: list[str] | None = None) -> pd.DataFrame:
    """Load the consolidated H-1B/LCA master file."""
    df = _read_master(path, usecols or LCA_USECOLS)
    df = _parse_dates(df, ["RECEIVED_DATE", "DECISION_DATE"])
    for col in ["WAGE_RATE_OF_PAY_FROM", "WAGE_RATE_OF_PAY_TO", "PREVAILING_WAGE",
                "TOTAL_WORKER_POSITIONS"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def load_perm(path: Path = PERM_PATH, usecols: list[str] | None = None) -> pd.DataFrame:
    """Load the consolidated PERM master file."""
    df = _read_master(path, usecols or PERM_USECOLS)
    df = _parse_dates(df, ["RECEIVED_DATE", "DECISION_DATE"])
    for col in ["JOB_OPP_WAGE_FROM", "JOB_OPP_WAGE_TO", "EMP_NUM_PAYROLL", "EMP_YEAR_COMMENCED"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def annual_wage(amount: pd.Series, unit: pd.Series) -> pd.Series:
    """Normalize a wage column to an annualized figure given its pay-unit column."""
    multipliers = {
        "Hour": 2080,
        "Week": 52,
        "Bi-Weekly": 26,
        "Month": 12,
        "Year": 1,
    }
    mult = unit.map(multipliers)
    return amount * mult
