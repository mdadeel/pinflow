"""LLM client with multi-provider failover.

When `LLM_PROVIDERS` (JSON) is set, requests are spread across all providers
using round-robin selection. A provider that errors (credits exhausted, rate
limited, network failure, bad response) is cooled down and skipped until it
recovers, so a single dead key never stalls analysis. With a single provider
(configured via the legacy `LLM_*` / `OPENROUTER_*` settings) behavior is
unchanged.
"""

import json
import threading
import time
from typing import Any, Optional

import httpx

from pinterest_automation.config.settings import settings
from pinterest_automation.utils.http_retry import HTTPTooManyRetries

log = __import__("logging").getLogger("pinterest_automation.llm")

URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MAX_TOKENS = 1024

_RETRYABLE = (HTTPTooManyRetries, httpx.HTTPStatusError, httpx.TransportError, httpx.TimeoutException)


class LLMError(RuntimeError):
    pass


# --- provider health (module-global, guarded by a lock) -------------------

_health: dict[str, float] = {}  # name -> cooldown until (monotonic seconds)
_idx = 0
_hlock = threading.Lock()


def _cooldown_for(status: int) -> float:
    # 402 (credits) and 429 (rate limit) need longer to recover.
    return 3600.0 if status in (402, 429) else 1800.0


def _mark_cooldown(name: str, seconds: float = 1800.0) -> None:
    with _hlock:
        _health[name] = time.monotonic() + seconds


def _select_provider(providers: list[dict]) -> Optional[dict]:
    """Round-robin pick of a provider that is not currently cooled down."""
    global _idx
    now = time.monotonic()
    with _hlock:
        n = len(providers)
        for i in range(n):
            p = providers[(_idx + i) % n]
            until = _health.get(p["name"])
            if until is None or until <= now:
                _idx = (_idx + i + 1) % n
                return p
        return None


def get_providers() -> list[dict]:
    """Build the provider list from `LLM_PROVIDERS`, else a single legacy one."""
    raw = (settings.llm_providers or "").strip()
    if raw:
        try:
            items = json.loads(raw)
            provs: list[dict] = []
            for it in items:
                key = it.get("api_key")
                if not key:
                    continue
                provs.append({
                    "name": it.get("name") or f"prov-{len(provs) + 1}",
                    "base_url": it.get("base_url") or "",
                    "api_key": key,
                    "model": it.get("model") or "",
                    "protocol": (it.get("protocol") or "openai").lower(),
                })
            if provs:
                return provs
        except Exception as e:  # malformed JSON -> fall back, never crash
            log.warning("LLM_PROVIDERS parse failed, using legacy config: %s", e)

    api_key = settings.llm_api_key or settings.openrouter_api_key
    if not api_key:
        return []
    return [{
        "name": "default",
        "base_url": settings.llm_base_url,
        "api_key": api_key,
        "model": settings.llm_model or settings.openrouter_model,
        "protocol": (settings.llm_protocol or "openai").lower(),
    }]


# --- request building ------------------------------------------------------

def _build_request(prov: dict, messages: list[dict], overrides: dict) -> tuple[str, dict, dict]:
    ov = dict(overrides)  # don't mutate caller's dict (used across providers)
    protocol = (prov.get("protocol") or "openai").lower()
    max_tokens = ov.pop("max_tokens", DEFAULT_MAX_TOKENS)
    if protocol == "anthropic":
        url = prov["base_url"].rstrip("/") + "/v1/messages"
        payload = {"model": prov.get("model") or "", "max_tokens": max_tokens,
                   "messages": [_to_anthropic_message(m) for m in messages]}
        payload.update(ov)
        headers = {"x-api-key": prov["api_key"], "anthropic-version": "2023-06-01",
                   "content-type": "application/json"}
    else:
        url = prov["base_url"]
        payload = {"model": prov.get("model") or "", "messages": messages, "max_tokens": max_tokens}
        payload.update(ov)
        headers = {"Authorization": f"Bearer {prov['api_key']}", "content-type": "application/json"}
    return url, headers, payload


def _parse(prov: dict, response: httpx.Response) -> str:
    protocol = (prov.get("protocol") or "openai").lower()
    return _anthropic_content(response) if protocol == "anthropic" else _openai_content(response)


# --- public API ------------------------------------------------------------

def chat(messages: list[dict], **overrides) -> str:
    providers = get_providers()
    if not providers:
        raise LLMError("no LLM providers configured (set LLM_PROVIDERS or LLM_API_KEY)")
    last_err = "no providers available"
    for _ in range(max(1, len(providers)) * 2):
        prov = _select_provider(providers)
        if prov is None:
            break
        try:
            url, headers, payload = _build_request(prov, messages, overrides)
            r = _post(url, headers, payload)
        except _RETRYABLE as e:
            _mark_cooldown(prov["name"])
            status = getattr(getattr(e, "response", None), "status_code", None)
            last_err = f"HTTP {status}" if status else f"{type(e).__name__}: {e}"
            continue
        if r.status_code >= 400:
            _mark_cooldown(prov["name"], _cooldown_for(r.status_code))
            last_err = f"HTTP {r.status_code}"
            continue
        try:
            return _parse(prov, r)
        except LLMError as e:
            _mark_cooldown(prov["name"], 300.0)
            last_err = str(e)
            continue
    raise LLMError(f"all LLM providers failed: {last_err}")


def _post(url: str, headers: dict, payload: dict) -> httpx.Response:
    return request_with_retry("POST", url, headers=headers, json=payload)


# --- transport / adapters (unchanged semantics) ----------------------------

def request_with_retry(method: str, url: str, **kwargs) -> httpx.Response:
    cfg = getattr(settings, "http", None)
    max_attempts = getattr(cfg, "max_attempts", 3) if cfg else 3
    backoff = getattr(cfg, "backoff_base", 1.0) if cfg else 1.0
    timeout = getattr(cfg, "timeout", 120.0) if cfg else 120.0

    last_exc: Optional[Exception] = None
    for attempt in range(1, max_attempts + 1):
        try:
            with httpx.Client(timeout=timeout) as client:
                r = client.request(method, url, **kwargs)
                if r.status_code == 429:
                    _raise_too_many(r)
                r.raise_for_status()
                return r
        except HTTPTooManyRetries:
            raise
        except (httpx.TransportError, httpx.TimeoutException) as e:
            last_exc = e
        except httpx.HTTPStatusError as e:
            last_exc = e
            if e.response is not None and e.response.status_code < 500:
                raise
        if attempt < max_attempts:
            time.sleep(backoff * (2 ** (attempt - 1)))
    raise HTTPTooManyRetries(f"request failed after {max_attempts} attempts: {last_exc}")


def _raise_too_many(r: httpx.Response) -> None:
    raise HTTPTooManyRetries(f"429 Too Many Requests: {r.text[:200]}")


def _openai_content(response: httpx.Response) -> str:
    try:
        data = response.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        raise LLMError(f"unexpected response shape: {e}") from e


def _anthropic_content(response: httpx.Response) -> str:
    try:
        data = response.json()
        parts = [b["text"] for b in data.get("content", []) if b.get("type") == "text"]
        if not parts:
            raise LLMError("no text content in anthropic response")
        return "\n".join(parts)
    except LLMError:
        raise
    except Exception as e:
        raise LLMError(f"unexpected anthropic response: {e}") from e


def _to_anthropic_message(msg: dict) -> dict:
    content = msg.get("content")
    if isinstance(content, str):
        return {"role": msg["role"], "content": [{"type": "text", "text": content}]}
    out = []
    for block in content:
        if block.get("type") == "text":
            out.append({"type": "text", "text": block["text"]})
        elif block.get("type") == "image_url":
            url = block["image_url"]["url"]
            media, _, data = url.partition(",")
            media_type = media.split(";")[0].replace("data:", "")
            out.append({"type": "image", "source": {"type": "base64", "media_type": media_type, "data": data}})
    return {"role": msg["role"], "content": out}


def image_data_url(path) -> str:
    from pathlib import Path
    p = Path(path)
    suffix = p.suffix.lower().lstrip(".")
    mime = "jpeg" if suffix in ("jpg", "jpeg") else (suffix or "png")
    import base64
    b64 = base64.b64encode(p.read_bytes()).decode()
    return f"data:image/{mime};base64,{b64}"
