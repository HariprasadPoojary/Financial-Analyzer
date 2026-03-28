"""
FastAPI app — financial analyzer web interface.

Routes:
  GET  /                      → upload UI (with date range filter)
  POST /analyze               → process CSV(s), return report URL
  GET  /report/{id}           → serve generated HTML report
  GET  /review/{id}           → uncategorized transaction review UI
  POST /review/{id}           → apply reclassifications, regenerate report
  GET  /settings              → category editor UI
  GET  /api/rules             → return rules as JSON
  POST /api/rules             → save rules
  POST /api/rules/reset       → reset rules to defaults
"""

import pickle
import sys
import uuid
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

sys.path.insert(0, str(Path(__file__).parent))

from parser import merge_statements, parse_csv

from analyzer import analyze
from categorizer import categorize_dataframe
from report_builder import generate_report
from rules_store import (
    get_category_names,
    get_rules_as_dicts,
    reset_to_defaults,
    save_rules,
)

# ── Directories ───────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
REPORT_DIR = BASE_DIR / "reports"
SESSION_DIR = BASE_DIR / "sessions"
DATA_DIR = BASE_DIR / "data"
TEMPLATES_DIR = BASE_DIR / "app" / "templates"

for d in (UPLOAD_DIR, REPORT_DIR, SESSION_DIR, DATA_DIR):
    d.mkdir(exist_ok=True)

app = FastAPI(title="Financial Analyzer")


# ── Session helpers ───────────────────────────────────────────────────────────


def _load_session(session_id: str) -> dict | None:
    pkl = SESSION_DIR / f"{session_id}.pkl"
    if not pkl.exists():
        return None
    with open(pkl, "rb") as f:
        return pickle.load(f)


def _save_session(session_id: str, data: dict) -> None:
    with open(SESSION_DIR / f"{session_id}.pkl", "wb") as f:
        pickle.dump(data, f)


# ── Analyze ───────────────────────────────────────────────────────────────────


@app.post("/analyze")
async def analyze_statements(
    files: list[UploadFile] = File(...),
    date_from: str = Form(default=None),
    date_to: str = Form(default=None),
):
    if not files or all(f.filename == "" for f in files):
        return JSONResponse(status_code=400, content={"error": "No files uploaded."})

    session_id = uuid.uuid4().hex[:10]
    saved_paths, parse_results, all_warnings = [], [], []

    for file in files:
        if not file.filename or not file.filename.endswith(".csv"):
            return JSONResponse(
                status_code=400,
                content={"error": f"Only CSV files accepted. Got: {file.filename}"},
            )
        dest = UPLOAD_DIR / f"{session_id}_{file.filename}"
        dest.write_bytes(await file.read())
        saved_paths.append(dest)
        try:
            result = parse_csv(str(dest))
            parse_results.append(result)
            all_warnings.extend(result.warnings)
        except Exception as e:
            for p in saved_paths:
                p.unlink(missing_ok=True)
            return JSONResponse(
                status_code=422, content={"error": f"Failed to parse {file.filename}: {e}"}
            )

    df = parse_results[0].df if len(parse_results) == 1 else merge_statements(parse_results)

    # ── Date range filter ─────────────────────────────────────────────────────
    if date_from:
        try:
            df = df[df["date"] >= pd.to_datetime(date_from)]
        except Exception:
            pass
    if date_to:
        try:
            df = df[df["date"] <= pd.to_datetime(date_to)]
        except Exception:
            pass

    if df.empty:
        for p in saved_paths:
            p.unlink(missing_ok=True)
        return JSONResponse(
            status_code=422, content={"error": "No transactions in the selected date range."}
        )

    df = categorize_dataframe(df)
    _save_session(session_id, {"df": df, "warnings": all_warnings})

    analysis = analyze(df, all_warnings)
    report_path = REPORT_DIR / f"report_{session_id}.html"
    generate_report(analysis, str(report_path), session_id=session_id)

    for p in saved_paths:
        p.unlink(missing_ok=True)

    other_count = int((df["category"].isin(["Other", "Other Income"])).sum())
    return JSONResponse(content={"report_url": f"/report/{session_id}", "other_count": other_count})


# ── Report ────────────────────────────────────────────────────────────────────


@app.get("/report/{session_id}")
def get_report(session_id: str):
    path = REPORT_DIR / f"report_{session_id}.html"
    if not path.exists():
        return HTMLResponse(
            "<h2 style='font-family:sans-serif;padding:40px'>Report not found.</h2>",
            status_code=404,
        )
    return FileResponse(path, media_type="text/html")


# ── Uncategorized Review ──────────────────────────────────────────────────────


@app.get("/review/{session_id}", response_class=HTMLResponse)
def review_page(session_id: str):
    data = _load_session(session_id)
    if data is None:
        return HTMLResponse(
            "<h2 style='font-family:sans-serif;padding:40px'>Session not found.</h2>",
            status_code=404,
        )

    df = data["df"]
    other_df = df[df["category"].isin(["Other", "Other Income"])].copy()

    if other_df.empty:
        return HTMLResponse(
            f"""<html><body style='font-family:sans-serif;padding:40px;background:#0f172a;color:#e2e8f0'>
        <h2>✅ No uncategorized transactions!</h2><br>
        <a href='/report/{session_id}' style='color:#63cab7'>← Back to report</a></body></html>"""
        )

    categories = get_category_names()
    cat_options = "".join(f'<option value="{c}">{c}</option>' for c in categories)

    rows_html = ""
    for idx, row in other_df.iterrows():
        amt_class = "pos" if row["amount"] > 0 else "neg"
        amt_sign = "+" if row["amount"] > 0 else ""
        date_str = str(row["date"])[:10]
        desc = str(row["description"]).replace('"', "&quot;")
        rows_html += f"""
        <tr>
          <td class="mono muted">{date_str}</td>
          <td class="desc" title="{desc}">{desc}</td>
          <td class="{amt_class} mono">{amt_sign}₹{abs(row['amount']):,.0f}</td>
          <td><span class="cur-cat">{row['category']}</span></td>
          <td><select class="cat-select" data-idx="{idx}">
            <option value="">— keep as {row['category']} —</option>
            {cat_options}
          </select></td>
        </tr>"""

    return HTMLResponse(
        (TEMPLATES_DIR / "settings.html")
        .read_text(encoding="utf-8")
        .replace("__SESSION_ID__", session_id)
        .replace("__OTHER_COUNT__", str(len(other_df)))
        .replace("__ROWS__", rows_html)
        .replace("__REPORT_URL__", f"/report/{session_id}")
    )


@app.post("/review/{session_id}")
async def apply_review(session_id: str, request: Request):
    data = _load_session(session_id)
    if data is None:
        return JSONResponse(status_code=404, content={"error": "Session not found."})

    body = await request.json()
    overrides = {int(k): v for k, v in body.get("overrides", {}).items() if v}
    if not overrides:
        return JSONResponse(status_code=400, content={"error": "No changes submitted."})

    df = data["df"].copy()
    for idx, cat in overrides.items():
        if idx in df.index:
            df.at[idx, "category"] = cat

    _save_session(session_id, {"df": df, "warnings": data["warnings"]})
    analysis = analyze(df, data["warnings"])
    generate_report(analysis, str(REPORT_DIR / f"report_{session_id}.html"), session_id=session_id)

    return JSONResponse(content={"report_url": f"/report/{session_id}"})


# ── Settings / Category Editor ────────────────────────────────────────────────


@app.get("/settings", response_class=HTMLResponse)
def settings_page():
    return (TEMPLATES_DIR / "settings.html").read_text(encoding="utf-8")


@app.get("/api/rules")
def get_rules_api():
    return JSONResponse(content=get_rules_as_dicts())


@app.post("/api/rules")
async def save_rules_api(request: Request):
    try:
        rules = await request.json()
        save_rules(rules)
        return JSONResponse(content={"ok": True, "count": len(rules)})
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": str(e)})


@app.post("/api/rules/reset")
def reset_rules_api():
    reset_to_defaults()
    return JSONResponse(content={"ok": True})


# ── Upload UI ─────────────────────────────────────────────────────────────────


@app.get("/", response_class=HTMLResponse)
def index():
    """Serve the main HTML page with the file upload form."""
    return (TEMPLATES_DIR / "index.html").read_text(encoding="utf-8")
