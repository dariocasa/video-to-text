from __future__ import annotations

import argparse
import logging
import sys

from app.config.models import ParseConfig
from app.llm.json_cleaner import clean_json_with_llm


def configure_logging() -> None:
    """Configure application logging."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Create an LLM-cleaned JSON document from parsed OCR output."
    )
    parser.add_argument(
        "video_name",
        help="Video folder name inside output/ (for example: jan26_q1_35).",
    )
    return parser.parse_args()


def main() -> int:
    """CLI entrypoint for LLM JSON cleanup."""
    configure_logging()
    try:
        args = parse_args()
        output_path = clean_json_with_llm(args.video_name, ParseConfig())
        logging.info(f"JSON LLM creato: {output_path}")
    except Exception as error:
        logging.error(f"Errore: {error}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
