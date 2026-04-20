from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[2]
ENV_PATH = BASE_DIR / ".env"
load_dotenv(ENV_PATH)


def _get_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    base_dir: Path = BASE_DIR
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    openai_temperature: float = float(os.getenv("OPENAI_TEMPERATURE", "0"))
    openai_max_output_tokens: int = int(os.getenv("OPENAI_MAX_OUTPUT_TOKENS", "2000"))
    llm_input_suffix: str = os.getenv("LLM_INPUT_SUFFIX", ".json")
    llm_output_suffix: str = os.getenv("LLM_OUTPUT_SUFFIX", ".llm.json")
    llm_fail_on_missing_key: bool = _get_bool("LLM_FAIL_ON_MISSING_KEY", True)


settings = Settings()
