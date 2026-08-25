import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path

from typing import Literal

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, or_

from pinterest_automation.config.settings import settings
from pinterest_automation.database import db as dbmod
from pinterest_automation.database.models import AnalyticsRow, Pin
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
    file_size: int | None = None
    width: int | None = None
    height: int | None = None
    created_at: datetime


def _to_pin_out(pin: Pin) -> PinOut:
    def _list(raw: str | None) -> list[str] | None:
        return json.loads(raw) if raw else None

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
