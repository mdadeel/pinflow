import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from pinterest_automation.config.settings import settings
from pinterest_automation.database.db import get_session_factory, utcnow
from pinterest_automation.database.models import Pin
from pinterest_automation.services import events
from pinterest_automation.services.seo_generator import (
    PinMetadata,
    MetadataValidationError,  # noqa: F401 - re-exported for tests/callers
    generate_metadata,
)

log = logging.getLogger(__name__)

MAX_ANALYZE_RETRIES = 5


def _apply(pin: Pin, m: PinMetadata) -> None:
    pin.title = m.title
    pin.description = m.description
    pin.alt_text = m.alt_text
    pin.primary_keyword = m.primary_keyword
    pin.secondary_keywords = json.dumps(m.secondary_keywords)
    pin.tags = json.dumps(m.tags)
    pin.board_name = m.board
    pin.content_category = m.category
    pin.ai_called_at = utcnow()
    pin.status = "ready"
    events.publish("metadata.generated", pin_id=pin.id, title=m.title)


def _analyze_one(pin_id: int, image_path: str, factory=None) -> bool:
    """Analyze a single pin in its own session (thread-safe, fixes pool leak)."""
    s = (factory or get_session_factory())()
    try:
        pin = s.get(Pin, pin_id)
        if pin is None or pin.status != "pending":
            return False
        if not Path(image_path).is_file():
            pin.status = "failed"
            pin.error_message = "image file missing"
            s.commit()
            return False
        _apply(pin, generate_metadata(Path(image_path)))
        s.commit()
        return True
    except Exception as e:  # noqa: BLE001 - record per-pin failure, keep the batch alive
        s.rollback()
        try:
            pin = s.get(Pin, pin_id)
            if pin is not None and pin.status == "pending":
                pin.retry_count += 1
                pin.error_message = str(e)[:500]
                if pin.retry_count >= MAX_ANALYZE_RETRIES:
                    pin.status = "failed"
                    log.error("pin %s hit max analyze retries (%d): %s",
                              pin_id, MAX_ANALYZE_RETRIES, str(e)[:150])
                else:
                    log.error("analyze failed for %s: %s", image_path, str(e)[:200])
                s.commit()
        except Exception:
            pass
        events.publish("metadata.failed", pin_id=pin_id, error=str(e)[:200])
        return False
    finally:
        s.close()


def analyze_pending(db, limit: int | None = None, workers: int | None = None,
                    session_factory=None) -> int:
    """Generate metadata for pending pins, settings.batch_size at a time.

    Pins are processed concurrently (`settings.analysis_workers`) so the
    multi-provider pool is exercised in parallel. Rows whose image file is
    gone become failed permanently; pins that fail repeatedly are moved to
    "failed" after MAX_ANALYZE_RETRIES.
    """
    workers = workers if workers is not None else settings.analysis_workers
    if session_factory is None:
        # Derive a factory from the caller's session engine so thread workers
        # hit the same database (important for tests that use tmp DBs).
        from sqlalchemy.orm import sessionmaker
        factory = sessionmaker(bind=db.get_bind(), expire_on_commit=False)
    else:
        factory = session_factory
    ok = 0
    # ponytail: attempted_ids guard — persistent-failure rows stay "pending",
    # so without this they'd be re-queued forever within one call.
    attempted_ids: set[int] = set()
    while True:
        remaining = None if limit is None else limit - ok
        if remaining is not None and remaining <= 0:
            break
        take = min(settings.batch_size, remaining) if remaining is not None else settings.batch_size
        q = db.query(Pin.id, Pin.image_path).filter(Pin.status == "pending")
        if attempted_ids:
            q = q.filter(Pin.id.not_in(attempted_ids))
        rows = q.limit(take).all()
        if not rows:
            break
        attempted_ids.update(r.id for r in rows)
        tasks = [(r.id, r.image_path) for r in rows]
        if workers and len(tasks) > 1:
            with ThreadPoolExecutor(max_workers=min(workers, len(tasks))) as ex:
                futures = [ex.submit(_analyze_one, pid, path, factory) for pid, path in tasks]
                for f in as_completed(futures):
                    try:
                        if f.result():
                            ok += 1
                    except Exception as e:  # noqa: BLE001 - a crashed worker shouldn't abort the batch
                        log.error("analyze worker crashed: %s", e)
        else:
            for pid, path in tasks:
                if _analyze_one(pid, path, factory):
                    ok += 1
        if len(rows) < take:
            break
    return ok


def regenerate_pin(db, pin_id: int) -> Pin | None:
    pin = db.get(Pin, pin_id)
    if pin is None:
        return None
    if not Path(pin.image_path).is_file():
        pin.status = "failed"
        pin.error_message = "image file missing"
        db.commit()
        raise FileNotFoundError(f"image missing for pin {pin_id}")
    _apply(pin, generate_metadata(Path(pin.image_path)))
    db.commit()
    return pin
