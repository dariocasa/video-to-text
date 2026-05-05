from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from app.common.path_utils import build_named_output_dir, natural_sort_key, sanitize_name
from app.config.models import ParseConfig


QUESTION_NUMBER_PATTERN = re.compile(r"^\s*(\d+)\.")
OPTION_PATTERN = re.compile(r"([ABCD])\.")
ANSWER_PATTERN = re.compile(r"ans\w*:\s*([ABCD])\.(.*)", re.IGNORECASE | re.DOTALL)
EXPLANATION_PATTERN = re.compile(r"explan\w*:\s*(.*)", re.IGNORECASE | re.DOTALL)
TRAILING_SCORE_PATTERN = re.compile(r"\b15\b\s*$")


def list_text_files(video_name: str, config: ParseConfig) -> list[Path]:
    text_dir = config.text_root / video_name
    if not text_dir.exists():
        raise FileNotFoundError(f"Cartella testo non trovata: {text_dir}")
    text_files = sorted(text_dir.glob("*.txt"), key=natural_sort_key)
    if not text_files:
        raise FileNotFoundError(f"Nessun file di testo trovato in: {text_dir}")
    return text_files


def group_files_by_question(text_files: list[Path]) -> dict[str, dict[str, Path]]:
    groups = {}
    for f in text_files:
        parts = f.stem.split("_")
        if len(parts) < 4:
            continue
        # "001_1_1_question" → q_id="001" (numeric prefix, new format)
        # "frame_00-00-00_1_question" → q_id="frame_00-00-00" (timestamp prefix, old format)
        q_id = parts[0] if parts[0].isdigit() else f"{parts[0]}_{parts[1]}"
        label = parts[-1]
        if q_id not in groups:
            groups[q_id] = {}
        groups[q_id][label] = f
    return groups


def parse_question_label(file_path: Path) -> tuple[int, str]:
    text = file_path.read_text(encoding="utf-8").strip()
    match = QUESTION_NUMBER_PATTERN.search(text)
    if not match:
        # Fallback to file name if no number found
        try:
            q_num = int(file_path.stem.split("_")[0])
        except:
            q_num = 0
        return q_num, text
    
    q_num = int(match.group(1))
    q_text = text[match.end():].strip()
    return q_num, q_text


def parse_option_label(file_path: Path) -> dict[str, str]:
    lines = file_path.read_text(encoding="utf-8").splitlines()
    options = {"A": "", "B": "", "C": "", "D": ""}
    for line in lines:
        line = line.strip()
        match = OPTION_PATTERN.match(line)
        if match:
            letter = match.group(1).upper()
            text = line[match.end():].strip()
            options[letter] = text
    return options


def parse_answer_label(file_path: Path) -> tuple[str, str]:
    text = file_path.read_text(encoding="utf-8").strip()
    # Expecting "Answer: [A]. [Text]"
    match = ANSWER_PATTERN.search(text)
    if match:
        return match.group(1).upper(), match.group(2).strip()
    return "", text


def parse_explanation_label(file_path: Path) -> str:
    text = file_path.read_text(encoding="utf-8").strip()
    # Strip "Explanation: " prefix if present
    match = EXPLANATION_PATTERN.search(text)
    if match:
        return match.group(1).strip()
    return text


def _frame_filename(text_path: Path) -> str:
    """Reconstruct the original frame filename from a text file path.

    New format: "001_1_1_question.txt" → "001_1_question.jpg"
    Old format: "frame_00-00-00_1_question.txt" → "frame_00-00-00.jpg"
    """
    parts = text_path.stem.split("_")
    if parts[0].isdigit():
        return f"{parts[0]}_{parts[1]}_{parts[-1]}.jpg"
    return f"{parts[0]}_{parts[1]}.jpg"


def build_records(video_name: str, config: ParseConfig) -> list[dict[str, object]]:
    text_files = list_text_files(video_name, config)
    groups = group_files_by_question(text_files)
    records: list[dict[str, object]] = []

    q_ids = sorted(groups.keys())
    # Holds a question slide waiting to be paired with its answer slide (old timestamp format)
    pending: dict | None = None

    for q_id in q_ids:
        files = groups[q_id]
        if "question" not in files:
            continue

        q_num, q_text = parse_question_label(files["question"])

        if "answer" in files:
            # New numeric format: answer label is a dedicated file
            if pending:
                records.append(pending)
                pending = None
            options = parse_option_label(files["option"]) if "option" in files else {}
            sol_letter, sol_text = parse_answer_label(files["answer"])
            explanation = parse_explanation_label(files["explanation"]) if "explanation" in files else ""
            records.append({
                "question_number": q_num,
                "question": q_text,
                "options": options,
                "source_question_file": _frame_filename(files["question"]),
                "solution": sol_letter,
                "solution_text": sol_text,
                "explanation": explanation,
                "source_answer_file": _frame_filename(files["answer"])
            })
        elif q_num > 0:
            # Old timestamp format: this is a question slide
            if pending:
                records.append(pending)
            options = parse_option_label(files["option"]) if "option" in files else {}
            pending = {
                "question_number": q_num,
                "question": q_text,
                "options": options,
                "source_question_file": _frame_filename(files["question"]),
                "solution": "",
                "solution_text": "",
                "explanation": "",
                "source_answer_file": ""
            }
        else:
            # Old timestamp format: answer slide (q_num==0, "question" file contains "Answer: X.")
            sol_letter, sol_text = parse_answer_label(files["question"])
            explanation = parse_explanation_label(files["option"]) if "option" in files else ""
            if sol_letter and pending:
                pending["solution"] = sol_letter
                pending["solution_text"] = sol_text
                pending["explanation"] = explanation
                pending["source_answer_file"] = _frame_filename(files["question"])
                records.append(pending)
                pending = None

    if pending:
        records.append(pending)

    return records


def save_json(records: list[dict[str, object]], output_dir: Path, video_name: str) -> Path:
    output_path = output_dir / f"{video_name}.json"
    output_path.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")
    return output_path


def build_json_document(video_name: str, config: ParseConfig) -> Path:
    records = build_records(video_name, config)
    output_dir = build_named_output_dir(config.output_root, video_name)
    return save_json(records, output_dir, video_name)


def process_all_documents(config: ParseConfig | None = None) -> None:
    """Build JSON documents for all text folders in the text directory."""
    config = config or ParseConfig()

    if not config.text_root.exists():
        logging.getLogger(__name__).warning(f"La cartella testo '{config.text_root}' non esiste.")
        return

    # Filter for directories in text root
    video_folders = [
        d for d in config.text_root.iterdir()
        if d.is_dir()
    ]

    if not video_folders:
        logging.getLogger(__name__).info("Nessuna cartella di testo trovata.")
        return

    logging.getLogger(__name__).info(f"Trovate {len(video_folders)} cartelle di testo da processare.")

    for folder in video_folders:
        video_name = folder.name
        output_path = config.output_root / video_name / f"{video_name}.json"

        # Skip if JSON already exists
        if output_path.exists():
            logging.getLogger(__name__).info(f"Salto '{video_name}': JSON gia' presente in {output_path}")
            continue

        try:
            build_json_document(video_name, config)
            logging.getLogger(__name__).info(f"Documento JSON creato per '{video_name}'")
        except Exception as e:
            logging.getLogger(__name__).error(f"Errore durante la creazione del JSON per '{video_name}': {e}")
