"""
Analyzer — computes all aggregates needed for the report.

Input:  categorized dataframe (output of categorizer.categorize_dataframe)
Output: AnalysisResult dataclass with all stats pre-computed

Nothing here renders anything — pure data transformation.
"""

from dataclasses import dataclass, field

import pandas as pd


@dataclass
class MonthlySummary:
    month: str  # "2024-01"
    month_label: str  # "Jan 2024"
    income: float
    expenses: float
    net: float


@dataclass
class CategorySummary:
    category: str
    total: float  # always positive
    count: int
    pct_of_expenses: float


@dataclass
class TopMerchant:
    description: str
    total: float  # always positive
    count: int
    category: str


@dataclass
class AnalysisResult:
    # Period
    date_from: str
    date_to: str
    total_months: int

    # Top-level
    total_income: float
    total_expenses: float
    net_savings: float
    savings_rate: float  # % of income saved

    # Breakdowns
    monthly: list[MonthlySummary]
    by_category: list[CategorySummary]
    top_merchants: list[TopMerchant]

    # Daily spending series (for trend chart)
    daily_expenses: dict  # {"2024-01-05": 45.99, ...}

    # UPI/Transfer breakdown (debit only — useful for Indian banks)
    upi_debits: list[TopMerchant] = field(default_factory=list)

    # Raw categorized df (kept for the transaction table in report)
    transactions: pd.DataFrame = field(default_factory=pd.DataFrame)

    # Warnings passed through from parser
    warnings: list[str] = field(default_factory=list)


# ── Income categories — anything in this set is income, not an expense ────────
INCOME_CATEGORIES = {"Income", "Other Income"}


def _fmt_month(period: pd.Period) -> str:
    return period.strftime("%b %Y")


def analyze(df: pd.DataFrame, warnings: list[str] | None = None) -> AnalysisResult:
    """
    Main entry point.

    df must have columns: date, description, amount, type, category
    """
    if df.empty:
        raise ValueError("Cannot analyze an empty dataframe.")

    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df["month"] = df["date"].dt.to_period("M")

    warnings = warnings or []

    # ── Income vs Expenses ────────────────────────────────────────────────────
    income_mask = df["category"].isin(INCOME_CATEGORIES)

    income_df = df[income_mask & (df["amount"] > 0)]
    expense_df = df[~income_mask & (df["amount"] < 0)]

    total_income = income_df["amount"].sum()
    total_expenses = abs(expense_df["amount"].sum())
    net_savings = total_income - total_expenses
    savings_rate = (net_savings / total_income * 100) if total_income > 0 else 0.0

    # ── Monthly summaries ─────────────────────────────────────────────────────
    monthly_income = income_df.groupby("month")["amount"].sum().rename("income")
    monthly_expenses = expense_df.groupby("month")["amount"].sum().abs().rename("expenses")

    monthly_df = pd.DataFrame({"income": monthly_income, "expenses": monthly_expenses})
    monthly_df = monthly_df.fillna(0).sort_index()
    monthly_df["net"] = monthly_df["income"] - monthly_df["expenses"]

    monthly = [
        MonthlySummary(
            month=str(period),
            month_label=_fmt_month(period),
            income=round(row["income"], 2),
            expenses=round(row["expenses"], 2),
            net=round(row["net"], 2),
        )
        for period, row in monthly_df.iterrows()
    ]

    # ── Category breakdown (expenses only) ───────────────────────────────────
    cat_df = (
        expense_df.groupby("category")
        .agg(total=("amount", lambda x: abs(x.sum())), count=("amount", "count"))
        .reset_index()
        .sort_values("total", ascending=False)
    )

    by_category = [
        CategorySummary(
            category=row["category"],
            total=round(row["total"], 2),
            count=int(row["count"]),
            pct_of_expenses=(
                round(row["total"] / total_expenses * 100, 1) if total_expenses > 0 else 0
            ),
        )
        for _, row in cat_df.iterrows()
    ]

    # ── Top merchants (expenses, excluding generic transfer patterns) ─────────
    skip_categories = {"UPI & Transfers"}

    merchant_df = (
        expense_df[~expense_df["category"].isin(skip_categories)]
        .groupby(["description", "category"])
        .agg(total=("amount", lambda x: abs(x.sum())), count=("amount", "count"))
        .reset_index()
        .sort_values("total", ascending=False)
        .head(15)
    )

    top_merchants = [
        TopMerchant(
            description=row["description"],
            total=round(row["total"], 2),
            count=int(row["count"]),
            category=row["category"],
        )
        for _, row in merchant_df.iterrows()
    ]

    # ── UPI debit breakdown (useful for Indian banks) ─────────────────────────
    upi_df = (
        expense_df[expense_df["category"] == "UPI & Transfers"]
        .groupby("description")
        .agg(total=("amount", lambda x: abs(x.sum())), count=("amount", "count"))
        .reset_index()
        .sort_values("total", ascending=False)
        .head(10)
    )

    upi_debits = [
        TopMerchant(
            description=row["description"],
            total=round(row["total"], 2),
            count=int(row["count"]),
            category="UPI & Transfers",
        )
        for _, row in upi_df.iterrows()
    ]

    # ── Daily expense series ──────────────────────────────────────────────────
    daily = expense_df.groupby(expense_df["date"].dt.date)["amount"].sum().abs().sort_index()
    daily_expenses = {str(k): round(v, 2) for k, v in daily.items()}

    # ── Period metadata ───────────────────────────────────────────────────────
    date_from = df["date"].min().strftime("%d %b %Y")
    date_to = df["date"].max().strftime("%d %b %Y")
    total_months = len(monthly_df)

    # ── Prepare transactions table ────────────────────────────────────────────
    transactions = df[["date", "description", "amount", "type", "category"]].copy()
    transactions["date"] = transactions["date"].dt.strftime("%d %b %Y")
    transactions = transactions.sort_values("date", ascending=False).reset_index(drop=True)

    return AnalysisResult(
        date_from=date_from,
        date_to=date_to,
        total_months=total_months,
        total_income=round(total_income, 2),
        total_expenses=round(total_expenses, 2),
        net_savings=round(net_savings, 2),
        savings_rate=round(savings_rate, 1),
        monthly=monthly,
        by_category=by_category,
        top_merchants=top_merchants,
        upi_debits=upi_debits,
        daily_expenses=daily_expenses,
        transactions=transactions,
        warnings=warnings,
    )
