import sys

sys.path.insert(0, ".")

from app.categorizer import categorize_dataframe
from app.parser import parse_csv


def format_indian_currency(amount: float) -> str:
    """Format amount with Indian number system (commas at different intervals)."""
    # Split into integer and decimal parts
    is_negative = amount < 0
    amount = abs(amount)

    whole, *decimal_part = f"{amount:.2f}".split(".")
    decimal = decimal_part[0] if decimal_part else "00"

    # Format whole part with Indian commas
    # Pattern: last 3 digits, then every 2 digits before that
    if len(whole) <= 3:
        formatted_whole = whole
    else:
        # Last 3 digits
        last_three = whole[-3:]
        remaining = whole[:-3]

        # Group remaining digits in pairs from right to left
        groups = []
        for i in range(len(remaining), 0, -2):
            start = max(0, i - 2)
            groups.append(remaining[start:i])

        formatted_whole = ",".join(reversed(groups)) + "," + last_three

    result = f"{formatted_whole}.{decimal}"
    return f"-{result}" if is_negative else result


# ← Point this to your actual CSV file
AXIS_CSV_PATH = "app\\uploads\\Axis_statement_last_3_months.csv"
SBI_CSV_PATH = "app\\uploads\\SBI_statement_last_3_months.csv"

result = parse_csv(AXIS_CSV_PATH)

print(f"[OK] Parsed {result.row_count} transactions")
print(f"[DATE] Date range: {result.date_range[0]} -> {result.date_range[1]}")

if result.warnings:
    print("\n[WARNING] Warnings:")
    for w in result.warnings:
        print(f"   {w}")

df = categorize_dataframe(result.df)

print("\n--- Sample (first 100 rows) ---")
print(df[["date", "description", "amount", "category"]].head(100).to_string())

print("\n--- Category Totals ---")
category_totals = df.groupby("category")["amount"].sum().sort_values()
for category, amount in category_totals.items():
    formatted_amount = format_indian_currency(amount)
    print(f"{category:20} {formatted_amount:>15}")

print("\n--- Uncategorized (check these) ---")
other = df[df["category"].isin(["Other", "Other Income"])]
print(other[["description", "amount"]].to_string())
