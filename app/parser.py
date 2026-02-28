"""
CSV Parser — normalizes bank statement CSVs from different banks
into a single clean schema:

    date | description | amount | type (debit/credit)

Supported formats auto-detected:
    - Standard: Date, Description, Amount (negative = debit)
    - Split columns: Date, Description, Debit, Credit
    - OFX-style: Date, Name, Amount, Transaction Type
"""

import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

# ── Output schema ─────────────────────────────────────────────────────────────

NORMALIZED_COLUMNS = ["date", "description", "amount", "type"]


@dataclass
class ParseResult:
    df: pd.DataFrame  # normalized dataframe
    source_file: str  # original filename
    row_count: int
    date_range: tuple  # (min_date, max_date)
    warnings: list[str]  # non-fatal issues found during parsing


# ── Column name aliases (case-insensitive matching) ────────────────────────────

DATE_ALIASES = [
    "date",
    "transaction date",
    "trans date",
    "post date",
    "posted date",
    "value date",
    "booking date",
]

DESCRIPTION_ALIASES = [
    "description",
    "desc",
    "narrative",
    "details",
    "merchant",
    "merchant name",
    "name",
    "payee",
    "reference",
    "memo",
    "particulars",
    "transaction description",
    "transaction details",
    "beneficiary",
]

AMOUNT_ALIASES = [
    "amount",
    "transaction amount",
    "net amount",
    "value",
]

DEBIT_ALIASES = [
    "debit",
    "debit amount",
    "withdrawal",
    "withdrawals",
    "dr",
    "payments",
    "payment",
    "charges",
    "charge",
]

CREDIT_ALIASES = [
    "credit",
    "credit amount",
    "deposit",
    "deposits",
    "cr",
    "receipts",
]


def _normalize_col_name(name: str) -> str:
    return name.strip().lower()


def _find_column(df_cols: list[str], aliases: list[str]) -> str | None:
    """Return the first df column that matches any alias."""
    normalized = {_normalize_col_name(c): c for c in df_cols}
    for alias in aliases:
        if alias in normalized:
            return normalized[alias]
    return None


def _detect_header_row(raw: pd.DataFrame) -> int:
    """
    Some bank CSVs have metadata rows before the actual header.
    Scan the first 10 rows to find the row that contains the most
    recognizable column names.
    """
    all_aliases = (
        DATE_ALIASES + DESCRIPTION_ALIASES + AMOUNT_ALIASES + DEBIT_ALIASES + CREDIT_ALIASES
    )

    best_row, best_score = 0, 0
    for i in range(min(10, len(raw))):
        row_values = [str(v).strip().lower() for v in raw.iloc[i].values]
        score = sum(1 for v in row_values if v in all_aliases)
        if score > best_score:
            best_score, best_row = score, i

    return best_row if best_score >= 2 else 0


def _parse_amount(value) -> float | None:
    """Clean and convert amount strings like '$1,234.56' or '(500.00)'."""
    if pd.isna(value):
        return None
    s = str(value).strip()
    if not s or s in ("-", ""):
        return None
    # Handle accounting negatives: (500.00) → -500.00
    negative = s.startswith("(") and s.endswith(")")
    s = re.sub(r"[()$£€,\s]", "", s)
    try:
        val = float(s)
        return -abs(val) if negative else val
    except ValueError:
        return None


def _parse_date(series: pd.Series) -> pd.Series:
    """Try multiple date formats, return normalized datetime series."""
    formats = [
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%d-%m-%Y",
        "%m-%d-%Y",
        "%d %b %Y",
        "%d %B %Y",
        "%Y%m%d",
    ]
    for fmt in formats:
        try:
            parsed = pd.to_datetime(series, format=fmt, dayfirst=False)
            if parsed.notna().sum() > len(series) * 0.8:
                return parsed
        except Exception:
            continue
    # Last resort: let pandas infer
    return pd.to_datetime(series, format="mixed", dayfirst=True, errors="coerce")


# ── Core parsing logic ─────────────────────────────────────────────────────────


def _load_raw_csv(filepath: str) -> pd.DataFrame:
    """Load CSV, trying common encodings."""
    for encoding in ("utf-8", "latin-1", "cp1252"):
        try:
            return pd.read_csv(filepath, encoding=encoding, header=None, dtype=str)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Cannot decode file: {filepath}")


def _build_normalized_df(
    df: pd.DataFrame,
    date_col: str,
    desc_col: str,
    amount_col: str | None,
    debit_col: str | None,
    credit_col: str | None,
    warnings: list[str],
) -> pd.DataFrame:
    """Build the normalized dataframe from detected columns."""

    result = pd.DataFrame()

    # Date
    result["date"] = _parse_date(df[date_col])
    bad_dates = result["date"].isna().sum()
    if bad_dates:
        warnings.append(f"{bad_dates} rows had unparseable dates and were dropped.")

    # Description
    result["description"] = df[desc_col].fillna("").str.strip()

    # Amount — two strategies
    if amount_col:
        result["amount"] = df[amount_col].apply(_parse_amount)
        # Positive = credit, negative = debit
        result["type"] = result["amount"].apply(
            lambda x: "credit" if (x is not None and x > 0) else "debit"
        )
    elif debit_col and credit_col:
        debits = df[debit_col].apply(_parse_amount).fillna(0)
        credits = df[credit_col].apply(_parse_amount).fillna(0)
        # Debits stored as negative amounts
        result["amount"] = credits - debits
        result["type"] = result["amount"].apply(lambda x: "credit" if x >= 0 else "debit")
    elif debit_col:
        result["amount"] = (
            df[debit_col].apply(_parse_amount).apply(lambda x: -abs(x) if x is not None else None)
        )
        result["type"] = "debit"
    elif credit_col:
        result["amount"] = df[credit_col].apply(_parse_amount)
        result["type"] = "credit"
    else:
        raise ValueError("No amount, debit, or credit column found in CSV.")

    # Drop rows with null dates or null amounts
    before = len(result)
    result = result.dropna(subset=["date", "amount"])
    dropped = before - len(result)
    if dropped:
        warnings.append(f"{dropped} rows dropped due to missing date or amount.")

    result["amount"] = result["amount"].astype(float)
    result["date"] = pd.to_datetime(result["date"])
    result = result.sort_values("date").reset_index(drop=True)

    return result


def parse_csv(filepath: str) -> ParseResult:
    """
    Main entry point. Parse a bank statement CSV and return a ParseResult
    with a normalized dataframe.
    """
    warnings = []
    source_file = Path(filepath).name

    raw = _load_raw_csv(filepath)

    if raw.empty:
        raise ValueError(f"File is empty: {filepath}")

    # Find the actual header row
    header_row = _detect_header_row(raw)
    if header_row > 0:
        warnings.append(f"Skipped {header_row} metadata row(s) before header.")

    # Re-read with correct header
    df = pd.read_csv(
        filepath,
        skiprows=header_row,
        dtype=str,
        encoding="latin-1",
    )
    df.columns = [str(c).strip() for c in df.columns]

    # Detect columns
    date_col = _find_column(list(df.columns), DATE_ALIASES)
    desc_col = _find_column(list(df.columns), DESCRIPTION_ALIASES)
    amount_col = _find_column(list(df.columns), AMOUNT_ALIASES)
    debit_col = _find_column(list(df.columns), DEBIT_ALIASES)
    credit_col = _find_column(list(df.columns), CREDIT_ALIASES)

    if not date_col:
        raise ValueError(f"Could not find a date column. Found columns: {list(df.columns)}")
    if not desc_col:
        raise ValueError(f"Could not find a description column. Found columns: {list(df.columns)}")
    if not (amount_col or debit_col or credit_col):
        raise ValueError(f"Could not find any amount column. Found columns: {list(df.columns)}")

    normalized = _build_normalized_df(
        df, date_col, desc_col, amount_col, debit_col, credit_col, warnings
    )

    date_range = (
        normalized["date"].min().date(),
        normalized["date"].max().date(),
    )

    return ParseResult(
        df=normalized,
        source_file=source_file,
        row_count=len(normalized),
        date_range=date_range,
        warnings=warnings,
    )


def merge_statements(results: list[ParseResult]) -> pd.DataFrame:
    """Merge multiple parsed statements, deduplicate by (date, description, amount)."""
    if not results:
        raise ValueError("No parse results to merge.")
    combined = pd.concat([r.df for r in results], ignore_index=True)
    before = len(combined)
    combined = combined.drop_duplicates(subset=["date", "description", "amount"])
    after = len(combined)
    if before != after:
        print(f"[parser] Removed {before - after} duplicate transactions.")
    return combined.sort_values("date").reset_index(drop=True)
