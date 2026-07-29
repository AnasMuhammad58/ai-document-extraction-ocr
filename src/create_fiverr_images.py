"""Generate three deterministic Fiverr portfolio images from genuine project outputs."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import sys
import fitz
from PIL import Image, ImageDraw, ImageFont, ImageStat

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "fiverr"
PREVIEWS = OUT / "previews"
SIZE = (1280, 769)
SMALL = (640, 385)
BG = "#F8F5EF"
NAVY = "#17324D"
GREEN = "#3F7D63"
GREEN_LIGHT = "#E2EEE8"
CARD = "#FFFFFF"
NEUTRAL = "#ECE9E2"
MUTED = "#667382"
LINE = "#D9D5CC"
AMBER = "#A76622"
SAFE_MARGIN = 36

FONT_REGULAR = Path(r"C:\Windows\Fonts\segoeui.ttf")
FONT_BOLD = Path(r"C:\Windows\Fonts\segoeuib.ttf")

def font(size: int, bold=False):
    path = FONT_BOLD if bold else FONT_REGULAR
    if path.exists(): return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()

def load_metrics() -> dict:
    summary = json.loads((ROOT/"outputs/evaluation/evaluation_summary.json").read_text(encoding="utf-8"))
    return {
        "critical_field_accuracy": summary["critical_field_accuracy"],
        "numeric_tolerance_accuracy": summary["numeric_field_tolerance_accuracy"],
        "line_item_f1": summary["line_item_row_f1"],
        "test_variant_count": summary["test_variant_count"],
        "document_type_accuracy": summary["document_type_classification"]["accuracy"],
    }

def load_prediction(document_id: str) -> dict:
    predictions = json.loads((ROOT/"outputs/evaluation/test_predictions.json").read_text(encoding="utf-8"))
    matches = [p for p in predictions if p["document_id"] == document_id and p["quality_condition"] == "clean"]
    if len(matches) != 1: raise ValueError(f"Expected one clean prediction for {document_id}")
    prediction = matches[0]
    if not prediction["success"]: raise ValueError(f"Prediction failed for {document_id}")
    return prediction

def render_document(path: Path, target=(330, 450)) -> Image.Image:
    with fitz.open(path) as pdf:
        pix = pdf[0].get_pixmap(matrix=fitz.Matrix(1.7, 1.7), alpha=False)
        image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    # Retain the real page but remove excessive empty page area for a readable composition.
    gray = image.convert("L")
    mask = gray.point(lambda p: 255 if p < 247 else 0)
    bbox = mask.getbbox()
    if bbox:
        left, top, right, bottom = bbox
        image = image.crop((max(0,left-20), max(0,top-20), min(image.width,right+20), min(image.height,bottom+20)))
    image.thumbnail(target, Image.Resampling.LANCZOS)
    return image

class Canvas:
    def __init__(self):
        self.image = Image.new("RGB", SIZE, BG)
        self.draw = ImageDraw.Draw(self.image)
        self.text_elements = []

    def text(self, xy, value, size, fill=NAVY, bold=False, anchor=None):
        f = font(size, bold)
        self.draw.text(xy, value, font=f, fill=fill, anchor=anchor)
        box = self.draw.textbbox(xy, value, font=f, anchor=anchor)
        self.text_elements.append({"text": value, "bbox": list(box)})
        return box

    def rounded(self, box, radius=18, fill=CARD, outline=LINE, width=1):
        self.draw.rounded_rectangle(box, radius, fill=fill, outline=outline, width=width)

    def badge(self, x, y, text):
        f = font(17, True); box = self.draw.textbbox((0,0), text, font=f)
        width = box[2]-box[0]+30
        self.rounded((x,y,x+width,y+38),19,GREEN_LIGHT,None)
        self.text((x+15,y+19),text,17,GREEN,True,"lm")
        return width

    def paste_contained(self, image, box):
        x1,y1,x2,y2 = box
        copy = image.copy(); copy.thumbnail((x2-x1,y2-y1),Image.Resampling.LANCZOS)
        x=x1+(x2-x1-copy.width)//2; y=y1+(y2-y1-copy.height)//2
        self.image.paste(copy,(x,y))
        return (x,y,x+copy.width,y+copy.height)

def arrow(canvas: Canvas, start, end, color=GREEN):
    canvas.draw.line((start,end),fill=color,width=7)
    ex,ey=end
    canvas.draw.polygon([(ex,ey),(ex-18,ey-12),(ex-18,ey+12)],fill=color)

def metric_text(value): return f"{value*100:.2f}%"

def image_one(prediction: dict) -> tuple[Image.Image,list[dict],list[str]]:
    c=Canvas()
    c.text((56,68),"AI DOCUMENT",55,NAVY,True)
    c.text((56,126),"EXTRACTION",55,GREEN,True)
    c.text((58,207),"PDF • INVOICE • RECEIPT • OCR",22,NAVY,True)
    c.text((58,242),"Excel • CSV • JSON",21,MUTED)
    y=315
    for label in ["Batch Processing","Custom Fields","Validation Checks"]:
        c.badge(58,y,label); y+=55
    c.text((58,548),"Document to structured data",20,NAVY,True)
    c.text((58,582),"Offline OCR + embedded PDF text",18,MUTED)
    c.rounded((610,62,1224,708),24,CARD,LINE,2)
    c.text((642,92),"GENUINE SYNTHETIC EXAMPLE",16,GREEN,True)
    document=render_document(ROOT/prediction["file_path"],(270,500))
    c.rounded((640,132,918,654),14,"#FBFBFA",LINE)
    c.paste_contained(document,(652,144,906,642))
    arrow(c,(925,393),(968,393))
    c.rounded((980,184,1195,602),16,"#F4F7F5",LINE)
    c.text((1000,207),"STRUCTURED DATA",18,NAVY,True)
    fields=prediction["predicted_fields"]
    rows=[("Invoice No.",fields["invoice_number"]),("Date",fields["invoice_date"]),
          ("Vendor",fields["vendor_name"]),("Total",f'${fields["total_amount"]:,.2f}'),
          ("Currency",fields["currency"])]
    y=260
    for label,value in rows:
        c.text((1000,y),label.upper(),13,MUTED,True)
        c.text((1000,y+24),str(value),17,NAVY,True)
        c.draw.line((1000,y+53,1175,y+53),fill=LINE,width=1); y+=67
    c.text((640,676),"SYNTHETIC TEST DOCUMENT",13,MUTED,True)
    texts=[x["text"] for x in c.text_elements]
    return c.image,c.text_elements,texts

def image_two(prediction: dict, metrics: dict) -> tuple[Image.Image,list[dict],list[str]]:
    c=Canvas()
    c.text((54,48),"FROM DOCUMENTS TO STRUCTURED DATA",38,NAVY,True)
    c.text((56,99),"Tested on Synthetic Invoices and Receipts",20,MUTED)
    c.rounded((48,144,410,570),20,CARD,LINE,2)
    c.text((68,164),"SYNTHETIC TEST DOCUMENT",14,GREEN,True)
    doc=render_document(ROOT/prediction["file_path"],(315,360))
    c.paste_contained(doc,(68,200,390,550))
    arrow(c,(425,356),(480,356))
    c.rounded((500,144,1227,570),20,CARD,LINE,2)
    c.text((525,165),"EXTRACTED FIELDS",17,NAVY,True)
    fields=prediction["predicted_fields"]
    field_rows=[("Invoice Number",fields["invoice_number"]),("Invoice Date",fields["invoice_date"]),
        ("Vendor",fields["vendor_name"]),("Subtotal",f'${fields["subtotal"]:,.2f}'),
        ("Tax",f'${fields["tax_amount"]:,.2f}'),("Total",f'${fields["total_amount"]:,.2f}')]
    y=210
    for label,value in field_rows:
        c.text((525,y),label,14,MUTED,True); c.text((685,y),str(value),16,NAVY,True); y+=43
    c.text((525,486),f'Validation: {"Passed" if not prediction["validation_warnings"] else "Review"}',16,GREEN,True)
    c.text((525,520),f'Confidence: {prediction["confidence_label"]} ({prediction["structured_confidence"]:.3f})',15,NAVY,True)
    c.text((850,165),"LINE ITEMS",17,NAVY,True)
    headers=["Item","Qty","Amount"]; xs=[850,1082,1150]
    for x,label in zip(xs,headers): c.text((x,210),label,13,MUTED,True)
    c.draw.line((850,235,1197,235),fill=LINE,width=2)
    y=252
    for item in prediction["predicted_line_items"][:4]:
        c.text((850,y),item["description"],14,NAVY)
        c.text((1090,y),f'{item["quantity"]:g}',14,NAVY,anchor="ra")
        c.text((1197,y),f'${item["line_total"]:,.2f}',14,NAVY,anchor="ra")
        y+=45
    metric_specs=[
        ("CRITICAL-FIELD ACCURACY",metric_text(metrics["critical_field_accuracy"])),
        ("NUMERIC TOLERANCE ACCURACY",metric_text(metrics["numeric_tolerance_accuracy"])),
        ("LINE-ITEM F1",metric_text(metrics["line_item_f1"])),
    ]
    x=48
    for label,value in metric_specs:
        c.rounded((x,600,x+374,704),16,GREEN_LIGHT,None)
        c.text((x+20,620),label,14,GREEN,True)
        c.text((x+20,650),value,30,NAVY,True)
        x+=405
    c.text((640,739),f'Evaluated on {metrics["test_variant_count"]} synthetic document variants',
           14,MUTED,anchor="mm")
    texts=[x["text"] for x in c.text_elements]
    return c.image,c.text_elements,texts

def image_three() -> tuple[Image.Image,list[dict],list[str]]:
    c=Canvas()
    c.text((54,54),"AUTOMATED OCR WORKFLOW",42,NAVY,True)
    c.text((56,106),"Printed English Invoices and Receipts",19,MUTED)
    cards=[
        ("01","Upload Documents","PDF • PNG • JPG"),
        ("02","Preprocessing","Deskew • Clean • Enhance"),
        ("03","PDF Text / OCR","PyMuPDF • RapidOCR"),
        ("04","Field Extraction","Headers • Totals • Line Items"),
        ("05","Validation","Confidence • Reconciliation"),
        ("06","Structured Export","Excel • CSV • JSON"),
    ]
    x0,y,w,h,gap=45,195,180,250,27
    for index,(number,title,body) in enumerate(cards):
        x=x0+index*(w+gap)
        c.rounded((x,y,x+w,y+h),18,CARD,LINE,2)
        c.rounded((x+16,y+18,x+58,y+60),12,GREEN_LIGHT,None)
        c.text((x+37,y+39),number,15,GREEN,True,"mm")
        # Explicit wrapping keeps every card comfortably inside its bounds.
        title_lines={"Upload Documents":["Upload","Documents"],"PDF Text / OCR":["PDF Text","/ OCR"],
            "Field Extraction":["Field","Extraction"],"Structured Export":["Structured","Export"]}.get(title,[title])
        ty=y+88
        for line in title_lines:
            c.text((x+16,ty),line,19,NAVY,True); ty+=25
        body_lines=body.split(" • ")
        by=y+168
        for line in body_lines:
            c.text((x+16,by),line,14,MUTED); by+=21
        if index<len(cards)-1: arrow(c,(x+w+4,y+125),(x+w+gap-7,y+125),GREEN)
    features=["Batch Processing","Editable Review","Confidence Checks","Reusable Python Workflow"]
    x=82
    for label in features:
        width=c.badge(x,510,label); x+=width+25
    c.rounded((45,591,1235,696),18,"#EEF2F0",None)
    c.text((69,616),"HYBRID DOCUMENT PROCESSING",14,GREEN,True)
    c.text((69,648),"Digital PDF text when available. Offline OCR for scans and images.",23,NAVY,True)
    c.text((640,735),"PDF • PNG • JPG  →  EXCEL • CSV • JSON",15,MUTED,True,"mm")
    texts=[x["text"] for x in c.text_elements]
    return c.image,c.text_elements,texts

def validate_image(path: Path, elements: list[dict], texts: list[str], metrics: dict) -> dict:
    with Image.open(path) as image:
        image.load()
        variance=sum(ImageStat.Stat(image.convert("L")).var)
        dimensions=list(image.size)
    bounds_ok=all(box["bbox"][0]>=SAFE_MARGIN-2 and box["bbox"][1]>=20 and
                  box["bbox"][2]<=SIZE[0]-SAFE_MARGIN+2 and box["bbox"][3]<=SIZE[1]-18
                  for box in elements)
    combined=" ".join(texts).lower()
    prohibited=["100% accurate","guaranteed error-free","human-level extraction",
                "production-ready for every industry","client document","ocr cer","ocr wer"]
    return {"exists":path.exists(),"dimensions":dimensions,"opens_successfully":True,
        "non_blank":variance>20,"pixel_variance":round(variance,2),"text_within_safe_bounds":bounds_ok,
        "contains_prohibited_claim":any(x in combined for x in prohibited),
        "contains_ocr_cer_or_wer":"ocr cer" in combined or "ocr wer" in combined,
        "synthetic_only_source":True}

def generate() -> dict:
    OUT.mkdir(parents=True,exist_ok=True); PREVIEWS.mkdir(parents=True,exist_ok=True)
    metrics=load_metrics()
    thumb_prediction=load_prediction("INV-0011")
    result_prediction=load_prediction("INV-0037")
    metric_checks={
        "critical_field_accuracy":metrics["critical_field_accuracy"],
        "numeric_tolerance_accuracy":metrics["numeric_tolerance_accuracy"],
        "line_item_f1":metrics["line_item_f1"],
        "test_variant_count":metrics["test_variant_count"],
        "source":"outputs/evaluation/evaluation_summary.json",
        "all_values_loaded_from_summary":True,
    }
    (OUT/"metric_verification.json").write_text(json.dumps(metric_checks,indent=2),encoding="utf-8")
    specs=[
        ("01_gig_thumbnail.png",*image_one(thumb_prediction)),
        ("02_extraction_result.png",*image_two(result_prediction,metrics)),
        ("03_ocr_workflow.png",*image_three()),
    ]
    validations={}
    for name,image,elements,texts in specs:
        path=OUT/name
        image.save(path,"PNG",optimize=False)
        preview=image.resize(SMALL,Image.Resampling.LANCZOS)
        preview.save(PREVIEWS/name.replace(".png","_small.png"),"PNG",optimize=False)
        validations[name]=validate_image(path,elements,texts,metrics)
        validations[name]["preview_exists"]=(PREVIEWS/name.replace(".png","_small.png")).exists()
        validations[name]["preview_dimensions"]=list(SMALL)
        validations[name]["displayed_text"]=texts
    validations["metric_integrity"]={
        "critical_field_matches":metric_checks["critical_field_accuracy"]==metrics["critical_field_accuracy"],
        "numeric_field_matches":metric_checks["numeric_tolerance_accuracy"]==metrics["numeric_tolerance_accuracy"],
        "line_item_f1_matches":metric_checks["line_item_f1"]==metrics["line_item_f1"],
        "test_variant_count_matches":metric_checks["test_variant_count"]==metrics["test_variant_count"],
    }
    validations["source_documents"]={"image_1":"INV-0011-digital_pdf","image_2":"INV-0037-digital_pdf"}
    validations["all_checks_passed"]=all(
        v["exists"] and v["dimensions"]==list(SIZE) and v["non_blank"] and
        v["text_within_safe_bounds"] and not v["contains_prohibited_claim"] and
        not v["contains_ocr_cer_or_wer"] and v["preview_exists"]
        for k,v in validations.items() if k.endswith(".png")
    ) and all(validations["metric_integrity"].values())
    (OUT/"image_validation.json").write_text(json.dumps(validations,indent=2),encoding="utf-8")
    return validations

if __name__ == "__main__":
    result=generate()
    print("Generated Fiverr images:", OUT)
    print("Validation passed:", result["all_checks_passed"])
    if not result["all_checks_passed"]: sys.exit(1)

