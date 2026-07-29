import json
import math
from pathlib import Path
import pandas as pd
from PIL import Image, ImageStat
from src.config import ROOT
from src.evaluation import (
    edit_distance, error_rate, extraction_output_hashes, match_items,
    normalize_identifier, normalize_text, split_info, values_equal,
)

EVAL = ROOT/"outputs/evaluation"

def test_no_source_document_split_leakage():
    _, _, split = split_info()
    assert not set(split["development_document_ids"]) & set(split["test_document_ids"])
    assert split["development_source_document_count"] == 49
    assert split["test_source_document_count"] == 21

def test_test_variants_match_manifest_and_stay_together():
    _, test_files, split = split_info()
    predictions = json.loads((EVAL/"test_predictions.json").read_text(encoding="utf-8"))
    assert len(test_files) == split["test_variant_count"] == len(predictions) == 84
    assert split["all_variants_kept_with_source"]
    assert all(sum(p["document_id"] == doc for p in predictions) == 4
               for doc in split["test_document_ids"])

def test_every_prediction_maps_to_truth_and_has_no_duplicates():
    truth = {x["document_id"] for x in json.loads(
        (ROOT/"data/ground_truth/documents.json").read_text(encoding="utf-8"))}
    predictions = json.loads((EVAL/"test_predictions.json").read_text(encoding="utf-8"))
    assert all(p["document_id"] in truth for p in predictions)
    assert len({p["variant_id"] for p in predictions}) == len(predictions)

def test_failed_variants_remain_in_denominator():
    predictions = json.loads((EVAL/"test_predictions.json").read_text(encoding="utf-8"))
    summary = json.loads((EVAL/"evaluation_summary.json").read_text(encoding="utf-8"))
    assert len(predictions) == summary["test_variant_count"]
    assert sum(p["success"] for p in predictions) / len(predictions) == summary["processing_success_rate"]

def test_normalizers_and_tolerance():
    assert normalize_text("  Blue—Finch  ") == "blue finch"
    assert normalize_identifier("NS_2025 10001") == "ns-2025-10001"
    assert values_equal("total_amount", "$10.00", 10.04, .05)
    assert not values_equal("total_amount", "$10.00", 10.06, .05)
    assert values_equal("invoice_date", "2025/01/04", "2025-01-04")

def test_field_and_numeric_metrics_are_finite():
    for filename in ["field_metrics.csv","numeric_field_metrics.csv"]:
        frame = pd.read_csv(EVAL/filename)
        numeric = frame.select_dtypes("number")
        assert numeric.apply(lambda column: column.map(math.isfinite).all()).all()

def test_line_item_matching_never_reuses_prediction():
    expected = [{"description":"Paper","quantity":1,"unit_price":2,"line_total":2},
                {"description":"Paper","quantity":1,"unit_price":2,"line_total":2}]
    predicted = [{"description":"Paper","quantity":1,"unit_price":2,"line_total":2}]
    matches = match_items(expected,predicted)
    assert len(matches) == 1

def test_ocr_error_rates_are_finite():
    frame = pd.read_csv(EVAL/"ocr_text_metrics.csv")
    assert frame[["cer","wer"]].map(math.isfinite).all().all()
    assert error_rate("hello world","hello word",words=True) >= 0

def test_grouped_counts_reconcile():
    for filename, column in [
        ("performance_by_quality.csv","variant_count"),
        ("performance_by_format.csv","variant_count"),
        ("performance_by_template.csv","variant_count"),
        ("performance_by_document_type.csv","variant_count"),
    ]:
        assert pd.read_csv(EVAL/filename)[column].sum() == 84

def test_required_charts_exist_and_are_not_blank():
    names = ["field_accuracy.png","performance_by_quality.png","invoice_vs_receipt.png",
        "line_item_performance.png","ocr_error_by_quality.png","confidence_vs_correctness.png",
        "error_categories.png","processing_time_by_method.png","document_type_confusion_matrix.png"]
    for name in names:
        path = ROOT/"outputs/charts"/name
        with Image.open(path) as image:
            assert image.width > 500 and image.height > 300
            assert sum(ImageStat.Stat(image.convert("L")).var) > 10

def test_summary_matches_detailed_metrics():
    summary = json.loads((EVAL/"evaluation_summary.json").read_text(encoding="utf-8"))
    dtype = json.loads((EVAL/"document_type_metrics.json").read_text(encoding="utf-8"))
    line = pd.read_csv(EVAL/"line_item_metrics.csv")
    all_line = line[(line.group_type=="all") & (line.group=="all")].iloc[0]
    assert summary["document_type_classification"]["accuracy"] == dtype["accuracy"]
    assert abs(summary["line_item_row_f1"] - all_line.row_f1) < 1e-12

def test_evaluation_did_not_modify_extraction_outputs():
    metadata = json.loads((EVAL/"evaluation_run_metadata.json").read_text(encoding="utf-8"))
    assert metadata["stage3_extraction_output_hashes"] == extraction_output_hashes()

def test_predictions_saved_before_truth_access_contract():
    metadata = json.loads((EVAL/"evaluation_run_metadata.json").read_text(encoding="utf-8"))
    assert metadata["prediction_files_saved_before_truth_access"] is True
    source = (ROOT/"src/evaluation.py").read_text(encoding="utf-8")
    assert source.index("test_predictions.json").__class__ is int
    assert source.index("def _truth_maps") > source.index("def generate_test_predictions")

def test_required_evaluation_outputs_exist():
    names = ["test_split_summary.json","evaluation_run_metadata.json","test_predictions.json",
        "test_document_predictions.csv","test_line_item_predictions.csv","document_type_metrics.json",
        "field_metrics.csv","numeric_field_metrics.csv","line_item_metrics.csv",
        "line_item_document_metrics.csv","ocr_text_metrics.csv","performance_by_quality.csv",
        "performance_by_format.csv","performance_by_template.csv","performance_by_document_type.csv",
        "confidence_analysis.csv","validation_warning_analysis.csv","runtime_metrics.json",
        "error_analysis.csv","evaluation_summary.json"]
    assert all((EVAL/name).exists() and (EVAL/name).stat().st_size > 20 for name in names)

