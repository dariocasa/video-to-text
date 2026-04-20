from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

from app.config.models import DownloadConfig
from app.download.downloader import download_youtube_video


def configure_logging() -> None:
    """Configure application logging."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")


def load_entries(json_path: Path) -> list[dict[str, str]]:
    """Load download entries from a JSON file."""
    data = json.loads(json_path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("Il file input_video.json deve contenere una lista di oggetti.")

    entries: list[dict[str, str]] = []
    for item in data:
        if not isinstance(item, dict):
            raise ValueError("Ogni elemento del JSON deve essere un oggetto.")
        name = str(item.get("nome", "")).strip()
        url = str(item.get("url", "")).strip()
        if not name or not url:
            raise ValueError("Ogni oggetto deve contenere i campi 'nome' e 'url'.")
        entries.append({"nome": name, "url": url})
    return entries


def main() -> int:
    """Download all videos listed in input_video.json."""
    configure_logging()

    try:
        config = DownloadConfig()
        entries = load_entries(Path("input_video.json"))

        for entry in entries:
            target_path = config.output_dir / f"{entry['nome']}.mp4"
            if target_path.exists():
                logging.info("Gia' presente, salto: %s", target_path)
                continue
            logging.info("Scarico %s", entry["nome"])
            download_youtube_video(entry["url"], config, output_name=entry["nome"])
    except Exception as error:
        logging.error(f"Errore: {error}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
