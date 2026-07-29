# Synthetic Dataset Generation Report

> Synthetic documents created for testing and portfolio demonstration.

- Mode: normal
- Source documents: 70 (40 invoices, 30 receipts)
- Templates: 5 invoice and 4 receipt
- Rendered variants: 280 (four per source)
- Formats: {'pdf': 70, 'png': 70, 'jpg': 70, 'scanned_pdf': 70}
- Quality conditions: {'clean': 70, 'slight_rotation': 30, 'mild_blur': 30, 'lower_contrast': 30, 'light_noise': 30, 'mild_shadow': 30, 'jpeg_compression': 30, 'perspective': 30}
- Deterministic seed: 20260728

## Field coverage

- `cashier`: 30/70
- `currency`: 70/70
- `customer_address`: 40/70
- `customer_name`: 40/70
- `discount`: 40/70
- `document_id`: 70/70
- `document_type`: 70/70
- `due_date`: 40/70
- `invoice_date`: 40/70
- `invoice_number`: 40/70
- `last_four_digits`: 20/70
- `merchant_address`: 30/70
- `merchant_name`: 30/70
- `merchant_phone`: 30/70
- `notes`: 20/70
- `payment_method`: 30/70
- `payment_terms`: 40/70
- `purchase_order`: 26/70
- `receipt_number`: 30/70
- `shipping`: 40/70
- `source_template`: 70/70
- `subtotal`: 70/70
- `tax_amount`: 70/70
- `tax_rate`: 40/70
- `total_amount`: 70/70
- `transaction_date`: 30/70
- `transaction_time`: 30/70
- `vendor_address`: 40/70
- `vendor_email`: 40/70
- `vendor_name`: 40/70
- `vendor_phone`: 40/70

## Regeneration

```powershell
.\.venv\Scripts\python.exe run_all.py --stage 1 --force
```

Digital PDFs retain embedded text. Scanned PDFs contain raster images only. Every rendered file is traceable through the `variants` array in `documents.json`.
