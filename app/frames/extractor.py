from __future__ import annotations

import logging
from pathlib import Path

import cv2

from app.common.path_utils import build_video_output_dir, sanitize_name
from app.config.models import (
    SUPPORTED_VIDEO_EXTENSIONS,
    VIDEO_DIR,
    ExtractionConfig,
)


def open_video_capture(video_path: Path) -> cv2.VideoCapture:
    """Open the video file and validate that it can be read."""
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        capture.release()
        raise RuntimeError(f"Impossibile aprire il file video: {video_path}")
    return capture


def get_video_metadata(capture: cv2.VideoCapture) -> tuple[float, int]:
    """Extract FPS and total frame count from the video metadata."""
    fps = float(capture.get(cv2.CAP_PROP_FPS))
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    if fps <= 0:
        raise RuntimeError("FPS non validi letti dai metadati del video.")
    if frame_count <= 0:
        raise RuntimeError("Numero di frame non valido letto dai metadati del video.")
    return fps, frame_count


def format_timestamp(seconds: float) -> str:
    """Format a timestamp as HH-MM-SS-ms for human-readable filenames."""
    total_milliseconds = int(round(seconds * 1000))
    hours, remainder = divmod(total_milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    whole_seconds, milliseconds = divmod(remainder, 1000)
    if milliseconds:
        return f"{hours:02d}-{minutes:02d}-{whole_seconds:02d}-{milliseconds:03d}"
    return f"{hours:02d}-{minutes:02d}-{whole_seconds:02d}"


def build_frame_filename(index: int) -> str:
    """Build a 00n_1_question or 00n_2_answer output filename."""
    n = (index // 2) + 1
    sub_index = 1 if index % 2 == 0 else 2
    prefix = "question" if index % 2 == 0 else "answer"
    return f"{n:03d}_{sub_index}_{prefix}.jpg"


def compute_frame_signature(frame) -> cv2.typing.MatLike:
    """Build a grayscale signature for duplicate and scene-change checks."""
    grayscale = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return cv2.resize(grayscale, (64, 64), interpolation=cv2.INTER_AREA)


def mean_frame_difference(current_signature, previous_signature) -> float:
    """Compute the mean absolute difference between two frame signatures."""
    difference = cv2.absdiff(current_signature, previous_signature)
    return float(difference.mean())


def should_keep_frame(current_signature, last_saved_signature, config: ExtractionConfig) -> tuple[bool, str]:
    """Decide whether the current frame should be saved."""
    if last_saved_signature is None:
        return True, "first frame"

    difference = mean_frame_difference(current_signature, last_saved_signature)
    if difference <= config.duplicate_threshold:
        return False, "duplicate"
    if config.scene_threshold is not None and difference < config.scene_threshold:
        return False, "scene unchanged"
    return True, "kept"


def save_frame(frame, output_dir: Path, index: int, image_quality: int) -> Path:
    """Persist a frame to disk using a sequence-based filename."""
    output_path = output_dir / build_frame_filename(index)
    success = cv2.imwrite(str(output_path), frame, [cv2.IMWRITE_JPEG_QUALITY, image_quality])
    if not success:
        raise RuntimeError(f"Impossibile salvare il frame: {output_path}")
    return output_path


def extract_frames(video_path: Path, config: ExtractionConfig) -> int:
    """Extract frames from a video into a dedicated output directory."""
    output_dir = build_video_output_dir(config.output_root, video_path)
    capture = open_video_capture(video_path)
    saved_count = 0
    processed_targets = 0
    last_saved_signature = None

    logging.info(f"Estrazione frame da: {video_path}")
    logging.info(f"Output frame: {output_dir}")

    try:
        fps, frame_count = get_video_metadata(capture)
        duration_seconds = frame_count / fps
        logging.info("Metadati video: fps=%.3f, total_frames=%d, duration=%.2fs", fps, frame_count, duration_seconds)

        next_timestamp = 0.0
        while next_timestamp <= duration_seconds + 1e-9:
            target_frame_index = min(int(round(next_timestamp * fps)), max(frame_count - 1, 0))
            capture.set(cv2.CAP_PROP_POS_FRAMES, target_frame_index)

            success, frame = capture.read()
            if not success or frame is None:
                raise RuntimeError(
                    f"Impossibile leggere il frame al timestamp {next_timestamp:.3f}s "
                    f"(indice {target_frame_index})."
                )

            frame_signature = compute_frame_signature(frame)
            keep_frame, reason = should_keep_frame(frame_signature, last_saved_signature, config)

            processed_targets += 1
            if keep_frame:
                save_frame(frame, output_dir, saved_count, config.image_quality)
                logging.info("Estratti %d frame: %s", saved_count + 1, build_frame_filename(saved_count))
                saved_count += 1
                last_saved_signature = frame_signature
            # else:
            #     logging.info("Saltato timestamp %s (%s).", format_timestamp(next_timestamp), reason)

            next_timestamp += config.seconds_interval

        logging.info("Completato. Campioni processati: %d, frame salvati: %d.", processed_targets, saved_count)
        return saved_count
    finally:
        capture.release()


def process_all_videos(config: ExtractionConfig | None = None) -> None:
    """Process all video files in the video directory into frames."""
    config = config or ExtractionConfig()
    
    if not VIDEO_DIR.exists():
        logging.warning(f"La cartella video '{VIDEO_DIR}' non esiste.")
        return

    # Filter files by supported extensions
    video_files = [
        f for f in VIDEO_DIR.iterdir() 
        if f.is_file() and f.suffix.lower() in SUPPORTED_VIDEO_EXTENSIONS
    ]

    if not video_files:
        logging.info("Nessun video trovato da processare.")
        return

    logging.info(f"Trovati {len(video_files)} video da processare.")

    for video_path in video_files:
        output_dir = config.output_root / sanitize_name(video_path.stem)
        
        # Check if the video has already been processed (folder exists and is not empty)
        if output_dir.exists() and any(output_dir.iterdir()):
            logging.info(f"Salto '{video_path.name}': output gia' presente in {output_dir}")
            continue

        try:
            extract_frames(video_path, config)
        except Exception as e:
            logging.error(f"Errore durante l'elaborazione di '{video_path.name}': {e}")
