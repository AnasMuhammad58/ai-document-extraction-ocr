# Streamlit Integration Design

The app calls `src.pipeline.process_document`, the same single-document hybrid pipeline used by batch processing. It reuses document loading, PyMuPDF embedded text, RapidOCR, classification, field extraction, line-item parsing, validation, confidence, and OCR caching rather than duplicating extraction logic.

Supported inputs are PDF, PNG, JPG, and JPEG, capped at 20 MB per file. PDFs are previewed by rendering their first page with PyMuPDF; the current extractor handles only page one. Uploaded bytes are written only inside a secure temporary directory using a SHA-256-derived stable prefix and sanitized filename, then removed automatically. OCR cache entries use content and configuration fingerprints, so safe cached results survive temporary-file cleanup without becoming stale.

The OCR model is initialized once with `st.cache_resource`. User edits are never cached. Original fields and line items remain stored separately from reviewed values. Revalidation operates on reviewed values without changing raw extracted text.

Downloads are generated in memory through shared app services. JSON preserves original and reviewed values; CSVs provide documents, line items, and warnings; Excel retains Documents, Line Items, Validation Warnings, and Run Summary sheets.

Limitations: printed English invoices and receipts only, one-page extraction, 20 MB per file, offline CPU OCR, no handwriting or multilingual processing, and confidence is not correctness.

