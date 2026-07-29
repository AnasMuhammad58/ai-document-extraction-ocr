from __future__ import annotations
import csv
import json
import logging
import shutil
from collections import Counter
from pathlib import Path
import fitz
from PIL import Image
from .config import ROOT, load_config
from .document_templates import render_pdf
from .image_degradation import QUALITY_PROFILES, apply, metadata
from .synthetic_data import build_documents, expected_text

def _paths() -> None:
    for p in [
        "data/synthetic/invoices/pdf", "data/synthetic/invoices/png", "data/synthetic/invoices/jpg",
        "data/synthetic/receipts/pdf", "data/synthetic/receipts/png", "data/synthetic/receipts/jpg",
        "data/synthetic/scanned_pdfs", "data/ground_truth", "data/samples",
        "outputs/extracted", "outputs/evaluation", "outputs/charts", "outputs/app_screenshots",
        "outputs/fiverr", "reports", "tests", "logs",
    ]: (ROOT / p).mkdir(parents=True, exist_ok=True)

def _raster(pdf: Path, dpi: int) -> Image.Image:
    with fitz.open(pdf) as handle:
        pix = handle[0].get_pixmap(matrix=fitz.Matrix(dpi/72, dpi/72), alpha=False)
    return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)

def _write_csv(path: Path, rows: list[dict]) -> None:
    fieldnames = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader(); writer.writerows(rows)

def generate(quick=False, force=False) -> dict:
    cfg = load_config(); _paths()
    gt = ROOT / "data/ground_truth/documents.json"
    if gt.exists() and not force:
        return json.loads((ROOT / "reports/dataset_summary.json").read_text(encoding="utf-8"))
    for folder in [ROOT/"data/synthetic", ROOT/"data/ground_truth", ROOT/"data/samples"]:
        if folder.exists(): shutil.rmtree(folder)
    _paths()
    inv = cfg["dataset"]["quick_invoices"] if quick else cfg["dataset"]["invoices"]
    rec = cfg["dataset"]["quick_receipts"] if quick else cfg["dataset"]["receipts"]
    docs = build_documents(inv, rec, cfg["seed"])
    variants, field_rows, item_rows = [], [], []
    for index, doc in enumerate(docs):
        dtype, stem = doc["document_type"] + "s", doc["document_id"].lower()
        pdf = ROOT/f"data/synthetic/{dtype}/pdf/{stem}_digital.pdf"
        render_pdf(doc, pdf)
        image = _raster(pdf, cfg["render"]["dpi"])
        labels = [QUALITY_PROFILES[(index*3+j) % len(QUALITY_PROFILES)] for j in range(3)]
        output_specs = [
            ("digital_pdf", pdf, "clean", "pdf"),
            ("image_png", ROOT/f"data/synthetic/{dtype}/png/{stem}_{labels[0]}.png", labels[0], "png"),
            ("image_jpg", ROOT/f"data/synthetic/{dtype}/jpg/{stem}_{labels[1]}.jpg", labels[1], "jpg"),
            ("scanned_pdf", ROOT/f"data/synthetic/scanned_pdfs/{stem}_{labels[2]}.pdf", labels[2], "scanned_pdf"),
        ]
        for variant_type, path, label, fmt in output_specs:
            if variant_type != "digital_pdf":
                altered = apply(image.copy(), label, cfg["seed"] + index)
                if fmt == "png": altered.save(path, "PNG")
                elif fmt == "jpg": altered.save(path, "JPEG", quality=metadata(label)["compression_quality"])
                else: altered.save(path, "PDF", resolution=cfg["render"]["dpi"])
            variants.append({"document_id": doc["document_id"], "variant_id": f'{doc["document_id"]}-{variant_type}',
                "source_template": doc["source_template"], "document_type": doc["document_type"],
                "file_path": path.relative_to(ROOT).as_posix(), "format": fmt, "variant_type": variant_type,
                **metadata(label)})
        flat = {k: v for k, v in doc.items() if k != "line_items"}
        flat["expected_text"] = expected_text(doc); field_rows.append(flat)
        for order, item in enumerate(doc["line_items"], 1):
            item_rows.append({"document_id": doc["document_id"], "item_order": order, **item})
        doc["expected_text"] = expected_text(doc)
        doc["variants"] = [v for v in variants if v["document_id"] == doc["document_id"]]
    gt.write_text(json.dumps(docs, indent=2), encoding="utf-8")
    _write_csv(ROOT/"data/ground_truth/document_fields.csv", field_rows)
    _write_csv(ROOT/"data/ground_truth/line_items.csv", item_rows)
    for doc in [docs[0], docs[min(inv, len(docs)-1)]]:
        for v in doc["variants"][:2]:
            src = ROOT/v["file_path"]
            shutil.copy2(src, ROOT/"data/samples"/src.name)
    formats, qualities = Counter(v["format"] for v in variants), Counter(v["quality_label"] for v in variants)
    summary = {"mode": "quick" if quick else "normal", "invoices": inv, "receipts": rec,
        "documents": len(docs), "invoice_templates": 5, "receipt_templates": 4,
        "variants": len(variants), "format_counts": dict(formats), "quality_counts": dict(qualities)}
    (ROOT/"reports/dataset_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    coverage = Counter(k for d in docs for k,v in d.items() if v is not None and k not in ("variants","line_items","expected_text"))
    report = f"""# Synthetic Dataset Generation Report

> Synthetic documents created for testing and portfolio demonstration.

- Mode: {summary['mode']}
- Source documents: {len(docs)} ({inv} invoices, {rec} receipts)
- Templates: 5 invoice and 4 receipt
- Rendered variants: {len(variants)} (four per source)
- Formats: {dict(formats)}
- Quality conditions: {dict(qualities)}
- Deterministic seed: {cfg['seed']}

## Field coverage

""" + "\n".join(f"- `{k}`: {v}/{len(docs)}" for k,v in sorted(coverage.items())) + """

## Regeneration

```powershell
.\\.venv\\Scripts\\python.exe run_all.py --stage 1 --force
```

Digital PDFs retain embedded text. Scanned PDFs contain raster images only. Every rendered file is traceable through the `variants` array in `documents.json`.
"""
    (ROOT/"reports/data_generation_report.md").write_text(report, encoding="utf-8")
    logging.info("Generated %s documents and %s variants", len(docs), len(variants))
    return summary
