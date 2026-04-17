from __future__ import annotations

import json
import re
from pathlib import Path

from app.models import ParseConfig
from app.ocr_retry import build_retry_candidates
from app.path_utils import build_named_output_dir


QUESTION_NUMBER_PATTERN = re.compile(r"^\s*(\d+)\.")
OPTION_PATTERN = re.compile(r"([ABCD])\.")
ANSWER_PATTERN = re.compile(r"ans\w*:\s*([ABCD])\.(.*)", re.IGNORECASE | re.DOTALL)
EXPLANATION_PATTERN = re.compile(r"explan\w*:\s*(.*)", re.IGNORECASE | re.DOTALL)
TRAILING_SCORE_PATTERN = re.compile(r"\b15\b\s*$")


def list_text_files(video_name: str, config: ParseConfig) -> list[Path]:
    """Return OCR text files for a video in timestamp order."""
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
    """Normalize spacing while keeping the text readable."""
    value = value.replace("\r", "\n")
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def count_filled_options(options: dict[str, str]) -> int:
    """Count how many answer options contain text."""
    return sum(1 for option_text in options.values() if option_text.strip())


def parse_question_text(raw_text: str, source_name: str) -> dict[str, object]:
    """Extract question number, text, and options from OCR text."""
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

    question_start = question_number_match.end()
    question_end = option_matches[0].start()
    question_text = joined_text[question_start:question_end].strip()

    options: dict[str, str] = {letter: "" for letter in ("A", "B", "C", "D")}
    for index, match in enumerate(option_matches):
        option_letter = match.group(1)
        option_start = match.end(1) + 1
        option_end = option_matches[index + 1].start() if index + 1 < len(option_matches) else len(joined_text)
        option_text = joined_text[option_start:option_end].strip()
        options[option_letter] = option_text

    return {
        "question_number": question_number,
        "question": question_text,
        "options": options,
        "source_question_file": source_name,
    }


def parse_question_file(question_file: Path) -> dict[str, object]:
    """Extract question data from a question OCR file."""
    return parse_question_text(
        question_file.read_text(encoding="utf-8"),
        question_file.name,
    )


def parse_answer_text(raw_text: str, source_name: str) -> dict[str, str]:
    """Extract solution and explanation from OCR text."""
    raw_text = normalize_whitespace(raw_text)

    answer_match = ANSWER_PATTERN.search(raw_text)
    explanation_match = EXPLANATION_PATTERN.search(raw_text)
    if not answer_match:
        raise ValueError(f"Soluzione non trovata in {source_name}")
    if not explanation_match:
        raise ValueError(f"Spiegazione non trovata in {source_name}")

    solution_letter = answer_match.group(1).upper()
    solution_text = answer_match.group(2)
    if explanation_match:
        solution_text = solution_text[: explanation_match.start() - answer_match.start(2)]
    solution_text = normalize_whitespace(solution_text)
    explanation_text = normalize_whitespace(explanation_match.group(1))

    return {
        "solution": solution_letter,
        "solution_text": solution_text,
        "explanation": explanation_text,
        "source_answer_file": source_name,
    }


def parse_answer_file(answer_file: Path) -> dict[str, str]:
    """Extract answer data from an answer OCR file."""
    return parse_answer_text(
        answer_file.read_text(encoding="utf-8"),
        answer_file.name,
    )


def validate_record(record: dict[str, object]) -> list[str]:
    """Return validation warnings for a structured record."""
    warnings: list[str] = []
    options = record.get("options", {})
    missing_options = [
        option_letter
        for option_letter in ("A", "B", "C", "D")
        if not str(options.get(option_letter, "")).strip()
    ]
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
    """Score a parsed question record by completeness."""
    return (
        count_filled_options(record["options"]),
        len(str(record["question"])),
    )


def score_answer_record(record: dict[str, str]) -> tuple[int, int]:
    """Score a parsed answer record by completeness."""
    return (
        1 if record.get("solution") else 0,
        len(record.get("solution_text", "")) + len(record.get("explanation", "")),
    )


def build_frame_path(video_name: str, text_file: Path, config: ParseConfig) -> Path:
    """Map a text file back to its source frame image."""
    return config.frames_root / video_name / f"{text_file.stem}.jpg"


def retry_question_record(video_name: str, question_file: Path, config: ParseConfig) -> tuple[dict[str, object] | None, dict[str, object] | None]:
    """Retry OCR for a question frame and return the best parsed record."""
    best_record: dict[str, object] | None = None
    best_details: dict[str, object] | None = None

    for candidate in build_retry_candidates(
        build_frame_path(video_name, question_file, config),
        config.ocr_min_confidence,
    ):
        if not candidate["text"]:
            continue
        try:
            record = parse_question_text(
                str(candidate["text"]),
                f"{question_file.name}#{candidate['variant']}",
            )
        except ValueError:
            continue

        if best_record is None or score_question_record(record) > score_question_record(best_record):
            best_record = record
            best_details = {
                "variant": candidate["variant"],
                "filled_options": count_filled_options(record["options"]),
            }

    return best_record, best_details


def retry_answer_record(video_name: str, answer_file: Path, config: ParseConfig) -> tuple[dict[str, str] | None, dict[str, object] | None]:
    """Retry OCR for an answer frame and return the best parsed record."""
    best_record: dict[str, str] | None = None
    best_details: dict[str, object] | None = None

    for candidate in build_retry_candidates(
        build_frame_path(video_name, answer_file, config),
        config.ocr_min_confidence,
    ):
        if not candidate["text"]:
            continue
        try:
            record = parse_answer_text(
                str(candidate["text"]),
                f"{answer_file.name}#{candidate['variant']}",
            )
        except ValueError:
            continue

        if best_record is None or score_answer_record(record) > score_answer_record(best_record):
            best_record = record
            best_details = {
                "variant": candidate["variant"],
                "text_length": len(record["solution_text"]) + len(record["explanation"]),
            }

    return best_record, best_details


def parse_pair_with_retry(
    video_name: str,
    question_file: Path,
    answer_file: Path,
    config: ParseConfig,
) -> dict[str, object]:
    """Parse one question/answer pair and retry OCR when validation fails."""
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
    """Build structured question records from paired OCR files."""
    text_files = list_text_files(video_name, config)
    records: list[dict[str, object]] = []

    for index in range(0, len(text_files), 2):
        question_file = text_files[index]
        answer_file = text_files[index + 1]

        record = parse_pair_with_retry(
            video_name,
            question_file,
            answer_file,
            config,
        )
        records.append(record)

    return records


def save_json(records: list[dict[str, object]], output_dir: Path, video_name: str) -> Path:
    """Save structured OCR data as JSON."""
    output_path = output_dir / f"{video_name}.json"
    output_path.write_text(
        json.dumps(records, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return output_path


def render_markdown(records: list[dict[str, object]], video_name: str) -> str:
    """Render structured OCR records as a readable Markdown document."""
    lines = [f"# {video_name}", ""]

    for record in records:
        lines.append(f"## Domanda {record['question_number']}")
        lines.append("")
        lines.append(f"**Domanda**  ")
        lines.append(str(record["question"]))
        lines.append("")
        lines.append("**Opzioni**")
        lines.append("")

        options = record["options"]
        for option_letter in ("A", "B", "C", "D"):
            option_text = options.get(option_letter, "")
            lines.append(f"- {option_letter}. {option_text}")

        lines.append("")
        lines.append(f"**Soluzione**  ")
        lines.append(f"{record['solution']}. {record['solution_text']}")
        lines.append("")
        lines.append("**Spiegazione**  ")
        lines.append(str(record["explanation"]))
        lines.append("")

        warnings = record.get("validation_warnings", [])
        if warnings:
            lines.append("**Warning**  ")
            lines.append(", ".join(str(warning) for warning in warnings))
            lines.append("")

    return "\n".join(lines).strip() + "\n"


def save_markdown(records: list[dict[str, object]], output_dir: Path, video_name: str) -> Path:
    """Save the readable Markdown document."""
    output_path = output_dir / f"{video_name}.md"
    output_path.write_text(render_markdown(records, video_name), encoding="utf-8")
    return output_path


def build_documents(video_name: str, config: ParseConfig) -> tuple[Path, Path]:
    """Create both JSON and Markdown outputs for a video OCR folder."""
    records = build_records(video_name, config)
    output_dir = build_named_output_dir(config.output_root, video_name)
    json_path = save_json(records, output_dir, video_name)
    markdown_path = save_markdown(records, output_dir, video_name)
    return json_path, markdown_path
