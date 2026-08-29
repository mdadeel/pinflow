import logging
from pathlib import Path

from pinterest_automation.database.models import Pin
from pinterest_automation.services import analyzer
from pinterest_automation.services import events
from pinterest_automation.services import scheduler

log = logging.getLogger(__name__)

# Pin columns cleared when a pin is wiped back to a clean "pending" slate.
_METADATA_FIELDS = (
    "title",
    "description",
    "alt_text",
    "primary_keyword",
    "secondary_keywords",
    "tags",
    "board_name",
    "content_category",
    "board_id",
    "pin_id_str",
    "pin_url",
    "error_message",
)


def _is_publish_error(pin: Pin) -> bool:
    err = (pin.error_message or "").lower()
    return any(k in err for k in ("publish", "pinterest", "board", "create_pin"))


def reset_pin(db, pin_id: int) -> Pin | None:
    """Wipe a pin back to a clean 'pending' state so it re-enters the pipeline."""
    pin = db.get(Pin, pin_id)
    if pin is None:
        return None
    for field in _METADATA_FIELDS:
        setattr(pin, field, None)
    pin.scheduled_time = None
    pin.published_time = None
    pin.retry_count = 0
    pin.status = "pending"
    db.commit()
    db.refresh(pin)
    events.publish("pin.reset", pin_id=pin.id)
    return pin


def delete_pin(db, pin_id: int) -> bool:
    pin = db.get(Pin, pin_id)
    if pin is None:
        return False
    path = Path(pin.image_path)
    db.delete(pin)
    db.commit()
    if path.is_file():
        path.unlink(missing_ok=True)
    events.publish("pin.deleted", pin_id=pin_id)
    return True


def _publish_now(db, pin: Pin, token: str | None) -> bool:
    from pinterest_automation.processors.uploader import publish_pin

    if pin.status != "scheduled":
        pin.status = "scheduled"
        db.commit()
    return publish_pin(db, pin, token=token)


def retry_pin(db, pin_id: int, token: str | None = None) -> Pin | None:
    """Re-attempt the phase the pin is stuck on; if it still fails, reset it.

    Phase mapping:
      - ready                         -> assign a publish slot (schedule)
      - pending / failed-at-analysis -> regenerate metadata, then schedule
      - scheduled / failed-at-publish-> publish now
    """
    pin = db.get(Pin, pin_id)
    if pin is None:
        return None
    if pin.status == "published":
        return pin
    try:
        if pin.status == "ready":
            scheduler.assign_schedule_times(db, [pin_id])
        elif pin.status in ("pending", "failed") and not _is_publish_error(pin):
            analyzer.regenerate_pin(db, pin_id)
            pin = db.get(Pin, pin_id)
            if pin.status in ("pending", "failed") and pin.title:
                pin.status = "ready"
                scheduler.assign_schedule_times(db, [pin_id])
        else:
            _publish_now(db, pin, token)
        pin = db.get(Pin, pin_id)
        if pin.status != "failed":
            pin.retry_count = 0
            pin.error_message = None
            db.commit()
        return pin
    except Exception as e:  # noqa: BLE001 - retry failed -> reset the whole process
        log.error("retry failed for pin %s, resetting: %s", pin_id, str(e)[:200])
        return reset_pin(db, pin_id)


def bulk_action(db, action: str, ids: list[int] | None = None,
                token: str | None = None) -> dict:
    if ids is None:
        ids = [p.id for p in db.query(Pin.id).all()]
    processed = 0
    for pid in ids:
        if action == "delete":
            processed += 1 if delete_pin(db, pid) else 0
        elif action == "reset":
            processed += 1 if reset_pin(db, pid) else 0
        elif action == "retry":
            retry_pin(db, pid, token=token)
            processed += 1
    return {"action": action, "processed": processed, "requested": len(ids)}
