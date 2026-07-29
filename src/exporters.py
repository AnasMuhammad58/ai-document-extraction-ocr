from __future__ import annotations
import json
from pathlib import Path
import pandas as pd
from openpyxl import load_workbook
from .schemas import ExtractionResult

def export_results(results: list[ExtractionResult], out: Path, run_summary: dict) -> None:
    out.mkdir(parents=True, exist_ok=True)
    payload = [r.model_dump(mode="json") for r in results]
    (out/"document_results.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    documents, items, warnings = [], [], []
    for r in results:
        fields = r.fields.model_dump() if hasattr(r.fields, "model_dump") else r.fields
        documents.append({"document_id": r.document_id, "variant_id": r.variant_id, "file_name": r.file_name,
            "document_type": r.document_type, "extraction_method": r.extraction_method,
            "ocr_confidence": r.ocr_confidence, "structured_confidence": r.structured_confidence,
            "confidence_label": r.confidence.label, "validation_status": r.validation_status,
            "processing_time_seconds": r.processing_time_seconds, **fields})
        for order, item in enumerate(r.line_items, 1):
            items.append({"document_id": r.document_id, "variant_id": r.variant_id, "item_order": order,
                          **item.model_dump()})
        for warning in r.warnings:
            warnings.append({"document_id": r.document_id, "variant_id": r.variant_id, **warning.model_dump()})
    doc_df, item_df, warning_df = pd.DataFrame(documents), pd.DataFrame(items), pd.DataFrame(warnings)
    doc_df.to_csv(out/"document_summary.csv", index=False)
    item_df.to_csv(out/"line_items.csv", index=False)
    warning_df.to_csv(out/"validation_warnings.csv", index=False)
    (out/"run_summary.json").write_text(json.dumps(run_summary, indent=2), encoding="utf-8")
    with pd.ExcelWriter(out/"extracted_data.xlsx", engine="openpyxl") as writer:
        doc_df.to_excel(writer, sheet_name="Documents", index=False)
        item_df.to_excel(writer, sheet_name="Line Items", index=False)
        warning_df.to_excel(writer, sheet_name="Validation Warnings", index=False)
        pd.DataFrame([run_summary]).to_excel(writer, sheet_name="Run Summary", index=False)
    wb = load_workbook(out/"extracted_data.xlsx")
    for ws in wb.worksheets:
        ws.freeze_panes = "A2"; ws.auto_filter.ref = ws.dimensions
        for column in ws.columns:
            width = min(42, max(11, max(len(str(cell.value or "")) for cell in column) + 2))
            ws.column_dimensions[column[0].column_letter].width = width
    wb.save(out/"extracted_data.xlsx")

