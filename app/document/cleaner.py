from __future__ import annotations

import copy
import json
import re
from pathlib import Path

import wordninja

from app.common.path_utils import build_named_output_dir
from app.config.models import ParseConfig


KNOWN_REPLACEMENTS = (
    ("â†’", " -> "),
    ("BigQueryML", "BigQuery ML"),
    ("Big Query ML", "BigQuery ML"),
    ("Big Query", "BigQuery"),
    ("UseML.", "Use ML."),
    ("ApplyBigQueryML", "Apply BigQuery ML"),
    ("MLMLEVALUATE", "ML.EVALUATE"),
    ("MLCOMPARE", "ML.COMPARE"),
    ("MLEVALUATE", "ML.EVALUATE"),
    ("MLPREDICT", "ML.PREDICT"),
    ("MLWEIGHTS", "ML.WEIGHTS"),
    ("MLFEATURE_INFO", "ML.FEATURE_INFO"),
    ("MLGENERATE_EMBEDDINGS", "ML.GENERATE_EMBEDDINGS"),
    ("MLGLOBALEXPLAIN", "ML.GLOBAL_EXPLAIN"),
    ("MLONLINEPREDICT", "ML.ONLINE_PREDICT"),
    ("MLFAIRNESS_METRICS", "ML.FAIRNESS_METRICS"),
    ("CREATEMODEL", "CREATE MODEL"),
    ("LOGISTIC_REGmodel", "LOGISTIC_REG model"),
    ("LINEAR_REGmodel", "LINEAR_REG model"),
    ("CLASS_WEIGHTSoption", "CLASS_WEIGHTS option"),
    ("featurepreprocessing", "feature preprocessing"),
    ("traininglabels", "training labels"),
    ("classweighting", "class weighting"),
    ("Whatshould", "What should"),
    ("Whichapproach", "Which approach"),
    ("Whichmethod", "Which method"),
    ("Whatshouldtheyexecute", "What should they execute"),
    ("Whatshould theydo", "What should they do"),
    ("shouldthey", "should they"),
    ("theydo", "they do"),
    ("Theynotice", "They notice"),
    ("Theywant", "They want"),
    ("Theyneed", "They need"),
    ("wantto", "want to"),
    ("wantsto", "wants to"),
    ("needfast", "need fast"),
    ("directlyin", "directly in"),
    ("withoutexporting", "without exporting"),
    ("throughafeature", "through a feature"),
    ("Thisisthe", "This is the"),
    ("Asof", "As of"),
    ("Thisenables", "This enables"),
    ("withoutbatchqueries", "without batch queries"),
    ("companywants", "company wants"),
    ("modelsummary", "model summary"),
)


def load_records(video_name: str, config: ParseConfig) -> list[dict[str, object]]:
    input_path = config.output_root / video_name / f"{video_name}.json"
    if not input_path.exists():
        raise FileNotFoundError(f"Documento JSON non trovato: {input_path}")
    return json.loads(input_path.read_text(encoding="utf-8"))


def collapse_spacing(text: str) -> str:
    text = text.replace("\r", "\n")
    text = re.sub(r"\n+", " ", text)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\b15\b", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def insert_common_prefix_spaces(text: str) -> str:
    prefixes = ("A", "An", "The", "They", "Their", "What", "Which", "When", "Why", "How")
    for prefix in prefixes:
        text = re.sub(rf"(^|[.!?]\s+)({prefix})(?=[a-z])", rf"\1{prefix} ", text)
    return text


def split_lowercase_token(token: str) -> str:
    core_match = re.match(r"^([a-z']+)([^a-z']*)$", token)
    if not core_match:
        return token
    core = core_match.group(1)
    suffix = core_match.group(2)
    if len(core) < 12:
        return token
    possessive = ""
    if core.endswith("'s"):
        core = core[:-2]
        possessive = "'s"
    pieces = wordninja.split(core)
    if len(pieces) <= 1:
        return token
    return " ".join(pieces) + possessive + suffix


def segment_glued_words(text: str) -> str:
    return " ".join(split_lowercase_token(token) for token in text.split())


def cleanup_text(text: str) -> str:
    cleaned = collapse_spacing(text)
    for source, target in KNOWN_REPLACEMENTS:
        cleaned = cleaned.replace(source, target)
    cleaned = insert_common_prefix_spaces(cleaned)
    cleaned = segment_glued_words(cleaned)
    cleaned = re.sub(r"\s+([,.;:?])", r"\1", cleaned)
    cleaned = re.sub(r"([,;:!?])(?=[^\s])", r"\1 ", cleaned)
    cleaned = re.sub(r"(?<![A-Z])\.(?=[A-Z][a-z])", ". ", cleaned)
    cleaned = re.sub(r"\s+\.", ".", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    for source, target in KNOWN_REPLACEMENTS:
        cleaned = cleaned.replace(source, target)
    return cleaned.strip()


def clean_record(record: dict[str, object]) -> dict[str, object]:
    cleaned_record = copy.deepcopy(record)
    cleaned_record["question"] = cleanup_text(str(record.get("question", "")))
    cleaned_options = {key: cleanup_text(str(value)) for key, value in dict(record.get("options", {})).items()}
    cleaned_record["options"] = cleaned_options
    cleaned_record["solution_text"] = cleanup_text(str(record.get("solution_text", "")))
    cleaned_record["explanation"] = cleanup_text(str(record.get("explanation", "")))
    cleaned_record["cleanup_applied"] = True
    cleaned_record["cleanup_notes"] = []

    solution_letter = str(record.get("solution", "")).upper()
    selected_option = cleaned_options.get(solution_letter, "").strip()
    solution_text = str(cleaned_record["solution_text"]).strip()
    if selected_option and (not solution_text or len(solution_text) < max(20, len(selected_option) // 2)):
        cleaned_record["solution_text"] = selected_option
        cleaned_record["cleanup_notes"].append("solution_text_aligned_with_option")

    return cleaned_record


def clean_records(records: list[dict[str, object]]) -> list[dict[str, object]]:
    return [clean_record(record) for record in records]


def save_clean_json(records: list[dict[str, object]], video_name: str, config: ParseConfig) -> Path:
    output_dir = build_named_output_dir(config.output_root, video_name)
    output_path = output_dir / f"{video_name}.cleaned.json"
    output_path.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")
    return output_path


def build_clean_json(video_name: str, config: ParseConfig) -> Path:
    cleaned_records = clean_records(load_records(video_name, config))
    return save_clean_json(cleaned_records, video_name, config)
