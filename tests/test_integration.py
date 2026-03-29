"""
Integration tests — full pipeline end-to-end.

These tests run the complete flow:
    CSV → parse → categorize → analyze → report

No mocking. Tests real behavior across all modules together.
"""

from pathlib import Path

import pandas as pd
import pytest
from conftest import SPLIT_CREDIT_DEBIT_CSV, STANDARD_CSV, write_csv

from app.analyzer import analyze
from app.categorizer import categorize_dataframe
from app.const import CATEGORY_RULES
from app.parser import merge_statements, parse_csv
from app.report_builder import generate_report
from app.rules_store import get_rules, reset_to_defaults, save_rules

# ── Full pipeline ─────────────────────────────────────────────────────────────


class TestFullPipeline:

    def test_single_file_pipeline(self, tmp_path):
        f = write_csv(tmp_path, "stmt.csv", STANDARD_CSV)
        result = parse_csv(str(f))
        df = categorize_dataframe(result.df)
        analysis = analyze(df, result.warnings)
        report_path = str(tmp_path / "report.html")
        generate_report(analysis, report_path, session_id="test01")

        assert Path(report_path).exists()
        assert analysis.total_income > 0
        assert analysis.total_expenses > 0
        assert len(analysis.by_category) > 0

    def test_multi_file_pipeline(self, tmp_path):
        f1 = write_csv(tmp_path, "s1.csv", STANDARD_CSV)
        f2 = write_csv(tmp_path, "s2.csv", SPLIT_CREDIT_DEBIT_CSV)
        r1 = parse_csv(str(f1))
        r2 = parse_csv(str(f2))
        df = merge_statements([r1, r2])
        df = categorize_dataframe(df)
        analysis = analyze(df)
        assert len(analysis.transactions) == r1.row_count + r2.row_count

    def test_date_range_filter_reduces_transactions(self, tmp_path):
        f = write_csv(tmp_path, "stmt.csv", STANDARD_CSV)
        result = parse_csv(str(f))
        full_count = result.row_count

        # Filter to January only
        df_filtered = result.df[result.df["date"] >= pd.to_datetime("2024-02-01")]
        assert len(df_filtered) < full_count

    def test_category_overrides_flow(self, tmp_path):
        f = write_csv(tmp_path, "stmt.csv", STANDARD_CSV)
        result = parse_csv(str(f))
        df = categorize_dataframe(result.df)

        # Find an "Other" row and reclassify it
        other_rows = df[df["category"].isin(["Other", "Other Income"])]
        if len(other_rows) > 0:
            idx = other_rows.index[0]
            df_updated = categorize_dataframe(result.df, overrides={idx: "Shopping"})
            assert df_updated.at[idx, "category"] == "Shopping"

    def test_no_null_categories_in_pipeline(self, tmp_path):
        f = write_csv(tmp_path, "stmt.csv", STANDARD_CSV)
        result = parse_csv(str(f))
        df = categorize_dataframe(result.df)
        assert df["category"].notna().all()

    def test_report_html_has_correct_currency(self, tmp_path):
        f = write_csv(tmp_path, "stmt.csv", STANDARD_CSV)
        result = parse_csv(str(f))
        df = categorize_dataframe(result.df)
        analysis = analyze(df)
        report_path = str(tmp_path / "report.html")
        generate_report(analysis, report_path)
        html = Path(report_path).read_text(encoding="utf-8")
        assert "₹" in html


# ── Pattern changes affect categorization ─────────────────────────────────────


class TestRulesIntegration:

    def test_custom_rules_used_in_pipeline(self, tmp_path, tmp_rules_file):

        # Save a custom rule that matches our test data
        save_rules(
            [
                {"category": "Income", "patterns": ["SALARY"], "txn_type": "credit"},
                {"category": "MyCustom", "patterns": ["Zomato"], "txn_type": "debit"},
            ]
        )

        f = write_csv(tmp_path, "stmt.csv", STANDARD_CSV)
        result = parse_csv(str(f))
        df = categorize_dataframe(result.df)

        zomato_rows = df[df["description"].str.contains("Zomato", case=False, na=False)]
        if len(zomato_rows) > 0:
            assert (zomato_rows["category"] == "MyCustom").all()

    def test_reset_rules_restores_defaults(self, tmp_path, tmp_rules_file):
        save_rules([{"category": "Temp", "patterns": ["xyz"], "txn_type": "both"}])
        reset_to_defaults()
        assert get_rules() == CATEGORY_RULES


# ── Savings rate correctness ──────────────────────────────────────────────────


class TestSavingsRateIntegration:

    def test_high_spender_negative_savings(self, tmp_path):
        csv = """Date,PARTICULARS,Debit,Credit,Balance
01/01/2024,SALARY,,10000,10000
05/01/2024,RENT,8000,,2000
10/01/2024,SHOPPING,5000,,-3000
"""
        f = write_csv(tmp_path, "s.csv", csv)
        result = parse_csv(str(f))
        df = categorize_dataframe(result.df)
        analysis = analyze(df)
        assert analysis.net_savings < 0
        assert analysis.savings_rate < 0

    def test_good_saver_positive_savings(self, tmp_path):
        csv = """Date,PARTICULARS,Debit,Credit,Balance
01/01/2024,SALARY,,100000,100000
05/01/2024,RENT,15000,,85000
10/01/2024,GROCERIES,5000,,80000
"""
        f = write_csv(tmp_path, "s.csv", csv)
        result = parse_csv(str(f))
        df = categorize_dataframe(result.df)
        analysis = analyze(df)
        assert analysis.net_savings > 0
        assert analysis.savings_rate == pytest.approx(80.0, abs=1.0)
