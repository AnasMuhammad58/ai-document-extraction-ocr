from __future__ import annotations
from datetime import datetime
import re

def parse_amount(value: str | None) -> float | None:
    if not value: return None
    match = re.search(r"-?\s*(?:USD|\$)?\s*([\d,]+(?:\.\d{1,2})?)", value, re.I)
    if not match: return None
    try: return float(match.group(1).replace(",", ""))
    except ValueError: return None

def parse_date(value: str | None) -> str | None:
    if not value: return None
    match = re.search(r"\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{2,4}", value)
    if not match: return None
    token = match.group()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%m-%d-%Y", "%m/%d/%y"):
        try: return datetime.strptime(token, fmt).date().isoformat()
        except ValueError: continue
    return None

def normalize_currency(value: str | None) -> str | None:
    if not value: return None
    upper = value.upper()
    if "$" in value or "USD" in upper: return "USD"
    return upper if upper in {"EUR", "GBP", "CAD", "AUD"} else None

