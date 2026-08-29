import json
import logging
import re
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError

from pinterest_automation.api.openrouter import chat, image_data_url

log = logging.getLogger(__name__)
PROMPT_FILE = Path(__file__).resolve().parent.parent / "prompts" / "pinterest_seo.txt"


class MetadataValidationError(ValueError):
    pass


class PinMetadata(BaseModel):
    title: str = Field(min_length=10, max_length=100)
    description: str = Field(min_length=30, max_length=500)
    alt_text: str = Field(min_length=5)
    primary_keyword: str = Field(min_length=2)
    secondary_keywords: list[str] = Field(min_length=3, max_length=20)
    tags: list[str] = Field(min_length=5, max_length=25)
    board: str = Field(min_length=2)
    category: str = Field(min_length=2)


def load_prompt() -> str:
    return PROMPT_FILE.read_text(encoding="utf-8")


# Max lengths for free-text fields; mirrors PinMetadata. Lists stay strict
# (the model rarely over-produces them, and a bad list should be retried).
_MAX_STR_LEN = {"title": 100, "description": 500}


def _clamp_metadata(data: dict) -> dict:
    """Truncate over-long text so validation never fails on model verbosity."""
    for name, mx in _MAX_STR_LEN.items():
        val = data.get(name)
        if isinstance(val, str) and len(val) > mx:
            cut = val[:mx].rsplit(" ", 1)[0]
            data[name] = cut or val[:mx]
    return data


def parse_metadata(raw: str) -> PinMetadata:
    text = re.sub(r"^```(?:json)?\s*|```$", "", raw.strip(), flags=re.M).strip()
    match = re.search(r"\{.*\}", text, flags=re.S)
    if not match:
        raise MetadataValidationError("no JSON object found in model output")
    try:
        data = json.loads(match.group())
    except json.JSONDecodeError as e:
        raise MetadataValidationError(f"invalid JSON: {e}") from e
    data = _clamp_metadata(data)
    try:
        return PinMetadata.model_validate(data)
    except ValidationError as e:
        raise MetadataValidationError(str(e)) from e


def _vision_message(prompt: str, image_url: str) -> dict:
    return {"role": "user", "content": [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": image_url}},
    ]}


def generate_metadata(image_path: Path) -> PinMetadata:
    """Vision call -> strict JSON -> validate. One corrective retry on invalid output."""
    prompt = load_prompt()
    image_url = image_data_url(image_path)
    raw = chat([_vision_message(prompt, image_url)])
    try:
        return parse_metadata(raw)
    except MetadataValidationError as first_error:
        log.warning("metadata rejected (%s); retrying once with feedback",
                    str(first_error)[:120])
        fixup = (
            f"{prompt}\n\nYour previous answer was rejected:\n{str(first_error)[:1000]}\n"
            "Fix ALL issues and return strict JSON only."
        )
        return parse_metadata(chat([_vision_message(fixup, image_url)]))
