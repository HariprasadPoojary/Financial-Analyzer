"""
Categorizer — keyword/regex-based transaction categorization.

Categories are matched in priority order (first match wins).
You can extend CATEGORY_RULES with your own bank's transaction descriptions.
"""

import re

import pandas as pd

# ── Category rules: (category, [keywords/patterns]) ───────────────────────────
# Order matters — more specific rules should come first.

CATEGORY_RULES: list[tuple[str, list[str]]] = [
    # Income
    (
        "Income",
        [
            r"\bsalary\b",
            r"\bpayroll\b",
            r"\bdirect deposit\b",
            r"\bpaycheck\b",
            r"\bfreelance\b",
            r"\binvoice\b",
            r"\brefund\b",
            r"\bcashback\b",
            r"\bopening balance\b",
            r"\btransfer in\b",
            r"\breceived from\b",
        ],
    ),
    # Housing
    (
        "Housing",
        [
            r"\brent\b",
            r"\bmortgage\b",
            r"\bhoa\b",
            r"\bproperty tax\b",
            r"\blandlord\b",
            r"\bstrata\b",
            r"\bleasing\b",
        ],
    ),
    # Groceries
    (
        "Groceries",
        [
            r"\bwhole foods\b",
            r"\btrader joe",
            r"\bkroger\b",
            r"\bsafeway\b",
            r"\baldi\b",
            r"\bwegmans\b",
            r"\bpublix\b",
            r"\bcostco\b",
            r"\bwaitrose\b",
            r"\btesco\b",
            r"\bsainsbury\b",
            r"\basda\b",
            r"\blidl\b",
            r"\bmorrisons\b",
            r"\bsupermarket\b",
            r"\bgrocery\b",
            r"\bfood store\b",
            r"\bmarket\b",
        ],
    ),
    # Dining & Restaurants
    (
        "Dining",
        [
            r"\brestaurant\b",
            r"\bcafe\b",
            r"\bcoffee\b",
            r"\bstarbucks\b",
            r"\bmcdonald",
            r"\bburger king\b",
            r"\bsubway\b",
            r"\bchipotle\b",
            r"\bdomino\b",
            r"\bpizza\b",
            r"\bkfc\b",
            r"\bnando\b",
            r"\bcosta\b",
            r"\bgreggs\b",
            r"\bdiner\b",
            r"\bbistro\b",
            r"\bgrille?\b",
            r"\btavern\b",
            r"\bpub\b",
            r"\bbar\b",
            r"\buber eats\b",
            r"\bjust eat\b",
            r"\bdoordash\b",
            r"\bdeliveroo\b",
            r"\bpostmates\b",
            r"\bgrab food\b",
            r"\bgrubhub\b",
        ],
    ),
    # Transport
    (
        "Transport",
        [
            r"\buber\b",
            r"\blyft\b",
            r"\bcabify\b",
            r"\bbolt\b",
            r"\bgas station\b",
            r"\bshell\b",
            r"\bbp\b",
            r"\besso\b",
            r"\bmobil\b",
            r"\bchevron\b",
            r"\btotal\b",
            r"\bcaltex\b",
            r"\bparking\b",
            r"\btoll\b",
            r"\bbus\b",
            r"\btrain\b",
            r"\bmetro\b",
            r"\bsubway fare\b",
            r"\btravel card\b",
            r"\boyster\b",
            r"\btfl\b",
            r"\bamtrak\b",
            r"\bairline\b",
            r"\bflight\b",
        ],
    ),
    # Utilities
    (
        "Utilities",
        [
            r"\belectric\b",
            r"\bgas bill\b",
            r"\bwater bill\b",
            r"\binternet\b",
            r"\bbroadband\b",
            r"\bphone\b",
            r"\bmobile\b",
            r"\bbt group\b",
            r"\bvirgin media\b",
            r"\bpge\b",
            r"\bcon edison\b",
            r"\bcouncil tax\b",
            r"\brates\b",
        ],
    ),
    # Subscriptions & Entertainment
    (
        "Subscriptions",
        [
            r"\bnetflix\b",
            r"\bspotify\b",
            r"\bapple\b",
            r"\bgoogle play\b",
            r"\bamazon prime\b",
            r"\bdisney\+?\b",
            r"\bhbo\b",
            r"\bhulu\b",
            r"\byoutube\b",
            r"\btwitch\b",
            r"\bpatreon\b",
            r"\bsubscription\b",
            r"\bmembership\b",
            r"\bsky\b",
            r"\bnow tv\b",
        ],
    ),
    # Shopping
    (
        "Shopping",
        [
            r"\bamazon\b",
            r"\bebay\b",
            r"\baliexpress\b",
            r"\bshein\b",
            r"\bzara\b",
            r"\bh&m\b",
            r"\bnike\b",
            r"\badidas\b",
            r"\bwalmart\b",
            r"\btarget\b",
            r"\bbestbuy\b",
            r"\bpcworld\b",
            r"\bcurrys\b",
            r"\bjohn lewis\b",
            r"\bipayment\b",
            r"\bpaypal\b",
            r"\bstripe\b",
        ],
    ),
    # Health & Medical
    (
        "Health",
        [
            r"\bpharmacy\b",
            r"\bcvs\b",
            r"\bwalgreens\b",
            r"\bboots\b",
            r"\bdoctor\b",
            r"\bclinic\b",
            r"\bhospital\b",
            r"\bdentist\b",
            r"\boptician\b",
            r"\bgym\b",
            r"\bfitness\b",
            r"\bspa\b",
            r"\bmedical\b",
            r"\bhealth\b",
        ],
    ),
    # Education
    (
        "Education",
        [
            r"\buniversity\b",
            r"\bcollege\b",
            r"\bschool\b",
            r"\bcourse\b",
            r"\budemy\b",
            r"\bcoursera\b",
            r"\bbook\b",
            r"\bamazon kindle\b",
            r"\btuition\b",
            r"\blibrary\b",
        ],
    ),
    # ATM & Cash
    (
        "Cash & ATM",
        [
            r"\batm\b",
            r"\bcash withdrawal\b",
            r"\bcash advance\b",
            r"\bwithdrawal\b",
        ],
    ),
    # Transfers
    (
        "Transfers",
        [
            r"\btransfer\b",
            r"\bwise\b",
            r"\brevolut\b",
            r"\bpayment\b",
            r"\bbank transfer\b",
            r"\bstanding order\b",
            r"\bdirect debit\b",
        ],
    ),
]


def _compile_rules() -> list[tuple[str, list[re.Pattern]]]:
    return [
        (category, [re.compile(p, re.IGNORECASE) for p in patterns])
        for category, patterns in CATEGORY_RULES
    ]


_COMPILED_RULES = _compile_rules()


def categorize_transaction(description: str, amount: float) -> str:
    """Return the category for a single transaction."""
    for category, patterns in _COMPILED_RULES:
        if any(p.search(description) for p in patterns):
            return category

    # Fallback: infer from amount sign if no match
    return "Other Income" if amount > 0 else "Other"


def categorize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add a 'category' column to the normalized transaction dataframe.
    Operates on the 'description' and 'amount' columns.
    """
    df = df.copy()
    df["category"] = df.apply(
        lambda row: categorize_transaction(row["description"], row["amount"]),
        axis=1,
    )
    return df
