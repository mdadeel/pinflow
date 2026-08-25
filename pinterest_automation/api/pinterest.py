import base64
import logging
from pathlib import Path

import httpx

from pinterest_automation.config.settings import settings
from pinterest_automation.utils.http_retry import HTTPTooManyRetries, request_with_retry

log = logging.getLogger(__name__)
BASE = "https://api.pinterest.com/v5"
MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
METRIC_TYPES = "IMPRESSIONS,CLICKS,SAVES,OUTBOUND_CLICKS"
MAX_BOARD_PAGES = 20   # 100/page -> 2000 boards, far beyond need


class PinterestError(RuntimeError):
    pass


def _token(token: str | None) -> str:
    tok = token or settings.pinterest_access_token
    if not tok:
        raise PinterestError("no PINTEREST_ACCESS_TOKEN configured")
    return tok


def _call(method: str, url: str, token: str, **kw) -> httpx.Response:
    try:
        return request_with_retry(method, url,
                                  headers={"Authorization": f"Bearer {token}"}, **kw)
    except HTTPTooManyRetries as e:
        raise PinterestError(str(e)) from e
    except httpx.HTTPStatusError as e:
        raise PinterestError(f"{e.response.status_code}: {e.response.text[:300]}") from e


def get_boards(token: str | None = None) -> list[dict]:
    tok = _token(token)
    boards: list[dict] = []
    bookmark: str | None = None
    for _page in range(MAX_BOARD_PAGES):
        params: dict = {"page_size": 100}
        if bookmark:
            params["bookmark"] = bookmark
        data = _call("GET", f"{BASE}/boards", tok, params=params).json()
        boards.extend(data.get("items", []))
        bookmark = data.get("bookmark")
        if not bookmark:
            return boards
    raise PinterestError(f"boards pagination exceeded {MAX_BOARD_PAGES} pages")


def create_pin(board_id: str, title: str, description: str, image_path: Path,
               link: str | None = None, token: str | None = None) -> dict:
    tok = _token(token)
    mime = MIME[image_path.suffix.lower()]
    payload: dict = {
        "board_id": board_id,
        "title": title,
        "description": description,
        # ponytail: Pinterest v5 create-pin has no alt_text field; alt text lives in our DB only
        "media_source": {
            "source_type": "image_base64",
            "content_type": mime,
            "data": base64.b64encode(image_path.read_bytes()).decode(),
        },
    }
    if link:
        payload["link"] = link
    # non-2xx raises PinterestError via _call wrapping HTTPStatusError
    r = _call("POST", f"{BASE}/pins", tok, json=payload)
    log.info("created pin on board %s", board_id)
    return r.json()


def get_pin_analytics(pin_id: str, start_date: str, end_date: str,
                      token: str | None = None) -> dict:
    """Flattened lifetime-window metric totals for one pin."""
    tok = _token(token)
    r = _call("GET", f"{BASE}/pins/{pin_id}/analytics", tok,
              params={"start_date": start_date, "end_date": end_date,
                      "metric_types": METRIC_TYPES})
    metrics = r.json().get("all", {}).get("metrics", {})

    def val(name: str) -> int:
        return int(metrics.get(name, {}).get("value", 0) or 0)

    return {"impressions": val("IMPRESSIONS"),
            "clicks": val("CLICKS"),
            "saves": val("SAVES"),
            "outbound_clicks": val("OUTBOUND_CLICKS")}
