import logging
from datetime import date, timedelta

from pinterest_automation.api.pinterest import get_pin_analytics
from pinterest_automation.database.db import utcnow
from pinterest_automation.database.models import AnalyticsRow, Pin

log = logging.getLogger(__name__)


def sync_published(db, token: str | None = None,
                   lookback_days: int = 30, limit: int = 200) -> int:
    """Refresh metric snapshots for recently published pins."""
    cutoff = utcnow() - timedelta(days=lookback_days)
    pins = (db.query(Pin)
              .filter(Pin.status == "published",
                      Pin.pin_id_str.is_not(None),
                      Pin.published_time >= cutoff)
              .order_by(Pin.published_time.desc())
              .limit(limit)
              .all())
    synced = 0
    today = date.today()
    for pin in pins:
        start = pin.published_time.date()
        try:
            m = get_pin_analytics(pin.pin_id_str, start.isoformat(),
                                  today.isoformat(), token=token)
        except Exception as e:  # noqa: BLE001 - one bad pin must not stop the sync
            log.warning("analytics fetch failed for %s: %s", pin.pin_id_str, str(e)[:150])
            continue
        row = db.query(AnalyticsRow).filter(AnalyticsRow.pin_id == pin.id).one_or_none()
        if row is None:
            row = AnalyticsRow(pin_id=pin.id)
            db.add(row)
        row.impressions = m["impressions"]
        row.clicks = m["clicks"]
        row.saves = m["saves"]
        row.outbound_clicks = m["outbound_clicks"]
        row.ctr = m["clicks"] / m["impressions"] if m["impressions"] else 0.0
        row.last_updated = utcnow()
        synced += 1
    db.commit()
    return synced
