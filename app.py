from __future__ import annotations
import json
import logging
import time
from pathlib import Path
import pandas as pd
import streamlit as st
from src.app_services import (
    SAMPLES, apply_review, batch_summary, make_downloads, preview_info,
    process_bytes, result_to_review, validate_upload,
)
from src.config import ROOT, load_config
from src.ocr_engine import OfflineOCREngine

st.set_page_config(page_title="AI Document Extraction", page_icon="📄", layout="wide",
                   initial_sidebar_state="expanded")
st.markdown("""
<style>
  .stApp { background: #faf8f3; color: #162b45; }
  h1, h2, h3 { color: #162b45; letter-spacing: -0.02em; }
  [data-testid="stSidebar"] { background: #f0eee8; border-right: 1px solid #dedbd2; }
  [data-testid="stMetric"] { background: #ffffff; border: 1px solid #dedbd2;
    border-radius: 10px; padding: 12px 14px; }
  .hero { background: #fff; border: 1px solid #dedbd2; border-left: 5px solid #3f7d63;
    padding: 18px 22px; border-radius: 12px; margin-bottom: 18px; }
  .subtle { color: #536273; font-size: .94rem; }
  .status-ok { color: #256044; font-weight: 700; }
  .status-review { color: #9a5b16; font-weight: 700; }
  .document-card { background: white; border: 1px solid #dedbd2; border-radius: 12px;
    padding: 12px; margin-bottom: 8px; }
</style>
""", unsafe_allow_html=True)

cfg = load_config()["extraction"]
logging.basicConfig(filename=ROOT/"logs/pipeline.log", level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")

@st.cache_resource(show_spinner="Loading offline OCR engine…")
def get_ocr_engine():
    return OfflineOCREngine()

def source_records():
    records = []
    uploads = st.session_state.get("uploaded_documents") or []
    for uploaded in uploads:
        records.append({"name": uploaded.name, "data": uploaded.getvalue(), "source": "upload"})
    selected = st.session_state.get("sample_document")
    if selected and selected != "None":
        path = SAMPLES[selected]
        records.append({"name": path.name, "data": path.read_bytes(), "source": "synthetic sample"})
    # Keep one instance of identical bytes.
    unique = {}
    for record in records:
        unique[(record["name"], hash(record["data"]))] = record
    return list(unique.values())

def friendly_warning(row):
    actions = {
        "TOTAL_MISMATCH": "Review subtotal, tax, and total.",
        "LINE_ITEM_SUM_MISMATCH": "Review quantities and line totals.",
        "NO_LINE_ITEMS_FOUND": "Add or review product rows.",
        "LOW_OCR_CONFIDENCE": "Try a clearer scan.",
        "DOCUMENT_TYPE_UNCERTAIN": "Confirm the document type.",
        "MISSING_DATE": "Enter the printed document date.",
        "MISSING_DOCUMENT_NUMBER": "Enter the printed invoice or receipt number.",
    }
    return {**row, "suggested_review_action": actions.get(row["code"], "Review the affected field.")}

st.markdown("""<div class="hero">
<h1 style="margin:0">AI Document Extraction</h1>
<p style="font-size:1.12rem;margin:.35rem 0">Convert invoices and receipts into structured Excel, CSV, and JSON data.</p>
<p class="subtle" style="margin:0">This demonstration processes printed English invoices and receipts. Results depend on document quality and layout complexity.</p>
</div>""", unsafe_allow_html=True)

with st.sidebar:
    st.header("Processing settings")
    preprocessing = st.toggle("Enable image preprocessing", value=True)
    use_cache = st.toggle("Use cached OCR results when available", value=True)
    show_raw = st.toggle("Show raw OCR text", value=False)
    show_evidence = st.toggle("Show extraction evidence", value=False)
    confidence_threshold = st.slider("Confidence threshold", 0.0, 1.0,
                                     float(cfg["low_extraction_confidence"]), .05)
    tolerance = st.number_input("Numeric validation tolerance", min_value=0.0, max_value=5.0,
                                value=float(cfg["numeric_tolerance"]), step=.01)
    st.divider()
    st.subheader("Supported inputs")
    st.markdown("Digital PDF · Scanned PDF · PNG · JPG · JPEG")
    st.divider()
    st.subheader("Important note")
    st.caption("Printed English documents are supported. Handwriting and multilingual documents are outside the current demonstration scope. Sensitive information should be anonymized before upload.")

st.subheader("1. Add documents")
upload_col, sample_col = st.columns([1.5, 1])
with upload_col:
    st.file_uploader("Upload one or more invoices or receipts", type=["pdf","png","jpg","jpeg"],
                     accept_multiple_files=True, key="uploaded_documents",
                     help="Maximum 20 MB per file.")
with sample_col:
    st.selectbox("Try a Synthetic Sample", ["None", *SAMPLES.keys()],
                 index=1, key="sample_document")
    st.caption("Samples are existing fictional Stage 1 documents and use the normal extraction pipeline.")

records = source_records()
valid_records, preview_failures = [], []
if records:
    st.subheader("2. Preview")
    preview_tabs = st.tabs([r["name"] for r in records])
    for tab, record in zip(preview_tabs, records):
        with tab:
            error = validate_upload(record["name"], record["data"])
            if error:
                st.error(error); preview_failures.append({"file": record["name"], "error": error}); continue
            try:
                info = preview_info(record["name"], record["data"])
                left, right = st.columns([1.25, .75])
                with left: st.image(info["image"], caption=f'{record["name"]} — first-page preview', width=520)
                with right:
                    st.markdown(f"**Filename:** {record['name']}")
                    st.markdown(f"**Type:** {info['file_type']}")
                    st.markdown(f"**Size:** {len(record['data'])/1024:.1f} KB")
                    st.markdown(f"**Pages:** {info['page_count']}")
                    st.markdown(f"**Source:** {record['source'].title()}")
                    if info["page_count"] > 1:
                        st.warning("This demonstration processes only the first page of multi-page PDFs.")
                valid_records.append(record)
            except Exception as exc:
                message = str(exc)
                st.error(message); preview_failures.append({"file": record["name"], "error": message})

extract_clicked = st.button("Extract Document Data", type="primary", disabled=not valid_records,
                            use_container_width=True)
if extract_clicked:
    engine = get_ocr_engine()
    reviews, failures = [], list(preview_failures)
    started = time.perf_counter()
    progress = st.progress(0, text="Preparing documents")
    for index, record in enumerate(valid_records):
        status = st.status(f"Processing {record['name']}", expanded=True)
        try:
            status.write("Loading document")
            status.write("Extracting embedded text or running OCR")
            result = process_bytes(record["name"], record["data"], engine, use_cache,
                                   preprocessing, tolerance)
            status.write("Detecting document type and extracting fields")
            status.write("Extracting line items and running validation")
            status.write("Preparing reviewed result")
            reviews.append(result_to_review(result))
            status.update(label=f"{record['name']} processed", state="complete", expanded=False)
        except Exception as exc:
            logging.exception("App processing failed for %s", record["name"])
            failures.append({"file": record["name"], "error": str(exc)})
            status.update(label=f"{record['name']} could not be processed", state="error")
        progress.progress((index+1)/len(valid_records), text=f"Completed {index+1} of {len(valid_records)}")
    st.session_state["reviews"] = reviews
    st.session_state["failures"] = failures
    st.session_state["batch_summary"] = batch_summary(reviews, len(records), failures,
                                                       time.perf_counter()-started)
    st.session_state["source_bytes"] = {r["name"]: r["data"] for r in valid_records}

reviews = st.session_state.get("reviews", [])
failures = st.session_state.get("failures", [])
if reviews or failures:
    summary = st.session_state["batch_summary"]
    st.subheader("3. Batch summary")
    metric_values = [
        ("Uploaded", summary["uploaded"]), ("Successful", summary["successful"]),
        ("Failed", summary["failed"]), ("Invoices", summary["invoices"]),
        ("Receipts", summary["receipts"]), ("Embedded text", summary["embedded"]),
        ("OCR", summary["ocr"]), ("High confidence", summary["high"]),
        ("Medium confidence", summary["medium"]), ("Low confidence", summary["low"]),
        ("Warnings", summary["warnings"]), ("Processing time", f'{summary["seconds"]:.2f}s'),
    ]
    for start in range(0, len(metric_values), 6):
        cols = st.columns(6)
        for col, (label, value) in zip(cols, metric_values[start:start+6]):
            col.metric(label, value)
    for failure in failures:
        st.error(f'**{failure["file"]}:** {failure["error"]}')

    st.subheader("4. Review results")
    result_tabs = st.tabs([review["result"].file_name for review in reviews])
    for doc_index, (tab, review) in enumerate(zip(result_tabs, reviews)):
        with tab:
            result = review["result"]
            status_class = "status-ok" if result.validation_status == "Passed" else "status-review"
            st.markdown(f"""<div class="document-card"><b>{result.file_name}</b><br>
            {result.document_type.title()} · {result.extraction_method.replace('_',' ').title()} ·
            {result.processing_time_seconds:.2f}s · <span class="{status_class}">{result.confidence.label} confidence ({result.structured_confidence:.3f})</span> ·
            Validation: {result.validation_status}</div>""", unsafe_allow_html=True)
            if result.structured_confidence < confidence_threshold:
                st.warning("This result is below your selected confidence threshold and should be reviewed carefully.")
            preview_col, fields_col = st.columns([.85, 1.15])
            with preview_col:
                data = st.session_state.get("source_bytes", {}).get(result.file_name)
                if data:
                    try: st.image(preview_info(result.file_name, data)["image"], width=430)
                    except Exception: st.info("Preview is unavailable after processing.")
            with fields_col:
                st.markdown(f"#### {result.document_type.title()} fields")
                original = review["original_fields"]
                rows = [{"Field": key.replace("_"," ").title(),
                         "Reviewed Value": "" if value is None else value,
                         "Original Extracted Value": "" if value is None else value}
                        for key, value in review["reviewed_fields"].items()]
                edited_df = st.data_editor(pd.DataFrame(rows), hide_index=True, use_container_width=True,
                    disabled=["Field","Original Extracted Value"], key=f"fields_editor_{doc_index}")
                edited_fields = {}
                for (key, old), value in zip(review["reviewed_fields"].items(), edited_df["Reviewed Value"]):
                    if value == "": value = None
                    elif isinstance(old, (float, int)) and value is not None:
                        try: value = float(value)
                        except (TypeError, ValueError): pass
                    edited_fields[key] = value
                button_cols = st.columns(3)
                if button_cols[0].button("Apply corrections", key=f"apply_{doc_index}"):
                    items = st.session_state.get(f"items_value_{doc_index}", review["reviewed_line_items"])
                    st.session_state["reviews"][doc_index] = apply_review(review, edited_fields, items, tolerance)
                    st.rerun()
                if button_cols[1].button("Reset edits", key=f"reset_{doc_index}"):
                    review["reviewed_fields"] = dict(review["original_fields"])
                    review["reviewed_line_items"] = list(review["original_line_items"])
                    review["edited_fields"] = []
                    st.rerun()
                if button_cols[2].button("Revalidate", key=f"revalidate_{doc_index}"):
                    items = st.session_state.get(f"items_value_{doc_index}", review["reviewed_line_items"])
                    st.session_state["reviews"][doc_index] = apply_review(review, edited_fields, items, tolerance)
                    st.rerun()
                if review["edited_fields"]:
                    st.success("Edited fields: " + ", ".join(x.replace("_"," ").title() for x in review["edited_fields"]))

            st.markdown("#### Line items")
            if review["reviewed_line_items"]:
                item_df = pd.DataFrame(review["reviewed_line_items"]).rename(columns={
                    "description":"Description","quantity":"Quantity","unit_price":"Unit Price",
                    "line_total":"Line Total","confidence":"Confidence","raw_text":"Raw Text"})
            else:
                st.info("No line items were detected. Add rows below if the document contains products.")
                item_df = pd.DataFrame(columns=["Description","Quantity","Unit Price","Line Total","Confidence","Raw Text"])
            edited_items = st.data_editor(item_df, num_rows="dynamic", hide_index=True,
                column_config={"Confidence": st.column_config.NumberColumn(disabled=True),
                               "Raw Text": st.column_config.TextColumn(disabled=True)},
                use_container_width=True, key=f"line_items_editor_{doc_index}")
            normalized_items = edited_items.rename(columns={"Description":"description","Quantity":"quantity",
                "Unit Price":"unit_price","Line Total":"line_total","Confidence":"confidence",
                "Raw Text":"raw_text"}).where(pd.notna(edited_items), None).to_dict("records")
            st.session_state[f"items_value_{doc_index}"] = normalized_items

            st.markdown("#### Validation Results")
            warnings = [friendly_warning(x) for x in review["review_warnings"]]
            if warnings:
                st.dataframe(pd.DataFrame(warnings), hide_index=True, use_container_width=True)
            else: st.success("No validation warnings.")

            with st.expander("How confidence was calculated"):
                st.caption("Confidence estimates extraction reliability; it is not a guarantee of correctness.")
                components = result.confidence.components
                st.write(f'OCR confidence (30%): **{components["ocr"]:.3f}**')
                st.write(f'Field evidence (35%): **{components["field_evidence"]:.3f}**')
                st.write(f'Document-type confidence (15%): **{components["document_type"]:.3f}**')
                st.write(f'Validation consistency (20%): **{components["validation_consistency"]:.3f}**')
            if show_raw:
                with st.expander("Raw extracted text", expanded=False):
                    try:
                        raw = json.loads((ROOT/result.raw_text_path).read_text(encoding="utf-8"))["raw_text"]
                        st.text_area("Raw text", raw, height=260, key=f"raw_{doc_index}")
                    except Exception: st.warning("Raw extraction text is unavailable.")
            if show_evidence:
                with st.expander("Extraction evidence", expanded=False):
                    evidence = [{"Field": key, **value.model_dump()} for key,value in result.field_evidence.items()]
                    st.dataframe(pd.DataFrame(evidence), hide_index=True, use_container_width=True)

    st.subheader("5. Download reviewed data")
    try:
        downloads = make_downloads(reviews)
        cols = st.columns(5)
        cols[0].download_button("Download JSON", downloads["json"], "document_results.json", "application/json")
        cols[1].download_button("Document summary CSV", downloads["documents_csv"], "document_summary.csv", "text/csv")
        cols[2].download_button("Line items CSV", downloads["line_items_csv"], "line_items.csv", "text/csv")
        cols[3].download_button("Warnings CSV", downloads["warnings_csv"], "validation_warnings.csv", "text/csv")
        cols[4].download_button("Download Excel", downloads["excel"], "document_extraction_results.xlsx",
                                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        if len(reviews) == 1:
            st.caption("The downloads above contain the current reviewed values and preserve original extracted fields.")
    except Exception:
        logging.exception("App export preparation failed")
        st.error("Downloads could not be prepared. Technical details were written to logs/pipeline.log.")
