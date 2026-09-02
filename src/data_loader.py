"""
Loaders for the DOL OFLC disclosure data (LCA/H-1B and PERM).

Both source files are large (400MB+ / 230MB+) DOL quarterly disclosure
extracts. Two quirks to know about before touching them:

1. Some cell values contain embedded newlines (e.g. multi-line address or
   comment fields), so pandas' C engine must be read with low_memory=False
   or it can silently get out of sync on chunk boundaries. (The pyarrow
   engine flat out refuses these files with an ArrowInvalid error.)
2. Each quarterly file is pre-allocated for the full fiscal year: only the
   first N rows have data, the rest are fully blank rows. We drop any row
   with a blank CASE_NUMBER to get the "real" record count.
"""

from pathlib import Path

import pandas as pd

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
LCA_PATH = RAW_DIR / "LCA_Disclosure_Data_FY2026_Q3.csv"
PERM_PATH = RAW_DIR / "PERM_Disclosure_Data_FY2026_Q3.csv"

# Columns we actually need for MBA-focused sponsorship analysis. The full
# files have ~98 (LCA) / ~137 (PERM) columns, most of it recruiting-process
# and attorney/POC contact detail that we don't need in memory.
LCA_USECOLS = [
    "CASE_NUMBER",
    "CASE_STATUS",
    "RECEIVED_DATE",
    "DECISION_DATE",
    "VISA_CLASS",
    "JOB_TITLE",
    "SOC_CODE",
    "SOC_TITLE",
    "FULL_TIME_POSITION",
    "TOTAL_WORKER_POSITIONS",
    "NEW_EMPLOYMENT",
    "CONTINUED_EMPLOYMENT",
    "CHANGE_EMPLOYER",
    "EMPLOYER_NAME",
    "EMPLOYER_CITY",
    "EMPLOYER_STATE",
    "EMPLOYER_COUNTRY",
    "NAICS_CODE",
    "WORKSITE_CITY",
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
    "OCCUPATION_TYPE",
    "EMP_BUSINESS_NAME",
    "EMP_CITY",
    "EMP_STATE",
    "EMP_COUNTRY",
    "EMP_NAICS",
    "PWD_SOC_CODE",
    "PWD_SOC_TITLE",
    "JOB_TITLE",
    "JOB_OPP_WAGE_FROM",
    "JOB_OPP_WAGE_TO",
    "JOB_OPP_WAGE_PER",
    "PRIMARY_WORKSITE_CITY",
    "PRIMARY_WORKSITE_STATE",
]

DATE_FORMAT = "%m/%d/%y"


def _read_raw(path: Path, usecols: list[str]) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Place the raw DOL CSV export in data/raw/."
        )
    df = pd.read_csv(path, usecols=usecols, low_memory=False)
    df = df.dropna(subset=["CASE_NUMBER"]).reset_index(drop=True)
    return df


def _parse_dates(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    for col in cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], format=DATE_FORMAT, errors="coerce")
    return df


def load_lca(path: Path = LCA_PATH, usecols: list[str] | None = None) -> pd.DataFrame:
    """Load the H-1B/LCA disclosure file, dropping unpopulated template rows."""
    df = _read_raw(path, usecols or LCA_USECOLS)
    df = _parse_dates(df, ["RECEIVED_DATE", "DECISION_DATE"])
    for col in ["WAGE_RATE_OF_PAY_FROM", "WAGE_RATE_OF_PAY_TO", "PREVAILING_WAGE",
                "TOTAL_WORKER_POSITIONS"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def load_perm(path: Path = PERM_PATH, usecols: list[str] | None = None) -> pd.DataFrame:
    """Load the PERM disclosure file, dropping unpopulated template rows."""
    df = _read_raw(path, usecols or PERM_USECOLS)
    df = _parse_dates(df, ["RECEIVED_DATE", "DECISION_DATE"])
    for col in ["JOB_OPP_WAGE_FROM", "JOB_OPP_WAGE_TO"]:
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
