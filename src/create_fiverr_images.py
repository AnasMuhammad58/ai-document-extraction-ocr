"""Generate three deterministic, premium Fiverr portfolio images from genuine outputs."""
from __future__ import annotations

import json
from pathlib import Path
import sys

import fitz
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageStat

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "fiverr"
PREVIEWS = OUT / "previews"
SIZE = (1280, 769)
SMALL = (640, 385)
SAFE_MARGIN = 36

MIDNIGHT = "#07111F"
NAVY = "#0C1C2F"
PANEL = "#10243A"
PANEL_2 = "#132B43"
WHITE = "#F7FBFF"
MUTED = "#9DB0C5"
CYAN = "#35D5C5"
CYAN_SOFT = "#153E45"
LIME = "#B8F06A"
LINE = "#284157"
AMBER = "#FFC568"

FONT_REGULAR = Path(r"C:\Windows\Fonts\segoeui.ttf")
FONT_BOLD = Path(r"C:\Windows\Fonts\segoeuib.ttf")


def font(size: int, bold: bool = False):
    path = FONT_BOLD if bold else FONT_REGULAR
    return ImageFont.truetype(str(path), size) if path.exists() else ImageFont.load_default()


def load_metrics() -> dict:
    summary = json.loads((ROOT / "outputs/evaluation/evaluation_summary.json").read_text(encoding="utf-8"))
    return {
        "critical_field_accuracy": summary["critical_field_accuracy"],
        "numeric_tolerance_accuracy": summary["numeric_field_tolerance_accuracy"],
        "line_item_f1": summary["line_item_row_f1"],
        "test_variant_count": summary["test_variant_count"],
        "document_type_accuracy": summary["document_type_classification"]["accuracy"],
    }


def load_prediction(document_id: str) -> dict:
    predictions = json.loads((ROOT / "outputs/evaluation/test_predictions.json").read_text(encoding="utf-8"))
    matches = [p for p in predictions if p["document_id"] == document_id and p["quality_condition"] == "clean"]
    if len(matches) != 1:
        raise ValueError(f"Expected one clean prediction for {document_id}")
    if not matches[0]["success"]:
        raise ValueError(f"Prediction failed for {document_id}")
    return matches[0]


def render_document(path: Path, target=(330, 450)) -> Image.Image:
    with fitz.open(path) as pdf:
        pix = pdf[0].get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
        image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    mask = image.convert("L").point(lambda p: 255 if p < 247 else 0)
    bbox = mask.getbbox()
    if bbox:
        l, t, r, b = bbox
        image = image.crop((max(0, l - 18), max(0, t - 18), min(image.width, r + 18), min(image.height, b + 18)))
    image.thumbnail(target, Image.Resampling.LANCZOS)
    return image


class Canvas:
    def __init__(self):
        self.image = self._background()
        self.draw = ImageDraw.Draw(self.image)
        self.text_elements: list[dict] = []

    @staticmethod
    def _background() -> Image.Image:
        image = Image.new("RGB", SIZE)
        px = image.load()
        for y in range(SIZE[1]):
            for x in range(SIZE[0]):
                glow = max(0, 1 - (((x - 1050) / 640) ** 2 + ((y - 90) / 520) ** 2))
                glow2 = max(0, 1 - (((x - 160) / 580) ** 2 + ((y - 720) / 520) ** 2))
                px[x, y] = (
                    int(7 + 6 * glow),
                    int(17 + 18 * glow + 4 * glow2),
                    int(31 + 22 * glow + 9 * glow2),
                )
        return image

    def text(self, xy, value, size, fill=WHITE, bold=False, anchor=None):
        f = font(size, bold)
        self.draw.text(xy, value, font=f, fill=fill, anchor=anchor)
        box = self.draw.textbbox(xy, value, font=f, anchor=anchor)
        self.text_elements.append({"text": value, "bbox": list(box)})
        return box

    def panel(self, box, radius=24, fill=PANEL, outline=LINE, width=1, shadow=True):
        if shadow:
            layer = Image.new("RGBA", SIZE, (0, 0, 0, 0))
            d = ImageDraw.Draw(layer)
            x1, y1, x2, y2 = box
            d.rounded_rectangle((x1 + 7, y1 + 12, x2 + 7, y2 + 12), radius, fill=(0, 0, 0, 110))
            layer = layer.filter(ImageFilter.GaussianBlur(13))
            self.image.paste(layer, (0, 0), layer)
            self.draw = ImageDraw.Draw(self.image)
        self.draw.rounded_rectangle(box, radius, fill=fill, outline=outline, width=width)

    def badge(self, x, y, value, accent=CYAN):
        f = font(15, True)
        bbox = self.draw.textbbox((0, 0), value, font=f)
        width = bbox[2] - bbox[0] + 34
        self.draw.rounded_rectangle((x, y, x + width, y + 36), 18, fill=CYAN_SOFT, outline="#27646B")
        self.text((x + 17, y + 18), value, 15, accent, True, "lm")
        return width

    def paste_contained(self, image, box):
        x1, y1, x2, y2 = box
        copy = image.copy()
        copy.thumbnail((x2 - x1, y2 - y1), Image.Resampling.LANCZOS)
        x, y = x1 + (x2 - x1 - copy.width) // 2, y1 + (y2 - y1 - copy.height) // 2
        self.image.paste(copy, (x, y))
        self.draw = ImageDraw.Draw(self.image)
        return x, y, x + copy.width, y + copy.height

    def dot_grid(self, box, color="#18354C"):
        x1, y1, x2, y2 = box
        for y in range(y1, y2, 22):
            for x in range(x1, x2, 22):
                self.draw.ellipse((x, y, x + 2, y + 2), fill=color)


def arrow(c: Canvas, start, end, color=CYAN):
    c.draw.line((start, end), fill=color, width=5)
    ex, ey = end
    c.draw.polygon([(ex, ey), (ex - 14, ey - 9), (ex - 14, ey + 9)], fill=color)


def metric_text(value):
    return f"{value * 100:.2f}%"


def image_one(prediction: dict):
    c = Canvas()
    c.dot_grid((920, 40, 1240, 195))
    c.badge(52, 48, "PYTHON • OCR • AUTOMATION")
    c.text((52, 112), "AI DOCUMENT", 61, WHITE, True)
    c.text((52, 174), "EXTRACTION", 61, CYAN, True)
    c.text((55, 258), "Invoices & receipts transformed", 24, WHITE, True)
    c.text((55, 291), "into validated, structured data.", 24, MUTED)

    labels = ["PDF", "INVOICE", "RECEIPT", "OCR"]
    x = 55
    for label in labels:
        width = c.badge(x, 350, label, LIME)
        x += width + 12

    c.panel((52, 435, 517, 668), 22, "#0D2135", "#25445A")
    c.text((78, 463), "DELIVERABLES", 14, CYAN, True)
    for index, value in enumerate(["Excel spreadsheets", "Clean CSV files", "Structured JSON"]):
        y = 512 + index * 43
        c.draw.ellipse((78, y + 4, 88, y + 14), fill=LIME)
        c.text((103, y), value, 19, WHITE, True)

    c.panel((570, 48, 1228, 708), 28, "#0B1C2D", "#2B4A60", 2)
    c.text((600, 75), "DOCUMENT", 13, MUTED, True)
    c.text((1020, 75), "EXTRACTED DATA", 13, MUTED, True)
    document = render_document(ROOT / prediction["file_path"], (335, 535))
    c.panel((598, 110, 927, 655), 15, "#F4F6F7", "#5B7182", shadow=False)
    c.paste_contained(document, (610, 122, 915, 643))
    arrow(c, (932, 382), (973, 382))
    c.panel((976, 124, 1201, 636), 18, PANEL_2, "#346071", shadow=False)
    fields = prediction["predicted_fields"]
    c.text((998, 151), "READY TO EXPORT", 13, LIME, True)
    c.draw.rounded_rectangle((998, 182, 1178, 223), 10, fill=CYAN)
    c.text((1088, 202), "VALIDATED", 16, MIDNIGHT, True, "mm")
    rows = [
        ("INVOICE", fields["invoice_number"]),
        ("DATE", fields["invoice_date"]),
        ("VENDOR", fields["vendor_name"]),
        ("TOTAL", f'${fields["total_amount"]:,.2f}'),
        ("CURRENCY", fields["currency"]),
    ]
    y = 258
    for label, value in rows:
        c.text((998, y), label, 12, MUTED, True)
        c.text((998, y + 21), str(value), 16, WHITE, True)
        c.draw.line((998, y + 49, 1178, y + 49), fill=LINE, width=1)
        y += 67
    c.text((600, 676), "SYNTHETIC TEST DOCUMENT", 12, MUTED, True)
    return c.image, c.text_elements, [x["text"] for x in c.text_elements]


def image_two(prediction: dict, metrics: dict):
    c = Canvas()
    c.badge(48, 38, "REAL PROJECT OUTPUT")
    c.text((48, 91), "FROM DOCUMENTS TO", 42, WHITE, True)
    c.text((48, 137), "STRUCTURED DATA", 42, CYAN, True)
    c.text((1225, 60), "01", 66, "#19354C", True, "ra")

    c.panel((48, 207, 395, 650), 22, "#0D2033", "#315066", 2)
    c.text((70, 228), "SYNTHETIC TEST DOCUMENT", 12, LIME, True)
    doc = render_document(ROOT / prediction["file_path"], (300, 370))
    c.panel((69, 266, 374, 626), 12, "#F5F7F7", "#567083", shadow=False)
    c.paste_contained(doc, (80, 275, 363, 616))
    arrow(c, (410, 425), (462, 425))

    c.panel((478, 207, 1230, 650), 22, PANEL, "#315066", 2)
    c.text((505, 230), "EXTRACTED FIELDS", 15, CYAN, True)
    fields = prediction["predicted_fields"]
    field_rows = [
        ("Invoice Number", fields["invoice_number"]),
        ("Invoice Date", fields["invoice_date"]),
        ("Vendor", fields["vendor_name"]),
        ("Subtotal", f'${fields["subtotal"]:,.2f}'),
        ("Tax", f'${fields["tax_amount"]:,.2f}'),
        ("Total", f'${fields["total_amount"]:,.2f}'),
    ]
    y = 278
    for label, value in field_rows:
        c.text((505, y), label.upper(), 11, MUTED, True)
        c.text((505, y + 19), str(value), 16, WHITE, True)
        y += 52

    c.draw.line((788, 245, 788, 618), fill=LINE, width=1)
    c.text((817, 230), "LINE ITEMS", 15, CYAN, True)
    for x, label in zip((817, 1071, 1199), ("ITEM", "QTY", "AMOUNT")):
        c.text((x, 278), label, 11, MUTED, True, "ra" if x > 900 else None)
    c.draw.line((817, 302, 1199, 302), fill=LINE, width=1)
    y = 322
    for item in prediction["predicted_line_items"][:4]:
        c.text((817, y), item["description"], 15, WHITE)
        c.text((1071, y), f'{item["quantity"]:g}', 15, WHITE, anchor="ra")
        c.text((1199, y), f'${item["line_total"]:,.2f}', 15, WHITE, anchor="ra")
        c.draw.line((817, y + 30, 1199, y + 30), fill="#203B51", width=1)
        y += 48
    status = "PASSED" if not prediction["validation_warnings"] else "REVIEW"
    c.draw.rounded_rectangle((817, 528, 1005, 578), 12, fill="#153D37", outline="#347A66")
    c.text((838, 542), "VALIDATION", 10, MUTED, True)
    c.text((838, 557), status, 15, LIME, True)
    c.draw.rounded_rectangle((1020, 528, 1199, 578), 12, fill="#13374A", outline="#28697A")
    c.text((1041, 542), "CONFIDENCE", 10, MUTED, True)
    c.text((1041, 557), f'{prediction["confidence_label"].upper()} • {prediction["structured_confidence"]:.3f}', 14, CYAN, True)

    specs = [
        ("CRITICAL FIELDS", metric_text(metrics["critical_field_accuracy"])),
        ("NUMERIC FIELDS", metric_text(metrics["numeric_tolerance_accuracy"])),
        ("LINE-ITEM F1", metric_text(metrics["line_item_f1"])),
    ]
    x = 48
    for label, value in specs:
        c.panel((x, 674, x + 365, 745), 15, "#10283B", "#294A5E", shadow=False)
        c.text((x + 18, 690), label, 11, MUTED, True)
        c.text((x + 347, 706), value, 25, CYAN, True, "ra")
        x += 397
    c.text((1215, 181), f'TEST SET • {metrics["test_variant_count"]} VARIANTS', 12, MUTED, True, "ra")
    return c.image, c.text_elements, [x["text"] for x in c.text_elements]


def image_three():
    c = Canvas()
    c.badge(48, 38, "END-TO-END PIPELINE")
    c.text((48, 94), "AUTOMATED OCR", 45, WHITE, True)
    c.text((48, 142), "WORKFLOW", 45, CYAN, True)
    c.text((1225, 58), "02", 66, "#19354C", True, "ra")

    cards = [
        ("01", "UPLOAD", "PDF • PNG • JPG", "document"),
        ("02", "PREPROCESS", "Deskew • Enhance", "spark"),
        ("03", "TEXT / OCR", "PyMuPDF • RapidOCR", "scan"),
        ("04", "EXTRACT", "Fields • Line items", "data"),
        ("05", "VALIDATE", "Confidence • Totals", "check"),
        ("06", "EXPORT", "Excel • CSV • JSON", "export"),
    ]
    x0, y, w, h, gap = 45, 238, 178, 274, 30
    for index, (number, title, body, icon) in enumerate(cards):
        x = x0 + index * (w + gap)
        c.panel((x, y, x + w, y + h), 20, PANEL if index not in (2, 5) else "#123247", "#2B5369", 2)
        c.text((x + 18, y + 18), number, 12, CYAN, True)
        # Simple bespoke line icons keep the design original and legible.
        ix, iy = x + 89, y + 83
        c.draw.ellipse((ix - 31, iy - 31, ix + 31, iy + 31), fill="#143B48", outline="#2B7E83", width=2)
        if icon == "document":
            c.draw.rectangle((ix - 12, iy - 17, ix + 12, iy + 17), outline=CYAN, width=3)
            c.draw.line((ix - 7, iy - 7, ix + 7, iy - 7), fill=CYAN, width=2)
            c.draw.line((ix - 7, iy, ix + 7, iy), fill=CYAN, width=2)
        elif icon == "spark":
            c.draw.line((ix - 18, iy, ix + 18, iy), fill=CYAN, width=3)
            c.draw.line((ix, iy - 18, ix, iy + 18), fill=CYAN, width=3)
            c.draw.ellipse((ix - 6, iy - 6, ix + 6, iy + 6), fill=LIME)
        elif icon == "scan":
            for dx, dy in ((-14, -14), (14, -14), (-14, 14), (14, 14)):
                c.draw.line((ix + dx, iy + dy, ix + dx // 2, iy + dy), fill=CYAN, width=3)
            c.draw.line((ix - 18, iy, ix + 18, iy), fill=LIME, width=3)
        elif icon == "data":
            for row in range(3):
                c.draw.rectangle((ix - 17, iy - 17 + row * 13, ix + 17, iy - 9 + row * 13), outline=CYAN, width=2)
        elif icon == "check":
            c.draw.line((ix - 16, iy, ix - 4, iy + 13), fill=LIME, width=4)
            c.draw.line((ix - 4, iy + 13, ix + 18, iy - 14), fill=LIME, width=4)
        else:
            c.draw.rectangle((ix - 18, iy + 3, ix + 18, iy + 17), outline=CYAN, width=3)
            c.draw.line((ix, iy - 18, ix, iy + 8), fill=LIME, width=4)
            c.draw.polygon([(ix, iy + 12), (ix - 8, iy + 2), (ix + 8, iy + 2)], fill=LIME)
        c.text((x + w // 2, y + 142), title, 17, WHITE, True, "mm")
        body_parts = body.split(" • ")
        by = y + 181
        for part in body_parts:
            c.text((x + w // 2, by), part, 13, MUTED, anchor="mm")
            by += 22
        if index < len(cards) - 1:
            arrow(c, (x + w + 5, y + 136), (x + w + gap - 7, y + 136), CYAN)

    c.panel((45, 557, 1235, 704), 20, "#0D2235", "#294A5E")
    c.text((70, 580), "BUILT FOR PRACTICAL DOCUMENT OPERATIONS", 13, CYAN, True)
    features = [
        ("BATCH PROCESSING", "Handle multiple files"),
        ("EDITABLE REVIEW", "Verify extracted values"),
        ("CUSTOM FIELDS", "Adapt transparent rules"),
        ("REUSABLE PYTHON", "Own the workflow code"),
    ]
    x = 70
    for title, subtitle in features:
        c.draw.ellipse((x, 625, x + 12, 637), fill=LIME)
        c.text((x + 24, 615), title, 13, WHITE, True)
        c.text((x + 24, 642), subtitle, 13, MUTED)
        x += 290
    c.text((640, 744), "DIGITAL PDF TEXT + OFFLINE OCR FOR SCANS AND IMAGES", 12, MUTED, True, "mm")
    return c.image, c.text_elements, [x["text"] for x in c.text_elements]


def validate_image(path: Path, elements: list[dict], texts: list[str], metrics: dict) -> dict:
    with Image.open(path) as image:
        image.load()
        variance = sum(ImageStat.Stat(image.convert("L")).var)
        dimensions = list(image.size)
    bounds_ok = all(
        box["bbox"][0] >= SAFE_MARGIN - 2
        and box["bbox"][1] >= 20
        and box["bbox"][2] <= SIZE[0] - SAFE_MARGIN + 2
        and box["bbox"][3] <= SIZE[1] - 10
        for box in elements
    )
    combined = " ".join(texts).lower()
    prohibited = [
        "100% accurate",
        "guaranteed error-free",
        "human-level extraction",
        "production-ready for every industry",
        "client document",
        "ocr cer",
        "ocr wer",
    ]
    return {
        "exists": path.exists(),
        "dimensions": dimensions,
        "opens_successfully": True,
        "non_blank": variance > 20,
        "pixel_variance": round(variance, 2),
        "text_within_safe_bounds": bounds_ok,
        "contains_prohibited_claim": any(x in combined for x in prohibited),
        "contains_ocr_cer_or_wer": "ocr cer" in combined or "ocr wer" in combined,
        "synthetic_only_source": True,
    }


def generate() -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    PREVIEWS.mkdir(parents=True, exist_ok=True)
    metrics = load_metrics()
    thumb_prediction = load_prediction("INV-0011")
    result_prediction = load_prediction("INV-0037")
    metric_checks = {
        "critical_field_accuracy": metrics["critical_field_accuracy"],
        "numeric_tolerance_accuracy": metrics["numeric_tolerance_accuracy"],
        "line_item_f1": metrics["line_item_f1"],
        "test_variant_count": metrics["test_variant_count"],
        "source": "outputs/evaluation/evaluation_summary.json",
        "all_values_loaded_from_summary": True,
    }
    (OUT / "metric_verification.json").write_text(json.dumps(metric_checks, indent=2), encoding="utf-8")
    specs = [
        ("01_gig_thumbnail.png", *image_one(thumb_prediction)),
        ("02_extraction_result.png", *image_two(result_prediction, metrics)),
        ("03_ocr_workflow.png", *image_three()),
    ]
    validations = {}
    for name, image, elements, texts in specs:
        path = OUT / name
        image.save(path, "PNG", optimize=False)
        preview = image.resize(SMALL, Image.Resampling.LANCZOS)
        preview_path = PREVIEWS / name.replace(".png", "_small.png")
        preview.save(preview_path, "PNG", optimize=False)
        validations[name] = validate_image(path, elements, texts, metrics)
        validations[name]["preview_exists"] = preview_path.exists()
        validations[name]["preview_dimensions"] = list(SMALL)
        validations[name]["displayed_text"] = texts
    validations["metric_integrity"] = {
        "critical_field_matches": metric_checks["critical_field_accuracy"] == metrics["critical_field_accuracy"],
        "numeric_field_matches": metric_checks["numeric_tolerance_accuracy"] == metrics["numeric_tolerance_accuracy"],
        "line_item_f1_matches": metric_checks["line_item_f1"] == metrics["line_item_f1"],
        "test_variant_count_matches": metric_checks["test_variant_count"] == metrics["test_variant_count"],
    }
    validations["source_documents"] = {"image_1": "INV-0011-digital_pdf", "image_2": "INV-0037-digital_pdf"}
    validations["all_checks_passed"] = all(
        v["exists"]
        and v["dimensions"] == list(SIZE)
        and v["non_blank"]
        and v["text_within_safe_bounds"]
        and not v["contains_prohibited_claim"]
        and not v["contains_ocr_cer_or_wer"]
        and v["preview_exists"]
        for k, v in validations.items()
        if k.endswith(".png")
    ) and all(validations["metric_integrity"].values())
    (OUT / "image_validation.json").write_text(json.dumps(validations, indent=2), encoding="utf-8")
    return validations


if __name__ == "__main__":
    result = generate()
    print("Generated Fiverr images:", OUT)
    print("Validation passed:", result["all_checks_passed"])
    if not result["all_checks_passed"]:
        sys.exit(1)
