from __future__ import annotations
from typing import Any, Literal
from pydantic import BaseModel, Field

class OCRLine(BaseModel):
    text: str
    confidence: float | None = None
    bbox: list[list[float]] | None = None

class FieldEvidence(BaseModel):
    value: Any = None
    raw_matched_text: str | None = None
    extraction_method: str | None = None
    confidence: float = 0.0
    source_line: str | None = None
    bbox: list[list[float]] | None = None

class LineItem(BaseModel):
    description: str | None = None
    quantity: float | None = None
    unit_price: float | None = None
    line_total: float | None = None
    raw_text: str = ""
    confidence: float = 0.0

class InvoiceResult(BaseModel):
    vendor_name: str | None = None
    vendor_address: str | None = None
    vendor_email: str | None = None
    vendor_phone: str | None = None
    customer_name: str | None = None
    customer_address: str | None = None
    invoice_number: str | None = None
    invoice_date: str | None = None
    due_date: str | None = None
    currency: str | None = None
    purchase_order: str | None = None
    subtotal: float | None = None
    tax_rate: float | None = None
    tax_amount: float | None = None
    discount: float | None = None
    shipping: float | None = None
    total_amount: float | None = None
    payment_terms: str | None = None

class ReceiptResult(BaseModel):
    merchant_name: str | None = None
    merchant_address: str | None = None
    merchant_phone: str | None = None
    receipt_number: str | None = None
    transaction_date: str | None = None
    transaction_time: str | None = None
    currency: str | None = None
    subtotal: float | None = None
    tax_amount: float | None = None
    total_amount: float | None = None
    payment_method: str | None = None
    last_four_digits: str | None = None
    cashier: str | None = None

class ValidationWarning(BaseModel):
    code: str
    message: str
    field: str | None = None
    severity: Literal["info", "warning", "error"] = "warning"

class ConfidenceBreakdown(BaseModel):
    score: float = Field(ge=0, le=1)
    label: Literal["High", "Medium", "Low"]
    components: dict[str, float]
    formula: str

class ExtractionInput(BaseModel):
    document_id: str
    variant_id: str
    file_path: str
    file_type: str
    page_count: int
    extraction_method: Literal["embedded_text", "ocr"]
    raw_text: str
    lines: list[OCRLine] = []
    ocr_confidence: float | None = None
    processing_warnings: list[str] = []

class ExtractionResult(BaseModel):
    document_id: str
    variant_id: str
    file_name: str
    document_type: Literal["invoice", "receipt", "unknown"]
    document_type_confidence: float
    classification_evidence: list[str]
    extraction_method: str
    processing_time_seconds: float
    ocr_confidence: float | None = None
    structured_confidence: float
    confidence: ConfidenceBreakdown
    validation_status: str
    warnings: list[ValidationWarning]
    fields: InvoiceResult | ReceiptResult | dict
    field_evidence: dict[str, FieldEvidence]
    line_items: list[LineItem]
    raw_text_path: str

