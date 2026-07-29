from __future__ import annotations
from .schemas import ConfidenceBreakdown, FieldEvidence, ValidationWarning

FORMULA = "0.30 OCR + 0.35 field evidence + 0.15 document type + 0.20 validation consistency"

def score(ocr_confidence: float | None, evidence: dict[str, FieldEvidence], type_confidence: float,
          warnings: list[ValidationWarning]) -> ConfidenceBreakdown:
    ocr = ocr_confidence if ocr_confidence is not None else .95
    populated = [e.confidence for e in evidence.values() if e.value is not None]
    fields = sum(populated) / len(populated) if populated else 0
    severe = {"TOTAL_MISMATCH","MISSING_DOCUMENT_NUMBER","MISSING_DATE","NO_LINE_ITEMS_FOUND"}
    consistency = max(0, 1 - .18 * sum(w.code in severe for w in warnings) - .05 * len(warnings))
    components = {"ocr": round(ocr,4), "field_evidence": round(fields,4),
                  "document_type": round(type_confidence,4), "validation_consistency": round(consistency,4)}
    value = max(0, min(1, .30*ocr + .35*fields + .15*type_confidence + .20*consistency))
    label = "High" if value >= .80 else "Medium" if value >= .60 else "Low"
    return ConfidenceBreakdown(score=round(value,4), label=label, components=components, formula=FORMULA)

