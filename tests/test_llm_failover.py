import json

import httpx
import pytest


def test_chat_fails_over_to_next_provider(monkeypatch):
    from pinterest_automation.api import openrouter as orr
    from pinterest_automation.config.settings import settings
    from pinterest_automation.utils.http_retry import HTTPTooManyRetries

    providers = [
        {"name": "p_fail", "protocol": "openai",
         "base_url": "https://fail.example/chat/completions", "api_key": "k1", "model": "m"},
        {"name": "p_ok", "protocol": "openai",
         "base_url": "https://ok.example/chat/completions", "api_key": "k2", "model": "m"},
    ]
    monkeypatch.setattr(settings, "llm_providers", json.dumps(providers))

    def fake(url, headers, payload):
        if "fail.example" in url:
            raise HTTPTooManyRetries("rate limited")
        return httpx.Response(200, json={"choices": [{"message": {"content": "recovered"}}]})

    monkeypatch.setattr(orr, "_post", fake)
    assert orr.chat([{"role": "user", "content": "hi"}]) == "recovered"


def test_chat_raises_when_all_providers_fail(monkeypatch):
    from pinterest_automation.api import openrouter as orr
    from pinterest_automation.config.settings import settings

    providers = [
        {"name": "a", "protocol": "openai", "base_url": "https://a/chat/completions", "api_key": "k", "model": "m"},
        {"name": "b", "protocol": "openai", "base_url": "https://b/chat/completions", "api_key": "k", "model": "m"},
    ]
    monkeypatch.setattr(settings, "llm_providers", json.dumps(providers))

    def boom(url, headers, payload):
        r = httpx.Response(402, json={"error": "no credits"}, request=httpx.Request("POST", url))
        r.raise_for_status()

    monkeypatch.setattr(orr, "_post", boom)
    with pytest.raises(orr.LLMError, match="all LLM providers failed"):
        orr.chat([{"role": "user", "content": "hi"}])
