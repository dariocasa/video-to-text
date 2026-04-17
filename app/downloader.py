from __future__ import annotations

import logging
from pathlib import Path

from yt_dlp import YoutubeDL

from app.models import DownloadConfig
from app.path_utils import ensure_directory


def download_youtube_video(url: str, config: DownloadConfig) -> Path:
    """Download a YouTube video into the configured video directory."""
    output_dir = ensure_directory(config.output_dir)
    output_template = str(output_dir / "%(title)s [%(id)s].%(ext)s")

    options = {
        "format": "mp4/bestvideo+bestaudio/best",
        "merge_output_format": "mp4",
        "outtmpl": output_template,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
    }

    logging.info("Download del video in corso...")
    with YoutubeDL(options) as downloader:
        info = downloader.extract_info(url, download=True)
        downloaded_path = Path(downloader.prepare_filename(info))

    if downloaded_path.suffix.lower() != ".mp4":
        mp4_candidate = downloaded_path.with_suffix(".mp4")
        if mp4_candidate.exists():
            downloaded_path = mp4_candidate

    if not downloaded_path.exists():
        raise FileNotFoundError("Il file video scaricato non e' stato trovato.")

    logging.info(f"Video salvato in: {downloaded_path}")
    return downloaded_path
