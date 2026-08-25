import json
import logging
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

from sqlalchemy import func

from pinterest_automation.config.settings import settings
from pinterest_automation.database.models import AnalyticsRow, Pin

log = logging.getLogger(__name__)


def _day_bounds_utc(day: date):
    start = datetime.combine(day, time.min, tzinfo=timezone.utc)
    return start, start + timedelta(days=1)


def daily_report(db, day: date) -> dict:
    start, end = _day_bounds_utc(day)
    posted = (db.query(func.count(Pin.id))
                .filter(Pin.status == "published",
                        Pin.published_time >= start, Pin.published_time < end)
                .scalar())
    failed = (db.query(func.count(Pin.id))
                .filter(Pin.status == "failed",
                        Pin.updated_at >= start, Pin.updated_at < end)
                .scalar())
    ai_calls = (db.query(func.count(Pin.id))
                  .filter(Pin.ai_called_at.is_not(None),
                          Pin.ai_called_at >= start, Pin.ai_called_at < end)
                  .scalar())
    return {"date": day.isoformat(), "pins_posted": posted,
            "pins_failed": failed, "ai_calls": ai_calls}


def _top(db, column, label: str, since, until, n: int = 5) -> list[dict]:
    rows = (db.query(column.label("k"),
                     func.sum(AnalyticsRow.impressions).label("imp"),
                     func.sum(AnalyticsRow.clicks).label("clk"))
              .join(Pin, Pin.id == AnalyticsRow.pin_id)
              .filter(Pin.published_time >= since, Pin.published_time < until,
                      column.is_not(None))
              .group_by(column)
              .order_by(func.sum(AnalyticsRow.clicks).desc())
              .limit(n)
              .all())
    return [{label: r.k, "impressions": r.imp or 0, "clicks": r.clk or 0} for r in rows]


def weekly_report(db, end_day: date) -> dict:
    end_start, until = _day_bounds_utc(end_day)
    since = end_start - timedelta(days=6)   # trailing 7 calendar days incl end_day
    return {
        "week_ending": end_day.isoformat(),
        "top_categories": _top(db, Pin.content_category, "category", since, until),
        "best_keywords": _top(db, Pin.primary_keyword, "keyword", since, until),
        "best_boards": _top(db, Pin.board_name, "board_name", since, until),
    }


def write_report(report: dict, kind: str) -> Path:
    d = settings.reports_dir
    d.mkdir(parents=True, exist_ok=True)
    stamp = report.get("date") or report.get("week_ending")
    path = d / f"{stamp}-{kind}.json"
    path.write_text(json.dumps(report, indent=2))
    log.info("report written: %s", path)
    return path
