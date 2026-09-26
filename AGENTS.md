# Agent guide

## Application purpose

This repository contains a local financial statement analyzer. Users upload one or more bank statement CSV files; the app normalizes and categorizes transactions, calculates summaries, and generates an interactive, self-contained HTML report. Categorization is deterministic and rule based. There is no AI/LLM integration, paid API, or remote analysis service.

The application is aimed at personal bank statements, including Indian bank formats and payment descriptions such as UPI, NEFT, IMPS, ACH, and merchant names. Keep processing local and avoid adding paid services or external data dependencies without a direct request.

## Run and project layout

- Python 3.14+ is specified in `pyproject.toml`; dependencies are managed with `uv`.
- Validate Python code with `uv run ruff check .` and `uv run mypy` before committing. Install the Git hooks with `uv run pre-commit install`; the configured pre-commit hooks run both checks.
- Start the web application from the repository root with `uvicorn app.fast_api:app --reload --host 0.0.0.0 --port 8000`.
- `app/` is a Python package. Imports use `from app.<module> import ...`.
- `main.py` and `test_pipeline.py` are CLI/example scripts, not the FastAPI entry point. The web entry point is `app/fast_api.py`.
- `app/templates/index.html`, `settings.html`, and `review.html` are plain HTML pages read directly from disk. Their JavaScript calls the JSON/API routes for dynamic behavior. `report.html` is the report template rendered by Jinja2 in `app/report_builder.py`.
- `data/rules.json` stores user-edited rules when present. `uploads/`, `reports/`, and `sessions/` hold temporary uploads, generated reports, and session state; these directories are ignored by Git. Do not treat their contents as source code or overwrite user data casually.
- `tests/` contains pytest tests for parser, categorizer, rules store, analyzer, report builder, and integration flow. Pytest configuration is in `pyproject.toml`.

## Request flow and module responsibilities

```text
CSV upload(s)
  -> app.parser.parse_csv()
  -> app.parser.merge_statements() (when multiple files are uploaded)
  -> app.categorizer.categorize_dataframe()
  -> app.analyzer.analyze()
  -> app.report_builder.generate_report()
```

- `app/const.py`: column-name aliases and built-in default category rules.
- `app/parser.py`: detects headers and bank columns, parses dates and amounts, normalizes to `date`, `description`, `amount`, and `type`, and reports non-fatal parsing warnings. `ParseResult` exposes the normalized dataframe as `.df`.
- `app/categorizer.py`: compiles rule patterns and assigns a category. Rules are evaluated in order; the first matching rule wins. Unmatched positive amounts become `Other Income`; other unmatched transactions become `Other`. Optional row-index overrides support manual review.
- `app/rules_store.py`: reads `data/rules.json` when available and otherwise uses `CATEGORY_RULES` from `const.py`; saves or resets rules. The categorizer loads rules for each dataframe categorization so UI edits apply to subsequent analyses without restarting the server.
- `app/analyzer.py`: transforms the categorized dataframe into an `AnalysisResult` containing totals, monthly/category summaries, merchant lists, daily spending, warnings, and report transactions. `Income` and `Other Income` are treated as income categories.
- `app/report_builder.py`: builds Plotly charts and renders `app/templates/report.html` with Jinja2. Plotly output is HTML and chart template variables must remain marked safe in the template so they render as charts rather than escaped text. Plotly is included inline, so generated reports work offline.
- `app/fast_api.py`: defines upload, report, review, settings, and rules API routes. It saves a categorized dataframe and parser warnings in a pickle session so review edits can regenerate the report without parsing the CSVs again.

## Categorization pattern syntax

The settings UI accepts these patterns, implemented by `pattern_to_regex()` in `app/categorizer.py`:

- `zomato`: case-insensitive literal substring (default; punctuation is escaped).
- `case:Zomato`: case-sensitive literal substring.
- `re:\bUPI/\w+`: raw, case-insensitive regular expression.
- `re:case:[A-Z]+`: raw, case-sensitive regular expression.

Use plain literal patterns for ordinary merchant names. Use raw regex only when matching structure requires it. Rule ordering matters because the first matching category is returned. The transaction scope is `credit`, `debit`, or `both`.

## Web workflow

- `GET /`: upload page.
- `POST /analyze`: accepts CSV uploads and optional `date_from` / `date_to` fields, parses and merges statements, applies filtering and categorization, persists the session, generates a report, and returns a report URL and uncategorized count.
- `GET /report/{session_id}`: serves the generated report.
- `GET /review/{session_id}` and `POST /review/{session_id}`: show unmatched transactions and apply category overrides, then regenerate the report.
- `GET /settings`, `GET /api/rules`, `POST /api/rules`, and `POST /api/rules/reset`: serve and manage categorization rules.

Session IDs are short UUID-derived identifiers. Session files use Python pickle and are local application state, not a portable or untrusted interchange format.

## Current repository findings and follow-up points

- The user-provided project summary described the review page as `review.html`, but the current `review_page()` implementation in `app/fast_api.py` reads `settings.html` and substitutes review-specific placeholders. Confirm and correct this route/template mismatch when working on the review UI; do not assume the summary overrides the checked-in code.
- `app/report_builder.py` currently loads `app/templates/report.html` using `Environment.from_string()`. It does not use a `FileSystemLoader` for app pages.
- The checked-in README describes rules as regex patterns, but the current categorizer also supports plain literal and case-sensitive literal modes. Keep documentation aligned with the actual syntax when editing it.
- Root-level `main.py` and `test_pipeline.py` contain example paths and scripts; verify paths against the current layout before relying on them.

## Change guidance

- Preserve the normalized transaction schema (`date`, `description`, `amount`, `type`) and add `category` during categorization. Update downstream consumers if that contract changes.
- Keep CSV format aliases in `app/const.py`; avoid duplicating bank-specific aliases in parser logic.
- Keep ordinary app pages static HTML with browser-side API calls unless there is a clear reason to change the rendering model. Keep report-specific Jinja2 rendering in `report_builder.py`.
- When changing rules, maintain compatibility between built-in tuples, `data/rules.json`, the rules API, settings UI, and categorizer pattern syntax.
- The app handles private financial records. Avoid logging statement contents, exposing uploaded files, or adding network transmission of transaction data.
