# Extraction Design

The Stage 1 dataset contains 70 single-page English source documents: 40 invoices across five templates and 30 receipts across four templates. Each source has a clean digital PDF, PNG, JPG, and raster-only scanned PDF. Quality metadata covers clean, rotation, blur, low contrast, noise, shadow, JPEG compression, and mild perspective distortion. IDs appear in generated filenames and in Stage 1 metadata; normal extraction derives processing IDs from filenames and never reads ground truth.

Digital PDFs are under `data/synthetic/{invoices|receipts}/pdf`. PNG and JPG variants are under corresponding format folders. Raster PDFs are under `data/synthetic/scanned_pdfs`. Ground truth stores nested ordered line items; optional invoice fields include purchase order, notes, discounts, and shipping, while receipt card digits are absent for cash.

## Strategy

- PyMuPDF first extracts positioned embedded words from PDFs. Insufficient text triggers page rasterization and OCR.
- RapidOCR with ONNX Runtime performs offline CPU OCR on scanned PDFs and images, returning text regions, boxes, and confidence.
- Conservative preprocessing uses quality-sensitive deskew, contrast normalization, denoising, resizing, and adaptive thresholding.
- Transparent keyword scoring classifies invoices versus receipts.
- Regex anchors, positional header rules, normalization, and table-row parsing extract fields and line items. Every field carries evidence and confidence.
- Validation never changes extracted values.

Known dataset limitations are synthetic identities, single pages, English printed text, relatively regular tables, moderate degradation, and no handwriting or multilingual examples.

