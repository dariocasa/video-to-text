from __future__ import annotations

import logging
import re
from pathlib import Path

from rapidocr_onnxruntime import RapidOCR

from app.common.path_utils import build_named_output_dir, natural_sort_key, sanitize_name
from app.config.models import FRAMES_DIR, OcrConfig
from app.ocr.processor import QuizFrameProcessor
from app.ocr.retry import load_frame_image


SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def list_frame_files(frame_dir: Path) -> list[Path]:
    """Return all supported frame images in a directory."""
    if not frame_dir.exists():
        raise FileNotFoundError(f"Cartella frame non trovata: {frame_dir}")
    if not frame_dir.is_dir():
        raise NotADirectoryError(f"Il percorso dei frame non e' una cartella: {frame_dir}")

    frame_files = sorted(
        (
            path
            for path in frame_dir.iterdir()
            if path.is_file() and path.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS
        ),
        key=natural_sort_key
    )
    if not frame_files:
        raise FileNotFoundError(f"Nessun frame trovato in: {frame_dir}")
    return frame_files


def extract_text_sections(ocr_engine: RapidOCR, frame_path: Path, min_confidence: float) -> list[tuple[list[str], str]]:
    """
    Extract text from logical sections of the frame.
    Returns a list of (lines, suffix) tuples.
    """
    image = load_frame_image(frame_path)
    sections = QuizFrameProcessor.process(image, frame_path.name)
    
    results: list[tuple[list[str], str]] = []
    
    for processed_img, label in sections:
        ocr_result, _ = ocr_engine(processed_img)
        
        lines: list[str] = []
        if ocr_result:
            for item in ocr_result:
                text = str(item[1]).strip()
                score = float(item[2])
                if text and score >= min_confidence:
                    lines.append(text)
        results.append((lines, label))
        
    return results


def merge_option_lines(lines: list[str]) -> list[str]:
    """Merge lines that belong to the same option (A, B, C, D)."""
    import re
    merged = []
    # Pattern to detect start of a new option: "A.", "B.", "(A)", "A)" etc.
    option_pattern = re.compile(r'^([A-Z][\.\)])|(\([A-Z]\))')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        if option_pattern.match(line):
            merged.append(line)
        else:
            if merged:
                merged[-1] += " " + line
            else:
                merged.append(line)
    return merged


def save_section_text(output_dir: Path, frame_path: Path, lines: list[str], sub_index: int, label: str) -> Path:
    """
    Save extracted text for a specific section.
    Naming follows: 00n_typeindex_subindex_label.txt
    """
    # frame_path.stem is e.g. 001_1_question
    # output should be 001_1_1_question.txt
    parts = frame_path.stem.split("_")
    n = parts[0]
    type_index = parts[1]
    
    filename = f"{n}_{type_index}_{sub_index}_{label}.txt"
    output_path = output_dir / filename
    
    if label == "option":
        # Merge multi-line options but keep A, B, C, D on separate lines
        formatted_lines = merge_option_lines(lines)
        output_path.write_text("\n".join(formatted_lines), encoding="utf-8")
    else:
        # Questions, answers and explanations should be single-line
        output_path.write_text(" ".join(lines), encoding="utf-8")
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
        section_results = extract_text_sections(ocr_engine, frame_path, config.min_confidence)
        
        for sub_index, (lines, label) in enumerate(section_results, start=1):
            save_section_text(output_dir, frame_path, lines, sub_index, label)
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
