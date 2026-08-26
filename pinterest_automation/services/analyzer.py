import json
import logging
from pathlib import Path

from pinterest_automation.config.settings import settings
from pinterest_automation.database.db import utcnow
from pinterest_automation.database.models import Pin
from pinterest_automation.services import events
from pinterest_automation.services.seo_generator import (
    PinMetadata,
    MetadataValidationError,  # noqa: F401 - re-exported for tests/callers
    generate_metadata,
)

log = logging.getLogger(__name__)


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


def analyze_pending(db, limit: int | None = None) -> int:
    """Generate metadata for pending pins, settings.batch_size at a time.

    Failed pins stay pending (retried on a later invocation); rows whose
    image file is gone become failed permanently.
    """
    ok = 0
    # ponytail: attempted_ids guard — persistent-failure rows stay "pending",
    # so without this they'd be re-queued forever within one call.
    attempted_ids: set[int] = set()
    while True:
        remaining = None if limit is None else limit - ok
        if remaining is not None and remaining <= 0:
            break
        take = min(settings.batch_size, remaining) if remaining is not None else settings.batch_size
        q = db.query(Pin).filter(Pin.status == "pending")
        if attempted_ids:
            q = q.filter(Pin.id.not_in(attempted_ids))
        pins = q.limit(take).all()
        if not pins:
            break
        for pin in pins:
            attempted_ids.add(pin.id)
            if not Path(pin.image_path).is_file():
                pin.status = "failed"
                pin.error_message = "image file missing"
                log.error("image missing for pin %s: %s", pin.id, pin.image_path)
                continue
            try:
                _apply(pin, generate_metadata(Path(pin.image_path)))
                ok += 1
            except Exception as e:  # noqa: BLE001 - record per-pin failure, keep the batch alive
                pin.retry_count += 1
                pin.error_message = str(e)[:500]
                events.publish("metadata.failed", pin_id=pin.id, error=str(e)[:200])
                log.error("analyze failed for %s: %s", pin.image_path, str(e)[:200])
        db.commit()
        if len(pins) < take:
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
