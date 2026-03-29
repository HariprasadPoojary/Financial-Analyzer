"""
Categorizer — transaction categorization with simple pattern matching.

Pattern syntax (what users type in the UI):
    zomato            → case-insensitive substring match  (default)
    case:Zomato       → case-sensitive substring match
    re:\bUPI/\w+      → regex, case-insensitive
    re:case:UPI/[A-Z] → regex, case-sensitive

Order of prefixes is always: re: first, case: second.
"""

import re

import pandas as pd

from .rules_store import get_rules


def pattern_to_regex(pattern: str) -> re.Pattern:
    """
    Compile a user-facing pattern string into a compiled regex.

    Handles four modes based on prefix:
        - Plain text  → re.escape() + case-insensitive
        - case:       → re.escape() + case-sensitive
        - re:         → raw regex + case-insensitive
        - re:case:    → raw regex + case-sensitive
    """
    raw_mode = False
    case_sensitive = False

    if pattern.startswith("re:"):
        raw_mode = True
        pattern = pattern[3:]

    if pattern.startswith("case:"):
        case_sensitive = True
        pattern = pattern[5:]

    flags = 0 if case_sensitive else re.IGNORECASE

    if not raw_mode:
        pattern = re.escape(pattern)

    return re.compile(pattern, flags)


def _compile_rules(rules: list[tuple]) -> list[tuple]:
    """Compile a list of (category, patterns, txn_type) into regex patterns."""
    compiled = []
    for category, patterns, txn_type in rules:
        compiled_patterns = []
        for p in patterns:
            try:
                compiled_patterns.append(pattern_to_regex(p))
            except re.error as e:
                # Bad regex — skip silently rather than crashing the whole run
                print(f"[categorizer] Invalid pattern '{p}' in '{category}': {e}")
        compiled.append((category, compiled_patterns, txn_type))
    return compiled


def categorize_transaction(
    description: str,
    amount: float,
    txn_type: str = "both",
    compiled_rules: list | None = None,
) -> str:
    """
    Return the category for a single transaction.

    Args:
        description:    Transaction description to match against patterns
        amount:         Transaction amount (used for fallback only)
        txn_type:       'credit', 'debit', or 'both'
        compiled_rules: Pre-compiled rules. If None, loads from rules_store.
    """
    if pd.isna(amount):
        return "Other"

    if compiled_rules is None:
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
    Add a 'category' column to the normalized transaction dataframe.

    Loads rules fresh from rules_store on each call so UI changes
    take effect immediately on the next analysis run.

    overrides: optional {row_index: category} applied after rule matching.
    """
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
