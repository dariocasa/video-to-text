from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


VIDEO_DIR = Path("video")
FRAMES_DIR = Path("frames")
TEXT_DIR = Path("text")
OUTPUT_DIR = Path("output")
DEFAULT_SECONDS_INTERVAL = 1.0
DEFAULT_DUPLICATE_THRESHOLD = 1.0
DEFAULT_SCENE_THRESHOLD = 20.0
DEFAULT_IMAGE_QUALITY = 95
DEFAULT_OCR_MIN_CONFIDENCE = 0.5


@dataclass(frozen=True)
class DownloadConfig:
    output_dir: Path = VIDEO_DIR


@dataclass(frozen=True)
class ExtractionConfig:
    output_root: Path = FRAMES_DIR
    seconds_interval: float = DEFAULT_SECONDS_INTERVAL
    duplicate_threshold: float = DEFAULT_DUPLICATE_THRESHOLD
    scene_threshold: float | None = DEFAULT_SCENE_THRESHOLD
    image_quality: int = DEFAULT_IMAGE_QUALITY


@dataclass(frozen=True)
class OcrConfig:
    frames_root: Path = FRAMES_DIR
    output_root: Path = TEXT_DIR
    min_confidence: float = DEFAULT_OCR_MIN_CONFIDENCE


@dataclass(frozen=True)
class ParseConfig:
    text_root: Path = TEXT_DIR
    output_root: Path = OUTPUT_DIR
    frames_root: Path = FRAMES_DIR
    retry_ocr: bool = True
    ocr_min_confidence: float = DEFAULT_OCR_MIN_CONFIDENCE
