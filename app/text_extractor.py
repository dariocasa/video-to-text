from __future__ import annotations

import logging
from pathlib import Path

from rapidocr_onnxruntime import RapidOCR

from app.models import OcrConfig
from app.path_utils import build_named_output_dir


SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def list_frame_files(frame_dir: Path) -> list[Path]:
    """Return all supported frame images in a directory."""
    if not frame_dir.exists():
        raise FileNotFoundError(f"Cartella frame non trovata: {frame_dir}")
    if not frame_dir.is_dir():
        raise NotADirectoryError(f"Il percorso dei frame non e' una cartella: {frame_dir}")

    frame_files = sorted(
        path
        for path in frame_dir.iterdir()
        if path.is_file() and path.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS
    )
    if not frame_files:
        raise FileNotFoundError(f"Nessun frame trovato in: {frame_dir}")
    return frame_files


def extract_text_lines(ocr_engine: RapidOCR, frame_path: Path, min_confidence: float) -> list[str]:
    """Extract ordered text lines from a frame image."""
    result, _ = ocr_engine(str(frame_path))
    if not result:
        return []

    lines: list[str] = []
    for item in result:
        text = str(item[1]).strip()
        score = float(item[2])
        if text and score >= min_confidence:
            lines.append(text)
    return lines


def save_text_file(output_dir: Path, frame_path: Path, lines: list[str]) -> Path:
    """Save extracted text for a frame in a matching .txt file."""
    output_path = output_dir / f"{frame_path.stem}.txt"
    content = "\n".join(lines)
    output_path.write_text(content, encoding="utf-8")
    return output_path


def extract_text_from_video_frames(video_name: str, config: OcrConfig) -> int:
    """Extract OCR text for every frame of a video into text/<video_name>."""
    frame_dir = config.frames_root / video_name
    frame_files = list_frame_files(frame_dir)
    output_dir = build_named_output_dir(config.output_root, video_name)
    ocr_engine = RapidOCR()
    saved_count = 0

    logging.info(f"Frame input: {frame_dir}")
    logging.info(f"Text output: {output_dir}")

    for index, frame_path in enumerate(frame_files, start=1):
        lines = extract_text_lines(ocr_engine, frame_path, config.min_confidence)
        save_text_file(output_dir, frame_path, lines)
        saved_count += 1
        logging.info(
            "Testo estratto %d/%d: %s",
            index,
            len(frame_files),
            frame_path.name,
        )

    logging.info("Completato. File di testo salvati: %d.", saved_count)
    return saved_count
