from __future__ import annotations
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen.canvas import Canvas

PALETTES = [
    ("#183B56", "#DDECF3"), ("#274C3B", "#E4EFE8"), ("#5A315D", "#F0E3F1"),
    ("#70421B", "#F5E9DC"), ("#24355A", "#E4E9F3"),
]

def _amount(v): return f"${v:,.2f}"

def render_pdf(doc: dict, path: Path) -> None:
    receipt = doc["document_type"] == "receipt"
    template_no = int(doc["source_template"].split("_")[1])
    page = (260 + template_no * 10, 560 + template_no * 22) if receipt else A4
    c = Canvas(str(path), pagesize=page)
    w, h = page
    dark, pale = PALETTES[(template_no - 1) % len(PALETTES)]
    margin = 24 if receipt else 46
    if template_no % 2:
        c.setFillColor(colors.HexColor(dark)); c.rect(0, h - (82 if receipt else 112), w, 112, fill=1, stroke=0)
        c.setFillColor(colors.white)
    else:
        c.setFillColor(colors.HexColor(pale)); c.roundRect(margin, h-110, w-2*margin, 78, 8, fill=1, stroke=0)
        c.setFillColor(colors.HexColor(dark))
    name = doc.get("vendor_name") or doc.get("merchant_name")
    c.setFont("Helvetica-Bold", 15 if receipt else 21)
    align_center = template_no in (2, 4)
    (c.drawCentredString(w/2, h-55, name) if align_center else c.drawString(margin, h-55, name))
    c.setFont("Helvetica", 7.5 if receipt else 9)
    address = doc.get("vendor_address") or doc.get("merchant_address")
    (c.drawCentredString(w/2, h-70, address) if align_center else c.drawString(margin, h-70, address))
    c.setFillColor(colors.HexColor(dark))
    title = "RECEIPT" if receipt else "INVOICE"
    c.setFont("Helvetica-Bold", 13 if receipt else 27)
    c.drawRightString(w-margin, h-(100 if receipt else 142), title)
    c.setFillColor(colors.black); c.setFont("Helvetica", 8 if receipt else 9)
    number = doc.get("receipt_number") or doc.get("invoice_number")
    date_value = doc.get("transaction_date") or doc.get("invoice_date")
    y = h-(120 if receipt else 164)
    c.drawRightString(w-margin, y, f"No: {number}")
    c.drawRightString(w-margin, y-14, f"Date: {date_value}")
    if not receipt:
        c.setFont("Helvetica-Bold", 9); c.drawString(margin, h-156, "BILL TO")
        c.setFont("Helvetica", 9); c.drawString(margin, h-171, doc["customer_name"])
        c.drawString(margin, h-185, doc["customer_address"][:70])
        if doc.get("due_date"): c.drawRightString(w-margin, y-28, f'Due: {doc["due_date"]}')
    table_y = h-(190 if receipt else 230)
    c.setFillColor(colors.HexColor(dark)); c.rect(margin, table_y, w-2*margin, 20, fill=1, stroke=0)
    c.setFillColor(colors.white); c.setFont("Helvetica-Bold", 8)
    c.drawString(margin+6, table_y+6, "ITEM")
    c.drawRightString(w-margin-94, table_y+6, "QTY")
    c.drawRightString(w-margin-45, table_y+6, "PRICE")
    c.drawRightString(w-margin-5, table_y+6, "AMOUNT")
    c.setFillColor(colors.black); c.setFont("Helvetica", 8)
    row_y = table_y-17
    for idx, item in enumerate(doc["line_items"]):
        if idx % 2 == 0 and template_no in (1, 3, 5):
            c.setFillColor(colors.HexColor(pale)); c.rect(margin, row_y-4, w-2*margin, 16, fill=1, stroke=0); c.setFillColor(colors.black)
        c.drawString(margin+6, row_y, item["description"][:28 if receipt else 45])
        c.drawRightString(w-margin-94, row_y, str(item["quantity"]))
        c.drawRightString(w-margin-45, row_y, _amount(item["unit_price"]))
        c.drawRightString(w-margin-5, row_y, _amount(item["line_total"]))
        row_y -= 18
    row_y -= 5
    c.line(w-margin-125, row_y+10, w-margin, row_y+10)
    for label, value in [("Subtotal", doc["subtotal"]), ("Tax", doc["tax_amount"]), ("TOTAL", doc["total_amount"])]:
        c.setFont("Helvetica-Bold" if label == "TOTAL" else "Helvetica", 9)
        c.drawRightString(w-margin-58, row_y, label)
        c.drawRightString(w-margin-5, row_y, _amount(value)); row_y -= 17
    c.setFillColor(colors.HexColor(dark)); c.setFont("Helvetica-Bold", 7)
    c.drawCentredString(w/2, 22, "SYNTHETIC DOCUMENT • FOR TESTING AND PORTFOLIO DEMONSTRATION")
    c.setTitle(doc["document_id"]); c.showPage(); c.save()

