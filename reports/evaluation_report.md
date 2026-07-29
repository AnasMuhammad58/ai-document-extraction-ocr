# Final Evaluation Report

## 1. Executive Summary

The frozen pipeline processed 84 variants from 21 untouched synthetic test sources. Processing success was 100.0%. Metrics below are specific; no universal accuracy claim is made.

## 2. Evaluation Dataset

The deterministic source-level split contains 49 development and 21 test sources. Test variants include digital PDF, PNG, JPG, and scanned PDF.

## 3. Leakage Prevention

All four variants stay with their source. Predictions were saved before the evaluator opened ground truth. Normal OCR/extraction modules do not import ground truth.

## 4. Extraction Methods

Digital PDFs use PyMuPDF embedded text. Raster PDFs and images use RapidOCR 1.4.4 with ONNX Runtime CPU.

## 5. Document-Type Classification

- Accuracy: 100.0%
- Macro F1: 100.0%

## 6. Header-Field Results

- Macro precision: 84.2%
- Macro recall: 81.5%
- Macro F1: 82.7%
- Micro F1: 83.3%
- Critical-field accuracy: 97.1%
- Complete-record accuracy: 26.2%

Only visibly rendered fields were scored.

## 7. Numeric-Field Results

Tolerance-based accuracy at the configured tolerance is 95.7%.

## 8. Line-Item Results

- Row precision: 100.0%
- Row recall: 78.7%
- Row F1: 88.1%

Compact receipts, rotated tables, and reconciliation-warning documents remain weaker.

## 9. OCR Text Results

- OCR-route CER: 1.010
- OCR-route WER: 0.718
- Embedded-text CER: 1.039
- Embedded-text WER: 0.962

The Stage 1 expected-text reference is incomplete relative to the full printed page, so insertion errors inflate these values.

## 10. Performance by Quality

Clean critical-field accuracy was 100.0%; degraded accuracy was 96.2%.

## 11. Performance by Format

Detailed format results are in `outputs/evaluation/performance_by_format.csv`.

## 12. Confidence Analysis

All test results were labelled High, so cross-band calibration cannot be inferred. Confidence remains a transparent reliability heuristic, not correctness probability.

## 13. Validation-Warning Analysis

Warnings are diagnostic signals, not guaranteed error detectors. Detailed false-warning and error-capture rates are reported in `validation_warning_analysis.csv`.

## 14. Runtime

- Uncached total: 380.92s
- Mean per variant: 4.532s
- Cached total: 3.92s

## 15. Error Analysis

Most frequent categories: OCR character error (83), label not detected (40), row grouping (18), rotation (16), compact receipt layout (13), perspective distortion (12).

## 16. Limitations

- Synthetic, printed, English, single-page documents only.
- Optional fields not visibly printed were excluded.
- Line-item grouping is weaker than header extraction.
- Expected OCR reference text is incomplete.
- Confidence bands lack diversity on this test set.

## 17. Appropriate Fiverr Claims

Appropriate: evaluated against known synthetic ground truth; supports digital PDFs, scanned PDFs, PNG, and JPG; exports Excel, CSV, and JSON; includes validation and confidence indicators; tested on multiple invoice and receipt layouts.

Not appropriate: 100% accurate, guaranteed error-free, human-level, or production-ready for every industry.
