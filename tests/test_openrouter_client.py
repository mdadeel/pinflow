import base64

import httpx


def _fake_post(content: str):
    def fake(payload, headers):
        assert payload["model"] == "test-model"
        assert headers["Authorization"] == "Bearer k-test"
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})
    return fake


def test_chat_returns_content(monkeypatch):
    from pinterest_automation.api import openrouter as orr
    from pinterest_automation.config.settings import settings
    monkeypatch.setattr(settings, "openrouter_model", "test-model")
    monkeypatch.setattr(settings, "openrouter_api_key", "k-test")
    monkeypatch.setattr(orr, "_post", _fake_post("hello!"))
    assert orr.chat([{"role": "user", "content": "hi"}]) == "hello!"


def test_chat_wraps_transport_errors(monkeypatch):
    from pinterest_automation.api import openrouter as orr
    from pinterest_automation.utils.http_retry import HTTPTooManyRetries

    def boom(payload, headers):
        raise HTTPTooManyRetries("dead")

    monkeypatch.setattr(orr, "_post", boom)
    import pytest
    with pytest.raises(orr.OpenRouterError):
        orr.chat([{"role": "user", "content": "hi"}])


def test_chat_wraps_http_status_error(monkeypatch):
    from pinterest_automation.api import openrouter as orr

    def unauthorized(payload, headers):
        r = httpx.Response(401, json={"error": "bad key"},
                           request=httpx.Request("POST", orr.URL))
        r.raise_for_status()

    monkeypatch.setattr(orr, "_post", unauthorized)
    import pytest
    with pytest.raises(orr.OpenRouterError, match="HTTP 401"):
        orr.chat([{"role": "user", "content": "hi"}])


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
