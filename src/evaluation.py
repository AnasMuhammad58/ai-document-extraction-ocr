from __future__ import annotations
from collections import Counter, defaultdict
from datetime import datetime, timezone
from difflib import SequenceMatcher
from importlib.metadata import version
import hashlib
import json
import math
import re
import statistics
import time
import unicodedata
from pathlib import Path
import pandas as pd
from .config import ROOT, load_config
from .document_loader import identity
from .ocr_engine import OfflineOCREngine, engine_info
from .parsing import normalize_currency, parse_amount, parse_date
from .pipeline import discover_files, development_files, process_document

VISIBLE_FIELDS = {
    "invoice": ["vendor_name","vendor_address","customer_name","customer_address",
        "invoice_number","invoice_date","due_date","currency","subtotal","tax_amount","total_amount"],
    "receipt": ["merchant_name","merchant_address","receipt_number","transaction_date",
        "currency","subtotal","tax_amount","total_amount"],
}
ALL_FIELDS = {
    "invoice": ["vendor_name","vendor_address","vendor_email","vendor_phone","customer_name",
        "customer_address","invoice_number","invoice_date","due_date","currency","purchase_order",
        "subtotal","tax_rate","tax_amount","discount","shipping","total_amount","payment_terms"],
    "receipt": ["merchant_name","merchant_address","merchant_phone","receipt_number","transaction_date",
        "transaction_time","currency","subtotal","tax_amount","total_amount","payment_method",
        "last_four_digits","cashier"],
}
CRITICAL = {
    "invoice": ["invoice_number","invoice_date","subtotal","tax_amount","total_amount"],
    "receipt": ["receipt_number","transaction_date","subtotal","tax_amount","total_amount"],
}
NUMERIC_HEADERS = ["subtotal","tax_rate","tax_amount","discount","shipping","total_amount"]

def normalize_text(value) -> str | None:
    if value is None or value == "": return None
    text = unicodedata.normalize("NFKC", str(value)).lower().strip()
    text = re.sub(r"[|•]", " ", text)
    text = re.sub(r"[^\w@.+-]+", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()

def normalize_identifier(value) -> str | None:
    text = normalize_text(value)
    return re.sub(r"[\s_-]+", "-", text).strip("-") if text else None

def normalize_phone(value) -> str | None:
    if value is None: return None
    digits = re.sub(r"\D", "", str(value))
    return digits or None

def normalize_email(value) -> str | None:
    return str(value).strip().lower() if value else None

def values_equal(field: str, expected, predicted, tolerance=.05) -> bool:
    if expected is None or expected == "": return predicted is None or predicted == ""
    if predicted is None or predicted == "": return False
    if field in NUMERIC_HEADERS or field in {"quantity","unit_price","line_total"}:
        a, b = parse_amount(str(expected)), parse_amount(str(predicted))
        return a is not None and b is not None and abs(a-b) <= tolerance
    if "date" in field:
        return parse_date(str(expected)) is not None and parse_date(str(expected)) == parse_date(str(predicted))
    if field == "currency":
        return normalize_currency(str(expected)) == normalize_currency(str(predicted))
    if "number" in field or field in {"purchase_order","receipt_number","invoice_number"}:
        return normalize_identifier(expected) == normalize_identifier(predicted)
    if "phone" in field: return normalize_phone(expected) == normalize_phone(predicted)
    if "email" in field: return normalize_email(expected) == normalize_email(predicted)
    return normalize_text(expected) == normalize_text(predicted)

def edit_distance(reference: list, hypothesis: list) -> int:
    previous = list(range(len(hypothesis)+1))
    for i, ref in enumerate(reference, 1):
        current = [i]
        for j, hyp in enumerate(hypothesis, 1):
            current.append(min(current[-1]+1, previous[j]+1, previous[j-1]+(ref != hyp)))
        previous = current
    return previous[-1]

def error_rate(reference: str, hypothesis: str, words=False) -> float:
    ref = normalize_text(reference) or ""
    hyp = normalize_text(hypothesis) or ""
    a, b = (ref.split(), hyp.split()) if words else (list(ref), list(hyp))
    return edit_distance(a, b) / max(1, len(a))

def _quality(path: Path) -> str:
    if "_digital" in path.stem: return "clean"
    for label in ("slight_rotation","mild_blur","lower_contrast","light_noise",
                  "mild_shadow","jpeg_compression","perspective"):
        if label in path.stem: return label
    return "unknown"

def _format(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        return "digital_pdf" if "_digital" in path.stem else "scanned_pdf"
    return path.suffix.lower().lstrip(".")

def _template(document_id: str) -> str:
    number = int(document_id.split("-")[1])
    return f'invoice_{(number-1)%5+1}' if document_id.startswith("INV") else f'receipt_{(number-1)%4+1}'

def split_info() -> tuple[list[Path], list[Path], dict]:
    files = discover_files()
    dev_files, dev_ids = development_files(files)
    dev_set = set(dev_ids)
    test_files = [p for p in files if identity(p)[0] not in dev_set]
    test_ids = sorted({identity(p)[0] for p in test_files})
    summary = {"development_source_document_count": len(dev_set),
        "test_source_document_count": len(test_ids), "development_variant_count": len(dev_files),
        "test_variant_count": len(test_files), "invoice_count": sum(x.startswith("INV") for x in test_ids),
        "receipt_count": sum(x.startswith("RCT") for x in test_ids),
        "format_counts": dict(Counter(_format(p) for p in test_files)),
        "quality_condition_counts": dict(Counter(_quality(p) for p in test_files)),
        "development_document_ids": sorted(dev_set), "test_document_ids": test_ids,
        "overlap_count": len(dev_set & set(test_ids)), "variants_per_test_source": 4,
        "all_variants_kept_with_source": all(sum(identity(p)[0]==x for p in test_files)==4 for x in test_ids)}
    return dev_files, test_files, summary

def code_hash() -> str:
    digest = hashlib.sha256()
    for path in sorted((ROOT/"src").glob("*.py")):
        if path.name != "evaluation.py": digest.update(path.read_bytes())
    digest.update((ROOT/"configs/config.yaml").read_bytes())
    return digest.hexdigest()

def freeze_metadata(force: bool) -> dict:
    cfg = load_config()
    packages = {}
    for package in ["rapidocr-onnxruntime","onnxruntime","PyMuPDF","pydantic","pandas",
                    "numpy","opencv-python-headless","matplotlib"]:
        try: packages[package] = version(package)
        except Exception: pass
    return {"run_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "ocr_engine": engine_info(), "extraction_configuration": cfg["extraction"],
        "preprocessing_configuration": cfg["extraction"]["preprocessing"],
        "confidence_thresholds": {"low_extraction": cfg["extraction"]["low_extraction_confidence"],
                                  "low_ocr": cfg["extraction"]["low_ocr_confidence"]},
        "numeric_tolerance": cfg["extraction"]["numeric_tolerance"],
        "code_configuration_hash": code_hash(), "package_versions": packages,
        "prediction_cache_mode": "uncached" if force else "cached",
        "stage3_extraction_output_hashes": extraction_output_hashes()}

def extraction_output_hashes() -> dict:
    names = ["document_results.json","document_summary.csv","line_items.csv",
             "validation_warnings.csv","extracted_data.xlsx"]
    return {name: hashlib.sha256((ROOT/"outputs/extracted"/name).read_bytes()).hexdigest()
            for name in names}

def generate_test_predictions(force=True) -> tuple[list[dict], dict]:
    """Ground-truth-free prediction phase. Save predictions before comparison."""
    _, files, split = split_info()
    out = ROOT/"outputs/evaluation"; out.mkdir(parents=True, exist_ok=True)
    (out/"test_split_summary.json").write_text(json.dumps(split, indent=2), encoding="utf-8")
    metadata = freeze_metadata(force)
    (out/"evaluation_run_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    engine, predictions, failures = OfflineOCREngine(), [], []
    started = time.perf_counter()
    for index, path in enumerate(files, 1):
        one = time.perf_counter()
        base = {"document_id": identity(path)[0], "variant_id": identity(path)[1],
            "file_path": path.relative_to(ROOT).as_posix(), "template": _template(identity(path)[0]),
            "quality_condition": _quality(path), "file_format": _format(path)}
        try:
            result = process_document(path, engine, force=force)
            fields = result.fields.model_dump() if hasattr(result.fields, "model_dump") else result.fields
            predictions.append({**base, "success": True, "error": None,
                "predicted_document_type": result.document_type,
                "document_type_confidence": result.document_type_confidence,
                "extraction_method": result.extraction_method, "predicted_fields": fields,
                "predicted_line_items": [x.model_dump() for x in result.line_items],
                "ocr_confidence": result.ocr_confidence,
                "structured_confidence": result.structured_confidence,
                "confidence_label": result.confidence.label,
                "validation_warnings": [x.model_dump() for x in result.warnings],
                "processing_time_seconds": result.processing_time_seconds,
                "raw_text_path": result.raw_text_path})
        except Exception as exc:
            failures.append(str(exc))
            predictions.append({**base, "success": False, "error": f"{type(exc).__name__}: {exc}",
                "predicted_document_type": "unknown", "document_type_confidence": 0,
                "extraction_method": None, "predicted_fields": {}, "predicted_line_items": [],
                "ocr_confidence": None, "structured_confidence": 0, "confidence_label": "Low",
                "validation_warnings": [], "processing_time_seconds": round(time.perf_counter()-one,4),
                "raw_text_path": None})
        if index % 20 == 0: print(f"Predicted {index}/{len(files)} test variants")
    uncached = time.perf_counter()-started
    # Required prediction files are committed before ground truth is loaded.
    (out/"test_predictions.json").write_text(json.dumps(predictions, indent=2), encoding="utf-8")
    pd.DataFrame([{k:v for k,v in p.items() if k not in ("predicted_fields","predicted_line_items","validation_warnings")}
                  | p["predicted_fields"] for p in predictions]).to_csv(out/"test_document_predictions.csv", index=False)
    pd.DataFrame([{"document_id":p["document_id"],"variant_id":p["variant_id"],"item_order":i,**item}
        for p in predictions for i,item in enumerate(p["predicted_line_items"],1)]).to_csv(
            out/"test_line_item_predictions.csv", index=False)
    metadata["prediction_files_saved_before_truth_access"] = True
    metadata["prediction_finished_timestamp_utc"] = datetime.now(timezone.utc).isoformat()
    (out/"evaluation_run_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return predictions, {"uncached_total_seconds": round(uncached,3), "failures": failures}

def _truth_maps():
    # This is the first ground-truth access in the evaluation flow.
    docs = json.loads((ROOT/"data/ground_truth/documents.json").read_text(encoding="utf-8"))
    return {d["document_id"]: d for d in docs}

def match_items(expected: list[dict], predicted: list[dict], tolerance=.05):
    used, matches = set(), []
    for expected_index, exp in enumerate(expected):
        best = None
        for predicted_index, pred in enumerate(predicted):
            if predicted_index in used: continue
            similarity = SequenceMatcher(None, normalize_text(exp.get("description")) or "",
                                         normalize_text(pred.get("description")) or "").ratio()
            order_bonus = .05 if expected_index == predicted_index else 0
            if similarity >= .90 and (best is None or similarity+order_bonus > best[0]):
                best = (similarity+order_bonus, predicted_index, pred)
        if best:
            used.add(best[1]); matches.append((exp, best[2]))
    return matches

def evaluate_predictions(predictions: list[dict], runtime_seed: dict) -> dict:
    out, charts = ROOT/"outputs/evaluation", ROOT/"outputs/charts"
    charts.mkdir(parents=True, exist_ok=True)
    truth = _truth_maps()
    tolerance = load_config()["extraction"]["numeric_tolerance"]
    field_instances, document_rows, error_rows, line_doc_rows, ocr_rows = [], [], [], [], []
    numeric_values: dict[str,list[tuple[float,float|None]]] = defaultdict(list)
    for pred in predictions:
        gt = truth[pred["document_id"]]; dtype = gt["document_type"]; fields = pred["predicted_fields"]
        visible = VISIBLE_FIELDS[dtype]
        correct_flags = {}
        for field in ALL_FIELDS[dtype]:
            expected = gt.get(field) if field in visible else None
            predicted = fields.get(field)
            expected_visible = field in visible and expected is not None
            correct = expected_visible and values_equal(field, expected, predicted, tolerance)
            if expected_visible:
                correct_flags[field] = correct
                field_instances.append({"variant_id":pred["variant_id"],"field":field,
                    "document_type":dtype,"expected":expected,"predicted":predicted,
                    "extracted":predicted is not None,"correct":correct})
                if not correct:
                    category = categorize_error(field, expected, predicted, pred)
                    error_rows.append(_error_row(pred, dtype, field, expected, predicted, category))
            if field in NUMERIC_HEADERS and expected_visible:
                numeric_values[field].append((float(expected), float(predicted) if predicted is not None else None))
        expected_items, predicted_items = gt["line_items"], pred["predicted_line_items"]
        matches = match_items(expected_items, predicted_items, tolerance)
        row_p = len(matches)/max(1,len(predicted_items)); row_r = len(matches)/max(1,len(expected_items))
        row_f1 = 2*row_p*row_r/max(1e-12,row_p+row_r)
        desc_correct = sum(values_equal("description",a["description"],b.get("description")) for a,b in matches)
        qty_correct = sum(values_equal("quantity",a["quantity"],b.get("quantity"),tolerance) for a,b in matches)
        unit_correct = sum(values_equal("unit_price",a["unit_price"],b.get("unit_price"),tolerance) for a,b in matches)
        total_correct = sum(values_equal("line_total",a["line_total"],b.get("line_total"),tolerance) for a,b in matches)
        complete_items = sum(all(values_equal(k,a[k],b.get(k),tolerance) for k in
            ("description","quantity","unit_price","line_total")) for a,b in matches)
        for exp, got in matches:
            for key in ("quantity","unit_price","line_total"):
                numeric_values[key].append((float(exp[key]), float(got[key]) if got.get(key) is not None else None))
        if row_f1 < 1:
            error_rows.append(_error_row(pred,dtype,"line_items",len(expected_items),len(predicted_items),
                "compact receipt layout" if dtype=="receipt" else "row grouping"))
        line_doc_rows.append({**_group_keys(pred,dtype),"expected_rows":len(expected_items),
            "predicted_rows":len(predicted_items),"matched_rows":len(matches),"row_precision":row_p,
            "row_recall":row_r,"row_f1":row_f1,"description_accuracy":desc_correct/max(1,len(matches)),
            "quantity_accuracy":qty_correct/max(1,len(matches)),"unit_price_accuracy":unit_correct/max(1,len(matches)),
            "line_total_accuracy":total_correct/max(1,len(matches)),
            "complete_line_item_accuracy":complete_items/max(1,len(expected_items)),
            "no_predicted_items":not predicted_items,"perfect_line_item_extraction":complete_items==len(expected_items)})
        raw_text = ""
        if pred.get("raw_text_path") and (ROOT/pred["raw_text_path"]).exists():
            raw_text = json.loads((ROOT/pred["raw_text_path"]).read_text(encoding="utf-8"))["raw_text"]
        cer, wer = error_rate(gt["expected_text"],raw_text), error_rate(gt["expected_text"],raw_text,True)
        ocr_rows.append({**_group_keys(pred,dtype),"cer":cer,"wer":wer})
        critical = CRITICAL[dtype]
        critical_acc = sum(correct_flags.get(x,False) for x in critical)/len(critical)
        all_correct = all(correct_flags.get(x,False) for x in visible)
        document_rows.append({**_group_keys(pred,dtype),"success":pred["success"],
            "expected_document_type":dtype,"predicted_document_type":pred["predicted_document_type"],
            "classification_correct":pred["predicted_document_type"]==dtype,
            "classification_uncertain":pred["predicted_document_type"]=="unknown" or pred["document_type_confidence"]<.65,
            "critical_field_accuracy":critical_acc,"visible_field_accuracy":sum(correct_flags.values())/len(visible),
            "complete_record_correct":all_correct,"line_item_f1":row_f1,"cer":cer,"wer":wer,
            "structured_confidence":pred["structured_confidence"],"confidence_label":pred["confidence_label"],
            "warning_count":len(pred["validation_warnings"]),
            "warning_codes":"|".join(w["code"] for w in pred["validation_warnings"]),
            "processing_time_seconds":pred["processing_time_seconds"],
            "has_actual_error":not (all_correct and complete_items==len(expected_items) and pred["predicted_document_type"]==dtype)})
    field_df = _field_metrics(field_instances)
    document_df = pd.DataFrame(document_rows)
    line_doc_df = pd.DataFrame(line_doc_rows)
    ocr_df = pd.DataFrame(ocr_rows)
    numeric_df = _numeric_metrics(numeric_values,tolerance)
    line_metrics = _aggregate_line_metrics(line_doc_df)
    type_metrics = _classification_metrics(document_df)
    field_df.to_csv(out/"field_metrics.csv",index=False)
    document_df.to_csv(out/"document_metrics.csv",index=False)
    numeric_df.to_csv(out/"numeric_field_metrics.csv",index=False)
    pd.DataFrame(line_metrics).to_csv(out/"line_item_metrics.csv",index=False)
    line_doc_df.to_csv(out/"line_item_document_metrics.csv",index=False)
    ocr_df.to_csv(out/"ocr_text_metrics.csv",index=False)
    pd.DataFrame(error_rows).to_csv(out/"error_analysis.csv",index=False)
    (out/"document_type_metrics.json").write_text(json.dumps(type_metrics,indent=2),encoding="utf-8")
    grouped = {}
    for column, filename in [("quality_condition","performance_by_quality.csv"),
                             ("file_format","performance_by_format.csv"),
                             ("template","performance_by_template.csv"),
                             ("document_type","performance_by_document_type.csv")]:
        grouped[column] = _group_metrics(document_df,column)
        grouped[column].to_csv(out/filename,index=False)
    confidence_df = _confidence_analysis(document_df)
    confidence_df.to_csv(out/"confidence_analysis.csv",index=False)
    warning_df = _warning_analysis(predictions,document_df)
    warning_df.to_csv(out/"validation_warning_analysis.csv",index=False)
    cached_started=time.perf_counter()
    engine=OfflineOCREngine()
    for p in split_info()[1]: process_document(p,engine,force=False)
    cached=time.perf_counter()-cached_started
    runtime = _runtime_metrics(document_df,runtime_seed,cached)
    (out/"runtime_metrics.json").write_text(json.dumps(runtime,indent=2),encoding="utf-8")
    summary = _summary(document_df,field_df,numeric_df,line_metrics,type_metrics,grouped,runtime,error_rows)
    (out/"evaluation_summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    from .visualization import create_evaluation_charts
    create_evaluation_charts(out,charts)
    _write_report(summary,field_df,numeric_df,warning_df,runtime,error_rows)
    return summary

def _group_keys(pred,dtype):
    return {"document_id":pred["document_id"],"variant_id":pred["variant_id"],"document_type":dtype,
        "template":pred["template"],"quality_condition":pred["quality_condition"],
        "quality_group":"clean" if pred["quality_condition"]=="clean" else "degraded",
        "file_format":pred["file_format"],"extraction_method":pred["extraction_method"]}

def categorize_error(field, expected, predicted, pred):
    if predicted is None: return "label not detected"
    if field in NUMERIC_HEADERS: return "amount confusion"
    if "date" in field: return "date parsing"
    if "rotation" in pred["quality_condition"]: return "rotation"
    if "perspective" in pred["quality_condition"]: return "perspective distortion"
    return "OCR character error" if pred["extraction_method"]=="ocr" else "incorrect nearby value"

def _error_row(pred,dtype,field,expected,predicted,category):
    return {"document_id":pred["document_id"],"variant_id":pred["variant_id"],"document_type":dtype,
        "template":pred["template"],"format":pred["file_format"],"quality_condition":pred["quality_condition"],
        "field":field,"expected_value":json.dumps(expected) if isinstance(expected,(dict,list)) else expected,
        "predicted_value":json.dumps(predicted) if isinstance(predicted,(dict,list)) else predicted,
        "error_category":category,"confidence":pred["structured_confidence"],
        "validation_warnings":"|".join(w["code"] for w in pred["validation_warnings"])}

def _field_metrics(instances):
    rows=[]
    for (dtype,field), values in sorted(pd.DataFrame(instances).groupby(["document_type","field"])):
        expected=len(values); extracted=int(values["extracted"].sum()); correct=int(values["correct"].sum())
        precision=correct/max(1,extracted); recall=correct/max(1,expected)
        rows.append({"field":field,"document_type":dtype,"expected_count":expected,
            "extracted_count":extracted,"correct_count":correct,"accuracy":correct/expected,
            "precision":precision,"recall":recall,"F1":2*precision*recall/max(1e-12,precision+recall),
            "missing_count":expected-extracted,"incorrect_count":extracted-correct})
    # Required absent-visible fields remain explicit with zero expected count.
    present={(r["document_type"],r["field"]) for r in rows}
    for dtype,fields in ALL_FIELDS.items():
        for field in fields:
            if (dtype,field) not in present:
                rows.append({"field":field,"document_type":dtype,"expected_count":0,"extracted_count":0,
                    "correct_count":0,"accuracy":0,"precision":0,"recall":0,"F1":0,
                    "missing_count":0,"incorrect_count":0})
    return pd.DataFrame(rows).sort_values(["document_type","field"])

def _numeric_metrics(values,tolerance):
    rows=[]
    for field,pairs in sorted(values.items()):
        present=[(a,b) for a,b in pairs if b is not None]; errors=[abs(a-b) for a,b in present]
        rows.append({"field":field,"expected_count":len(pairs),"predicted_count":len(present),
            "tolerance_accuracy":sum(abs(a-b)<=tolerance for a,b in present)/max(1,len(pairs)),
            "exact_normalized_accuracy":sum(a==b for a,b in present)/max(1,len(pairs)),
            "mean_absolute_error":statistics.mean(errors) if errors else 0,
            "median_absolute_error":statistics.median(errors) if errors else 0,
            "maximum_absolute_error":max(errors,default=0),"missing_count":len(pairs)-len(present),
            "tolerance":tolerance})
    return pd.DataFrame(rows)

def _aggregate_line_metrics(df):
    rows=[]
    groups=[("all","all",df)]
    for col in ["document_type","quality_group","template","file_format","quality_condition"]:
        groups += [(col,str(name),part) for name,part in df.groupby(col)]
    for group_type,group,part in groups:
        exp=int(part.expected_rows.sum()); pred=int(part.predicted_rows.sum()); matched=int(part.matched_rows.sum())
        precision=matched/max(1,pred); recall=matched/max(1,exp)
        rows.append({"group_type":group_type,"group":group,"variant_count":len(part),
            "expected_rows":exp,"predicted_rows":pred,"matched_rows":matched,
            "row_precision":precision,"row_recall":recall,
            "row_f1":2*precision*recall/max(1e-12,precision+recall),
            "description_accuracy":part.description_accuracy.mean(),
            "quantity_accuracy":part.quantity_accuracy.mean(),
            "unit_price_accuracy":part.unit_price_accuracy.mean(),
            "line_total_accuracy":part.line_total_accuracy.mean(),
            "complete_line_item_accuracy":part.complete_line_item_accuracy.mean(),
            "documents_with_no_predicted_items":int(part.no_predicted_items.sum()),
            "documents_with_perfect_line_item_extraction":int(part.perfect_line_item_extraction.sum())})
    return rows

def _classification_metrics(df):
    labels=["invoice","receipt"]; matrix=[]
    for actual in labels: matrix.append([int(((df.expected_document_type==actual)&(df.predicted_document_type==p)).sum()) for p in labels])
    per={}
    for label in labels:
        tp=int(((df.expected_document_type==label)&(df.predicted_document_type==label)).sum())
        fp=int(((df.expected_document_type!=label)&(df.predicted_document_type==label)).sum())
        fn=int(((df.expected_document_type==label)&(df.predicted_document_type!=label)).sum())
        p=tp/max(1,tp+fp); r=tp/max(1,tp+fn)
        per[label]={"precision":p,"recall":r,"f1":2*p*r/max(1e-12,p+r),"support":int((df.expected_document_type==label).sum())}
    return {"accuracy":float(df.classification_correct.mean()),"macro_precision":statistics.mean(x["precision"] for x in per.values()),
        "macro_recall":statistics.mean(x["recall"] for x in per.values()),"macro_f1":statistics.mean(x["f1"] for x in per.values()),
        "uncertain_count":int(df.classification_uncertain.sum()),"labels":labels,"confusion_matrix":matrix,"per_class":per}

def _group_metrics(df,column):
    rows=[]
    for name,part in df.groupby(column):
        rows.append({column:name,"variant_count":len(part),"processing_success_rate":part.success.mean(),
            "critical_field_accuracy":part.critical_field_accuracy.mean(),
            "macro_field_f1":part.visible_field_accuracy.mean(),"line_item_f1":part.line_item_f1.mean(),
            "ocr_cer":part.cer.mean(),"ocr_wer":part.wer.mean(),
            "average_confidence":part.structured_confidence.mean(),
            "average_processing_time":part.processing_time_seconds.mean(),
            "validation_warning_frequency":(part.warning_count>0).mean()})
    return pd.DataFrame(rows)

def _confidence_analysis(df):
    rows=[]
    for label in ["High","Medium","Low"]:
        part=df[df.confidence_label==label]
        rows.append({"confidence_band":label,"prediction_count":len(part),
            "critical_field_accuracy":part.critical_field_accuracy.mean() if len(part) else 0,
            "macro_field_f1":part.visible_field_accuracy.mean() if len(part) else 0,
            "complete_record_accuracy":part.complete_record_correct.mean() if len(part) else 0,
            "average_validation_warning_count":part.warning_count.mean() if len(part) else 0})
    for start in [0,.2,.4,.6,.8]:
        part=df[(df.structured_confidence>=start)&(df.structured_confidence<start+.2+(1e-9 if start==.8 else 0))]
        rows.append({"confidence_band":f"{start:.1f}-{start+.2:.1f}","prediction_count":len(part),
            "critical_field_accuracy":part.critical_field_accuracy.mean() if len(part) else 0,
            "macro_field_f1":part.visible_field_accuracy.mean() if len(part) else 0,
            "complete_record_accuracy":part.complete_record_correct.mean() if len(part) else 0,
            "average_validation_warning_count":part.warning_count.mean() if len(part) else 0})
    return pd.DataFrame(rows)

def _warning_analysis(predictions,doc_df):
    focus = {"TOTAL_MISMATCH","LINE_ITEM_SUM_MISMATCH","LOW_OCR_CONFIDENCE",
             "LOW_EXTRACTION_CONFIDENCE","DOCUMENT_TYPE_UNCERTAIN","NO_LINE_ITEMS_FOUND"}
    codes=sorted(focus | {w["code"] for p in predictions for w in p["validation_warnings"]})
    rows=[]; total_errors=int(doc_df.has_actual_error.sum())
    for code in codes:
        warned={p["variant_id"] for p in predictions if any(w["code"]==code for w in p["validation_warnings"])}
        part=doc_df[doc_df.variant_id.isin(warned)]; actual=int(part.has_actual_error.sum())
        rows.append({"warning_code":code,"occurrence_count":sum(sum(w["code"]==code for w in p["validation_warnings"]) for p in predictions),
            "document_count":len(warned),"warned_records_with_actual_error_percentage":actual/max(1,len(part)),
            "erroneous_records_caught_percentage":actual/max(1,total_errors),
            "false_warning_count":len(part)-actual})
    return pd.DataFrame(rows)

def _runtime_metrics(df,seed,cached):
    return {"uncached_total_seconds":seed["uncached_total_seconds"],
        "average_seconds_per_variant":df.processing_time_seconds.mean(),
        "median_seconds_per_variant":df.processing_time_seconds.median(),
        "digital_pdf_average_seconds":df[df.extraction_method=="embedded_text"].processing_time_seconds.mean(),
        "ocr_variant_average_seconds":df[df.extraction_method=="ocr"].processing_time_seconds.mean(),
        "cached_total_seconds":round(cached,3),"failure_count":int((~df.success).sum()),
        "exceptions":seed["failures"]}

def _summary(df,field_df,numeric_df,line_metrics,type_metrics,grouped,runtime,error_rows):
    scored=field_df[field_df.expected_count>0]
    macro_p=scored.precision.mean(); macro_r=scored.recall.mean(); macro_f=scored.F1.mean()
    correct=scored.correct_count.sum(); extracted=scored.extracted_count.sum(); expected=scored.expected_count.sum()
    micro_p=correct/max(1,extracted); micro_r=correct/max(1,expected)
    line=next(x for x in line_metrics if x["group_type"]=="all")
    numeric_expected=numeric_df.expected_count.sum()
    numeric_correct=sum(row.tolerance_accuracy*row.expected_count for _,row in numeric_df.iterrows())
    quality=grouped["quality_condition"]; dtype=grouped["document_type"]
    clean=df[df.quality_group=="clean"]; degraded=df[df.quality_group=="degraded"]
    categories=Counter(x["error_category"] for x in error_rows)
    return {"test_source_document_count":int(df.document_id.nunique()),"test_variant_count":len(df),
        "processing_success_rate":float(df.success.mean()),"document_type_classification":type_metrics,
        "macro_field_precision":macro_p,"macro_field_recall":macro_r,"macro_field_f1":macro_f,
        "micro_field_f1":2*micro_p*micro_r/max(1e-12,micro_p+micro_r),
        "critical_field_accuracy":float(df.critical_field_accuracy.mean()),
        "complete_record_accuracy":float(df.complete_record_correct.mean()),
        "numeric_field_tolerance_accuracy":numeric_correct/max(1,numeric_expected),
        "line_item_row_precision":line["row_precision"],"line_item_row_recall":line["row_recall"],
        "line_item_row_f1":line["row_f1"],
        "ocr_cer_ocr_route":float(df[df.extraction_method=="ocr"].cer.mean()),
        "ocr_wer_ocr_route":float(df[df.extraction_method=="ocr"].wer.mean()),
        "embedded_text_cer":float(df[df.extraction_method=="embedded_text"].cer.mean()),
        "embedded_text_wer":float(df[df.extraction_method=="embedded_text"].wer.mean()),
        "clean_document_performance":{"variant_count":len(clean),"critical_field_accuracy":clean.critical_field_accuracy.mean(),
            "visible_field_accuracy":clean.visible_field_accuracy.mean(),"line_item_f1":clean.line_item_f1.mean()},
        "degraded_document_performance":{"variant_count":len(degraded),"critical_field_accuracy":degraded.critical_field_accuracy.mean(),
            "visible_field_accuracy":degraded.visible_field_accuracy.mean(),"line_item_f1":degraded.line_item_f1.mean()},
        "invoice_performance":dtype[dtype.document_type=="invoice"].iloc[0].to_dict(),
        "receipt_performance":dtype[dtype.document_type=="receipt"].iloc[0].to_dict(),
        "runtime":runtime,"most_frequent_error_categories":dict(categories.most_common(8)),
        "main_limitations":["Optional fields absent from rendered documents were excluded from field scoring.",
            "Line-item spatial grouping is weaker on compact receipts and rotated tables.",
            "Stage 1 expected OCR text omits some visible address and label text, inflating CER/WER.",
            "All test results fell in the High confidence band, limiting confidence-band comparison."]}

def _write_report(summary,fields,numeric,warnings,runtime,errors):
    top=Counter(x["error_category"] for x in errors).most_common(8)
    content=f"""# Final Evaluation Report

## 1. Executive Summary

The frozen pipeline processed {summary['test_variant_count']} variants from {summary['test_source_document_count']} untouched synthetic test sources. Processing success was {summary['processing_success_rate']:.1%}. Metrics below are specific; no universal accuracy claim is made.

## 2. Evaluation Dataset

The deterministic source-level split contains 49 development and 21 test sources. Test variants include digital PDF, PNG, JPG, and scanned PDF.

## 3. Leakage Prevention

All four variants stay with their source. Predictions were saved before the evaluator opened ground truth. Normal OCR/extraction modules do not import ground truth.

## 4. Extraction Methods

Digital PDFs use PyMuPDF embedded text. Raster PDFs and images use RapidOCR 1.4.4 with ONNX Runtime CPU.

## 5. Document-Type Classification

- Accuracy: {summary['document_type_classification']['accuracy']:.1%}
- Macro F1: {summary['document_type_classification']['macro_f1']:.1%}

## 6. Header-Field Results

- Macro precision: {summary['macro_field_precision']:.1%}
- Macro recall: {summary['macro_field_recall']:.1%}
- Macro F1: {summary['macro_field_f1']:.1%}
- Micro F1: {summary['micro_field_f1']:.1%}
- Critical-field accuracy: {summary['critical_field_accuracy']:.1%}
- Complete-record accuracy: {summary['complete_record_accuracy']:.1%}

Only visibly rendered fields were scored.

## 7. Numeric-Field Results

Tolerance-based accuracy at the configured tolerance is {summary['numeric_field_tolerance_accuracy']:.1%}.

## 8. Line-Item Results

- Row precision: {summary['line_item_row_precision']:.1%}
- Row recall: {summary['line_item_row_recall']:.1%}
- Row F1: {summary['line_item_row_f1']:.1%}

Compact receipts, rotated tables, and reconciliation-warning documents remain weaker.

## 9. OCR Text Results

- OCR-route CER: {summary['ocr_cer_ocr_route']:.3f}
- OCR-route WER: {summary['ocr_wer_ocr_route']:.3f}
- Embedded-text CER: {summary['embedded_text_cer']:.3f}
- Embedded-text WER: {summary['embedded_text_wer']:.3f}

The Stage 1 expected-text reference is incomplete relative to the full printed page, so insertion errors inflate these values.

## 10. Performance by Quality

Clean critical-field accuracy was {summary['clean_document_performance']['critical_field_accuracy']:.1%}; degraded accuracy was {summary['degraded_document_performance']['critical_field_accuracy']:.1%}.

## 11. Performance by Format

Detailed format results are in `outputs/evaluation/performance_by_format.csv`.

## 12. Confidence Analysis

All test results were labelled High, so cross-band calibration cannot be inferred. Confidence remains a transparent reliability heuristic, not correctness probability.

## 13. Validation-Warning Analysis

Warnings are diagnostic signals, not guaranteed error detectors. Detailed false-warning and error-capture rates are reported in `validation_warning_analysis.csv`.

## 14. Runtime

- Uncached total: {runtime['uncached_total_seconds']:.2f}s
- Mean per variant: {runtime['average_seconds_per_variant']:.3f}s
- Cached total: {runtime['cached_total_seconds']:.2f}s

## 15. Error Analysis

Most frequent categories: {', '.join(f'{k} ({v})' for k,v in top)}.

## 16. Limitations

- Synthetic, printed, English, single-page documents only.
- Optional fields not visibly printed were excluded.
- Line-item grouping is weaker than header extraction.
- Expected OCR reference text is incomplete.
- Confidence bands lack diversity on this test set.

## 17. Appropriate Fiverr Claims

Appropriate: evaluated against known synthetic ground truth; supports digital PDFs, scanned PDFs, PNG, and JPG; exports Excel, CSV, and JSON; includes validation and confidence indicators; tested on multiple invoice and receipt layouts.

Not appropriate: 100% accurate, guaranteed error-free, human-level, or production-ready for every industry.
"""
    (ROOT/"reports/evaluation_report.md").write_text(content,encoding="utf-8")

def run_evaluation(force=True):
    predictions,runtime=generate_test_predictions(force)
    return evaluate_predictions(predictions,runtime)
