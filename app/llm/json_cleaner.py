from __future__ import annotations

import json

from app.common.path_utils import build_named_output_dir
from app.config.models import ParseConfig
from app.config.settings import settings


SYSTEM_PROMPT = """You clean OCR-derived multiple-choice exam records.
Return only valid JSON.
Do not invent facts.
Keep the same schema and keys.
Improve readability of question, options, solution_text, and explanation.
Preserve uncertainty: if text is ambiguous, keep the closest faithful wording and add a short note in llm_notes.
Do not change the correct answer letter unless the provided data clearly proves it is wrong.
"""


def load_records(video_name: str, config: ParseConfig) -> list[dict[str, object]]:
    input_path = config.output_root / video_name / f"{video_name}{settings.llm_input_suffix}"
    if not input_path.exists():
        raise FileNotFoundError(f"Documento JSON per LLM non trovato: {input_path}")
    return json.loads(input_path.read_text(encoding="utf-8"))


def build_prompt(record: dict[str, object]) -> str:
    payload = json.dumps(record, indent=2, ensure_ascii=False)
    return (
        "Clean this OCR-derived exam record and return JSON only.\n"
        "Requirements:\n"
        "- preserve the same top-level keys already present\n"
        "- improve readability without inventing missing content\n"
        "- keep validation_warnings, retry_applied, retry_details if present\n"
        "- add llm_cleaned=true\n"
        "- add llm_notes as an array of short strings\n"
        "- keep options as an object with A/B/C/D keys\n"
        "- do not add markdown fences\n\n"
        f"Record:\n{payload}"
    )


def clean_record_with_llm(client, record: dict[str, object]) -> dict[str, object]:
    response = client.responses.create(
        model=settings.openai_model,
        temperature=settings.openai_temperature,
        max_output_tokens=settings.openai_max_output_tokens,
        input=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_prompt(record)},
        ],
    )
    cleaned = json.loads(response.output_text)
    return cleaned


def clean_json_with_llm(video_name: str, config: ParseConfig) -> Path:
    if not settings.openai_api_key:
        if settings.llm_fail_on_missing_key:
            raise ValueError("OPENAI_API_KEY mancante. Inseriscila nel file .env.")
        raise ValueError("OPENAI_API_KEY mancante.")

    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key)
    records = load_records(video_name, config)
    cleaned_records = [clean_record_with_llm(client, record) for record in records]

    output_dir = build_named_output_dir(config.output_root, video_name)
    output_path = output_dir / f"{video_name}{settings.llm_output_suffix}"
    output_path.write_text(json.dumps(cleaned_records, indent=2, ensure_ascii=False), encoding="utf-8")
    return output_path
