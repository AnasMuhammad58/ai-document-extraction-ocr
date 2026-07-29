from pathlib import Path
import json
import openpyxl
import pytest
from streamlit.testing.v1 import AppTest
from src.app_services import apply_review, make_downloads, result_to_review, validate_upload
from src.config import ROOT
from src.schemas import ExtractionResult

@pytest.fixture(scope="module")
def initial_app():
    app = AppTest.from_file(str(ROOT/"app.py"), default_timeout=60).run()
    assert not app.exception
    return app

@pytest.fixture(scope="module")
def processed_app():
    app = AppTest.from_file(str(ROOT/"app.py"), default_timeout=60).run()
    app.button[0].click().run(timeout=60)
    assert not app.exception
    return app

def test_app_starts_and_title_appears(initial_app):
    assert any("AI Document Extraction" in element.value for element in initial_app.markdown)

def test_file_uploader_and_supported_formats_appear(initial_app):
    assert len(initial_app.get("file_uploader")) == 1
    assert any("Digital PDF" in element.value and "JPEG" in element.value
               for element in initial_app.markdown)

def test_sample_selector_and_preview_work(initial_app):
    assert initial_app.selectbox[0].label == "Try a Synthetic Sample"
    assert initial_app.selectbox[0].value == "Clean invoice (digital PDF)"
    assert len(initial_app.get("imgs")) >= 1 or len(initial_app.get("image")) >= 1

def test_extraction_button_exists(initial_app):
    assert any(button.label == "Extract Document Data" for button in initial_app.button)

def test_synthetic_sample_processes_and_metrics_appear(processed_app):
    values = {metric.label: metric.value for metric in processed_app.metric}
    assert values["Successful"] == "1"
    assert values["Invoices"] == "1"
    assert values["Embedded text"] == "1"

def test_fields_line_items_and_validation_appear(processed_app):
    # AppTest exposes st.data_editor through the arrow_data_frame collection.
    assert len(processed_app.dataframe) >= 3
    headings = [x.value for x in processed_app.subheader]
    assert "4. Review results" in headings
    assert any("Validation Results" in x.value for x in processed_app.markdown)

def test_download_controls_appear(processed_app):
    labels = [x.label for x in processed_app.get("download_button")]
    assert {"Download JSON","Document summary CSV","Line items CSV",
            "Warnings CSV","Download Excel"} <= set(labels)

def test_raw_text_can_be_enabled(processed_app):
    raw_toggle = next(x for x in processed_app.toggle if x.label == "Show raw OCR text")
    raw_toggle.set_value(True).run(timeout=60)
    assert not processed_app.exception
    assert any(x.label == "Raw extracted text" for x in processed_app.expander)

def test_invalid_upload_is_rejected_cleanly():
    assert "Unsupported file type" in validate_upload("malware.exe", b"not a document")
    assert "empty" in validate_upload("empty.pdf", b"").lower()

def test_download_bytes_are_genuine_and_excel_opens():
    payload = json.loads((ROOT/"outputs/extracted/document_results.json").read_text(encoding="utf-8"))[0]
    review = result_to_review(ExtractionResult.model_validate(payload))
    downloads = make_downloads([review])
    assert json.loads(downloads["json"])[0]["reviewed_fields"]
    temp = ROOT/"outputs/app_screenshots/_download_test.xlsx"
    temp.parent.mkdir(parents=True, exist_ok=True)
    temp.write_bytes(downloads["excel"])
    workbook = openpyxl.load_workbook(temp, read_only=True)
    assert workbook.sheetnames == ["Documents","Line Items","Validation Warnings","Run Summary"]
    workbook.close()
    temp.unlink()

def test_review_preserves_original_recalculates_and_revalidates():
    payload = json.loads((ROOT/"outputs/extracted/document_results.json").read_text(encoding="utf-8"))[0]
    review = result_to_review(ExtractionResult.model_validate(payload))
    original = dict(review["original_fields"])
    changed = dict(original)
    amount_field = "total_amount"
    changed[amount_field] = 999.0
    item = {"description":"Reviewed row","quantity":2,"unit_price":3.5,
            "line_total":None,"raw_text":"","confidence":1.0}
    updated = apply_review(review, changed, [item])
    assert updated["original_fields"] == original
    assert amount_field in updated["edited_fields"]
    assert updated["reviewed_line_items"][0]["line_total"] == 7.0
    assert updated["review_warnings"]
