from __future__ import annotations
import re
from .parsing import parse_amount
from .schemas import LineItem

STOP = re.compile(r"\b(subtotal|tax|total|discount|shipping|payment|synthetic document)\b", re.I)
HEADER = re.compile(r"\b(item|description)\b.*\b(qty|quantity)\b.*\b(price|rate)\b.*\b(amount|total)\b", re.I)

def extract_line_items(text: str, document_type: str) -> list[LineItem]:
    items, in_table = [], False
    for raw in text.splitlines():
        line = re.sub(r"\s+", " ", raw).strip()
        if HEADER.search(line.replace("|", " ")) or re.match(r"^ITEM(?:\s|\||$)", line, re.I):
            in_table = True; continue
        if not in_table or STOP.search(line): 
            if in_table and STOP.search(line): break
            continue
        parts = [p.strip() for p in line.split("|") if p.strip()]
        candidate = _parse_parts(parts, line)
        if candidate: items.append(candidate)
    return items

def _parse_parts(parts: list[str], raw: str) -> LineItem | None:
    if len(parts) >= 4:
        desc = " ".join(parts[:-3]).strip()
        qty_match = re.fullmatch(r"\d+(?:\.\d+)?", parts[-3])
        unit, total = parse_amount(parts[-2]), parse_amount(parts[-1])
        if desc and qty_match and unit is not None and total is not None:
            return LineItem(description=desc, quantity=float(qty_match.group()),
                unit_price=unit, line_total=total, raw_text=raw, confidence=.95)
    # OCR sometimes removes separators but preserves a trailing qty/price/amount pattern.
    match = re.match(r"(.+?)\s+(\d+(?:\.\d+)?)\s+\$?([\d,.]+)\s+\$?([\d,.]+)$", raw)
    if match:
        return LineItem(description=match.group(1).strip(), quantity=float(match.group(2)),
            unit_price=parse_amount(match.group(3)), line_total=parse_amount(match.group(4)),
            raw_text=raw, confidence=.85)
    return None
