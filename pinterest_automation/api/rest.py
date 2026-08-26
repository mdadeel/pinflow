import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from typing import Literal

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, or_

from pinterest_automation.config.settings import settings
from pinterest_automation.database import db as dbmod
from pinterest_automation.database.models import AnalyticsRow, Pin
from pinterest_automation.services import analyzer
from pinterest_automation.services import scheduler
from pinterest_automation.services.events import publish
from pinterest_automation.utils.media_types import EXTENSIONS, image_dimensions

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api")

MAX_UPLOAD_BYTES = 30 * 1024 * 1024


class RejectedFile(BaseModel):
    filename: str
    reason: str


class PinOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    image_url: str
    status: str
    title: str | None = None
    description: str | None = None
    alt_text: str | None = None
    primary_keyword: str | None = None
    secondary_keywords: list[str] | None = None
    tags: list[str] | None = None
    board_name: str | None = None
    content_category: str | None = None
    scheduled_time: str | None = None
    published_time: str | None = None
    file_size: int | None = None
    width: int | None = None
    height: int | None = None
    created_at: datetime


def _to_pin_out(pin: Pin) -> PinOut:
    def _list(raw: str | None) -> list[str] | None:
        return json.loads(raw) if raw else None

    def _iso(dt) -> str | None:
        if not dt:
            return None
        s = dt.isoformat()
        return s[:-6] if s.endswith("+00:00") else s

    return PinOut(
        id=pin.id,
        filename=Path(pin.image_path).name,
        image_url=f"/media/{pin.id}",
        status=pin.status,
        title=pin.title,
        description=pin.description,
        alt_text=pin.alt_text,
        primary_keyword=pin.primary_keyword,
        secondary_keywords=_list(pin.secondary_keywords),
        tags=_list(pin.tags),
        board_name=pin.board_name,
        content_category=pin.content_category,
        scheduled_time=_iso(pin.scheduled_time),
        published_time=_iso(pin.published_time),
        file_size=pin.file_size,
        width=pin.width,
        height=pin.height,
        created_at=pin.created_at,
    )


def _collision_free_path(folder: Path, name: str) -> Path:
    p = folder / name
    stem, suffix = p.stem, p.suffix
    n = 1
    while p.exists():
        p = folder / f"{stem} ({n}){suffix}"
        n += 1
    return p


@router.post("/uploads", status_code=201)
async def upload_images(files: list[UploadFile] = File(...)):
    folder = Path(settings.images_dir)
    folder.mkdir(parents=True, exist_ok=True)
    added, duplicates, rejected = [], [], []
    with dbmod.get_session_factory()() as db:
        existing_hashes = {h for (h,) in db.query(Pin.image_hash).all()}

        for uf in files:
            raw = Path(uf.filename or "").name  # strip directory components (path traversal)
            name = raw or "unnamed"
            if not name.lower().endswith(tuple(EXTENSIONS)):
                rejected.append(RejectedFile(filename=name, reason="unsupported type"))
                continue
            data = await uf.read()
            if len(data) > MAX_UPLOAD_BYTES:
                rejected.append(RejectedFile(filename=name, reason="too large"))
                continue
            digest = hashlib.sha256(data).hexdigest()
            if digest in existing_hashes:
                duplicates.append(name)
                continue
            dest = _collision_free_path(folder, name)
            dest.write_bytes(data)
            try:
                w, h = image_dimensions(dest)
            except Exception:  # noqa: BLE001 - corrupt image: reject, don't store
                dest.unlink(missing_ok=True)
                rejected.append(RejectedFile(filename=name, reason="unreadable image"))
                continue
            pin = Pin(image_path=str(dest.resolve()), image_hash=digest,
                      file_size=len(data), width=w, height=h)
            db.add(pin)
            db.commit()
            db.refresh(pin)
            existing_hashes.add(digest)
            added.append(_to_pin_out(pin))
            publish("image.uploaded", path=str(dest.resolve()), filename=name)
    return {"added": added, "duplicates": duplicates,
            "rejected": [r.model_dump() for r in rejected]}


PIN_STATUSES = Literal["pending", "ready", "scheduled", "published", "failed"]
MANUAL_MOVES = {("pending", "ready"), ("ready", "pending")}


class StatusUpdate(BaseModel):
    status: PIN_STATUSES


EDITABLE_STATUSES = ("pending", "ready")


class PinEdit(BaseModel):
    title: str | None = None
    description: str | None = None
    alt_text: str | None = None
    primary_keyword: str | None = None
    secondary_keywords: list[str] | None = None
    tags: list[str] | None = None
    board_name: str | None = None
    content_category: str | None = None


@router.patch("/pins/{pin_id}")
def edit_pin(pin_id: int, body: PinEdit):
    with dbmod.get_session_factory()() as db:
        pin = db.get(Pin, pin_id)
        if pin is None:
            raise HTTPException(404)
        if pin.status not in EDITABLE_STATUSES:
            raise HTTPException(409, detail=f"pin is {pin.status}, not editable")
        for field in ("title", "description", "alt_text", "primary_keyword",
                      "secondary_keywords", "tags", "board_name", "content_category"):
            if field not in body.model_fields_set:
                continue
            value = getattr(body, field)
            if field in ("secondary_keywords", "tags"):
                value = json.dumps(value)
            setattr(pin, field, value)
        db.commit()
        db.refresh(pin)
        out = _to_pin_out(pin)
    publish("metadata.edited", pin_id=out.id)
    return out


@router.get("/pins")
def list_pins(status: str | None = None, page: int = 1, per_page: int = 50,
              q: str | None = None):
    per_page = max(1, min(per_page, 200))
    page = max(1, page)
    with dbmod.get_session_factory()() as db:
        query = db.query(Pin).order_by(Pin.created_at.desc(), Pin.id.desc())
        if status:
            query = query.filter(Pin.status == status)
        if q:
            like = f"%{q}%"
            query = query.filter(or_(Pin.title.ilike(like), Pin.board_name.ilike(like),
                                     Pin.content_category.ilike(like),
                                     Pin.primary_keyword.ilike(like)))
        total = query.count()
        items = query.offset((page - 1) * per_page).limit(per_page).all()
        out = {"items": [_to_pin_out(p) for p in items],
               "total": total, "page": page, "per_page": per_page}
    return out


@router.get("/pins/{pin_id}")
def get_pin(pin_id: int):
    with dbmod.get_session_factory()() as db:
        pin = db.get(Pin, pin_id)
        if pin is None:
            raise HTTPException(404)
        return _to_pin_out(pin)


@router.patch("/pins/{pin_id}/status")
def move_pin(pin_id: int, body: StatusUpdate):
    with dbmod.get_session_factory()() as db:
        pin = db.get(Pin, pin_id)
        if pin is None:
            raise HTTPException(404)
        if (pin.status, body.status) not in MANUAL_MOVES:
            raise HTTPException(409, detail=f"manual move to '{body.status}' not allowed")
        pin.status = body.status
        db.commit()
        db.refresh(pin)
        out = _to_pin_out(pin)
    publish("pin.updated", pin_id=out.id, status=out.status)
    return out


class ScheduleUpdate(BaseModel):
    scheduled_time: str


@router.patch("/pins/{pin_id}/schedule")
def reschedule_pin(pin_id: int, body: ScheduleUpdate):
    with dbmod.get_session_factory()() as db:
        pin = db.get(Pin, pin_id)
        if pin is None:
            raise HTTPException(404)
        if pin.status not in ("ready", "scheduled"):
            raise HTTPException(409, detail=f"reschedule requires ready/scheduled, pin is {pin.status}")
        parsed = datetime.fromisoformat(body.scheduled_time)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        pin.scheduled_time = parsed
        pin.status = "scheduled"
        db.commit()
        db.refresh(pin)
        out = _to_pin_out(pin)
    publish("pin.scheduled", pin_id=out.id, scheduled_time=parsed.isoformat())
    return out


@router.post("/pins/{pin_id}/approve")
def approve_pin(pin_id: int):
    with dbmod.get_session_factory()() as db:
        pin = db.get(Pin, pin_id)
        if pin is None:
            raise HTTPException(404)
        if pin.status != "ready":
            raise HTTPException(409, detail=f"approve requires ready, pin is {pin.status}")
        scheduler.assign_schedule_times(db, [pin_id])
        db.refresh(pin)
        out = _to_pin_out(pin)
    publish("pin.scheduled", pin_id=out.id, scheduled_time=out.scheduled_time)
    return out


@router.post("/pins/{pin_id}/regenerate")
def regenerate(pin_id: int):
    with dbmod.get_session_factory()() as db:
        try:
            pin = analyzer.regenerate_pin(db, pin_id)
        except FileNotFoundError:
            raise HTTPException(409, detail="image file missing for pin")
        if pin is None:
            raise HTTPException(404)
        out = _to_pin_out(pin)
    return out


@router.get("/stats")
def stats():
    with dbmod.get_session_factory()() as db:
        counts = dict(db.query(Pin.status, func.count(Pin.id)).group_by(Pin.status).all())
        sums = db.query(func.sum(AnalyticsRow.impressions),
                        func.sum(AnalyticsRow.clicks),
                        func.sum(AnalyticsRow.saves),
                        func.sum(AnalyticsRow.outbound_clicks)).first()
    return {
        "total": sum(counts.values()),
        "pending": counts.get("pending", 0),
        "ready": counts.get("ready", 0),
        "scheduled": counts.get("scheduled", 0),
        "published": counts.get("published", 0),
        "failed": counts.get("failed", 0),
        "impressions": sums[0] or 0,
        "clicks": sums[1] or 0,
        "saves": sums[2] or 0,
        "outbound_clicks": sums[3] or 0,
    }


@router.get("/analytics")
def analytics_summary():
    # Pin has no impressions/saves/clicks columns (they live on AnalyticsRow),
    # so top_pins/ctr are empty/zero and the series only counts published pins.
    with dbmod.get_session_factory()() as db:
        total = db.query(func.count(Pin.id)).scalar() or 0
        counts = dict(db.query(Pin.status, func.count(Pin.id)).group_by(Pin.status).all())

        since = dbmod.utcnow() - timedelta(days=30)
        pubs = [t[0] for t in db.query(Pin.published_time)
                .filter(Pin.published_time >= since).all() if t[0] is not None]
        buckets: dict[str, int] = {}
        for pt in pubs:
            d = pt.date().isoformat()
            buckets[d] = buckets.get(d, 0) + 1

        today = dbmod.utcnow().date()
        series = [{"date": d.isoformat(), "published": buckets.get(d.isoformat(), 0)}
                  for d in (today - timedelta(days=i) for i in range(29, -1, -1))]

    return {
        "totals": {
            "pins": total,
            "published": counts.get("published", 0),
            "scheduled": counts.get("scheduled", 0),
            "pending": counts.get("pending", 0),
            "ready": counts.get("ready", 0),
            "failed": counts.get("failed", 0),
        },
        "by_status": counts,
        "top_pins": [],
        "series": series,
        "ctr": 0.0,
    }
