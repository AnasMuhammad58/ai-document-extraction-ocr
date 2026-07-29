from __future__ import annotations
from copy import deepcopy
from io import BytesIO
import hashlib
import json
import logging
import re
import tempfile
from pathlib import Path
import fitz
import pandas as pd
from PIL import Image
from openpyxl import load_workbook
from .config import ROOT
from .pipeline import process_document
from .schemas import ExtractionResult, InvoiceResult, LineItem, ReceiptResult
from .validation import validate

SUPPORTED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
SAMPLES = {
    "Clean invoice (digital PDF)": ROOT/"data/samples/inv-0001_digital.pdf",
    "Degraded invoice (rotated PNG)": ROOT/"data/samples/inv-0001_slight_rotation.png",
    "Clean receipt (digital PDF)": ROOT/"data/samples/rct-0001_digital.pdf",
    "Degraded receipt (perspective PNG)": ROOT/"data/synthetic/receipts/png/rct-0005_perspective.png",
    "Scanned invoice (raster PDF)": ROOT/"data/synthetic/scanned_pdfs/inv-0001_lower_contrast.pdf",
}

def safe_name(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", Path(name).name)
    return cleaned[:120] or "document"

def validate_upload(name: str, data: bytes) -> str | None:
    if Path(name).suffix.lower() not in SUPPORTED_EXTENSIONS:
        return "Unsupported file type. Upload PDF, PNG, JPG, or JPEG."
    if not data: return "The uploaded file is empty."
    if len(data) > MAX_UPLOAD_BYTES: return "The file exceeds the 20 MB demonstration limit."
    return None

def preview_info(name: str, data: bytes) -> dict:
    suffix = Path(name).suffix.lower()
    if suffix == ".pdf":
        try:
            with fitz.open(stream=data, filetype="pdf") as pdf:
                if pdf.needs_pass: raise ValueError("Encrypted PDF")
                if not len(pdf): raise ValueError("Empty PDF")
                pix = pdf[0].get_pixmap(matrix=fitz.Matrix(1.25, 1.25), alpha=False)
                image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                return {"image": image, "page_count": len(pdf), "file_type": "PDF"}
        except Exception as exc:
            raise ValueError("This PDF is corrupt, empty, or encrypted.") from exc
    try:
        image = Image.open(BytesIO(data)).convert("RGB")
        image.load()
        return {"image": image, "page_count": 1, "file_type": suffix.lstrip(".").upper()}
    except Exception as exc:
        raise ValueError("This image could not be opened.") from exc

def process_bytes(name: str, data: bytes, engine, use_cache=True, preprocessing=True,
                  tolerance=.05) -> ExtractionResult:
    error = validate_upload(name, data)
    if error: raise ValueError(error)
    digest = hashlib.sha256(data).hexdigest()[:16]
    with tempfile.TemporaryDirectory(prefix="doc_extract_") as directory:
        path = Path(directory)/f"{digest}_{safe_name(name)}"
        path.write_bytes(data)
        result = process_document(path, engine=engine, force=not use_cache,
                                  numeric_tolerance=tolerance,
                                  preprocessing_enabled=preprocessing)
        result.file_name = safe_name(name)
        return result

def result_to_review(result: ExtractionResult) -> dict:
    original = result.fields.model_dump() if hasattr(result.fields, "model_dump") else dict(result.fields)
    return {"result": result, "original_fields": deepcopy(original), "reviewed_fields": deepcopy(original),
            "original_line_items": [x.model_dump() for x in result.line_items],
            "reviewed_line_items": [x.model_dump() for x in result.line_items],
            "edited_fields": [], "review_warnings": [x.model_dump() for x in result.warnings]}

def apply_review(review: dict, fields: dict, line_items: list[dict], tolerance=.05) -> dict:
    for row in line_items:
        if row.get("line_total") in (None, "") and row.get("quantity") not in (None, "") \
                and row.get("unit_price") not in (None, ""):
            try: row["line_total"] = round(float(row["quantity"]) * float(row["unit_price"]), 2)
            except (TypeError, ValueError): pass
    review["reviewed_fields"] = fields
    review["reviewed_line_items"] = line_items
    review["edited_fields"] = [key for key, value in fields.items()
                               if value != review["original_fields"].get(key)]
    model = InvoiceResult(**fields) if review["result"].document_type == "invoice" else ReceiptResult(**fields)
    items = [LineItem(**row) for row in line_items if any(v not in (None, "") for v in row.values())]
    warnings = validate(review["result"].document_type, model, items,
        review["result"].ocr_confidence, review["result"].structured_confidence,
        review["result"].document_type == "unknown", tolerance)
    review["review_warnings"] = [x.model_dump() for x in warnings]
    return review

def make_downloads(reviews: list[dict]) -> dict[str, bytes]:
    nested, documents, items, warnings = [], [], [], []
    for review in reviews:
        result = review["result"]
        fields = review["reviewed_fields"]
        nested.append({"document_id": result.document_id, "variant_id": result.variant_id,
            "file_name": result.file_name, "document_type": result.document_type,
            "extraction_method": result.extraction_method,
            "confidence": result.confidence.model_dump(), "validation_status": result.validation_status,
            "original_extracted_fields": review["original_fields"], "reviewed_fields": fields,
            "edited_fields": review["edited_fields"], "line_items": review["reviewed_line_items"],
            "validation_warnings": review["review_warnings"]})
        documents.append({"document_id": result.document_id, "variant_id": result.variant_id,
            "file_name": result.file_name, "document_type": result.document_type,
            "extraction_method": result.extraction_method, "confidence_score": result.structured_confidence,
            "confidence_label": result.confidence.label, "edited_fields": ", ".join(review["edited_fields"]),
            **{f"original_{k}": v for k,v in review["original_fields"].items()},
            **{f"reviewed_{k}": v for k,v in fields.items()}})
        for order, item in enumerate(review["reviewed_line_items"], 1):
            items.append({"document_id": result.document_id, "variant_id": result.variant_id,
                          "item_order": order, **item})
        for warning in review["review_warnings"]:
            warnings.append({"document_id": result.document_id, "variant_id": result.variant_id, **warning})
    doc_df, item_df, warning_df = pd.DataFrame(documents), pd.DataFrame(items), pd.DataFrame(warnings)
    summary = {"documents": len(reviews), "invoices": sum(x["result"].document_type=="invoice" for x in reviews),
        "receipts": sum(x["result"].document_type=="receipt" for x in reviews),
        "validation_warnings": len(warnings), "reviewed_documents": sum(bool(x["edited_fields"]) for x in reviews)}
    workbook = BytesIO()
    with pd.ExcelWriter(workbook, engine="openpyxl") as writer:
        doc_df.to_excel(writer, sheet_name="Documents", index=False)
        item_df.to_excel(writer, sheet_name="Line Items", index=False)
        warning_df.to_excel(writer, sheet_name="Validation Warnings", index=False)
        pd.DataFrame([summary]).to_excel(writer, sheet_name="Run Summary", index=False)
    workbook.seek(0)
    wb = load_workbook(workbook)
    for ws in wb.worksheets:
        ws.freeze_panes = "A2"; ws.auto_filter.ref = ws.dimensions
        for column in ws.columns:
            ws.column_dimensions[column[0].column_letter].width = min(
                42, max(11, max(len(str(cell.value or "")) for cell in column)+2))
    final_book = BytesIO(); wb.save(final_book)
    return {"json": json.dumps(nested, indent=2).encode(),
        "documents_csv": doc_df.to_csv(index=False).encode(),
        "line_items_csv": item_df.to_csv(index=False).encode(),
        "warnings_csv": warning_df.to_csv(index=False).encode(),
        "excel": final_book.getvalue()}

def batch_summary(reviews: list[dict], uploaded: int, failures: list[dict], elapsed: float) -> dict:
    results = [x["result"] for x in reviews]
    return {"uploaded": uploaded, "successful": len(results), "failed": len(failures),
        "invoices": sum(x.document_type=="invoice" for x in results),
        "receipts": sum(x.document_type=="receipt" for x in results),
        "embedded": sum(x.extraction_method=="embedded_text" for x in results),
        "ocr": sum(x.extraction_method=="ocr" for x in results),
        "high": sum(x.confidence.label=="High" for x in results),
        "medium": sum(x.confidence.label=="Medium" for x in results),
        "low": sum(x.confidence.label=="Low" for x in results),
        "warnings": sum(len(x["review_warnings"]) for x in reviews),
        "seconds": round(elapsed, 2)}
