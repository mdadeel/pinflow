import base64

import httpx
import pytest


BOARDS_PAGE1 = {"items": [{"id": "b1", "name": "Anime Board"}], "bookmark": "NEXT"}
BOARDS_PAGE2 = {"items": [{"id": "b2", "name": "Nature Board"}]}


def test_get_boards_paginates(monkeypatch):
    from pinterest_automation.api import pinterest as pt
    calls = []

    def fake_req(method, url, **kw):
        calls.append((method, url, kw.get("params")))
        body = BOARDS_PAGE1 if len(calls) == 1 else BOARDS_PAGE2
        return httpx.Response(200, json=body)

    monkeypatch.setattr(pt, "request_with_retry", fake_req)
    boards = pt.get_boards(token="t")
    assert [b["id"] for b in boards] == ["b1", "b2"]
    assert calls[0][2]["page_size"] == 100
    assert "bookmark" not in calls[0][2]
    assert calls[1][2]["bookmark"] == "NEXT"


def test_get_boards_no_token_raises(monkeypatch):
    from pinterest_automation.api import pinterest as pt
    from pinterest_automation.config.settings import settings
    monkeypatch.setattr(settings, "pinterest_access_token", "")
    with pytest.raises(pt.PinterestError):
        pt.get_boards()


def test_create_pin_payload(monkeypatch, tmp_path):
    from pinterest_automation.api import pinterest as pt
    captured = {}

    def fake_req(method, url, **kw):
        captured.update(url=url, method=method, kw=kw)
        return httpx.Response(201, json={"id": "pin123", "url": "https://pinterest.com/pin/123"})

    monkeypatch.setattr(pt, "request_with_retry", fake_req)
    img = tmp_path / "w.PNG"
    img.write_bytes(b"\x89PNG-data")
    res = pt.create_pin(board_id="b1", title="T", description="D",
                        image_path=img, link="https://example.com", token="tok")
    assert res["id"] == "pin123"
    assert captured["url"].endswith("/v5/pins") and captured["method"] == "POST"
    body = captured["kw"]["json"]
    assert body["board_id"] == "b1" and body["title"] == "T" and body["description"] == "D"
    assert body["link"] == "https://example.com"
    ms = body["media_source"]
    assert ms["source_type"] == "image_base64" and ms["content_type"] == "image/png"
    assert base64.b64decode(ms["data"]) == b"\x89PNG-data"
    assert captured["kw"]["headers"]["Authorization"] == "Bearer tok"


def test_create_pin_link_omitted_when_none(monkeypatch, tmp_path):
    from pinterest_automation.api import pinterest as pt
    captured = {}

    def fake_req(method, url, **kw):
        captured.update(kw=kw)
        return httpx.Response(201, json={"id": "p", "url": "u"})

    monkeypatch.setattr(pt, "request_with_retry", fake_req)
    img = tmp_path / "w.png"; img.write_bytes(b"x")
    pt.create_pin(board_id="b", title="T", description="D", image_path=img, token="t")
    assert "link" not in captured["kw"]["json"]


def test_create_pin_rejects_error_status(monkeypatch, tmp_path):
    from pinterest_automation.api import pinterest as pt
    monkeypatch.setattr(
        pt, "request_with_retry",
        lambda m, u, **k: httpx.Response(403, json={"message": "denied"}),
    )
    img = tmp_path / "w.png"; img.write_bytes(b"x")
    with pytest.raises(pt.PinterestError):
        pt.create_pin(board_id="b", title="T", description="D", image_path=img, token="t")


def test_create_pin_wraps_retry_exhaustion(monkeypatch, tmp_path):
    from pinterest_automation.api import pinterest as pt
    from pinterest_automation.utils.http_retry import HTTPTooManyRetries

    def boom(m, u, **k):
        raise HTTPTooManyRetries("dead")

    monkeypatch.setattr(pt, "request_with_retry", boom)
    img = tmp_path / "w.png"; img.write_bytes(b"x")
    with pytest.raises(pt.PinterestError):
        pt.create_pin(board_id="b", title="T", description="D", image_path=img, token="t")


ANALYTICS_RAW = {"all": {"metrics": {
    "IMPRESSIONS": {"value": 100},
    "CLICKS": {},            # missing value -> 0
    "SAVES": {"value": 5},
}}}


def test_analytics_flattens_and_defaults(monkeypatch):
    from pinterest_automation.api import pinterest as pt
    captured = {}

    def fake_req(method, url, **kw):
        captured.update(url=url, params=kw.get("params"))
        return httpx.Response(200, json=ANALYTICS_RAW)

    monkeypatch.setattr(pt, "request_with_retry", fake_req)
    totals = pt.get_pin_analytics("pin123", "2026-08-01", "2026-08-24", token="t")
    assert totals == {"impressions": 100, "clicks": 0, "saves": 5, "outbound_clicks": 0}
    assert "/pins/pin123/analytics" in captured["url"]
    assert captured["params"]["metric_types"] == "IMPRESSIONS,CLICKS,SAVES,OUTBOUND_CLICKS"
