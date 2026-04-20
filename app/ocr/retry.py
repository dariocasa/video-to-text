from __future__ import annotations

from pathlib import Path

import cv2
from rapidocr_onnxruntime import RapidOCR


def load_frame_image(frame_path: Path):
    """Load a frame image from disk."""
    image = cv2.imread(str(frame_path))
    if image is None:
        raise FileNotFoundError(f"Frame non trovato o non leggibile: {frame_path}")
    return image


def build_image_variants(image) -> dict[str, object]:
    """Create OCR-friendly variants of a frame image."""
    height, width = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    scaled_gray = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    _, threshold = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    scaled_threshold = cv2.resize(threshold, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)

    return {
        "full": image,
        "bottom70": image[int(height * 0.25) :, :],
        "bottom55": image[int(height * 0.40) :, :],
        "gray2x": scaled_gray,
        "threshold2x": scaled_threshold,
        "top80_gray2x": cv2.resize(gray[: int(height * 0.80), :], None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC),
        "options_only_gray2x": cv2.resize(gray[int(height * 0.40) :, :], None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC),
        "options_only_threshold2x": cv2.resize(threshold[int(height * 0.40) :, :], None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC),
        "question_only_gray2x": cv2.resize(gray[: int(height * 0.55), :], None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC),
        "center_gray2x": cv2.resize(
            gray[int(height * 0.12) : int(height * 0.90), int(width * 0.03) : int(width * 0.97)],
            None,
            fx=2,
            fy=2,
            interpolation=cv2.INTER_CUBIC,
        ),
    }


def run_ocr_lines(ocr_engine: RapidOCR, image, min_confidence: float) -> list[str]:
    """Extract filtered OCR lines from an image variant."""
    result, _ = ocr_engine(image)
    if not result:
        return []

    lines: list[str] = []
    for item in result:
        text = str(item[1]).strip()
        score = float(item[2])
        if text and score >= min_confidence:
            lines.append(text)
    return lines


def build_retry_candidates(frame_path: Path, min_confidence: float) -> list[dict[str, object]]:
    """Run OCR over multiple image variants and collect candidate texts."""
    image = load_frame_image(frame_path)
    ocr_engine = RapidOCR()
    candidates: list[dict[str, object]] = []

    for variant_name, variant_image in build_image_variants(image).items():
        lines = run_ocr_lines(ocr_engine, variant_image, min_confidence)
        candidates.append({"variant": variant_name, "lines": lines, "text": "\n".join(lines).strip()})

    return candidates
