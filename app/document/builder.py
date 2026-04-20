from __future__ import annotations

import json
import re
from pathlib import Path

from app.common.path_utils import build_named_output_dir, sanitize_name
from app.config.models import ParseConfig
from app.ocr.retry import build_retry_candidates


QUESTION_NUMBER_PATTERN = re.compile(r"^\s*(\d+)\.")
OPTION_PATTERN = re.compile(r"([ABCD])\.")
ANSWER_PATTERN = re.compile(r"ans\w*:\s*([ABCD])\.(.*)", re.IGNORECASE | re.DOTALL)
EXPLANATION_PATTERN = re.compile(r"explan\w*:\s*(.*)", re.IGNORECASE | re.DOTALL)
TRAILING_SCORE_PATTERN = re.compile(r"\b15\b\s*$")


def list_text_files(video_name: str, config: ParseConfig) -> list[Path]:
    text_dir = config.text_root / video_name
    if not text_dir.exists():
        raise FileNotFoundError(f"Cartella testo non trovata: {text_dir}")
    text_files = sorted(text_dir.glob("*.txt"))
    if not text_files:
        raise FileNotFoundError(f"Nessun file di testo trovato in: {text_dir}")
    if len(text_files) % 2 != 0:
        raise ValueError("Il numero di file OCR non e' pari: impossibile creare coppie.")
    return text_files


def normalize_whitespace(value: str) -> str:
    value = value.replace("\r", "\n")
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def count_filled_options(options: dict[str, str]) -> int:
    return sum(1 for option_text in options.values() if option_text.strip())


def parse_question_text(raw_text: str, source_name: str) -> dict[str, object]:
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    joined_text = normalize_whitespace("\n".join(lines))
    joined_text = TRAILING_SCORE_PATTERN.sub("", joined_text).strip()
    question_number_match = QUESTION_NUMBER_PATTERN.search(joined_text)
    if not question_number_match:
        raise ValueError(f"Numero domanda non trovato in {source_name}")
    question_number = int(question_number_match.group(1))

    option_matches = list(OPTION_PATTERN.finditer(joined_text))
    if len(option_matches) < 2:
        raise ValueError(f"Opzioni insufficienti in {source_name}")

    question_text = joined_text[question_number_match.end() : option_matches[0].start()].strip()
    options: dict[str, str] = {letter: "" for letter in ("A", "B", "C", "D")}
    for index, match in enumerate(option_matches):
        option_letter = match.group(1)
        option_start = match.end(1) + 1
        option_end = option_matches[index + 1].start() if index + 1 < len(option_matches) else len(joined_text)
        options[option_letter] = joined_text[option_start:option_end].strip()

    return {
        "question_number": question_number,
        "question": question_text,
        "options": options,
        "source_question_file": source_name,
    }


def parse_question_file(question_file: Path) -> dict[str, object]:
    return parse_question_text(question_file.read_text(encoding="utf-8"), question_file.name)


def parse_answer_text(raw_text: str, source_name: str) -> dict[str, str]:
    raw_text = normalize_whitespace(raw_text)
    answer_match = ANSWER_PATTERN.search(raw_text)
    explanation_match = EXPLANATION_PATTERN.search(raw_text)
    if not answer_match:
        raise ValueError(f"Soluzione non trovata in {source_name}")
    if not explanation_match:
        raise ValueError(f"Spiegazione non trovata in {source_name}")

    solution_letter = answer_match.group(1).upper()
    solution_text = answer_match.group(2)
    solution_text = solution_text[: explanation_match.start() - answer_match.start(2)]

    return {
        "solution": solution_letter,
        "solution_text": normalize_whitespace(solution_text),
        "explanation": normalize_whitespace(explanation_match.group(1)),
        "source_answer_file": source_name,
    }


def parse_answer_file(answer_file: Path) -> dict[str, str]:
    return parse_answer_text(answer_file.read_text(encoding="utf-8"), answer_file.name)


def validate_record(record: dict[str, object]) -> list[str]:
    warnings: list[str] = []
    options = record.get("options", {})
    missing_options = [letter for letter in ("A", "B", "C", "D") if not str(options.get(letter, "")).strip()]
    if missing_options:
        warnings.append(f"missing_options:{','.join(missing_options)}")
    if not str(record.get("question", "")).strip():
        warnings.append("missing_question_text")
    if not str(record.get("solution", "")).strip():
        warnings.append("missing_solution_letter")
    if not str(record.get("solution_text", "")).strip():
        warnings.append("missing_solution_text")
    if not str(record.get("explanation", "")).strip():
        warnings.append("missing_explanation")
    return warnings


def score_question_record(record: dict[str, object]) -> tuple[int, int]:
    return (count_filled_options(record["options"]), len(str(record["question"])))


def score_answer_record(record: dict[str, str]) -> tuple[int, int]:
    return (1 if record.get("solution") else 0, len(record.get("solution_text", "")) + len(record.get("explanation", "")))


def build_frame_path(video_name: str, text_file: Path, config: ParseConfig) -> Path:
    return config.frames_root / video_name / f"{text_file.stem}.jpg"


def retry_question_record(video_name: str, question_file: Path, config: ParseConfig) -> tuple[dict[str, object] | None, dict[str, object] | None]:
    best_record = None
    best_details = None
    for candidate in build_retry_candidates(build_frame_path(video_name, question_file, config), config.ocr_min_confidence):
        if not candidate["text"]:
            continue
        try:
            record = parse_question_text(str(candidate["text"]), f"{question_file.name}#{candidate['variant']}")
        except ValueError:
            continue
        if best_record is None or score_question_record(record) > score_question_record(best_record):
            best_record = record
            best_details = {"variant": candidate["variant"], "filled_options": count_filled_options(record["options"])}
    return best_record, best_details


def retry_answer_record(video_name: str, answer_file: Path, config: ParseConfig) -> tuple[dict[str, str] | None, dict[str, object] | None]:
    best_record = None
    best_details = None
    for candidate in build_retry_candidates(build_frame_path(video_name, answer_file, config), config.ocr_min_confidence):
        if not candidate["text"]:
            continue
        try:
            record = parse_answer_text(str(candidate["text"]), f"{answer_file.name}#{candidate['variant']}")
        except ValueError:
            continue
        if best_record is None or score_answer_record(record) > score_answer_record(best_record):
            best_record = record
            best_details = {"variant": candidate["variant"], "text_length": len(record["solution_text"]) + len(record["explanation"])}
    return best_record, best_details


def parse_pair_with_retry(video_name: str, question_file: Path, answer_file: Path, config: ParseConfig) -> dict[str, object]:
    retry_details: dict[str, object] = {}
    question_record = parse_question_file(question_file)
    answer_record = parse_answer_file(answer_file)
    record: dict[str, object] = {**question_record, **answer_record}
    warnings = validate_record(record)

    if config.retry_ocr and warnings:
        if any(warning.startswith("missing_options") or warning == "missing_question_text" for warning in warnings):
            improved_question, details = retry_question_record(video_name, question_file, config)
            if improved_question and score_question_record(improved_question) > score_question_record(question_record):
                question_record = improved_question
                retry_details["question_retry"] = details

        if any(warning in {"missing_solution_letter", "missing_solution_text", "missing_explanation"} for warning in warnings):
            improved_answer, details = retry_answer_record(video_name, answer_file, config)
            if improved_answer and score_answer_record(improved_answer) > score_answer_record(answer_record):
                answer_record = improved_answer
                retry_details["answer_retry"] = details

        record = {**question_record, **answer_record}
        warnings = validate_record(record)

    record["validation_warnings"] = warnings
    record["retry_applied"] = bool(retry_details)
    record["retry_details"] = retry_details
    return record


def build_records(video_name: str, config: ParseConfig) -> list[dict[str, object]]:
    text_files = list_text_files(video_name, config)
    records: list[dict[str, object]] = []
    for index in range(0, len(text_files), 2):
        records.append(parse_pair_with_retry(video_name, text_files[index], text_files[index + 1], config))
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
