from __future__ import annotations

import argparse
import logging
import sys

from app.document_builder import build_documents
from app.models import ParseConfig


def configure_logging() -> None:
    """Configure application logging."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Build JSON and Markdown documents from OCR text pairs."
    )
    parser.add_argument(
        "video_name",
        help="Video folder name inside text/ (for example: jan26_q1_35).",
    )
    return parser.parse_args()


def main() -> int:
    """CLI entrypoint for OCR document building."""
    configure_logging()

    try:
        args = parse_args()
        json_path, markdown_path = build_documents(args.video_name, ParseConfig())
        logging.info(f"JSON creato: {json_path}")
        logging.info(f"Markdown creato: {markdown_path}")
    except Exception as error:
        logging.error(f"Errore: {error}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
