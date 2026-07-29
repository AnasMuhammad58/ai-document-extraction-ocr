from __future__ import annotations
from importlib.metadata import version
import numpy as np
import onnxruntime as ort
from rapidocr_onnxruntime import RapidOCR
from .schemas import OCRLine

class OfflineOCREngine:
    def __init__(self):
        self.engine = RapidOCR()

    def recognize(self, image: np.ndarray) -> tuple[str, list[OCRLine], float | None]:
        result, _ = self.engine(image)
        lines = []
        for box, text, confidence in result or []:
            lines.append(OCRLine(text=text.strip(), confidence=float(confidence),
                                 bbox=[[float(x), float(y)] for x, y in box]))
        lines.sort(key=lambda item: (min(p[1] for p in item.bbox or [[0, 0]]),
                                     min(p[0] for p in item.bbox or [[0, 0]])))
        raw = reconstruct_rows(lines)
        scores = [line.confidence for line in lines if line.confidence is not None]
        return raw, lines, sum(scores) / len(scores) if scores else None

def reconstruct_rows(lines: list[OCRLine], tolerance_scale: float = .95) -> str:
    rows: list[list[OCRLine]] = []
    for line in lines:
        y = sum(p[1] for p in line.bbox or [[0, 0]]) / 4
        placed = False
        for row in rows:
            ry = sum(p[1] for p in row[0].bbox or [[0, 0]]) / 4
            height = max(p[1] for p in line.bbox or [[0, 0]]) - min(p[1] for p in line.bbox or [[0, 0]])
            if abs(y - ry) <= max(3, height * tolerance_scale):
                row.append(line); placed = True; break
        if not placed: rows.append([line])
    rendered = []
    for row in rows:
        row.sort(key=lambda item: min(p[0] for p in item.bbox or [[0, 0]]))
        rendered.append(" | ".join(item.text for item in row))
    return "\n".join(rendered)

def engine_info() -> dict:
    return {"engine_name": "RapidOCR ONNX Runtime", "engine_version": version("rapidocr-onnxruntime"),
            "onnxruntime_version": ort.__version__, "execution_provider": ["CPUExecutionProvider"],
            "available_execution_providers": ort.get_available_providers(),
            "fallback_engine": None, "supported_file_types": ["pdf", "png", "jpg", "jpeg"],
            "bounding_boxes_available": True, "ocr_confidence_available": True}
