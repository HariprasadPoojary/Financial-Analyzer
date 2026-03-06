"""
Categorizer — keyword/regex-based transaction categorization.

Categories are matched in priority order (first match wins).
You can extend CATEGORY_RULES with your own bank's transaction descriptions.
"""

import re

import pandas as pd

from const import CATEGORY_RULES


def _compile_rules() -> list[tuple[str, list[re.Pattern], str]]:
    return [
        (category, [re.compile(p, re.IGNORECASE) for p in patterns], txn_type)
        for category, patterns, txn_type in CATEGORY_RULES
    ]


_COMPILED_RULES = _compile_rules()


def categorize_transaction(description: str, amount: float, txn_type: str = "both") -> str:
    """Return the category for a single transaction.

    Args:
        description: Transaction description to match against patterns
        amount: Transaction amount (for fallback categorization)
        txn_type: Transaction type ('credit', 'debit', or 'neutral')
    """
    # Handle NaN amounts
    if pd.isna(amount):
        return "Other"

    for category, patterns, rule_type in _COMPILED_RULES:
        # Check if rule applies to this transaction type
        if rule_type != "both" and rule_type != txn_type:
            continue

        if any(p.search(description) for p in patterns):
            return category

    # Fallback: infer from amount sign if no match
    return "Other Income" if amount > 0 else "Other"


def categorize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add a 'category' column to the normalized transaction dataframe.
    Operates on the 'description', 'amount', and 'type' columns.
    """
    df = df.copy()
    df["category"] = df.apply(
        lambda row: categorize_transaction(
            row["description"],
            row["amount"],
            row.get("type", "both"),  # Default to "both" if type not present
        ),
        axis=1,
    )
    return df
