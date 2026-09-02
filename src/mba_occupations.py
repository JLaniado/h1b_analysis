"""
Heuristics for flagging occupations relevant to MBA graduates.

Neither the LCA nor PERM disclosure extract includes a "minimum degree
required" field (PERM's disclosure file only exposes OCCUPATION_TYPE:
Professional / Non-professional / College-University Teacher / Schedule A /
None-Professional Athlete — it drops the more detailed FW_INFO_* education
fields present in DOL's full case-level PERM data). So "is this role
reachable by an MBA" is approximated from SOC major group + curated title
matching, not a real degree-requirement flag. Treat the tiers below as a
useful filter for exploration, not ground truth — flag this caveat any time
these tiers drive a headline number.

Tiers:
  - CORE:      SOC major groups 11 (Management) and 13 (Business & Financial
               Operations) — the roles an MBA is the standard/expected path
               into.
  - ADJACENT:  Titles outside those major groups that MBAs commonly land
               (product/BI/PM-flavored tech roles, technical sales, generalist
               marketing/comms) but that also hire non-MBA backgrounds.
  - EXCLUDED:  Everything else, notably pure software engineering, hard
               science, healthcare, and other roles that in practice require
               a technical/PhD-track degree an MBA doesn't substitute for.
"""

import re

import pandas as pd

CORE_SOC_MAJOR_GROUPS = {"11", "13"}

ADJACENT_TITLE_PATTERNS = [
    r"business intelligence analyst",
    r"information technology project manager",
    r"^project management specialist",
    r"operations research analyst",
    r"product manager",
    r"technical program manager",
    r"sales engineer",
    r"market research analyst",
    r"public relations specialist",
    r"technical writer",
]

# Titles that look business-y by keyword but are consistently technical/PhD
# tracks in practice — keep these out of ADJACENT even if a pattern above
# would otherwise catch a substring.
ADJACENT_EXCLUSIONS = [
    r"research scientist",
    r"data scientist",
]

_ADJACENT_RE = re.compile("|".join(ADJACENT_TITLE_PATTERNS), re.IGNORECASE)
_EXCLUSION_RE = re.compile("|".join(ADJACENT_EXCLUSIONS), re.IGNORECASE)


def classify_mba_relevance(soc_code: pd.Series, soc_title: pd.Series) -> pd.Series:
    """Return a Series of {"core", "adjacent", "excluded"} per row.

    soc_code: raw SOC_CODE / PWD_SOC_CODE column (e.g. "11-2021.00")
    soc_title: raw SOC_TITLE / PWD_SOC_TITLE column
    """
    major_group = soc_code.astype(str).str.slice(0, 2)
    title = soc_title.fillna("")

    is_core = major_group.isin(CORE_SOC_MAJOR_GROUPS)
    is_adjacent = title.str.contains(_ADJACENT_RE) & ~title.str.contains(_EXCLUSION_RE)

    result = pd.Series("excluded", index=soc_code.index)
    result[is_adjacent] = "adjacent"
    result[is_core] = "core"
    return result
