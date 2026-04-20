from __future__ import annotations

import logging
from pathlib import Path

from rapidocr_onnxruntime import RapidOCR

from app.common.path_utils import build_named_output_dir, sanitize_name
from app.config.models import FRAMES_DIR, OcrConfig
from app.ocr.retry import build_image_variants, load_frame_image


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
    """Extract ordered text lines from a frame image using the default OCR preprocessing."""
    image = load_frame_image(frame_path)
    preprocessed_image = build_image_variants(image)["gray2x"]
    result, _ = ocr_engine(preprocessed_image)
    if not result:
        return []

    lines: list[str] = []
    for item in result:
        text = str(item[1]).strip()
        score = float(item[2])
        if text and score >= min_confidence:
            lines.append(text)
    return lines


def clean_ocr_lines(lines: list[str]) -> list[str]:
    """Remove boilerplate '15' from the last line if it exists."""
    if lines and lines[-1] == "15":
        logging.info("Rimossa riga '15' finale.")
        return lines[:-1]
    return lines


def save_text_file(output_dir: Path, frame_path: Path, lines: list[str]) -> Path:
    """Save extracted text for a frame in a matching .txt file."""
    output_path = output_dir / f"{frame_path.stem}.txt"
    output_path.write_text("\n".join(lines), encoding="utf-8")
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
        cleaned_lines = clean_ocr_lines(lines)
        save_text_file(output_dir, frame_path, cleaned_lines)
        saved_count += 1
        logging.info("Testo estratto %d/%d: %s", index, len(frame_files), frame_path.name)

    logging.info("Completato. File di testo salvati: %d.", saved_count)
    return saved_count


def process_all_ocr_extractions(config: OcrConfig | None = None) -> None:
    """Extract text from all frame folders in the frames directory."""
    config = config or OcrConfig()

    if not config.frames_root.exists():
        logging.warning(f"La cartella frames '{config.frames_root}' non esiste.")
        return

    # Filter for directories in frames root
    video_folders = [
        d for d in config.frames_root.iterdir()
        if d.is_dir()
    ]

    if not video_folders:
        logging.info("Nessuna cartella di frame trovata.")
        return

    logging.info(f"Trovate {len(video_folders)} cartelle di frame da processare.")

    for folder in video_folders:
        video_name = folder.name
        output_dir = config.output_root / sanitize_name(video_name)

        # Skip if folder exists and contains files
        if output_dir.exists() and any(output_dir.iterdir()):
            logging.info(f"Salto '{video_name}': testo gia' estratto in {output_dir}")
            continue

        try:
            extract_text_from_video_frames(video_name, config)
        except Exception as e:
            logging.error(f"Errore durante l'OCR di '{video_name}': {e}")
