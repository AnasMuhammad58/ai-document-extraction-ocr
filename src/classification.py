from __future__ import annotations

INVOICE = {"invoice": 3, "bill to": 2, "due": 1, "payment terms": 2, "purchase order": 2}
RECEIPT = {"receipt": 3, "cashier": 2, "payment method": 2, "card": 1, "transaction": 1, "change": 1}

def classify(text: str) -> tuple[str, float, list[str], bool]:
    low = text.lower()
    inv_hits = [key for key in INVOICE if key in low]
    rec_hits = [key for key in RECEIPT if key in low]
    inv_score = sum(INVOICE[k] for k in inv_hits)
    rec_score = sum(RECEIPT[k] for k in rec_hits)
    if inv_score == rec_score == 0: return "unknown", 0.0, [], True
    predicted = "invoice" if inv_score >= rec_score else "receipt"
    high, low_score = max(inv_score, rec_score), min(inv_score, rec_score)
    confidence = min(1.0, .55 + .08 * high - .05 * low_score)
    evidence = inv_hits if predicted == "invoice" else rec_hits
    return predicted, confidence, evidence, confidence < .65

