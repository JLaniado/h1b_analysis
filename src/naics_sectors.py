"""
NAICS 2-digit sector code -> standard sector name lookup.

Neither LCA (`NAICS_CODE`) nor PERM (`EMP_NAICS`) ships a human-readable
industry name, only the numeric code. This is the standard 2022 NAICS
2-digit sector list (a handful of sectors span two codes, e.g. 31-33
Manufacturing — each of those codes is listed individually here since our
data always carries a specific 2-digit prefix, not a range).
"""

import pandas as pd

NAICS_SECTOR_NAMES = {
    "11": "Agriculture, Forestry, Fishing and Hunting",
    "21": "Mining, Quarrying, and Oil and Gas Extraction",
    "22": "Utilities",
    "23": "Construction",
    "31": "Manufacturing",
    "32": "Manufacturing",
    "33": "Manufacturing",
    "42": "Wholesale Trade",
    "44": "Retail Trade",
    "45": "Retail Trade",
    "48": "Transportation and Warehousing",
    "49": "Transportation and Warehousing",
    "51": "Information",
    "52": "Finance and Insurance",
    "53": "Real Estate and Rental and Leasing",
    "54": "Professional, Scientific, and Technical Services",
    "55": "Management of Companies and Enterprises",
    "56": "Administrative and Support and Waste Management Services",
    "61": "Educational Services",
    "62": "Health Care and Social Assistance",
    "71": "Arts, Entertainment, and Recreation",
    "72": "Accommodation and Food Services",
    "81": "Other Services (except Public Administration)",
    "92": "Public Administration",
}


def naics_sector(naics_code: pd.Series) -> pd.Series:
    """Map a raw NAICS_CODE/EMP_NAICS column to its 2-digit sector name."""
    prefix = naics_code.astype(str).str.strip().str.slice(0, 2)
    return prefix.map(NAICS_SECTOR_NAMES).fillna("Unknown / Unclassified")
