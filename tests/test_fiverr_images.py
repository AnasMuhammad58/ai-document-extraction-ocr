import hashlib
import json
from pathlib import Path
from PIL import Image, ImageStat
from src.config import ROOT
from src.create_fiverr_images import generate, load_metrics

OUT = ROOT/"outputs/fiverr"
NAMES = ["01_gig_thumbnail.png","02_extraction_result.png","03_ocr_workflow.png"]

def test_exactly_three_full_size_fiverr_images_exist():
    assert sorted(p.name for p in OUT.glob("*.png")) == NAMES

def test_fiverr_image_dimensions_are_exact():
    for name in NAMES:
        with Image.open(OUT/name) as image:
            assert image.size == (1280,769)

def test_fiverr_images_are_nonempty():
    for name in NAMES:
        with Image.open(OUT/name) as image:
            assert sum(ImageStat.Stat(image.convert("L")).var) > 20

def test_preview_images_exist_and_have_expected_size():
    expected=[name.replace(".png","_small.png") for name in NAMES]
    assert sorted(p.name for p in (OUT/"previews").glob("*.png")) == expected
    for name in expected:
        with Image.open(OUT/"previews"/name) as image:
            assert image.size == (640,385)

def test_displayed_metrics_come_from_evaluation_summary():
    summary=json.loads((ROOT/"outputs/evaluation/evaluation_summary.json").read_text())
    verification=json.loads((OUT/"metric_verification.json").read_text())
    assert verification["critical_field_accuracy"] == summary["critical_field_accuracy"]
    assert verification["numeric_tolerance_accuracy"] == summary["numeric_field_tolerance_accuracy"]
    assert verification["line_item_f1"] == summary["line_item_row_f1"]
    assert verification["all_values_loaded_from_summary"] is True

def test_test_variant_count_is_genuine():
    summary=json.loads((ROOT/"outputs/evaluation/evaluation_summary.json").read_text())
    verification=json.loads((OUT/"metric_verification.json").read_text())
    assert verification["test_variant_count"] == summary["test_variant_count"] == 84

def test_ocr_error_metrics_are_not_displayed():
    validation=json.loads((OUT/"image_validation.json").read_text())
    text=" ".join(" ".join(validation[name]["displayed_text"]) for name in NAMES).lower()
    assert "ocr cer" not in text and "ocr wer" not in text
    assert str(round(load_metrics().get("ocr_cer",999),3)) not in text

def test_no_prohibited_marketing_claims_are_present():
    validation=json.loads((OUT/"image_validation.json").read_text())
    combined=" ".join(" ".join(validation[name]["displayed_text"]) for name in NAMES).lower()
    prohibited=["100% accurate","guaranteed error-free","human-level extraction",
                "client document","production-ready for every industry"]
    assert not any(claim in combined for claim in prohibited)

def test_image_two_has_synthetic_document_label():
    validation=json.loads((OUT/"image_validation.json").read_text())
    assert "SYNTHETIC TEST DOCUMENT" in validation["02_extraction_result.png"]["displayed_text"]

def test_image_generation_is_deterministic():
    before={name:hashlib.sha256((OUT/name).read_bytes()).hexdigest() for name in NAMES}
    result=generate()
    after={name:hashlib.sha256((OUT/name).read_bytes()).hexdigest() for name in NAMES}
    assert before == after
    assert result["all_checks_passed"] is True

