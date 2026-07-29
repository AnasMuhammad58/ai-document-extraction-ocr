from __future__ import annotations
import re
from .parsing import normalize_currency, parse_amount, parse_date
from .schemas import FieldEvidence, InvoiceResult, ReceiptResult

def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("|", " ")).strip(" :-")

def _match(text: str, patterns: list[str], parser=lambda x: _clean(x), confidence=.92):
    for pattern in patterns:
        match = re.search(pattern, text, re.I | re.M)
        if match:
            raw = match.group(0)
            value = parser(match.group(1))
            if value is not None:
                return value, FieldEvidence(value=value, raw_matched_text=raw,
                    extraction_method="keyword_regex", confidence=confidence,
                    source_line=raw)
    return None, FieldEvidence()

def _first_content_lines(text: str) -> list[str]:
    return [_clean(x) for x in text.splitlines() if _clean(x)]

def extract_fields(text: str, document_type: str):
    evidence: dict[str, FieldEvidence] = {}
    lines = _first_content_lines(text)
    searchable = text.replace("|", " ")
    name = next((x for x in lines[:4] if not re.search(r"\b(invoice|receipt|synthetic)\b", x, re.I)), None)
    address = lines[1] if len(lines) > 1 else None
    if document_type == "invoice":
        values = {"vendor_name": name, "vendor_address": address}
        rules = {
            "invoice_number": ([r"(?:No|Invoice\s*(?:No|Number|#))\s*[:#]?\s*([A-Z]{1,5}-[\d-]+)"], _clean),
            "invoice_date": ([r"\bDate\s*[:|]?\s*(\d{4}[-/]\d{1,2}[-/]\d{1,2})"], parse_date),
            "due_date": ([r"\bDue(?:\s*Date)?\s*[:|]?\s*(\d{4}[-/]\d{1,2}[-/]\d{1,2})"], parse_date),
            "purchase_order": ([r"(?:Purchase\s*Order|PO)\s*[:#]?\s*([A-Z]{0,3}-?\d{4,})"], _clean),
            "subtotal": ([r"(?im)^\s*Subtotal\s*(?:\||:)?\s*(\$?[\d,.]+)"], parse_amount),
            "tax_amount": ([r"(?im)^\s*Tax(?:\s+Amount)?\s*(?:\||:)?\s*(\$?[\d,.]+)"], parse_amount),
            "discount": ([r"(?im)^\s*Discount\s*(?:\||:)?\s*(\$?[\d,.]+)"], parse_amount),
            "shipping": ([r"(?im)^\s*Shipping\s*(?:\||:)?\s*(\$?[\d,.]+)"], parse_amount),
            "total_amount": ([r"(?im)^\s*TOTAL\s*(?:\||:)?\s*(\$?[\d,.]+)"], parse_amount),
            "payment_terms": ([r"Payment\s*Terms?\s*[:|]?\s*([^\n|]+)"], _clean),
            "vendor_email": ([r"([\w.+-]+@[\w.-]+\.[A-Za-z]{2,})"], _clean),
            "vendor_phone": ([r"(\+?\d{1,3}\s+\d{3}\s+\d{3}\s+\d{4})"], _clean),
            "tax_rate": ([r"Tax\s*(?:Rate)?\s*[:|]?\s*(\d+(?:\.\d+)?)\s*%"], parse_amount),
        }
        for field, (patterns, parser) in rules.items():
            values[field], evidence[field] = _match(searchable, patterns, parser)
        bill_index = next((i for i,x in enumerate(lines) if re.search(r"\bBILL TO\b", x, re.I)), -1)
        values["customer_name"] = lines[bill_index+1] if 0 <= bill_index < len(lines)-1 else None
        values["customer_address"] = lines[bill_index+2] if 0 <= bill_index < len(lines)-2 else None
        for f in ("vendor_name","vendor_address","customer_name","customer_address"):
            evidence[f] = FieldEvidence(value=values[f], raw_matched_text=values[f],
                extraction_method="position_anchor", confidence=.8 if values[f] else 0,
                source_line=values[f])
        values["currency"] = normalize_currency(searchable) or ("USD" if "$" in searchable else None)
        evidence["currency"] = FieldEvidence(value=values["currency"], raw_matched_text="$" if "$" in text else None,
            extraction_method="symbol_normalization", confidence=.9 if values["currency"] else 0)
        return InvoiceResult(**values), evidence
    values = {"merchant_name": name, "merchant_address": address}
    rules = {
        "receipt_number": ([r"(?:No|Receipt\s*(?:No|Number|#))\s*[:#]?\s*([A-Z]{1,5}-[\d-]+)"], _clean),
        "transaction_date": ([r"\bDate\s*[:|]?\s*(\d{4}[-/]\d{1,2}[-/]\d{1,2})"], parse_date),
        "transaction_time": ([r"(?:Time|Transaction\s*Time)\s*[:|]?\s*(\d{1,2}:\d{2})"], _clean),
        "subtotal": ([r"(?im)^\s*Subtotal\s*(?:\||:)?\s*(\$?[\d,.]+)"], parse_amount),
        "tax_amount": ([r"(?im)^\s*Tax\s*(?:\||:)?\s*(\$?[\d,.]+)"], parse_amount),
        "total_amount": ([r"(?im)^\s*TOTAL\s*(?:\||:)?\s*(\$?[\d,.]+)"], parse_amount),
        "payment_method": ([r"(?:Payment\s*Method|Paid)\s*[:|]?\s*(VISA|MASTERCARD|CASH|AMEX)"], _clean),
        "last_four_digits": ([r"(?:ending|last\s*four|card)\D*(\d{4})"], _clean),
        "cashier": ([r"Cashier\s*[:|]?\s*([^\n|]+)"], _clean),
        "merchant_phone": ([r"(\+?\d{1,3}\s+\d{3}\s+\d{3}\s+\d{4})"], _clean),
    }
    for field, (patterns, parser) in rules.items():
        values[field], evidence[field] = _match(searchable, patterns, parser)
    for f in ("merchant_name","merchant_address"):
        evidence[f] = FieldEvidence(value=values[f], raw_matched_text=values[f],
            extraction_method="position_anchor", confidence=.8 if values[f] else 0, source_line=values[f])
    values["currency"] = normalize_currency(searchable) or ("USD" if "$" in searchable else None)
    evidence["currency"] = FieldEvidence(value=values["currency"], extraction_method="symbol_normalization",
        confidence=.9 if values["currency"] else 0)
    return ReceiptResult(**values), evidence
