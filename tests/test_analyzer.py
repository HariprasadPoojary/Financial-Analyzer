"""
Tests for app/analyzer.py

Covers:
  - Income vs expense separation
  - Monthly summaries
  - Category breakdown
  - Top merchants
  - Savings rate calculation
  - UPI debit breakdown
  - Edge cases: all income, all expenses, single transaction
"""

import pandas as pd
import pytest

from app.analyzer import analyze

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def full_df():
    """Two months of categorized transactions."""
    return pd.DataFrame(
        {
            "date": pd.to_datetime(
                [
                    "2024-01-01",
                    "2024-01-05",
                    "2024-01-10",
                    "2024-01-15",
                    "2024-01-20",
                    "2024-02-01",
                    "2024-02-05",
                    "2024-02-10",
                    "2024-02-15",
                ]
            ),
            "description": [
                "SALARY DEPOSIT",
                "Zomato Food",
                "Zepto Groceries",
                "ATM Withdrawal",
                "Netflix",
                "SALARY DEPOSIT",
                "Dominos Pizza",
                "BABITHA RENT",
                "Groww Mutual Fund",
            ],
            "amount": [
                85000.0,
                -450.0,
                -380.0,
                -2000.0,
                -199.0,
                85000.0,
                -320.0,
                -15000.0,
                -5000.0,
            ],
            "type": [
                "credit",
                "debit",
                "debit",
                "debit",
                "debit",
                "credit",
                "debit",
                "debit",
                "debit",
            ],
            "category": [
                "Income",
                "Dining",
                "Groceries",
                "Cash & ATM",
                "Subscriptions & Entertainment",
                "Income",
                "Dining",
                "Housing",
                "Investments",
            ],
        }
    )


# ── Income vs Expenses ────────────────────────────────────────────────────────


class TestIncomeExpenses:

    def test_total_income_correct(self, full_df):
        result = analyze(full_df)
        assert result.total_income == pytest.approx(170000.0)

    def test_total_expenses_correct(self, full_df):
        result = analyze(full_df)
        expected = 450 + 380 + 2000 + 199 + 320 + 15000 + 5000
        assert result.total_expenses == pytest.approx(expected)

    def test_net_savings_correct(self, full_df):
        result = analyze(full_df)
        assert result.net_savings == pytest.approx(result.total_income - result.total_expenses)

    def test_savings_rate_is_percentage(self, full_df):
        result = analyze(full_df)
        assert 0 <= result.savings_rate <= 100

    def test_savings_rate_calculation(self, full_df):
        result = analyze(full_df)
        expected_rate = (result.net_savings / result.total_income) * 100
        assert result.savings_rate == pytest.approx(expected_rate, abs=0.1)

    def test_negative_savings_when_expenses_exceed_income(self):
        df = pd.DataFrame(
            {
                "date": pd.to_datetime(["2024-01-01", "2024-01-05"]),
                "description": ["SALARY", "BIG EXPENSE"],
                "amount": [1000.0, -5000.0],
                "type": ["credit", "debit"],
                "category": ["Income", "Shopping"],
            }
        )
        result = analyze(df)
        assert result.net_savings < 0

    def test_zero_income_savings_rate_is_zero(self):
        df = pd.DataFrame(
            {
                "date": pd.to_datetime(["2024-01-05"]),
                "description": ["EXPENSE"],
                "amount": [-500.0],
                "type": ["debit"],
                "category": ["Shopping"],
            }
        )
        result = analyze(df)
        assert result.savings_rate == 0.0


# ── Monthly summaries ─────────────────────────────────────────────────────────


class TestMonthlySummaries:

    def test_correct_number_of_months(self, full_df):
        result = analyze(full_df)
        assert result.total_months == 2

    def test_monthly_labels_format(self, full_df):
        result = analyze(full_df)
        # e.g. "Jan 2024"
        for m in result.monthly:
            assert len(m.month_label.split()) == 2

    def test_monthly_net_equals_income_minus_expenses(self, full_df):
        result = analyze(full_df)
        for m in result.monthly:
            assert m.net == pytest.approx(m.income - m.expenses, abs=0.01)

    def test_monthly_sorted_chronologically(self, full_df):
        result = analyze(full_df)
        months = [m.month for m in result.monthly]
        assert months == sorted(months)

    def test_single_month_data(self):
        df = pd.DataFrame(
            {
                "date": pd.to_datetime(["2024-03-01", "2024-03-15"]),
                "description": ["SALARY", "RENT"],
                "amount": [50000.0, -15000.0],
                "type": ["credit", "debit"],
                "category": ["Income", "Housing"],
            }
        )
        result = analyze(df)
        assert result.total_months == 1
        assert result.monthly[0].income == pytest.approx(50000.0)
        assert result.monthly[0].expenses == pytest.approx(15000.0)


# ── Category breakdown ────────────────────────────────────────────────────────


class TestCategoryBreakdown:

    def test_income_excluded_from_categories(self, full_df):
        result = analyze(full_df)
        cats = [c.category for c in result.by_category]
        assert "Income" not in cats

    def test_categories_sorted_by_total_descending(self, full_df):
        result = analyze(full_df)
        totals = [c.total for c in result.by_category]
        assert totals == sorted(totals, reverse=True)

    def test_category_totals_are_positive(self, full_df):
        result = analyze(full_df)
        assert all(c.total > 0 for c in result.by_category)

    def test_pct_of_expenses_sums_to_100(self, full_df):
        result = analyze(full_df)
        total_pct = sum(c.pct_of_expenses for c in result.by_category)
        assert total_pct == pytest.approx(100.0, abs=0.5)

    def test_category_count_is_correct(self, full_df):
        result = analyze(full_df)
        dining = next(c for c in result.by_category if c.category == "Dining")
        assert dining.count == 2  # Zomato + Dominos


# ── Top merchants ─────────────────────────────────────────────────────────────


class TestTopMerchants:

    def test_returns_list(self, full_df):
        result = analyze(full_df)
        assert isinstance(result.top_merchants, list)

    def test_merchants_sorted_by_total_descending(self, full_df):
        result = analyze(full_df)
        totals = [m.total for m in result.top_merchants]
        assert totals == sorted(totals, reverse=True)

    def test_merchant_totals_positive(self, full_df):
        result = analyze(full_df)
        assert all(m.total > 0 for m in result.top_merchants)

    def test_upi_transfers_excluded_from_top_merchants(self):
        df = pd.DataFrame(
            {
                "date": pd.to_datetime(["2024-01-01", "2024-01-02"]),
                "description": ["UPI/someone123", "Zomato order"],
                "amount": [-50000.0, -450.0],
                "type": ["debit", "debit"],
                "category": ["UPI & Transfers", "Dining"],
            }
        )
        result = analyze(df)
        descs = [m.description for m in result.top_merchants]
        assert "UPI/someone123" not in descs
        assert "Zomato order" in descs


# ── UPI breakdown ─────────────────────────────────────────────────────────────


class TestUpiDebits:

    def test_upi_debits_list(self, full_df):
        result = analyze(full_df)
        assert isinstance(result.upi_debits, list)

    def test_upi_debits_only_from_upi_category(self):
        df = pd.DataFrame(
            {
                "date": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]),
                "description": ["UPI/friend123", "UPI/shop456", "SALARY"],
                "amount": [-500.0, -1200.0, 85000.0],
                "type": ["debit", "debit", "credit"],
                "category": ["UPI & Transfers", "UPI & Transfers", "Income"],
            }
        )
        result = analyze(df)
        descs = [m.description for m in result.upi_debits]
        assert "SALARY" not in descs


# ── Daily expenses ────────────────────────────────────────────────────────────


class TestDailyExpenses:

    def test_daily_expenses_is_dict(self, full_df):
        result = analyze(full_df)
        assert isinstance(result.daily_expenses, dict)

    def test_daily_values_are_positive(self, full_df):
        result = analyze(full_df)
        assert all(v > 0 for v in result.daily_expenses.values())

    def test_income_excluded_from_daily(self, full_df):
        result = analyze(full_df)
        # Total daily sum should equal total expenses, not income
        daily_sum = sum(result.daily_expenses.values())
        assert daily_sum == pytest.approx(result.total_expenses, abs=0.1)


# ── Transactions table ────────────────────────────────────────────────────────


class TestTransactionsTable:

    def test_transactions_is_dataframe(self, full_df):
        result = analyze(full_df)
        assert hasattr(result.transactions, "iterrows")

    def test_transactions_has_required_columns(self, full_df):
        result = analyze(full_df)
        required = {"date", "description", "amount", "type", "category"}
        assert required.issubset(set(result.transactions.columns))

    def test_transactions_row_count_matches_input(self, full_df):
        result = analyze(full_df)
        assert len(result.transactions) == len(full_df)


# ── Edge cases ────────────────────────────────────────────────────────────────


class TestEdgeCases:

    def test_empty_dataframe_raises(self):
        df = pd.DataFrame(columns=["date", "description", "amount", "type", "category"])
        with pytest.raises(ValueError, match="empty"):
            analyze(df)

    def test_single_transaction(self):
        df = pd.DataFrame(
            {
                "date": pd.to_datetime(["2024-01-15"]),
                "description": ["SALARY"],
                "amount": [50000.0],
                "type": ["credit"],
                "category": ["Income"],
            }
        )
        result = analyze(df)
        assert result.total_income == pytest.approx(50000.0)
        assert result.total_expenses == pytest.approx(0.0)

    def test_warnings_passed_through(self, full_df):
        warnings = ["Test warning 1", "Test warning 2"]
        result = analyze(full_df, warnings=warnings)
        assert result.warnings == warnings

    def test_period_metadata(self, full_df):
        result = analyze(full_df)
        assert result.date_from
        assert result.date_to
        assert result.total_months > 0
