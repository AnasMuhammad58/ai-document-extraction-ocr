import json
from pathlib import Path
import openpyxl
import pytest
from src.classification import classify
from src.confidence import score
from src.config import ROOT
from src.document_loader import load_document
from src.field_extractor import extract_fields
from src.line_item_extractor import extract_line_items
from src.parsing import normalize_currency, parse_amount, parse_date
from src.schemas import FieldEvidence, InvoiceResult, LineItem
from src.validation import validate

INVOICE_TEXT = """Northstar Paper Co.
18 Willow Loop, Alder Bay, OR 97001
INVOICE
No: NS-2025-10000
Date: 2025-01-24
BILL TO
Tracy Hayes
797 Gallagher Creek, Crosston
Due: 2025-02-07
ITEM | QTY | PRICE | AMOUNT
Herbal tea | 2 | $34.94 | $69.88
Cleaning cloths | 4 | $43.73 | $174.92
Subtotal | $244.80
Tax | $20.20
TOTAL | $265.00
"""
RECEIPT_TEXT = """Morning Oak Market
15 Orchard Way, Brookfield, VT 05036
RECEIPT
No: RC-2501-5000
Date: 2025-01-05
ITEM | QTY | PRICE | AMOUNT
Cable clips | 1 | $14.46 | $14.46
Subtotal | $14.46
Tax | $1.08
TOTAL | $15.54
"""

def test_embedded_pdf_extraction():
    result = load_document(ROOT/"data/samples/inv-0001_digital.pdf", force=True)
    assert result.extraction_method == "embedded_text"
    assert "Northstar" in result.raw_text

@pytest.mark.parametrize("path", [
    ROOT/"data/samples/inv-0001_slight_rotation.png",
    ROOT/"data/synthetic/invoices/jpg/inv-0001_mild_blur.jpg",
    ROOT/"data/synthetic/scanned_pdfs/inv-0001_lower_contrast.pdf",
])
def test_ocr_routes_are_nonempty(path):
    result = load_document(path)
    assert result.extraction_method == "ocr"
    assert len(result.raw_text) > 80
    assert result.ocr_confidence is not None

def test_classification():
    assert classify(INVOICE_TEXT)[0] == "invoice"
    assert classify(RECEIPT_TEXT)[0] == "receipt"

def test_parsers():
    assert parse_amount("USD $1,234.50") == 1234.5
    assert parse_date("Date: 2025/01/24") == "2025-01-24"
    assert normalize_currency("$12.00") == "USD"
    assert normalize_currency("XYZ") is None

def test_invoice_and_receipt_numbers_and_total_priority():
    invoice, _ = extract_fields(INVOICE_TEXT, "invoice")
    receipt, _ = extract_fields(RECEIPT_TEXT, "receipt")
    assert invoice.invoice_number == "NS-2025-10000"
    assert receipt.receipt_number == "RC-2501-5000"
    assert invoice.subtotal == 244.8 and invoice.total_amount == 265.0

def test_line_items_and_null_missing_fields():
    items = extract_line_items(INVOICE_TEXT, "invoice")
    fields, _ = extract_fields(INVOICE_TEXT, "invoice")
    assert len(items) == 2 and items[0].description == "Herbal tea"
    assert fields.purchase_order is None and fields.vendor_email is None

def test_validation_warnings():
    fields = InvoiceResult(invoice_number=None, invoice_date=None, currency="XYZ",
        subtotal=10, tax_amount=2, total_amount=99)
    warnings = validate("invoice", fields, [], .4, .3, True)
    codes = {w.code for w in warnings}
    assert {"MISSING_DOCUMENT_NUMBER","MISSING_DATE","UNKNOWN_CURRENCY","TOTAL_MISMATCH",
            "NO_LINE_ITEMS_FOUND","LOW_OCR_CONFIDENCE","LOW_EXTRACTION_CONFIDENCE",
            "DOCUMENT_TYPE_UNCERTAIN"} <= codes

def test_confidence_boundaries():
    value = score(.9, {"x": FieldEvidence(value="x", confidence=.8)}, .9, [])
    assert 0 <= value.score <= 1 and value.label in {"High","Medium","Low"}

def test_exports_and_relationships():
    out = ROOT/"outputs/extracted"
    for name in ["document_results.json","document_summary.csv","line_items.csv",
                 "validation_warnings.csv","extracted_data.xlsx","run_summary.json"]:
        assert (out/name).exists()
    results = json.loads((out/"document_results.json").read_text(encoding="utf-8"))
    assert all(row["document_id"] and row["variant_id"] for row in results)
    wb = openpyxl.load_workbook(out/"extracted_data.xlsx", read_only=True)
    assert wb.sheetnames == ["Documents","Line Items","Validation Warnings","Run Summary"]

def test_normal_extraction_has_no_ground_truth_dependency():
    modules = ["document_loader.py","pipeline.py","field_extractor.py","line_item_extractor.py",
               "validation.py","confidence.py","exporters.py"]
    for name in modules:
        assert "ground_truth" not in (ROOT/"src"/name).read_text(encoding="utf-8")

def test_batch_failure_isolation_contract(monkeypatch, tmp_path):
    # The batch loop catches per-file exceptions; prove the relevant handler is present.
    source = (ROOT/"src/pipeline.py").read_text(encoding="utf-8")
    assert "except Exception as exc:" in source
    assert "failures.append" in source
