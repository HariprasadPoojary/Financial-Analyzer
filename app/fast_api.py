"""
FastAPI app — handles file upload, runs the analysis pipeline,
serves the generated HTML report.
"""

import os
import sys
import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
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
                raise HTTPException(422, f"Failed to parse {Path(path).name}: {e}")

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
    return UPLOAD_PAGE


UPLOAD_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Financial Analyzer</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    :root {
      --bg: #080c12; --surface: #0e1520; --border: rgba(99,202,183,0.15);
      --accent: #63cab7; --accent2: #f0a500; --text: #e8f0ee;
      --muted: #5a7a72; --danger: #e05555;
    }
    body {
      background: var(--bg); color: var(--text);
      font-family: 'Syne', sans-serif; min-height: 100vh;
      display: flex; flex-direction: column; align-items: center;
      justify-content: center; padding: 24px; overflow-x: hidden;
    }
    body::before {
      content: ''; position: fixed; inset: 0;
      background-image:
        linear-gradient(rgba(99,202,183,0.03) 1px, transparent 1px),
        linear-gradient(90deg, rgba(99,202,183,0.03) 1px, transparent 1px);
      background-size: 48px 48px; pointer-events: none; z-index: 0;
    }
    .orb { position: fixed; border-radius: 50%; filter: blur(120px);
           pointer-events: none; z-index: 0; opacity: 0.35; }
    .orb-1 { width: 500px; height: 500px; background: #0d4a3f; top: -150px; right: -100px; }
    .orb-2 { width: 400px; height: 400px; background: #3a2500; bottom: -100px; left: -80px; }
    .container { position: relative; z-index: 1; width: 100%; max-width: 560px; }
    .header { text-align: center; margin-bottom: 48px; }
    .logo-mark {
      display: inline-flex; align-items: center; justify-content: center;
      width: 56px; height: 56px; border-radius: 14px;
      background: linear-gradient(135deg, #0d4a3f, #1a7a67);
      border: 1px solid var(--accent); font-size: 24px; margin-bottom: 20px;
      box-shadow: 0 0 40px rgba(99,202,183,0.2);
    }
    h1 {
      font-size: 2.4rem; font-weight: 800; line-height: 1.1; letter-spacing: -0.03em;
      background: linear-gradient(135deg, #e8f0ee 0%, var(--accent) 100%);
      -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
    }
    .subtitle { color: var(--muted); font-size: 0.9rem; margin-top: 10px;
                font-family: 'DM Mono', monospace; letter-spacing: 0.02em; }
    .dropzone {
      border: 1.5px dashed var(--border); border-radius: 16px;
      padding: 48px 32px; text-align: center; cursor: pointer;
      transition: all 0.25s ease; background: var(--surface); position: relative; overflow: hidden;
    }
    .dropzone::before {
      content: ''; position: absolute; inset: 0;
      background: radial-gradient(ellipse at 50% 0%, rgba(99,202,183,0.06) 0%, transparent 70%);
      pointer-events: none;
    }
    .dropzone:hover, .dropzone.drag-over {
      border-color: var(--accent); background: #0f1c1a;
      box-shadow: 0 0 40px rgba(99,202,183,0.08), inset 0 0 40px rgba(99,202,183,0.03);
    }
    .drop-icon { font-size: 2.4rem; margin-bottom: 16px; display: block;
                 animation: float 3s ease-in-out infinite; }
    @keyframes float { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-6px); } }
    .drop-title { font-size: 1rem; font-weight: 700; color: var(--text); margin-bottom: 6px; }
    .drop-sub { font-size: 0.8rem; color: var(--muted); font-family: 'DM Mono', monospace; }
    .drop-sub span { color: var(--accent); }
    input[type="file"] { display: none; }
    #file-list { margin-top: 16px; display: flex; flex-direction: column; gap: 8px; }
    .file-item {
      display: flex; align-items: center; gap: 10px;
      background: var(--surface); border: 1px solid var(--border);
      border-radius: 9px; padding: 10px 14px; font-size: 0.82rem;
      animation: slide-in 0.2s ease;
    }
    @keyframes slide-in { from { opacity: 0; transform: translateY(-6px); } to { opacity: 1; transform: translateY(0); } }
    .file-name { flex: 1; color: var(--text); font-family: 'DM Mono', monospace;
                 overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .file-size { color: var(--muted); font-family: 'DM Mono', monospace; font-size: 0.75rem; }
    .file-remove { cursor: pointer; color: var(--muted); font-size: 1rem;
                   transition: color 0.2s; background: none; border: none; padding: 2px 4px; }
    .file-remove:hover { color: var(--danger); }
    .btn {
      width: 100%; margin-top: 20px; padding: 15px 24px; border-radius: 10px; border: none;
      background: linear-gradient(135deg, #0d5c4e, #1a7a67); color: #e8f0ee;
      font-family: 'Syne', sans-serif; font-size: 0.95rem; font-weight: 700;
      letter-spacing: 0.04em; cursor: pointer; transition: all 0.2s ease;
      border: 1px solid rgba(99,202,183,0.3); box-shadow: 0 4px 24px rgba(99,202,183,0.1);
      display: none;
    }
    .btn:hover:not(:disabled) { transform: translateY(-1px); box-shadow: 0 8px 32px rgba(99,202,183,0.2); }
    .btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }
    .btn.visible { display: block; }
    #progress { display: none; margin-top: 24px; text-align: center; }
    .spinner {
      width: 36px; height: 36px; margin: 0 auto 14px;
      border: 2px solid rgba(99,202,183,0.15); border-top-color: var(--accent);
      border-radius: 50%; animation: spin 0.7s linear infinite;
    }
    @keyframes spin { to { transform: rotate(360deg); } }
    .progress-steps { display: flex; flex-direction: column; gap: 6px; }
    .step { font-size: 0.78rem; font-family: 'DM Mono', monospace; color: var(--muted);
            transition: color 0.3s; display: flex; align-items: center; gap: 8px; justify-content: center; }
    .step.active { color: var(--accent); }
    .step.done { color: var(--text); }
    .step-dot { width: 6px; height: 6px; border-radius: 50%; background: currentColor; flex-shrink: 0; }
    #error-box {
      display: none; margin-top: 16px;
      background: rgba(224,85,85,0.1); border: 1px solid rgba(224,85,85,0.3);
      border-radius: 9px; padding: 12px 16px;
      font-size: 0.82rem; color: #e08080; font-family: 'DM Mono', monospace;
    }
    .footer { margin-top: 32px; text-align: center; font-size: 0.72rem;
              color: var(--muted); font-family: 'DM Mono', monospace; }
  </style>
</head>
<body>
  <div class="orb orb-1"></div>
  <div class="orb orb-2"></div>
  <div class="container">
    <div class="header">
      <div class="logo-mark">₹</div>
      <h1>Financial<br>Analyzer</h1>
      <p class="subtitle">// drop your bank statements → get insights</p>
    </div>
    <div class="dropzone" id="dropzone" onclick="document.getElementById('file-input').click()">
      <span class="drop-icon">📂</span>
      <div class="drop-title">Drop CSV files here</div>
      <div class="drop-sub">or click to browse &nbsp;·&nbsp; <span>multiple files supported</span></div>
      <input type="file" id="file-input" accept=".csv" multiple/>
    </div>
    <div id="file-list"></div>
    <button class="btn" id="analyze-btn" onclick="submitFiles()">Generate Report →</button>
    <div id="progress">
      <div class="spinner"></div>
      <div class="progress-steps">
        <div class="step" id="step-1"><span class="step-dot"></span>Parsing transactions...</div>
        <div class="step" id="step-2"><span class="step-dot"></span>Categorizing spending...</div>
        <div class="step" id="step-3"><span class="step-dot"></span>Running analysis...</div>
        <div class="step" id="step-4"><span class="step-dot"></span>Generating report...</div>
      </div>
    </div>
    <div id="error-box"></div>
    <div class="footer">processes locally · no data leaves your machine</div>
  </div>
<script>
  let selectedFiles = [];
  const zone = document.getElementById('dropzone');
  zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('drag-over'); });
  zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
  zone.addEventListener('drop', e => { e.preventDefault(); zone.classList.remove('drag-over'); addFiles([...e.dataTransfer.files]); });
  document.getElementById('file-input').addEventListener('change', e => addFiles([...e.target.files]));

  function addFiles(newFiles) {
    const csvs = newFiles.filter(f => f.name.toLowerCase().endsWith('.csv'));
    csvs.forEach(f => {
      if (!selectedFiles.find(x => x.name === f.name && x.size === f.size)) selectedFiles.push(f);
    });
    renderFileList();
  }

  function removeFile(idx) { selectedFiles.splice(idx, 1); renderFileList(); }

  function renderFileList() {
    document.getElementById('file-list').innerHTML = selectedFiles.map((f, i) => `
      <div class="file-item">
        <span>📄</span>
        <span class="file-name">${f.name}</span>
        <span class="file-size">${(f.size/1024).toFixed(1)} KB</span>
        <button class="file-remove" onclick="removeFile(${i})">✕</button>
      </div>`).join('');
    document.getElementById('analyze-btn').classList.toggle('visible', selectedFiles.length > 0);
  }

  async function submitFiles() {
    if (!selectedFiles.length) return;
    const btn = document.getElementById('analyze-btn');
    const progress = document.getElementById('progress');
    const errorBox = document.getElementById('error-box');
    btn.disabled = true; btn.style.display = 'none';
    progress.style.display = 'block'; errorBox.style.display = 'none';
    const steps = ['step-1','step-2','step-3','step-4'];
    let stepIdx = 0;
    setStep(steps[0], 'active');
    const timer = setInterval(() => {
      if (stepIdx < steps.length - 1) { setStep(steps[stepIdx], 'done'); stepIdx++; setStep(steps[stepIdx], 'active'); }
    }, 900);
    const form = new FormData();
    selectedFiles.forEach(f => form.append('files', f));
    try {
      const res = await fetch('/analyze', { method: 'POST', body: form });
      clearInterval(timer);
      steps.forEach(s => setStep(s, 'done'));
      if (!res.ok) { const err = await res.json(); throw new Error(err.error || 'Unknown error'); }
      const data = await res.json();
      await new Promise(r => setTimeout(r, 400));
      window.location.href = data.report_url;
    } catch(err) {
      clearInterval(timer);
      progress.style.display = 'none';
      btn.disabled = false; btn.style.display = 'block';
      errorBox.style.display = 'block'; errorBox.textContent = '⚠ ' + err.message;
    }
  }

  function setStep(id, state) {
    const el = document.getElementById(id);
    el.classList.remove('active','done');
    if (state) el.classList.add(state);
  }
</script>
</body>
</html>
"""
