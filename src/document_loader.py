from __future__ import annotations
import hashlib
import json
import re
from pathlib import Path
import fitz
from PIL import Image
from .config import ROOT, load_config
from .ocr_engine import OfflineOCREngine, reconstruct_rows
from .preprocessing import pil_to_bgr, preprocess
from .schemas import ExtractionInput, OCRLine

SUPPORTED = {".pdf", ".png", ".jpg", ".jpeg"}

def identity(path: Path) -> tuple[str, str]:
    stem = path.stem.upper()
    match = re.search(r"(INV|RCT)-?(\d{4})", stem)
    doc_id = f"{match.group(1)}-{match.group(2)}" if match else path.stem
    if "_digital" in path.stem: suffix = "digital_pdf"
    elif path.suffix.lower() == ".pdf": suffix = "scanned_pdf"
    else: suffix = f"image_{path.suffix.lower().lstrip('.')}"
    return doc_id, f"{doc_id}-{suffix}"

def _pdf_image(path: Path, dpi: int) -> tuple[Image.Image, int]:
    with fitz.open(path) as pdf:
        pix = pdf[0].get_pixmap(matrix=fitz.Matrix(dpi/72, dpi/72), alpha=False)
        return Image.frombytes("RGB", (pix.width, pix.height), pix.samples), len(pdf)

def _embedded(path: Path) -> tuple[str, list[OCRLine], int]:
    with fitz.open(path) as pdf:
        words = pdf[0].get_text("words")
        lines = [OCRLine(text=w[4], confidence=None,
                         bbox=[[w[0],w[1]],[w[2],w[1]],[w[2],w[3]],[w[0],w[3]]]) for w in words]
        return reconstruct_rows(lines, tolerance_scale=.22), lines, len(pdf)

def load_document(path: Path, engine: OfflineOCREngine | None = None, force=False,
                  preprocessing_enabled: bool = True) -> ExtractionInput:
    cfg = load_config()["extraction"]
    doc_id, variant_id = identity(path)
    cache_settings = {"config": cfg, "preprocessing_enabled": preprocessing_enabled}
    fingerprint = hashlib.sha256(path.read_bytes() + json.dumps(cache_settings, sort_keys=True).encode()).hexdigest()
    cache_path = ROOT/"outputs/extracted/cache"/f"{variant_id}_{fingerprint[:16]}.json"
    if cache_path.exists() and not force:
        return ExtractionInput.model_validate_json(cache_path.read_text(encoding="utf-8"))
    warnings, text, lines, confidence, pages = [], "", [], None, 1
    if path.suffix.lower() == ".pdf":
        text, lines, pages = _embedded(path)
        method = "embedded_text"
        if len(re.sub(r"\s+", "", text)) < cfg["pdf_text_min_chars"]:
            image, pages = _pdf_image(path, cfg["render_dpi"])
            method, text, lines, confidence = _ocr(image, path, engine, cfg, preprocessing_enabled)
    else:
        image = Image.open(path).convert("RGB")
        method, text, lines, confidence = _ocr(image, path, engine, cfg, preprocessing_enabled)
    if not text.strip(): warnings.append("NO_TEXT_EXTRACTED")
    result = ExtractionInput(document_id=doc_id, variant_id=variant_id, file_path=str(path.resolve()),
        file_type=path.suffix.lower().lstrip("."), page_count=pages, extraction_method=method,
        raw_text=text, lines=lines, ocr_confidence=confidence, processing_warnings=warnings)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    for stale in cache_path.parent.glob(f"{variant_id}_*.json"):
        if stale != cache_path: stale.unlink()
    cache_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    return result

def _ocr(image: Image.Image, path: Path, engine: OfflineOCREngine | None, cfg: dict,
         preprocessing_enabled: bool = True):
    quality = next((q for q in ["rotation","blur","contrast","noise","shadow","compression","perspective"] if q in path.stem), "")
    processed, _ = preprocess(image, quality, cfg["preprocessing"]) if preprocessing_enabled \
        else (pil_to_bgr(image), {"preprocessing": "disabled"})
    raw, lines, confidence = (engine or OfflineOCREngine()).recognize(processed)
    return "ocr", raw, lines, confidence
