"""
FastAPI app — handles file upload, runs the analysis pipeline,
serves the generated HTML report.
"""

import os
import sys
import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

sys.path.insert(0, str(Path(__file__).parent))

from parser import merge_statements, parse_csv

from analyzer import analyze
from categorizer import categorize_dataframe
from report_builder import generate_report

# ── Dirs ──────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
REPORT_DIR = BASE_DIR / "reports"
UPLOAD_DIR.mkdir(exist_ok=True)
REPORT_DIR.mkdir(exist_ok=True)

app = FastAPI(title="Financial Analyzer")


# ── Upload + analyze endpoint ─────────────────────────────────────────────────


@app.post("/analyze")
async def analyze_statements(files: list[UploadFile] = File(...)):
    if not files:
        raise HTTPException(400, "No files uploaded.")

    saved_paths = []
    try:
        for file in files:
            if not file.filename or not file.filename.endswith(".csv"):
                raise HTTPException(400, f"Only CSV files accepted. Got: {file.filename}")
            dest = UPLOAD_DIR / f"{uuid.uuid4().hex}_{file.filename}"
            dest.write_bytes(await file.read())
            saved_paths.append(str(dest))

        parse_results = []
        all_warnings = []
        for path in saved_paths:
            try:
                r = parse_csv(path)
                parse_results.append(r)
                all_warnings.extend(r.warnings)
            except Exception as e:
                raise HTTPException(422, f"🤔 Failed to parse {Path(path).name}: {e}")

        merged_df = merge_statements(parse_results)
        categorized = categorize_dataframe(merged_df)
        result = analyze(categorized, all_warnings)

        report_id = uuid.uuid4().hex
        report_path = REPORT_DIR / f"report_{report_id}.html"
        generate_report(result, str(report_path))

        return JSONResponse(
            {
                "report_url": f"/report/{report_id}",
                "summary": {
                    "transactions": result.transactions.shape[0],
                    "date_from": result.date_from,
                    "date_to": result.date_to,
                    "total_income": result.total_income,
                    "total_expenses": result.total_expenses,
                    "net_savings": result.net_savings,
                    "savings_rate": result.savings_rate,
                },
            }
        )

    finally:
        for path in saved_paths:
            try:
                os.remove(path)
            except Exception:
                pass


@app.get("/report/{report_id}")
def get_report(report_id: str):
    if not all(c in "0123456789abcdef" for c in report_id):
        raise HTTPException(400, "Invalid report ID.")
    path = REPORT_DIR / f"report_{report_id}.html"
    if not path.exists():
        raise HTTPException(404, "Report not found.")
    return FileResponse(path, media_type="text/html")


@app.get("/", response_class=HTMLResponse)
def index():
    return (Path(__file__).parent / "templates" / "index.html").read_text(encoding="utf-8")
