import base64
import logging
from pathlib import Path

import httpx

from pinterest_automation.config.settings import settings
from pinterest_automation.utils.http_retry import HTTPTooManyRetries, request_with_retry
from pinterest_automation.utils.media_types import MIME

log = logging.getLogger(__name__)
URL = "https://openrouter.ai/api/v1/chat/completions"


class OpenRouterError(RuntimeError):
    pass


def _post(payload: dict, headers: dict) -> httpx.Response:
    """Seam for tests; routes through shared retry logic."""
    return request_with_retry("POST", URL, headers=headers, json=payload)


def chat(messages: list[dict], **overrides) -> str:
    payload = {"model": settings.openrouter_model, "messages": messages}
    payload.update(overrides)
    headers = {"Authorization": f"Bearer {settings.openrouter_api_key}"}
    try:
        r = _post(payload, headers)
    except HTTPTooManyRetries as e:
        raise OpenRouterError(str(e)) from e
    except httpx.HTTPStatusError as e:
        raise OpenRouterError(f"HTTP {e.response.status_code}: {e.response.text[:300]}") from e
    try:
        return r.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        raise OpenRouterError(f"unexpected response shape: {r.text[:300]}") from e


def image_data_url(path: Path) -> str:
    mime = MIME[path.suffix.lower()]
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"
