"""
Shared fixtures used across all test modules.
"""

from pathlib import Path

import pandas as pd
import pytest

import app.rules_store as rules_store
from app.categorizer import categorize_dataframe

# ── CSV helpers ───────────────────────────────────────────────────────────────


def write_csv(tmp_path: Path, filename: str, content: str) -> Path:
    """Write content to a temp CSV file and return its path."""
    p = tmp_path / filename
    p.write_text(content.strip(), encoding="utf-8")
    return p


# ── Standard single-amount CSV ────────────────────────────────────────────────

STANDARD_CSV = """
Date,PARTICULARS,Debit,Credit,Balance
01/01/2024,ACH-CR SALARY DEPOSIT,,85000,85000
05/01/2024,UPI/Zomato Food,450,,84550
08/01/2024,UPI/Zepto Groceries,380,,84170
15/01/2024,ATMCard Cash Withdrawal,2000,,82170
18/01/2024,NEFT Received,,12000,94170
20/01/2024,Netflix subscription,199,,93971
22/01/2024,Uber ride,350,,93621
25/01/2024,ACH-DR-Groww Mutual Funds,5000,,88621
28/01/2024,UPI/Amazon shopping,1200,,87421
01/02/2024,ACH-CR SALARY DEPOSIT,,85000,172421
03/02/2024,UPI/Dominos Pizza,320,,172101
07/02/2024,BABITHA  MANJUNATH Rent,15000,,157101
10/02/2024,Redbus travel,800,,156301
"""

SPLIT_CREDIT_DEBIT_CSV = """
Date,Details,Debit,Credit,Balance
01/03/2024,Opening Balance,,5000,5000
03/03/2024,Purchase TESCO,1200,,3800
10/03/2024,SALARY CREDIT,,50000,53800
15/03/2024,ATM Withdrawal,3000,,50800
"""

METADATA_ROWS_CSV = """
Account Number,123456789
Account Holder,Test User
Statement Period,Jan 2024

Date,PARTICULARS,Debit,Credit,Balance
01/01/2024,ACH-CR SALARY,,50000,50000
05/01/2024,UPI/Zomato,500,,49500
"""


# ── Normalized dataframe fixture ──────────────────────────────────────────────


@pytest.fixture
def sample_df():
    """Minimal normalized dataframe for analyzer/categorizer tests."""
    return pd.DataFrame(
        {
            "date": pd.to_datetime(
                [
                    "2024-01-01",
                    "2024-01-05",
                    "2024-01-10",
                    "2024-01-15",
                    "2024-02-01",
                    "2024-02-10",
                ]
            ),
            "description": [
                "ACH-CR SALARY DEPOSIT",
                "UPI/Zomato Food",
                "UPI/Zepto Groceries",
                "ATMCard Cash Withdrawal",
                "ACH-CR SALARY DEPOSIT",
                "Netflix subscription",
            ],
            "amount": [85000.0, -450.0, -380.0, -2000.0, 85000.0, -199.0],
            "type": ["credit", "debit", "debit", "debit", "credit", "debit"],
        }
    )


@pytest.fixture
def categorized_df(sample_df):

    return categorize_dataframe(sample_df)


@pytest.fixture
def tmp_rules_file(tmp_path, monkeypatch):
    """
    Redirect rules_store to use a temp data dir so tests
    never touch the real data/rules.json.
    """

    monkeypatch.setattr(rules_store, "DATA_DIR", tmp_path)
    monkeypatch.setattr(rules_store, "RULES_FILE", tmp_path / "rules.json")
    return tmp_path
