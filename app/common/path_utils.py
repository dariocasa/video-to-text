from __future__ import annotations

import re
from pathlib import Path


def ensure_directory(path: Path) -> Path:
    """Create a directory if it does not exist."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def sanitize_name(name: str) -> str:
    """Build a filesystem-safe name."""
    sanitized = re.sub(r"[^\w\s-]", "", name, flags=re.ASCII)
    sanitized = re.sub(r"[\s-]+", "_", sanitized.strip(), flags=re.ASCII)
    return sanitized or "video"


def build_video_output_dir(output_root: Path, video_path: Path) -> Path:
    """Return the output directory dedicated to a single video."""
    return ensure_directory(output_root / sanitize_name(video_path.stem))


def build_named_output_dir(output_root: Path, name: str) -> Path:
    """Return an output directory using a plain name."""
    return ensure_directory(output_root / sanitize_name(name))
