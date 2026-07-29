from __future__ import annotations
from datetime import date
from .schemas import LineItem, ValidationWarning

def validate(document_type: str, fields, items: list[LineItem], ocr_confidence: float | None,
             extraction_confidence: float, type_uncertain: bool, tolerance=.05) -> list[ValidationWarning]:
    data = fields.model_dump() if hasattr(fields, "model_dump") else fields
    warnings = []
    number = data.get("invoice_number") or data.get("receipt_number")
    if not number: warnings.append(_w("MISSING_DOCUMENT_NUMBER", "Document number was not extracted."))
    relevant_date = data.get("invoice_date") or data.get("transaction_date")
    if not relevant_date: warnings.append(_w("MISSING_DATE", "Primary document date was not extracted."))
    for field in ("invoice_date","due_date","transaction_date"):
        value = data.get(field)
        if value:
            try: date.fromisoformat(value)
            except ValueError: warnings.append(_w("UNPARSEABLE_DATE", f"{field} is not ISO-parseable.", field))
    if data.get("invoice_date") and data.get("due_date"):
        if data["due_date"] < data["invoice_date"]:
            warnings.append(_w("INVALID_DATE_ORDER", "Due date precedes invoice date.", "due_date"))
    if data.get("currency") not in {"USD","EUR","GBP","CAD","AUD"}:
        warnings.append(_w("UNKNOWN_CURRENCY", "Currency is missing or unsupported.", "currency"))
    for field in ("subtotal","tax_amount","total_amount","discount","shipping"):
        if data.get(field) is not None and data[field] < 0:
            warnings.append(_w("NEGATIVE_AMOUNT", f"{field} is negative.", field))
    if all(data.get(k) is not None for k in ("subtotal","tax_amount","total_amount")):
        if abs(data["subtotal"] + data["tax_amount"] - data["total_amount"]) > tolerance:
            warnings.append(_w("TOTAL_MISMATCH", "Subtotal plus tax does not match total.", "total_amount"))
    if not items: warnings.append(_w("NO_LINE_ITEMS_FOUND", "No line items were parsed."))
    elif data.get("subtotal") is not None:
        item_sum = sum(x.line_total or 0 for x in items)
        discount = data.get("discount") or 0
        shipping = data.get("shipping") or 0
        if min(abs(item_sum-data["subtotal"]), abs(item_sum-discount+shipping-data["subtotal"])) > tolerance:
            warnings.append(_w("LINE_ITEM_SUM_MISMATCH", "Line-item totals do not reconcile with subtotal."))
    if ocr_confidence is not None and ocr_confidence < .65:
        warnings.append(_w("LOW_OCR_CONFIDENCE", "Mean OCR confidence is below threshold."))
    if extraction_confidence < .55:
        warnings.append(_w("LOW_EXTRACTION_CONFIDENCE", "Structured extraction confidence is below threshold."))
    if type_uncertain: warnings.append(_w("DOCUMENT_TYPE_UNCERTAIN", "Document classification is uncertain."))
    return warnings

def _w(code, message, field=None):
    return ValidationWarning(code=code, message=message, field=field)

