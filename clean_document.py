from __future__ import annotations

import argparse
import logging
import sys

from app.models import ParseConfig
from app.text_cleaner import build_clean_documents


def configure_logging() -> None:
    """Configure application logging."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Create cleaned JSON and Markdown documents from parsed OCR output."
    )
    parser.add_argument(
        "video_name",
        help="Video folder name inside output/ (for example: jan26_q1_35).",
    )
    return parser.parse_args()


def main() -> int:
    """CLI entrypoint for cleaned document generation."""
    configure_logging()
    try:
        args = parse_args()
        json_path, markdown_path = build_clean_documents(args.video_name, ParseConfig())
        logging.info(f"JSON clean creato: {json_path}")
        logging.info(f"Markdown clean creato: {markdown_path}")
    except Exception as error:
        logging.error(f"Errore: {error}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
