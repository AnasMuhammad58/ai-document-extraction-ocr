from __future__ import annotations
import hashlib
import json
import logging
import time
from pathlib import Path
from PIL import Image
import fitz
from .classification import classify
from .confidence import score
from .config import ROOT, load_config
from .document_loader import SUPPORTED, identity, load_document
from .exporters import export_results
from .field_extractor import extract_fields
from .line_item_extractor import extract_line_items
from .ocr_engine import OfflineOCREngine, engine_info
from .preprocessing import preprocess, save_preprocessing_example
from .schemas import ExtractionResult
from .validation import validate

def process_document(path: Path, engine: OfflineOCREngine | None = None, force=False,
                     numeric_tolerance: float | None = None,
                     preprocessing_enabled: bool = True) -> ExtractionResult:
    """Run the genuine extraction stack for one document without ground-truth access."""
    one_started = time.perf_counter()
    loaded = load_document(path, engine or OfflineOCREngine(), force, preprocessing_enabled)
    dtype, type_confidence, type_evidence, uncertain = classify(loaded.raw_text)
    fields, evidence = extract_fields(loaded.raw_text, dtype)
    items = extract_line_items(loaded.raw_text, dtype)
    populated = [e.confidence for e in evidence.values() if e.value is not None]
    field_pre_score = sum(populated) / len(populated) if populated else 0
    tolerance = numeric_tolerance
    if tolerance is None: tolerance = load_config()["extraction"]["numeric_tolerance"]
    warnings = validate(dtype, fields, items, loaded.ocr_confidence, field_pre_score, uncertain, tolerance)
    confidence = score(loaded.ocr_confidence, evidence, type_confidence, warnings)
    if confidence.score < load_config()["extraction"]["low_extraction_confidence"] and \
            not any(w.code == "LOW_EXTRACTION_CONFIDENCE" for w in warnings):
        from .schemas import ValidationWarning
        warnings.append(ValidationWarning(code="LOW_EXTRACTION_CONFIDENCE",
            message="Final structured confidence is below threshold."))
    raw_dir = ROOT/"outputs/extracted/raw_text"
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir/f"{loaded.variant_id}.json"
    raw_path.write_text(json.dumps(loaded.model_dump(mode="json"), indent=2), encoding="utf-8")
    return ExtractionResult(document_id=loaded.document_id, variant_id=loaded.variant_id,
        file_name=path.name, document_type=dtype, document_type_confidence=type_confidence,
        classification_evidence=type_evidence, extraction_method=loaded.extraction_method,
        processing_time_seconds=round(time.perf_counter()-one_started,4),
        ocr_confidence=loaded.ocr_confidence, structured_confidence=confidence.score,
        confidence=confidence, validation_status="Passed" if not warnings else "Review",
        warnings=warnings, fields=fields, field_evidence=evidence, line_items=items,
        raw_text_path=raw_path.relative_to(ROOT).as_posix())

def discover_files() -> list[Path]:
    base = ROOT/"data/synthetic"
    return sorted(p for p in base.rglob("*") if p.suffix.lower() in SUPPORTED)

def development_files(files: list[Path]) -> tuple[list[Path], list[str]]:
    ids = sorted({identity(p)[0] for p in files},
                 key=lambda x: hashlib.sha256(("development-split:"+x).encode()).hexdigest())
    selected = set(ids[:round(len(ids)*.70)])
    return [p for p in files if identity(p)[0] in selected], sorted(selected)

def run_extraction(force=False, limit: int | None = None) -> dict:
    started = time.perf_counter()
    files, dev_ids = development_files(discover_files())
    if limit:
        grouped: dict[str, list[Path]] = {}
        for path in files: grouped.setdefault(identity(path)[0], []).append(path)
        inv = [k for k in grouped if k.startswith("INV")]
        rec = [k for k in grouped if k.startswith("RCT")]
        chosen = []
        while (inv or rec) and len(chosen) * 4 < limit:
            if inv: chosen.append(inv.pop(0))
            if rec and len(chosen) * 4 < limit: chosen.append(rec.pop(0))
        files = [p for key in chosen for p in grouped[key]]
    out, raw_dir = ROOT/"outputs/extracted", ROOT/"outputs/extracted/raw_text"
    raw_dir.mkdir(parents=True, exist_ok=True)
    (out/"ocr_engine_info.json").write_text(json.dumps(engine_info(), indent=2), encoding="utf-8")
    engine, results, failures = OfflineOCREngine(), [], []
    for index, path in enumerate(files, 1):
        one_started = time.perf_counter()
        try:
            results.append(process_document(path, engine, force))
        except Exception as exc:
            logging.exception("Failed processing %s", path)
            failures.append({"file_path": str(path), "error": f"{type(exc).__name__}: {exc}"})
        if index % 20 == 0: print(f"Processed {index}/{len(files)}")
    elapsed = time.perf_counter()-started
    summary = {"scope": "development", "source_documents": len(set(identity(p)[0] for p in files)),
        "variants_discovered": len(files), "processed_successfully": len(results), "failed": len(failures),
        "success_percentage": round(100*len(results)/max(1,len(files)),2),
        "embedded_text_count": sum(r.extraction_method=="embedded_text" for r in results),
        "ocr_count": sum(r.extraction_method=="ocr" for r in results),
        "elapsed_seconds": round(elapsed,2), "failures": failures,
        "development_document_ids": dev_ids}
    export_results(results, out, summary)
    logging.info("Extraction summary %s", summary)
    return summary

def create_preprocessing_examples() -> None:
    files = discover_files()
    wanted = ["rotation","blur","contrast","perspective","compression"]
    cfg = load_config()["extraction"]["preprocessing"]
    for label in wanted:
        path = next((p for p in files if label in p.stem and p.suffix.lower() != ".pdf"), None)
        if not path: continue
        image = Image.open(path).convert("RGB")
        processed, _ = preprocess(image, label, cfg)
        folder = ROOT/"outputs/charts/preprocessing"
        save_preprocessing_example(image, processed, folder/f"{label}_before.png", folder/f"{label}_after.png")
