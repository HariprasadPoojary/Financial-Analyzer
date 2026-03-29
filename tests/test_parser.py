"""
Tests for app/parser.py

Covers:
  - Standard debit/credit/balance column detection
  - Metadata rows before the header
  - Date format variations
  - Amount parsing (negatives, brackets, currency symbols)
  - Duplicate removal on merge
  - Error cases: empty file, missing columns
"""

import pytest
from conftest import METADATA_ROWS_CSV, SPLIT_CREDIT_DEBIT_CSV, STANDARD_CSV, write_csv

from app.parser import merge_statements, parse_csv

# ── Column detection ──────────────────────────────────────────────────────────


class TestColumnDetection:

    def test_standard_debit_credit_balance(self, tmp_path):
        f = write_csv(tmp_path, "stmt.csv", STANDARD_CSV)
        r = parse_csv(str(f))
        assert r.row_count > 0
        assert set(r.df.columns) >= {"date", "description", "amount", "type"}

    def test_split_debit_credit_columns(self, tmp_path):
        f = write_csv(tmp_path, "stmt.csv", SPLIT_CREDIT_DEBIT_CSV)
        r = parse_csv(str(f))
        assert r.row_count > 0

    def test_metadata_rows_skipped(self, tmp_path):
        f = write_csv(tmp_path, "stmt.csv", METADATA_ROWS_CSV)
        r = parse_csv(str(f))
        # Should still parse transactions, not metadata
        assert r.row_count >= 2
        assert "123456789" not in r.df["description"].values

    def test_missing_date_column_raises(self, tmp_path):
        bad = "PARTICULARS,Debit,Credit\nSALARY,,5000\n"
        f = write_csv(tmp_path, "bad.csv", bad)
        with pytest.raises(ValueError, match="date column"):
            parse_csv(str(f))

    def test_missing_description_column_raises(self, tmp_path):
        bad = "Date,Debit,Credit\n01/01/2024,,5000\n"
        f = write_csv(tmp_path, "bad.csv", bad)
        with pytest.raises(ValueError, match="description column"):
            parse_csv(str(f))

    def test_missing_amount_column_raises(self, tmp_path):
        bad = "Date,PARTICULARS\n01/01/2024,SALARY\n"
        f = write_csv(tmp_path, "bad.csv", bad)
        with pytest.raises(ValueError):
            parse_csv(str(f))


# ── Amount parsing ────────────────────────────────────────────────────────────


class TestAmountParsing:

    def test_credits_are_positive(self, tmp_path):
        f = write_csv(tmp_path, "s.csv", STANDARD_CSV)
        r = parse_csv(str(f))
        salary_rows = r.df[r.df["description"].str.contains("SALARY", na=False)]
        assert (salary_rows["amount"] > 0).all()

    def test_debits_are_negative(self, tmp_path):
        f = write_csv(tmp_path, "s.csv", STANDARD_CSV)
        r = parse_csv(str(f))
        debit_rows = r.df[r.df["type"] == "debit"]
        assert (debit_rows["amount"] < 0).all()

    def test_accounting_negative_brackets(self, tmp_path):
        csv = "Date,PARTICULARS,Debit,Credit,Balance\n01/01/2024,TEST DEBIT,(500.00),,1000\n"
        f = write_csv(tmp_path, "s.csv", csv)
        r = parse_csv(str(f))
        assert r.df.iloc[0]["amount"] < 0

    def test_currency_symbol_stripped(self, tmp_path):
        csv = "Date,PARTICULARS,Debit,Credit,Balance\n01/01/2024,SALARY,,₹85000,85000\n"
        f = write_csv(tmp_path, "s.csv", csv)
        r = parse_csv(str(f))
        assert r.df.iloc[0]["amount"] == pytest.approx(85000.0)

    def test_comma_in_amount_stripped(self, tmp_path):
        csv = 'Date,PARTICULARS,Debit,Credit,Balance\n01/01/2024,SALARY,,"1,00,000",100000\n'
        f = write_csv(tmp_path, "s.csv", csv)
        r = parse_csv(str(f))
        assert r.df.iloc[0]["amount"] == pytest.approx(100000.0)


# ── Date parsing ──────────────────────────────────────────────────────────────


class TestDateParsing:

    @pytest.mark.parametrize(
        "date_str,expected",
        [
            ("2024-01-15", "2024-01-15"),
            ("15/01/2024", "2024-01-15"),
            ("01/15/2024", "2024-01-15"),
            ("15-01-2024", "2024-01-15"),
        ],
    )
    def test_date_formats(self, tmp_path, date_str, expected):
        csv = f"Date,PARTICULARS,Debit,Credit,Balance\n{date_str},SALARY,,5000,5000\n"
        f = write_csv(tmp_path, "s.csv", csv)
        r = parse_csv(str(f))
        assert str(r.df.iloc[0]["date"].date()) == expected

    def test_date_range_is_correct(self, tmp_path):
        f = write_csv(tmp_path, "s.csv", STANDARD_CSV)
        r = parse_csv(str(f))
        assert r.date_range[0] <= r.date_range[1]

    def test_rows_sorted_by_date(self, tmp_path):
        f = write_csv(tmp_path, "s.csv", STANDARD_CSV)
        r = parse_csv(str(f))
        dates = r.df["date"].tolist()
        assert dates == sorted(dates)


# ── ParseResult metadata ──────────────────────────────────────────────────────


class TestParseResult:

    def test_row_count_matches_dataframe(self, tmp_path):
        f = write_csv(tmp_path, "s.csv", STANDARD_CSV)
        r = parse_csv(str(f))
        assert r.row_count == len(r.df)

    def test_source_file_name(self, tmp_path):
        f = write_csv(tmp_path, "mybank.csv", STANDARD_CSV)
        r = parse_csv(str(f))
        assert r.source_file == "mybank.csv"

    def test_warnings_is_list(self, tmp_path):
        f = write_csv(tmp_path, "s.csv", STANDARD_CSV)
        r = parse_csv(str(f))
        assert isinstance(r.warnings, list)


# ── Merge ─────────────────────────────────────────────────────────────────────


class TestMergeStatements:

    def test_merge_two_files(self, tmp_path):
        f1 = write_csv(tmp_path, "s1.csv", STANDARD_CSV)
        f2 = write_csv(tmp_path, "s2.csv", SPLIT_CREDIT_DEBIT_CSV)
        r1 = parse_csv(str(f1))
        r2 = parse_csv(str(f2))
        merged = merge_statements([r1, r2])
        assert len(merged) == r1.row_count + r2.row_count

    def test_duplicates_removed_on_merge(self, tmp_path):
        f1 = write_csv(tmp_path, "s1.csv", STANDARD_CSV)
        f2 = write_csv(tmp_path, "s2.csv", STANDARD_CSV)  # identical
        r1 = parse_csv(str(f1))
        r2 = parse_csv(str(f2))
        merged = merge_statements([r1, r2])
        # Deduplication should give same count as one file
        assert len(merged) == r1.row_count

    def test_merge_empty_raises(self):
        with pytest.raises(ValueError, match="No parse results"):
            merge_statements([])

    def test_merged_sorted_by_date(self, tmp_path):
        f1 = write_csv(tmp_path, "s1.csv", STANDARD_CSV)
        f2 = write_csv(tmp_path, "s2.csv", SPLIT_CREDIT_DEBIT_CSV)
        r1 = parse_csv(str(f1))
        r2 = parse_csv(str(f2))
        merged = merge_statements([r1, r2])
        dates = merged["date"].tolist()
        assert dates == sorted(dates)
