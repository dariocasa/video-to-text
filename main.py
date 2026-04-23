from __future__ import annotations

import logging
import sys

from pathlib import Path

from app.config.models import (
    VIDEO_DIR,
    SUPPORTED_VIDEO_EXTENSIONS,
    DownloadConfig,
    ExtractionConfig,
    OcrConfig,
    ParseConfig,
)
from app.document.builder import build_json_document, process_all_documents
from app.download.downloader import download_youtube_video
from app.frames.extractor import extract_frames, process_all_videos
from app.ocr.extractor import (
    extract_text_from_video_frames,
    process_all_ocr_extractions,
)


def configure_logging() -> None:
    """Configure application logging."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")


def prompt_youtube_url() -> str:
    """Prompt the user for a YouTube URL."""
    url = input("Inserisci il link YouTube: ").strip()
    if not url:
        raise ValueError("Il link YouTube non puo' essere vuoto.")
    return url


def prompt_video_name() -> str:
    """Prompt the user for a video name (folder name)."""
    name = input("Inserisci il nome del video (es: jan26_q36_70): ").strip()
    if not name:
        raise ValueError("Il nome del video non puo' essere vuoto.")
    return name


def prompt_video_file() -> Path:
    """Prompt the user to select a video file from the video directory."""
    if not VIDEO_DIR.exists():
        raise FileNotFoundError(f"La cartella '{VIDEO_DIR}' non esiste.")

    video_files = sorted([
        f for f in VIDEO_DIR.iterdir()
        if f.is_file() and f.suffix.lower() in SUPPORTED_VIDEO_EXTENSIONS
    ])

    if not video_files:
        raise FileNotFoundError(f"Nessun video trovato in '{VIDEO_DIR}'.")

    print("\nVideo disponibili:")
    for i, file in enumerate(video_files, 1):
        print(f"{i}. {file.name}")

    choice = input("\nSeleziona il numero del video: ").strip()
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(video_files):
            return video_files[idx]
        raise ValueError("Indice non valido.")
    except ValueError:
        raise ValueError("Inserimento non valido. Inserisci il numero corrispondente al video.")


def prompt_mode() -> str:
    """Prompt the user to choose between 'All' or 'Single' mode."""
    print("\nModalita':")
    print("1. Processa TUTTI i video")
    print("2. Processa un SINGOLO video")
    choice = input("Seleziona modalita' (1/2): ").strip()
    if choice == "1":
        return "all"
    elif choice == "2":
        return "single"
    else:
        raise ValueError("Scelta non valida.")


def main() -> int:
    """Application entry point."""
    configure_logging()

    print("\n--- Video to Text/Frames ---")
    print("1. Scarica video da YouTube")
    print("2. Gestione Frame (Tutti o Singolo)")
    print("3. Estrazione Testo (OCR) (Tutti o Singolo)")
    print("4. Costruzione JSON (Tutti o Singolo)")
    print("0. Esci")
    
    scelta = input("\nSeleziona un'opzione: ").strip()

    try:
        if scelta == "1":
            youtube_url = prompt_youtube_url()
            video_path = download_youtube_video(youtube_url, DownloadConfig())
            extract_frames(video_path, ExtractionConfig())
            
        elif scelta == "2":
            mode = prompt_mode()
            if mode == "all":
                process_all_videos()
            else:
                video_path = prompt_video_file()
                extract_frames(video_path, ExtractionConfig())
                
        elif scelta == "3":
            mode = prompt_mode()
            if mode == "all":
                process_all_ocr_extractions()
            else:
                video_name = prompt_video_name()
                extract_text_from_video_frames(video_name, OcrConfig())
                
        elif scelta == "4":
            mode = prompt_mode()
            if mode == "all":
                process_all_documents()
            else:
                video_name = prompt_video_name()
                build_json_document(video_name, ParseConfig())
                
        elif scelta == "0":
            return 0
        else:
            print("Opzione non valida.")
            return 1
    except Exception as error:
        logging.error(f"Errore: {error}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
