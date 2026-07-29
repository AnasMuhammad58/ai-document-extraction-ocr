from __future__ import annotations
from pathlib import Path
import cv2
import numpy as np
from PIL import Image

def pil_to_bgr(image: Image.Image) -> np.ndarray:
    return cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2BGR)

def deskew(gray: np.ndarray) -> tuple[np.ndarray, float]:
    points = np.column_stack(np.where(gray < 220))
    if len(points) < 100:
        return gray, 0.0
    angle = cv2.minAreaRect(points[:, ::-1].astype(np.float32))[-1]
    angle = -(90 + angle) if angle < -45 else -angle
    if abs(angle) > 3 or abs(angle) < 0.15:
        return gray, 0.0
    h, w = gray.shape
    matrix = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1)
    return cv2.warpAffine(gray, matrix, (w, h), flags=cv2.INTER_CUBIC,
                          borderMode=cv2.BORDER_CONSTANT, borderValue=255), angle

def preprocess(image: Image.Image, quality_hint: str = "", config: dict | None = None) -> tuple[np.ndarray, dict]:
    config = config or {}
    bgr = pil_to_bgr(image)
    if bgr.shape[1] < config.get("upscale_min_width", 900):
        scale = config["upscale_min_width"] / bgr.shape[1]
        bgr = cv2.resize(bgr, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    angle = 0.0
    if config.get("deskew", True) and ("rotation" in quality_hint or not quality_hint):
        gray, angle = deskew(gray)
    if config.get("normalize_contrast", True) and ("contrast" in quality_hint or "shadow" in quality_hint):
        gray = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(8, 8)).apply(gray)
    if config.get("denoise", True) and ("noise" in quality_hint or "compression" in quality_hint):
        gray = cv2.fastNlMeansDenoising(gray, None, 7, 7, 21)
    # RapidOCR performs reliably on grayscale and clean images; threshold only uneven scans.
    if "shadow" in quality_hint:
        gray = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                     cv2.THRESH_BINARY, 35, 12)
    return gray, {"deskew_angle": angle, "width": int(gray.shape[1]), "height": int(gray.shape[0])}

def save_preprocessing_example(before: Image.Image, after: np.ndarray, before_path: Path, after_path: Path) -> None:
    before_path.parent.mkdir(parents=True, exist_ok=True)
    before.convert("RGB").save(before_path)
    cv2.imwrite(str(after_path), after)

