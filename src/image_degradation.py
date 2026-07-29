"""Deterministic, moderate scanned-document degradation."""
from __future__ import annotations
import io
import random
from PIL import Image, ImageEnhance, ImageFilter

QUALITY_PROFILES = (
    "slight_rotation", "mild_blur", "lower_contrast", "light_noise",
    "mild_shadow", "jpeg_compression", "perspective",
)

def metadata(label: str) -> dict:
    values = {
        "quality_label": label, "rotation_degrees": 0.0, "blur_level": 0.0,
        "contrast_factor": 1.0, "noise_level": 0.0, "compression_quality": 95,
    }
    if label == "slight_rotation": values["rotation_degrees"] = 1.2
    elif label == "mild_blur": values["blur_level"] = 0.65
    elif label == "lower_contrast": values["contrast_factor"] = 0.78
    elif label == "light_noise": values["noise_level"] = 4.0
    elif label == "mild_shadow": values["contrast_factor"] = 0.9
    elif label == "jpeg_compression": values["compression_quality"] = 58
    elif label == "perspective": values["rotation_degrees"] = -0.45
    return values

def apply(image: Image.Image, label: str, seed: int) -> Image.Image:
    image = image.convert("RGB")
    if label == "slight_rotation":
        return image.rotate(1.2, resample=Image.Resampling.BICUBIC, expand=False, fillcolor="white")
    if label == "mild_blur":
        return image.filter(ImageFilter.GaussianBlur(0.65))
    if label == "lower_contrast":
        return ImageEnhance.Contrast(image).enhance(0.78)
    if label == "light_noise":
        rng = random.Random(seed)
        px = image.load()
        for _ in range(image.width * image.height // 22):
            x, y = rng.randrange(image.width), rng.randrange(image.height)
            base = px[x, y]
            delta = rng.randint(-18, 18)
            px[x, y] = tuple(max(0, min(255, c + delta)) for c in base)
        return image
    if label == "mild_shadow":
        overlay = Image.new("L", image.size)
        opx = overlay.load()
        for x in range(image.width):
            shade = int(255 - 28 * x / max(1, image.width - 1))
            for y in range(image.height):
                opx[x, y] = shade
        return Image.composite(image, Image.new("RGB", image.size, (232, 232, 228)), overlay)
    if label == "jpeg_compression":
        buf = io.BytesIO()
        image.save(buf, "JPEG", quality=58)
        buf.seek(0)
        return Image.open(buf).convert("RGB")
    if label == "perspective":
        w, h = image.size
        return image.transform((w, h), Image.Transform.QUAD,
            (10, 5, 0, h - 3, w - 1, h - 7, w - 8, 0),
            resample=Image.Resampling.BICUBIC, fillcolor="white")
    return image
