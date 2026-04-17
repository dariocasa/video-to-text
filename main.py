from __future__ import annotations

import logging
import sys

from app.downloader import download_youtube_video
from app.frame_extractor import extract_frames
from app.models import DownloadConfig, ExtractionConfig


def configure_logging() -> None:
    """Configure application logging."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")


def prompt_youtube_url() -> str:
    """Prompt the user for a YouTube URL."""
    url = input("Inserisci il link YouTube: ").strip()
    if not url:
        raise ValueError("Il link YouTube non puo' essere vuoto.")
    return url


def main() -> int:
    """Download a YouTube video and extract frames from it."""
    configure_logging()

    try:
        youtube_url = prompt_youtube_url()
        video_path = download_youtube_video(youtube_url, DownloadConfig())
        extract_frames(video_path, ExtractionConfig())
    except Exception as error:
        logging.error(f"Errore: {error}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
