"""
Match employers across the LCA (H-1B) and PERM (green card) datasets so we
can see who does *both* — the actual visa-to-green-card pathway a student
cares about, not just "who sponsors H-1B."

Same fuzziness caveat as `employer_canonicalization.py`: there's no reliable
shared key across the two systems (no common FEIN join — see that module's
docstring on why FEIN over-merges some employers already; LCA/PERM FEINs
also aren't guaranteed to be filed identically for the same company). This
reuses the same clean/suffix-strip `core_key` as the join key, which is a
reasonable heuristic for large, distinctly-named employers but can miss or
misjoin small/generic-named ones — treat "appears in both" as directional,
not a certified fact about any single employer.
"""

import pandas as pd

from employer_canonicalization import clean_name, core_key


def _core_key_map(names: pd.Series) -> pd.Series:
    return names.map(lambda n: core_key(clean_name(n)) if pd.notna(n) else n)


def match_employers(lca: pd.DataFrame, perm: pd.DataFrame,
                     lca_name_col: str = "EMPLOYER_CANONICAL",
                     perm_name_col: str = "EMPLOYER_CANONICAL") -> pd.DataFrame:
    """Return one row per employer core-key present in either dataset, with
    filing counts from each side and a `sponsors_both` flag."""
    lca_key = _core_key_map(lca[lca_name_col])
    perm_key = _core_key_map(perm[perm_name_col])

    lca_counts = lca.groupby(lca_key).agg(
        lca_canonical_name=(lca_name_col, lambda s: s.value_counts().idxmax()),
        lca_filings=(lca_name_col, "count"),
    )
    perm_counts = perm.groupby(perm_key).agg(
        perm_canonical_name=(perm_name_col, lambda s: s.value_counts().idxmax()),
        perm_filings=(perm_name_col, "count"),
    )

    merged = lca_counts.join(perm_counts, how="outer")
    merged["lca_filings"] = merged["lca_filings"].fillna(0).astype(int)
    merged["perm_filings"] = merged["perm_filings"].fillna(0).astype(int)
    merged["sponsors_both"] = (merged["lca_filings"] > 0) & (merged["perm_filings"] > 0)
    merged.index.name = "employer_core_key"
    return merged.reset_index()
