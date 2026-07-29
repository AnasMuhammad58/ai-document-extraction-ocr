# Confidence Scoring

Confidence estimates extraction reliability; it is not measured accuracy.

The score is bounded to 0–1:

`0.30 × OCR + 0.35 × field evidence + 0.15 × document-type confidence + 0.20 × validation consistency`

Embedded-text documents use a 0.95 text-quality proxy because OCR confidence does not apply. Field evidence averages populated-field parser confidences. Validation consistency starts at 1.0 and deducts more for missing identifiers, dates, totals mismatches, and absent line items than for informational warnings.

- High: at least 0.80
- Medium: 0.60–0.7999
- Low: below 0.60

The full component breakdown and formula are stored with every result.
