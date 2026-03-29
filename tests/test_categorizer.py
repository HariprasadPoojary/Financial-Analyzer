"""
Tests for app/categorizer.py

Covers:
  - pattern_to_regex: all four modes (plain, case:, re:, re:case:)
  - Special characters in plain patterns (/, ., brackets)
  - Bad regex handling (should not crash)
  - categorize_transaction: type filtering, fallback
  - categorize_dataframe: full df, overrides
"""

import re

import pytest

from app.categorizer import (
    categorize_dataframe,
    categorize_transaction,
    pattern_to_regex,
)

# ── pattern_to_regex ──────────────────────────────────────────────────────────


class TestPatternToRegex:

    # ── Plain substring (default) ─────────────────────────────────────────────

    def test_plain_matches_case_insensitive(self):
        r = pattern_to_regex("zomato")
        assert r.search("ZOMATO FOOD ORDER")
        assert r.search("Zomato delivery")
        assert r.search("zomato")

    def test_plain_no_match(self):
        r = pattern_to_regex("zomato")
        assert not r.search("Swiggy order")

    def test_plain_special_chars_escaped(self):
        # Slash should not be treated as regex operator
        r = pattern_to_regex("UPI/")
        assert r.search("UPI/CR SALARY")
        assert r.search("upi/transfer")

    def test_plain_dot_escaped(self):
        # Dot should match literally, not any character
        r = pattern_to_regex("1mg")
        assert r.search("Purchase at 1mg pharma")
        # Dot in pattern shouldn't match arbitrary char
        r2 = pattern_to_regex("A.B")
        assert r2.search("A.B")
        assert not r2.search("AXB")

    def test_plain_brackets_escaped(self):
        r = pattern_to_regex("(EMI)")
        assert r.search("HDFC (EMI) payment")
        assert not r.search("HDFC EMI payment")

    # ── case: prefix ──────────────────────────────────────────────────────────

    def test_case_sensitive_match(self):
        r = pattern_to_regex("case:Zomato")
        assert r.search("Zomato delivery")

    def test_case_sensitive_no_match_uppercase(self):
        r = pattern_to_regex("case:Zomato")
        assert not r.search("ZOMATO FOOD ORDER")

    def test_case_sensitive_no_match_lowercase(self):
        r = pattern_to_regex("case:NEFT")
        assert not r.search("neft transfer")
        assert r.search("NEFT/123456")

    def test_case_sensitive_with_slash(self):
        r = pattern_to_regex("case:UPI/")
        assert r.search("UPI/CR SALARY")
        assert not r.search("upi/cr salary")

    # ── re: prefix ────────────────────────────────────────────────────────────

    def test_re_word_boundary(self):
        # Simulates what browser sends: literal backslash sequences
        r = pattern_to_regex(r"re:\bNEFT\b")
        assert r.search("NEFT/123456")
        assert r.search("NEFT transfer")
        assert not r.search("INEFTING")

    def test_re_digit_pattern(self):
        r = pattern_to_regex(r"re:\d{6}")
        assert r.search("TXN123456REF")
        assert not r.search("TXN123REF")

    def test_re_alternation(self):
        r = pattern_to_regex(r"re:Zomato|Swiggy")
        assert r.search("Zomato order")
        assert r.search("Swiggy delivery")
        assert not r.search("Dunzo order")

    def test_re_case_insensitive_by_default(self):
        r = pattern_to_regex(r"re:salary")
        assert r.search("SALARY CREDIT")
        assert r.search("salary deposit")

    # ── re:case: prefix ───────────────────────────────────────────────────────

    def test_re_case_sensitive_match(self):
        r = pattern_to_regex(r"re:case:[A-Z]{4,}")
        assert r.search("SALARY")
        assert not r.search("salary")

    def test_re_case_sensitive_word_boundary(self):
        r = pattern_to_regex(r"re:case:\bUPI\b")
        assert r.search("UPI transfer")
        assert not r.search("upi transfer")

    # ── Invalid regex ─────────────────────────────────────────────────────────

    def test_invalid_regex_raises(self):
        with pytest.raises(re.error):
            pattern_to_regex("re:[invalid")


# ── categorize_transaction ────────────────────────────────────────────────────


class TestCategorizeTransaction:

    def test_matches_income_on_credit(self):
        rules = [("Income", [pattern_to_regex("salary")], "credit")]
        cat = categorize_transaction("ACH-CR SALARY DEPOSIT", 85000, "credit", rules)
        assert cat == "Income"

    def test_income_rule_skipped_for_debit(self):
        rules = [
            ("Income", [pattern_to_regex("salary")], "credit"),
            ("Other", [], "both"),
        ]
        # salary in a debit transaction should NOT match Income rule
        cat = categorize_transaction("SALARY REVERSAL", -500, "debit", rules)
        assert cat != "Income"

    def test_debit_rule_skipped_for_credit(self):
        rules = [("Shopping", [pattern_to_regex("amazon")], "debit")]
        # Amazon credit (refund) should not hit Shopping
        cat = categorize_transaction("AMAZON REFUND", 500, "credit", rules)
        assert cat == "Other Income"

    def test_both_type_matches_either(self):
        rules = [("Transfers", [pattern_to_regex("UPI/")], "both")]
        assert categorize_transaction("UPI/CR SALARY", 5000, "credit", rules) == "Transfers"
        assert categorize_transaction("UPI/Zomato", -450, "debit", rules) == "Transfers"

    def test_first_match_wins(self):
        rules = [
            ("Dining", [pattern_to_regex("Zomato")], "debit"),
            ("Transfers", [pattern_to_regex("UPI/")], "both"),
        ]
        # "UPI/Zomato" — Dining should win because it's first
        cat = categorize_transaction("UPI/Zomato Food", -450, "debit", rules)
        assert cat == "Dining"

    def test_fallback_positive_amount(self):
        cat = categorize_transaction("UNKNOWN CREDIT", 1000, "credit", [])
        assert cat == "Other Income"

    def test_fallback_negative_amount(self):
        cat = categorize_transaction("UNKNOWN DEBIT", -500, "debit", [])
        assert cat == "Other"

    def test_nan_amount_returns_other(self):
        import math

        cat = categorize_transaction("SOME TXN", float("nan"), "debit", [])
        assert cat == "Other"


# ── categorize_dataframe ──────────────────────────────────────────────────────


class TestCategorizeDataframe:

    def test_adds_category_column(self, sample_df):
        df = categorize_dataframe(sample_df)
        assert "category" in df.columns

    def test_original_df_not_mutated(self, sample_df):
        original_cols = set(sample_df.columns)
        categorize_dataframe(sample_df)
        assert set(sample_df.columns) == original_cols

    def test_no_nulls_in_category(self, sample_df):
        df = categorize_dataframe(sample_df)
        assert df["category"].notna().all()

    def test_salary_categorized_as_income(self, sample_df):
        df = categorize_dataframe(sample_df)
        salary_rows = df[df["description"].str.contains("SALARY", na=False)]
        assert (salary_rows["category"] == "Income").all()

    def test_overrides_applied(self, sample_df):
        df = categorize_dataframe(sample_df, overrides={1: "Dining"})
        assert df.at[1, "category"] == "Dining"

    def test_overrides_dont_affect_other_rows(self, sample_df):
        df_no_override = categorize_dataframe(sample_df)
        df_with_override = categorize_dataframe(sample_df, overrides={1: "Dining"})
        # Row 0 should be unchanged
        assert df_no_override.at[0, "category"] == df_with_override.at[0, "category"]

    def test_invalid_override_index_ignored(self, sample_df):
        # Should not raise even if index doesn't exist
        df = categorize_dataframe(sample_df, overrides={9999: "Dining"})
        assert len(df) == len(sample_df)

    def test_row_count_preserved(self, sample_df):
        df = categorize_dataframe(sample_df)
        assert len(df) == len(sample_df)
