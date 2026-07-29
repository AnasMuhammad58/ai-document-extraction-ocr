import csv
import json
from decimal import Decimal
from pathlib import Path
import fitz
from PIL import Image
from src.config import ROOT, load_config
from src.synthetic_data import build_documents

def documents():
    return json.loads((ROOT/"data/ground_truth/documents.json").read_text(encoding="utf-8"))

def test_deterministic_generation():
    cfg = load_config()
    assert build_documents(2, 2, cfg["seed"]) == build_documents(2, 2, cfg["seed"])

def test_expected_counts_and_unique_ids():
    docs = documents()
    assert len(docs) == 70
    assert len({d["document_id"] for d in docs}) == 70
    assert sum(d["document_type"] == "invoice" for d in docs) == 40
    assert sum(d["document_type"] == "receipt" for d in docs) == 30

def test_arithmetic_consistency():
    for doc in documents():
        item_sum = sum(Decimal(str(x["line_total"])) for x in doc["line_items"])
        if doc["document_type"] == "invoice":
            expected = item_sum - Decimal(str(doc["discount"])) + Decimal(str(doc["shipping"]))
        else: expected = item_sum
        assert abs(expected - Decimal(str(doc["subtotal"]))) <= Decimal(".01")
        assert abs(Decimal(str(doc["subtotal"])) + Decimal(str(doc["tax_amount"])) -
                   Decimal(str(doc["total_amount"]))) <= Decimal(".01")

def test_variants_traceable_and_supported():
    for doc in documents():
        assert len(doc["variants"]) == 4
        assert {v["format"] for v in doc["variants"]} == {"pdf", "png", "jpg", "scanned_pdf"}
        for variant in doc["variants"]:
            path = ROOT/variant["file_path"]
            assert path.exists() and path.stat().st_size > 1000
            assert variant["document_id"] == doc["document_id"]

def test_ground_truth_csv_relationships():
    with (ROOT/"data/ground_truth/document_fields.csv").open(encoding="utf-8") as h:
        fields = list(csv.DictReader(h))
    with (ROOT/"data/ground_truth/line_items.csv").open(encoding="utf-8") as h:
        items = list(csv.DictReader(h))
    assert len(fields) == 70
    assert {x["document_id"] for x in items} <= {x["document_id"] for x in fields}

def test_documents_open_and_scans_have_no_embedded_text():
    docs = documents()
    for doc in docs[::13]:
        digital = ROOT/next(v["file_path"] for v in doc["variants"] if v["format"] == "pdf")
        scan = ROOT/next(v["file_path"] for v in doc["variants"] if v["format"] == "scanned_pdf")
        with fitz.open(digital) as pdf: assert len(pdf[0].get_text()) > 100
        with fitz.open(scan) as pdf: assert pdf[0].get_text().strip() == ""
    for suffix in ("png", "jpg"):
        sample = next((ROOT/f"data/synthetic").rglob(f"*.{suffix}"))
        with Image.open(sample) as image: image.verify()

def test_all_quality_conditions_present():
    labels = {v["quality_label"] for d in documents() for v in d["variants"]}
    assert labels == {"clean", "slight_rotation", "mild_blur", "lower_contrast",
                      "light_noise", "mild_shadow", "jpeg_compression", "perspective"}

