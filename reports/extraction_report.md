# Development Extraction Report

## Scope

Stages 2 and 3 process the deterministic 70% development split only. All four variants of each selected source remain together. The run processed 49 source documents and 196 variants; no final evaluation metrics were calculated.

## Engine and ingestion

- OCR: RapidOCR 1.4.4 with ONNX Runtime 1.22.1, CPU execution
- Embedded PDF text: PyMuPDF 1.26.3 positioned-word extraction
- 49 digital PDFs used embedded text
- 147 PNG, JPG, and raster-only PDF variants used OCR
- 196/196 variants completed; no batch failures
- Uncached runtime: 673.9 seconds
- Cached pipeline runtime: 4.98 seconds (10.23 seconds including interpreter startup and console overhead)

Raw extraction JSON, including regions, boxes, and confidence, is stored per variant under `outputs/extracted/raw_text`.

## Development observations

Invoice and receipt classification succeeded throughout this run using content keywords. Header anchors reliably recovered the rendered document number, primary date, subtotal, tax, total, vendor/merchant name, address, and invoice customer details. Optional fields that Stage 1 does not visibly render remain null.

Line items were parsed for 175 of 196 variants, producing 530 rows. Twenty-one variants produced no line items and were flagged. Ninety-nine variants generated line-item reconciliation warnings, primarily where OCR region grouping shifted a quantity or product description on rotated or compact layouts. This is reported as a limitation rather than corrected from ground truth.

Validation marked 76 variants `Passed` and 120 `Review`. Warning counts were:

- `LINE_ITEM_SUM_MISMATCH`: 99
- `NO_LINE_ITEMS_FOUND`: 21

All 196 results received High confidence from OCR, anchor, classification, and validation evidence. This is a reliability heuristic, not accuracy; Stage 5 will measure actual extraction performance.

## Preprocessing

Representative before/after files are saved in `outputs/charts/preprocessing` for rotation, blur, low contrast, perspective distortion, and compression. Preprocessing is selected by quality hints: deskew for rotation, CLAHE for low contrast/shadow, denoising for noise/compression, adaptive thresholding for shadow, and upscaling for small receipt text. Clean inputs are not blindly thresholded.

## Known limitations

- The Stage 1 renderer does not display every optional ground-truth field, so email, phone, purchase order, payment terms, card details, cashier, and transaction time are often legitimately null.
- Spatial line reconstruction remains imperfect on some rotated and compact receipt rows.
- Line-item reconciliation is intentionally strict and may warn when discounts or shipping are not visibly printed.
- The current implementation supports one-page English printed documents only.
- No held-out accuracy, precision, recall, or F1 is reported before Stage 5.

