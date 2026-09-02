"""
Manually-curated rollup of distinct legal subsidiaries to one recognizable
parent-brand label — the follow-up `employer_canonicalization.py` flags as
deliberately out of scope for itself, because a generic/automated version of
this (fuzzy matching on a brand token) produces real false merges.

Every group below was built by hand: pulling the ~400 highest-volume
canonical employer names across LCA+PERM combined, grep-ing for candidate
brand families, and checking each specific variant before including it.
Confirmed exclusions during that review (i.e. don't add these even though
they look similar) — kept here so nobody "fixes" this by adding them back:

  - "Apple American Group LLC"      -> an Applebee's franchisee, not Apple Inc.
  - "The Citadel"                   -> the military college, not Citadel (hedge fund)
  - "Citadel Drilling (USA) Ltd."   -> an oil/gas drilling company, unrelated
  - "First National Bank of America"-> a distinct, unrelated bank from Bank of America
  - "DELL LANDSCAPING, INC." / "Dell Painting Corp." -> unrelated small businesses
  - "BCVS" / "CVSLOGIC.COM, INC."   -> ambiguous, not confidently CVS Health
  - Generic "DB ..." names (e.g. "DB Franchising USA, LLC") -> ambiguous;
    only DB entries with clear Deutsche Bank naming/context are included

This is scoped to the top employers that actually matter for the dashboard's
leaderboard, not applied blindly across the full ~55K-employer tail. Match on
`core_key(clean_name(...))` (from `employer_canonicalization`), not on exact
display spelling, so it's resilient to whichever raw variant ends up as the
canonical display name.
"""

import pandas as pd

from employer_canonicalization import clean_name, core_key

# brand display name -> example raw variants known to be that brand.
BRAND_GROUPS: dict[str, list[str]] = {
    "Amazon": [
        "Amazon.com Services LLC",
        "Amazon Web Services, Inc.",
        "Amazon Development Center U.S., Inc.",
        "Amazon Data Services, Inc",
        "Amazon Advertising LLC",
        "Amazon Retail LLC",
        "Amazon Payments, Inc.",
        "Amazon Studios, LLC",
        "Amazon Capital Services, Inc.",
        "Amazon Media Venture LLC",
    ],
    "Goldman Sachs": [
        "Goldman Sachs & Co. LLC",
        "Goldman Sachs Services LLC",
        "Goldman Sachs Bank USA",
        "Goldman Sachs Wealth Services, L.P.",
        "The Ayco Company, L.P., a Goldman Sachs Company",
        "The Goldman Sachs Trust Company, NA",
        "The Goldman Sachs Trust Company",
    ],
    "Deloitte": [
        "Deloitte Consulting LLP",
        "Deloitte & Touche LLP",
        "Deloitte Tax LLP",
        "Deloitte Services LP",
        "Deloitte Touche Tohmatsu Services, LLC",
        "Deloitte Transactions and Business Analytics LLP",
        "Deloitte LLP",
        "Deloitte Financial Advisory Services LLP",
    ],
    "PwC": [
        "PricewaterhouseCoopers Advisory Services LLC",
        "PricewaterhouseCoopers LLP",
        "PricewaterhouseCoopers IT Services US LLC",
        "PricewaterhouseCoopers Corporate Finance LLC",
    ],
    "Citigroup": [
        "Citibank, N.A.",
        "Citibank, N.A. Puerto Rico",
        "Citigroup Global Markets Inc.",
        "Citigroup Technology, Inc.",
        "Citigroup Energy Inc.",
        "Citigroup Washington, Inc.",
    ],
    "Capital One": [
        "Capital One Services, LLC",
        "Capital One, National Association",
    ],
    "Wells Fargo": [
        "Wells Fargo Bank, N.A.",
        "Wells Fargo Securities, LLC",
        "Wells Fargo Clearing Services, LLC",
    ],
    "Morgan Stanley": [
        "Morgan Stanley Services Group Inc.",
        "Morgan Stanley & Co., LLC",
        "Morgan Stanley Smith Barney LLC",
        "Morgan Stanley Investment Management Inc.",
        "Morgan Stanley Fund Services Inc.",
        "Morgan Stanley Bank N.A.",
        "Morgan Stanley Private Bank NA",
        "Morgan Stanley Capital Group Inc.",
    ],
    "Bank of America": [
        "Bank of America N.A.",
        "Bank of America Corporation",
        "BofA Securities, Inc.",
    ],
    "Deutsche Bank": [
        "DB Global Technology, Inc.",
        "DB USA Core Corporation",
        "Deutsche Bank Securities, Inc.",
        "Deutsche Bank New York Branch",
        "Deutsche Bank Trust Company Americas",
        "Deutsche Bank National Trust Company",
    ],
    "Visa": [
        "Visa Technology & Operations LLC",
        "Visa U.S.A. Inc.",
    ],
    "Mastercard": [
        "Mastercard Technologies, LLC",
        "Mastercard International Incorporated",
        "Mastercard Mobile Transactions Solutions, Inc.",
    ],
    "Dell": [
        "Dell USA L.P.",
        "Dell Products L.P.",
        "Dell Product L.P.",
        "Dell Marketing L.P.",
        "Dell Financial Services L.L.C.",
        "Dell Puerto Rico Corporation",
    ],
    "Samsung": [
        "Samsung Electronics America, Inc.",
        "Samsung Austin Semiconductor, L.L.C.",
        "Samsung Semiconductor, Inc.",
        "Samsung Research America, Inc.",
        "Samsung SDI America, Inc.",
        "Samsung HME America, Inc.",
        "Samsung Electronics Home Appliances America, LLC",
    ],
    "HCL": [
        "HCL America Inc",
        "HCL Global Systems Inc",
        "HCL America Solutions Inc",
    ],
    "Capgemini": [
        "Capgemini America Inc",
        "Capgemini Government Solutions LLC",
    ],
    "Wipro": [
        "Wipro Limited",
        "Wipro VLSI Design Services, LLC",
        "Wipro NextGen Enterprise Inc.",
        "Wipro Telecom Consulting LLC",
        "Wipro Connected Services Inc",
        "Wipro Appirio Inc",
        "Wipro Pari Inc.",
        "Wipro Enterprises, Inc.",
        "Wipro Designit Services, Inc.",
    ],
    "Fidelity Investments": [
        "Fidelity Technology Group, LLC d/b/a Fidelity Investments",
        "Fidelity Technology Group, LLC",
        "FMR LLC d/b/a Fidelity Investments",
        "Fidelity Brokerage Services LLC d/b/a Fidelity Investments",
        "Fidelity Workplace Investing LLC d/b/a Fidelity Investments",
        "Fidelity Management & Research Company LLC d/b/a Fidelity Investments",
        "National Charitable Services LLC d/b/a Fidelity Investments",
        "Fidelity Investments Institutional Operations Company d/b/a Fidelity Investments",
    ],
    "TikTok": [
        "TikTok Inc.",
        "TikTok U.S. Data Security Inc.",
        "TikTok USDS Joint Venture LLC",
        "BD TikTok USA LLC",
    ],
    "CVS Health": [
        "CVS Shared Services Resources LLC",
        "CVS Pharmacy Inc.",
        "CVS Rx Services Inc.",
        "Caremark LLC",
    ],
    "Citadel": [
        "Citadel Securities Americas Services LLC",
        "Citadel Americas Services LLC",
        "Citadel Enterprise Americas Services LLC",
    ],
}

_CORE_KEY_TO_BRAND: dict[str, str] = {}
for _brand, _variants in BRAND_GROUPS.items():
    for _variant in _variants:
        _CORE_KEY_TO_BRAND[core_key(clean_name(_variant))] = _brand


def apply_brand_rollup(canonical_names: pd.Series) -> pd.Series:
    """Map a canonicalized employer-name column to its brand label where a
    curated rollup rule matches; passes the input through unchanged for
    every employer not in `BRAND_GROUPS`."""
    keys = canonical_names.map(lambda n: core_key(clean_name(n)) if pd.notna(n) else n)
    rolled_up = keys.map(_CORE_KEY_TO_BRAND)
    return rolled_up.fillna(canonical_names)
