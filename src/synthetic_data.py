from __future__ import annotations
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
import random
from faker import Faker

VENDORS = [
    ("Northstar Paper Co.", "18 Willow Loop, Alder Bay, OR 97001"),
    ("Juniper Office Works", "72 Cedar Walk, Lumen City, CO 80014"),
    ("Blue Finch Supplies", "409 Harbor Lane, Fairhaven, ME 04032"),
    ("Copper & Pine Studio", "11 Quartz Street, Bellmere, AZ 85004"),
    ("Maple Circuit Goods", "260 Grove Avenue, Westvale, NY 10018"),
]
MERCHANTS = [
    ("Morning Oak Market", "15 Orchard Way, Brookfield, VT 05036"),
    ("Little Lantern Cafe", "88 Crescent Road, Pinecross, WA 98104"),
    ("Harbor Basket", "203 Tide Street, Seacliff, CA 94016"),
    ("Cobalt Corner Shop", "39 Prism Avenue, Eastmere, IL 60607"),
]
PRODUCTS = ["Archive folders", "Recycled notebooks", "Desk organizer", "Cable clips",
            "Gel pen set", "Shipping labels", "Coffee beans", "Herbal tea",
            "Granola cup", "Canvas tote", "USB adapter", "Cleaning cloths"]

def money(value) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

def _items(rng: random.Random, receipt=False) -> list[dict]:
    count = rng.randint(2, 5)
    rows = []
    for name in rng.sample(PRODUCTS, count):
        quantity = rng.randint(1, 4)
        unit = money(rng.uniform(2.5, 58 if not receipt else 18))
        rows.append({"description": name, "quantity": quantity, "unit_price": float(unit),
                     "line_total": float(money(unit * quantity))})
    return rows

def build_documents(invoice_count: int, receipt_count: int, seed: int) -> list[dict]:
    rng, fake = random.Random(seed), Faker("en_US")
    Faker.seed(seed)
    docs = []
    for i in range(invoice_count):
        items = _items(rng)
        line_sum = money(sum(Decimal(str(x["line_total"])) for x in items))
        discount = money(rng.choice([0, 0, 5, 10]))
        shipping = money(rng.choice([0, 4.95, 8.5, 12]))
        subtotal = money(line_sum - discount + shipping)
        tax_rate = Decimal(str(rng.choice([0, 5, 7.5, 8.25])))
        tax = money(subtotal * tax_rate / 100)
        issued = date(2025, 1, 1) + timedelta(days=rng.randint(0, 330))
        vendor, address = VENDORS[i % len(VENDORS)]
        doc = {
            "document_id": f"INV-{i+1:04d}", "document_type": "invoice",
            "source_template": f"invoice_{i % 5 + 1}", "vendor_name": vendor,
            "vendor_address": address, "vendor_email": f"billing@{vendor.lower().replace(' & ','-').replace(' ','').replace('.','')}.example",
            "vendor_phone": f"+1 555 {100+i:03d} {2000+i:04d}",
            "customer_name": fake.name(), "customer_address": fake.street_address() + ", " + fake.city(),
            "invoice_number": f"NS-{issued.year}-{10000+i}", "invoice_date": issued.isoformat(),
            "due_date": (issued + timedelta(days=rng.choice([14, 30, 45]))).isoformat(),
            "currency": "USD", "purchase_order": f"PO-{rng.randint(100000,999999)}" if i % 3 else None,
            "subtotal": float(subtotal), "tax_rate": float(tax_rate), "tax_amount": float(tax),
            "discount": float(discount), "shipping": float(shipping),
            "total_amount": float(money(subtotal + tax)), "payment_terms": "Net 30",
            "notes": "Thank you for your business." if i % 2 else None, "line_items": items,
        }
        docs.append(doc)
    for i in range(receipt_count):
        items = _items(rng, True)
        subtotal = money(sum(Decimal(str(x["line_total"])) for x in items))
        tax = money(subtotal * Decimal(str(rng.choice([0, 5, 7.5, 8.25]))) / 100)
        merchant, address = MERCHANTS[i % len(MERCHANTS)]
        trans = date(2025, 1, 1) + timedelta(days=rng.randint(0, 330))
        method = rng.choice(["VISA", "MASTERCARD", "CASH"])
        docs.append({
            "document_id": f"RCT-{i+1:04d}", "document_type": "receipt",
            "source_template": f"receipt_{i % 4 + 1}", "merchant_name": merchant,
            "merchant_address": address, "merchant_phone": f"+1 555 {500+i:03d} {6000+i:04d}",
            "receipt_number": f"RC-{trans.strftime('%y%m')}-{5000+i}",
            "transaction_date": trans.isoformat(), "transaction_time": f"{rng.randint(8,20):02d}:{rng.randint(0,59):02d}",
            "currency": "USD", "subtotal": float(subtotal), "tax_amount": float(tax),
            "total_amount": float(money(subtotal + tax)), "payment_method": method,
            "last_four_digits": f"{rng.randint(0,9999):04d}" if method != "CASH" else None,
            "cashier": f"Team {chr(65+i%6)}", "line_items": items,
        })
    return docs

def expected_text(doc: dict) -> str:
    title = doc.get("vendor_name") or doc.get("merchant_name")
    number = doc.get("invoice_number") or doc.get("receipt_number")
    lines = [title, f"Number: {number}"]
    for item in doc["line_items"]:
        lines.append(f'{item["description"]} {item["quantity"]} {item["unit_price"]:.2f} {item["line_total"]:.2f}')
    lines += [f'Subtotal: {doc["subtotal"]:.2f}', f'Tax: {doc["tax_amount"]:.2f}',
              f'Total: {doc["total_amount"]:.2f}']
    return "\n".join(lines)

