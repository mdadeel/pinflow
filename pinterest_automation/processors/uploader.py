import logging
from pathlib import Path

from pinterest_automation.api.pinterest import PinterestError, create_pin, get_boards
from pinterest_automation.config.settings import settings
from pinterest_automation.database.db import utcnow
from pinterest_automation.database.models import Pin
from pinterest_automation.services.board_mapper import map_board

log = logging.getLogger(__name__)


def publish_pin(db, pin: Pin, token: str | None = None,
                boards: list[dict] | None = None) -> bool:
    """Publish one pin. Returns True iff it reached status=published."""
    try:
        boards = boards if boards is not None else get_boards(token=token)
    except Exception as e:  # noqa: BLE001 - record and report False
        pin.error_message = str(e)[:500]
        db.commit()
        return False

    board_id = pin.board_id or map_board(pin.board_name or "", boards,
                                         overrides=settings.board_overrides)
    if not board_id:
        pin.status = "failed"
        pin.error_message = f"no matching pinterest board for {pin.board_name!r}"
        db.commit()
        return False
    pin.board_id = board_id

    try:
        res = create_pin(board_id, pin.title, pin.description or "",
                         Path(pin.image_path), token=token)
    except Exception as e:  # noqa: BLE001 - keep status; scheduler retries with backoff
        pin.retry_count += 1
        pin.error_message = str(e)[:500]
        db.commit()
        log.warning("pin %s create failed: %s", pin.id, str(e)[:200])
        return False

    pin.pin_id_str = str(res.get("id"))
    pin.pin_url = res.get("url")
    pin.published_time = utcnow()
    pin.status = "published"
    pin.error_message = None
    db.commit()
    log.info("published pin %s -> %s", pin.id, pin.pin_url)
    return True
