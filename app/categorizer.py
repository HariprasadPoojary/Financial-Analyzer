"""
Categorizer — keyword/regex-based transaction categorization.

Rules are loaded from rules_store (which reads data/rules.json if it exists,
falling back to const.py). Rules are compiled once per categorize_dataframe()
call so changes via the UI take effect on the next analysis run.
"""

import re

import pandas as pd


def _compile_rules(rules: list[tuple]) -> list[tuple]:
    return [
        (category, [re.compile(p, re.IGNORECASE) for p in patterns], txn_type)
        for category, patterns, txn_type in rules
    ]


def categorize_transaction(
    description: str,
    amount: float,
    txn_type: str = "both",
    compiled_rules: list | None = None,
) -> str:
    if pd.isna(amount):
        return "Other"

    if compiled_rules is None:
        from rules_store import get_rules

        compiled_rules = _compile_rules(get_rules())

    for category, patterns, rule_type in compiled_rules:
        if rule_type != "both" and rule_type != txn_type:
            continue
        if any(p.search(description) for p in patterns):
            return category

    return "Other Income" if amount > 0 else "Other"


def categorize_dataframe(
    df: pd.DataFrame,
    overrides: dict | None = None,
) -> pd.DataFrame:
    """
    Add a 'category' column. Loads rules fresh from rules_store on each call.
    overrides: optional {row_index: category} applied after rule matching.
    """
    from rules_store import get_rules

    compiled = _compile_rules(get_rules())

    df = df.copy()
    df["category"] = df.apply(
        lambda row: categorize_transaction(
            row["description"],
            row["amount"],
            row.get("type", "both"),
            compiled,
        ),
        axis=1,
    )

    if overrides:
        for idx, cat in overrides.items():
            if idx in df.index:
                df.at[idx, "category"] = cat

    return df
