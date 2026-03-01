import sys

sys.path.insert(0, ".")

from app.categorizer import categorize_dataframe
from app.parser import parse_csv

# ← Point this to your actual CSV file
CSV_PATH = "app\\uploads\\AxisBank_Dec_Month_Statement.csv"

result = parse_csv(CSV_PATH)

print(f"✅ Parsed {result.row_count} transactions")
print(f"📅 Date range: {result.date_range[0]} → {result.date_range[1]}")

if result.warnings:
    print("\n⚠️  Warnings:")
    for w in result.warnings:
        print(f"   {w}")

df = categorize_dataframe(result.df)

print("\n--- Sample (first 10 rows) ---")
print(df[["date", "description", "amount", "category"]].head(10).to_string())

print("\n--- Category Totals ---")
print(df.groupby("category")["amount"].sum().sort_values().to_string())

print("\n--- Uncategorized (check these) ---")
other = df[df["category"].isin(["Other", "Other Income"])]
print(other[["description", "amount"]].to_string())
