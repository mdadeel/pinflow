import logging
import time

import httpx

log = logging.getLogger(__name__)

RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class HTTPTooManyRetries(RuntimeError):
    pass


def request_with_retry(method: str, url: str, *, tries: int = 3,
                       timeout: float = 120.0, **kw) -> httpx.Response:
    delay = 2.0
    last: Exception | str | None = None
    for attempt in range(1, tries + 1):
        try:
            r = httpx.request(method, url, timeout=timeout, **kw)
            if r.status_code not in RETRYABLE_STATUS:
                r.raise_for_status()
                return r
            wait = float(r.headers.get("retry-after", delay))
            last = f"HTTP {r.status_code}"
            log.warning("%s %s -> %s, retry %d/%d in %.0fs",
                        method, url, r.status_code, attempt, tries, wait)
            time.sleep(wait)
        except httpx.HTTPStatusError:
            raise                      # non-retryable HTTP error -> caller sees it
        except httpx.HTTPError as e:
            last = e
            log.warning("network error %r on %s %s, retry %d/%d in %.0fs",
                        e, method, url, attempt, tries, delay)
            time.sleep(delay)
        delay *= 2
    raise HTTPTooManyRetries(f"{method} {url} failed after {tries} attempts ({last})")
