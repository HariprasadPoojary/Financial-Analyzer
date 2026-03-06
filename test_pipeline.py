import sys

sys.path.insert(0, "app")

from app.analyzer import analyze
from app.categorizer import categorize_dataframe
from app.parser import parse_csv
from app.report_builder import generate_report

# ← Point this to your actual CSV file
AXIS_CSV_PATH = "app\\uploads\\Axis_statement_last_3_months.csv"
SBI_CSV_PATH = "app\\uploads\\SBI_statement_last_3_months.csv"
OUTPUT = "reports/report.html"

# Run the pipeline
result = parse_csv(AXIS_CSV_PATH)
print(
    f"✅ Parsed {result.row_count} transactions ({result.date_range[0]} → {result.date_range[1]})"
)

df = categorize_dataframe(result.df)
print(f"✅ Categorized — uncategorized: {len(df[df['category'].isin(['Other', 'Other Income'])])}")

analysis = analyze(df, result.warnings)
print(
    f"✅ Analyzed — income: ₹{analysis.total_income:,.0f}, expenses: ₹{analysis.total_expenses:,.0f}"
)

generate_report(analysis, OUTPUT)
print(f"✅ Report saved → {OUTPUT}")

import os

# Open it automatically
import webbrowser

webbrowser.open(f"file://{os.path.abspath(OUTPUT)}")
