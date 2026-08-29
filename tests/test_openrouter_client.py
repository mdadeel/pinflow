import base64

import httpx


def _fake_post(content: str):
    def fake(url, headers, payload):
        assert payload["model"] == "test-model"
        assert headers["Authorization"] == "Bearer k-test"
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})
    return fake


def test_chat_returns_content(monkeypatch):
    from pinterest_automation.api import openrouter as orr
    from pinterest_automation.config.settings import settings
    monkeypatch.setattr(settings, "llm_providers", "")
    monkeypatch.setattr(settings, "openrouter_model", "test-model")
    monkeypatch.setattr(settings, "openrouter_api_key", "k-test")
    monkeypatch.setattr(orr, "_post", _fake_post("hello!"))
    assert orr.chat([{"role": "user", "content": "hi"}]) == "hello!"


def test_chat_wraps_transport_errors(monkeypatch):
    from pinterest_automation.api import openrouter as orr
    from pinterest_automation.config.settings import settings
    from pinterest_automation.utils.http_retry import HTTPTooManyRetries

    def boom(url, headers, payload):
        raise HTTPTooManyRetries("dead")

    monkeypatch.setattr(settings, "llm_providers", "")
    monkeypatch.setattr(settings, "openrouter_api_key", "k-test")
    monkeypatch.setattr(orr, "_post", boom)
    import pytest
    with pytest.raises(orr.LLMError):
        orr.chat([{"role": "user", "content": "hi"}])


def test_chat_wraps_http_status_error(monkeypatch):
    from pinterest_automation.api import openrouter as orr
    from pinterest_automation.config.settings import settings

    def unauthorized(url, headers, payload):
        r = httpx.Response(401, json={"error": "bad key"},
                           request=httpx.Request("POST", orr.URL))
        r.raise_for_status()

    monkeypatch.setattr(settings, "llm_providers", "")
    monkeypatch.setattr(settings, "openrouter_api_key", "k-test")
    monkeypatch.setattr(orr, "_post", unauthorized)
    import pytest
    with pytest.raises(orr.LLMError, match="HTTP 401"):
        orr.chat([{"role": "user", "content": "hi"}])


def test_chat_anthropic_protocol(monkeypatch):
    from pinterest_automation.api import openrouter as orr
    from pinterest_automation.config.settings import settings

    monkeypatch.setattr(settings, "llm_providers", "")
    monkeypatch.setattr(settings, "llm_api_key", "k-test")
    monkeypatch.setattr(settings, "llm_model", "claude-x")
    monkeypatch.setattr(settings, "llm_base_url", "https://capi.aerolink.lat")
    monkeypatch.setattr(settings, "llm_protocol", "anthropic")

    captured = {}

    def fake(url, headers, payload):
        captured["url"] = url
        captured["headers"] = headers
        captured["payload"] = payload
        return httpx.Response(200, json={"content": [{"type": "text", "text": "hi-anthropic"}]})

    monkeypatch.setattr(orr, "_post", fake)
    assert orr.chat([{"role": "user", "content": "hi"}]) == "hi-anthropic"
    assert captured["url"] == "https://capi.aerolink.lat/v1/messages"
    assert captured["headers"]["x-api-key"] == "k-test"
    assert captured["headers"]["anthropic-version"] == "2023-06-01"
    assert captured["payload"]["model"] == "claude-x"
    # openai-style image_url block is converted to an anthropic image source
    conv = orr._to_anthropic_message(
        {"role": "user", "content": [
            {"type": "text", "text": "t"},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,QQ=="}},
        ]}
    )
    img = conv["content"][1]
    assert img["type"] == "image" and img["source"]["media_type"] == "image/png"


def test_image_data_url(tmp_path):
    from pinterest_automation.api.openrouter import image_data_url
    p = tmp_path / "i.png"
    p.write_bytes(b"\x89PNG")
    url = image_data_url(p)
    mime, b64 = url.split(";")[0][5:], url.split(",")[1]
    assert mime == "image/png" and base64.b64decode(b64) == b"\x89PNG"


def test_image_data_url_jpeg(tmp_path):
    from pinterest_automation.api.openrouter import image_data_url
    p = tmp_path / "i.JPG"          # uppercase extension
    p.write_bytes(b"data")
    assert image_data_url(p).startswith("data:image/jpeg;base64,")
