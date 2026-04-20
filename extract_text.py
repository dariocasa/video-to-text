from __future__ import annotations

import argparse
import logging
import sys

from app.config.models import OcrConfig
from app.ocr.extractor import extract_text_from_video_frames


def configure_logging() -> None:
    """Configure application logging."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Extract text from all frames of a video folder."
    )
    parser.add_argument(
        "video_name",
        help="Video folder name inside frames/ (for example: jan26_q1_35).",
    )
    return parser.parse_args()


def main() -> int:
    """CLI entrypoint for OCR extraction."""
    configure_logging()

    try:
        args = parse_args()
        extract_text_from_video_frames(args.video_name, OcrConfig())
    except Exception as error:
        logging.error(f"Errore: {error}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
