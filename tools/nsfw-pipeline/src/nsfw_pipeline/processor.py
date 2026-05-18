from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from nsfw_pipeline.types import DetectionBox

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def list_images(path: Path) -> list[Path]:
    return sorted(item for item in path.rglob("*") if item.is_file() and item.suffix.lower() in SUPPORTED_EXTENSIONS)


def censor_image(
    input_path: Path,
    output_path: Path,
    detections: list[DetectionBox],
    *,
    effect: str = "blur",
    blur_kernel: int = 61,
    pixel_size: int = 18,
    padding_ratio: float = 0.08,
) -> dict:
    image = cv2.imread(str(input_path))
    if image is None:
        raise RuntimeError(f"Не удалось прочитать изображение: {input_path}")

    height, width = image.shape[:2]
    for detection in detections:
        x1, y1, x2, y2 = _expand_box(detection, width, height, padding_ratio)
        roi = image[y1:y2, x1:x2]
        if roi.size == 0:
            continue
        if effect == "pixelate":
            image[y1:y2, x1:x2] = _pixelate(roi, pixel_size)
        elif effect == "block":
            image[y1:y2, x1:x2] = np.zeros_like(roi)
        else:
            image[y1:y2, x1:x2] = cv2.GaussianBlur(roi, _odd_kernel(blur_kernel), 0)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output_path), image):
        raise RuntimeError(f"Не удалось сохранить изображение: {output_path}")

    return {
        "input": str(input_path),
        "output": str(output_path),
        "detections_count": len(detections),
        "detections": [item.as_dict() for item in detections],
    }


def render_final_image(
    input_path: Path,
    output_path: Path,
    *,
    max_width: int,
    max_height: int,
    white_background: bool,
    output_format: str,
    watermark_text: str = "",
    watermark_font_size: int = 28,
    watermark_image: Path | None = None,
    jpeg_quality: int = 92,
    webp_quality: int = 92,
) -> Path:
    image = Image.open(input_path).convert("RGBA")
    image.thumbnail((max_width, max_height))

    if white_background:
        canvas = Image.new("RGBA", image.size, (255, 255, 255, 255))
        canvas.alpha_composite(image)
        image = canvas

    if watermark_image and watermark_image.exists():
        image = _apply_watermark_image(image, watermark_image)

    if watermark_text:
        image = _apply_watermark_text(image, watermark_text, watermark_font_size)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    rgb = image.convert("RGB")
    fmt = output_format.upper()
    save_kwargs: dict = {}
    if fmt == "JPEG" or fmt == "JPG":
        fmt = "JPEG"
        save_kwargs["quality"] = jpeg_quality
    elif fmt == "WEBP":
        save_kwargs["quality"] = webp_quality
    rgb.save(output_path, format=fmt, **save_kwargs)
    return output_path


def save_report(path: Path, payload: dict | list) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _expand_box(box: DetectionBox, width: int, height: int, padding_ratio: float) -> tuple[int, int, int, int]:
    box_width = box.x2 - box.x1
    box_height = box.y2 - box.y1
    pad_x = int(box_width * padding_ratio)
    pad_y = int(box_height * padding_ratio)
    x1 = max(0, box.x1 - pad_x)
    y1 = max(0, box.y1 - pad_y)
    x2 = min(width, box.x2 + pad_x)
    y2 = min(height, box.y2 + pad_y)
    return x1, y1, x2, y2


def _odd_kernel(value: int) -> tuple[int, int]:
    size = max(3, int(value))
    if size % 2 == 0:
        size += 1
    return (size, size)


def _pixelate(image: np.ndarray, pixel_size: int) -> np.ndarray:
    h, w = image.shape[:2]
    scale = max(1, int(pixel_size))
    small = cv2.resize(image, (max(1, w // scale), max(1, h // scale)), interpolation=cv2.INTER_LINEAR)
    return cv2.resize(small, (w, h), interpolation=cv2.INTER_NEAREST)


def _apply_watermark_text(image: Image.Image, text: str, font_size: int) -> Image.Image:
    canvas = image.copy()
    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", font_size)
    except OSError:
        font = ImageFont.load_default()
    margin = max(12, font_size // 2)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    x = canvas.width - text_width - margin
    y = canvas.height - text_height - margin
    draw.rectangle((x - 8, y - 4, x + text_width + 8, y + text_height + 4), fill=(0, 0, 0, 120))
    draw.text((x, y), text, fill=(255, 255, 255, 220), font=font)
    return canvas


def _apply_watermark_image(image: Image.Image, watermark_path: Path) -> Image.Image:
    canvas = image.copy()
    watermark = Image.open(watermark_path).convert("RGBA")
    target_width = max(80, canvas.width // 6)
    ratio = target_width / watermark.width
    watermark = watermark.resize((target_width, max(1, int(watermark.height * ratio))))
    alpha = watermark.getchannel("A")
    alpha = alpha.point(lambda value: min(value, 180))
    watermark.putalpha(alpha)
    x = canvas.width - watermark.width - 24
    y = 24
    canvas.alpha_composite(watermark, (x, y))
    return canvas
