import logging
import math
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func

from pinterest_automation.api.pinterest import get_boards
from pinterest_automation.config.settings import Settings, settings
from pinterest_automation.database.db import utcnow
from pinterest_automation.database.models import Pin
from pinterest_automation.processors.uploader import publish_pin
from pinterest_automation.services import events

log = logging.getLogger(__name__)

BACKOFF_MINUTES = 15
MAX_RETRIES = 5
MAX_DAYS_AHEAD = 365


def _aware_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def _slot_taken_count(db, day: date, cfg: Settings) -> int:
    return (db.query(func.count(Pin.id))
              .filter(Pin.status == "scheduled",
                      func.strftime("%Y-%m-%d", Pin.scheduled_time) ==
                      day.strftime("%Y-%m-%d"))
              .scalar())


def _hour_slots_count(db, base: date, hour: int) -> int:
    from datetime import time
    start = datetime.combine(base, time(hour, 0, 0), tzinfo=timezone.utc)
    end = datetime.combine(base, time(hour, 59, 59), tzinfo=timezone.utc)
    return (db.query(func.count(Pin.id))
              .filter(Pin.status == "scheduled",
                      Pin.scheduled_time >= start,
                      Pin.scheduled_time <= end)
              .scalar() or 0)


def _next_free_slot(db, cfg: Settings, now: datetime):
    for offset in range(MAX_DAYS_AHEAD):
        base = (_aware_utc(now) + timedelta(days=offset)).date()
        taken = _slot_taken_count(db, base, cfg)
        if taken >= cfg.posts_per_day:
            continue
        
        candidates = []
        for hour in sorted(cfg.post_hours):
            slot = datetime(base.year, base.month, base.day, hour,
                            minute=0, tzinfo=timezone.utc)
            if slot <= now:
                continue
            
            slots_count = _hour_slots_count(db, base, hour)
            limit = math.ceil(cfg.posts_per_day / len(cfg.post_hours))
            if slots_count < limit:
                candidates.append((slots_count, hour))
        
        if candidates:
            # Sort by slots_count ascending, then hour ascending to distribute evenly
            candidates.sort()
            best_slots_count, best_hour = candidates[0]
            return datetime(base.year, base.month, base.day, best_hour,
                            minute=best_slots_count % 60,
                            tzinfo=timezone.utc)
    return None


def assign_schedule_times(db, pin_ids: list[int], cfg: Settings | None = None,
                          now: datetime | None = None) -> int:
    cfg = cfg or settings
    now = _aware_utc(now or utcnow())
    assigned = 0
    for pid in pin_ids:
        pin = db.get(Pin, pid)
        if pin is None or pin.status == "scheduled":
            continue
        slot = _next_free_slot(db, cfg, now)
        if slot is None:
            break
        pin.scheduled_time = slot
        pin.status = "scheduled"
        assigned += 1
        events.publish("pin.scheduled", pin_id=pin.id,
                       scheduled_time=slot.isoformat())
    db.commit()
    log.info("scheduled %d pins", assigned)
    return assigned


def due_pins(db, now: datetime | None = None) -> list[Pin]:
    now = _aware_utc(now or utcnow())
    return (db.query(Pin)
              .filter(Pin.status == "scheduled", Pin.scheduled_time <= now)
              .order_by(Pin.scheduled_time)
              .all())


def run_due(db, now: datetime | None = None, max_posts: int | None = None,
            token: str | None = None) -> tuple[int, int]:
    due = due_pins(db, now=now)[:max_posts if max_posts is not None else settings.posts_per_day]
    if not due:
        return 0, 0
    try:
        boards = get_boards(token=token)
    except Exception as e:  # noqa: BLE001 - infra failure is not pin failure: no retry_count/status change
        log.error("run_due aborted, get_boards failed: %s", str(e)[:200])
        for pin in due:
            pin.error_message = f"run aborted, boards unavailable: {str(e)[:200]}"
            if pin.retry_count >= MAX_RETRIES:
                pin.status = "failed"
                log.error("pin %s hit max retries (%d) on board fetch: %s",
                          pin.id, MAX_RETRIES, str(e)[:150])
            else:
                delay = timedelta(minutes=BACKOFF_MINUTES * max(1, pin.retry_count))
                pin.scheduled_time = (pin.scheduled_time or utcnow()) + delay
        db.commit()
        return 0, len(due)

    published = failed = 0
    for pin in due:
        if publish_pin(db, pin, token=token, boards=boards):
            published += 1
            continue
        failed += 1
        if pin.retry_count >= MAX_RETRIES:
            pin.status = "failed"
            log.error("pin %s hit max retries (%d): %s",
                      pin.id, MAX_RETRIES, str(pin.error_message)[:150])
        else:
            delay = timedelta(minutes=BACKOFF_MINUTES * max(1, pin.retry_count))
            pin.scheduled_time = (pin.scheduled_time or utcnow()) + delay
        db.commit()
    return published, failed
