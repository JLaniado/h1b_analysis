"""
Collapse near-duplicate employer name strings (casing, punctuation, whitespace,
and legal-suffix noise) into a single canonical name per underlying employer.

This fixes the "Hire IT people, Inc" / "Hire IT People, Inc." / "HIRE IT PEOPLE
INC" problem — same employer, fragmented across multiple raw string variants,
which understates their true filing volume and pollutes any employer-level
ranking or mix analysis.

Deliberately NOT attempted here: rolling distinct legal subsidiaries up to a
parent brand (e.g. "Amazon Web Services, Inc." + "Amazon Data Services, Inc."
+ "Amazon.com Services LLC" -> "Amazon"). That's a real fragmentation problem
too, but solving it generically is unsafe — naive prefix/substring matching on
a short brand token produces false merges (e.g. "Apple American Group LLC" is
an Applebee's franchisee, not Apple Inc.; "Meta Soft Inc." is unrelated to Meta
Platforms). Treat that as a separate, manually-curated follow-up scoped to
just the top employers that matter for the dashboard, not applied blindly
across the full ~55K-employer tail.

We also don't use EMPLOYER_FEIN as the grouping key even though a tax ID looks
like the obvious canonical identifier: some FEINs (e.g. state university
systems) are shared across many legally/organizationally distinct worksites
(SUNY Stony Brook, SUNY Buffalo, SUNY Binghamton all filed under one FEIN),
so FEIN-based grouping over-merges exactly the kind of entities students need
to tell apart.
"""

import re

import pandas as pd

# Trailing tokens stripped (repeatedly, from the end) to get a "core" grouping
# key. Order doesn't matter — stripping continues until no more suffix tokens
# remain at the end of the name.
LEGAL_SUFFIX_TOKENS = {
    "INC", "INCORPORATED", "LLC", "LLP", "LP", "LTD", "LIMITED", "CORP",
    "CORPORATION", "CO", "COMPANY", "PLLC", "PC", "PA", "PLC",
}


def clean_name(name: str) -> str:
    """Uppercase, strip punctuation noise, collapse whitespace. Keeps '&' and '-'."""
    if pd.isna(name):
        return name
    s = str(name).upper()
    s = re.sub(r"[.,'\"()]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def core_key(cleaned_name: str) -> str:
    """Strip trailing legal-entity suffix tokens to get a grouping key."""
    if pd.isna(cleaned_name) or cleaned_name == "":
        return cleaned_name
    tokens = cleaned_name.split(" ")
    while len(tokens) > 1 and tokens[-1] in LEGAL_SUFFIX_TOKENS:
        tokens.pop()
    return " ".join(tokens)


def build_canonical_map(names: pd.Series) -> pd.Series:
    """Map each distinct raw name in `names` to a canonical display name.

    Grouping key is the cleaned + suffix-stripped core string. Within each
    group, the canonical display name is the most frequent raw variant
    (ties broken in favor of a variant that isn't ALL CAPS, since that's
    usually a data-entry artifact rather than the employer's real styling).
    """
    raw_counts = names.dropna().str.strip().value_counts()
    df = raw_counts.rename("count").reset_index()
    df.columns = ["raw_name", "count"]
    df["core"] = df["raw_name"].map(clean_name).map(core_key)
    df["is_all_caps"] = df["raw_name"] == df["raw_name"].str.upper()

    df = df.sort_values(["core", "count", "is_all_caps"], ascending=[True, False, True])
    canonical = df.groupby("core", as_index=False).first()[["core", "raw_name"]]
    canonical = canonical.rename(columns={"raw_name": "canonical_name"})

    mapping = df.merge(canonical, on="core")[["raw_name", "canonical_name"]]
    return mapping.set_index("raw_name")["canonical_name"]


def add_canonical_employer(df: pd.DataFrame, raw_col: str, out_col: str) -> pd.DataFrame:
    """Add a canonical employer name column, deduplicating naming noise in raw_col."""
    mapping = build_canonical_map(df[raw_col])
    df[out_col] = df[raw_col].str.strip().map(mapping)
    return df
