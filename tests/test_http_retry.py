import httpx
import pytest


def test_retries_on_429_then_succeeds(monkeypatch):
    import pinterest_automation.utils.http_retry as hr
    calls = []

    def fake_request(method, url, **kw):
        calls.append(1)
        if len(calls) < 3:
            return httpx.Response(429, headers={"retry-after": "0"}, request=httpx.Request("GET", url))
        return httpx.Response(200, json={"ok": True}, request=httpx.Request("GET", url))

    monkeypatch.setattr(hr.httpx, "request", fake_request)
    monkeypatch.setattr(hr.time, "sleep", lambda s: None)
    r = hr.request_with_retry("GET", "https://x.test")
    assert r.status_code == 200 and len(calls) == 3


def test_raises_after_exhaustion(monkeypatch):
    import pinterest_automation.utils.http_retry as hr
    monkeypatch.setattr(hr.httpx, "request",
                        lambda m, u, **k: httpx.Response(500, request=httpx.Request("GET", u)))
    monkeypatch.setattr(hr.time, "sleep", lambda s: None)
    with pytest.raises(hr.HTTPTooManyRetries):
        hr.request_with_retry("GET", "https://x.test")


def test_no_retry_on_400(monkeypatch):
    import pinterest_automation.utils.http_retry as hr
    calls = []

    def fake(method, url, **kw):
        calls.append(1)
        return httpx.Response(400, request=httpx.Request("GET", url))

    monkeypatch.setattr(hr.httpx, "request", fake)
    with pytest.raises(httpx.HTTPStatusError):
        hr.request_with_retry("GET", "https://x.test")
    assert len(calls) == 1


def test_network_error_retries(monkeypatch):
    import pinterest_automation.utils.http_retry as hr
    calls = []

    def flaky(method, url, **kw):
        calls.append(1)
        if len(calls) < 2:
            raise httpx.ConnectError("boom")
        return httpx.Response(200, json={}, request=httpx.Request("GET", url))

    monkeypatch.setattr(hr.httpx, "request", flaky)
    monkeypatch.setattr(hr.time, "sleep", lambda s: None)
    assert hr.request_with_retry("GET", "https://x.test").status_code == 200
