# Final Evaluation Methodology

## Split and leakage control

The deterministic split is applied at source-document level: 49 development sources and 21 untouched test sources. Each source contributes exactly four variants, and no source ID occurs in both sets. Normal prediction generation discovers test files from the frozen split and runs without opening ground truth. It writes all prediction files before `documents.json` is loaded by the evaluator.

Failed variants remain predictions with null fields and stay in every denominator.

## Visible-field policy

Only fields visibly printed by the Stage 1 templates are evaluated. Invoice scoring covers vendor name/address, customer name/address, invoice number/date, due date, currency, subtotal, tax amount, and total. Receipt scoring covers merchant name/address, receipt number/date, currency, subtotal, tax amount, and total. Optional truth fields not printed on the page have expected count zero.

## Normalization

- Text: Unicode NFKC, lowercase, trim, collapse whitespace, and conservatively normalize punctuation.
- Identifiers: text normalization plus normalization of spaces, underscores, and hyphens to a common separator; letters and digits remain meaningful.
- Dates: parse and compare as ISO `YYYY-MM-DD`; unparseable dates are incorrect.
- Currency: normalize symbols and supported names to ISO codes.
- Phone/email: digits-only phone comparison and lowercase trimmed email comparison.
- Amounts: remove currency notation and thousands separators, parse as decimals, and use the configured absolute tolerance of $0.05. Exact numeric accuracy is reported separately.
- Names and addresses: normalized exact comparison is the primary metric. No loose fuzzy score replaces it.

## Field metrics

For each visibly expected field, accuracy and recall equal correct divided by expected. Precision is correct divided by extracted. F1 is the harmonic mean. Macro metrics average fields with nonzero expected count; micro F1 pools field instances. Complete-record accuracy requires every visible field to match. Critical-field accuracy covers identifiers, primary dates, subtotal, tax, and total.

## Line items

Rows are matched one-to-one. A predicted row can be used only once, and normalized description similarity must be at least 0.90; matching prefers the same order. Quantity, unit price, and line total are then assessed independently with numeric tolerance. This conservative approach avoids pairing unrelated rows.

## OCR text

CER and WER use Levenshtein edit distance divided by reference length. OCR routes and embedded-text routes are reported separately. Stage 1 expected text does not contain every printed address and label, so valid extra text is counted as insertions and inflates both rates.

## Confidence and validation

Confidence bands are compared with critical-field correctness, visible-field correctness, complete records, and warning frequency. This is diagnostic analysis, not formal probability calibration. Warning analysis reports actual-error concentration, error coverage, and false warnings; warnings are not guaranteed error detectors.

