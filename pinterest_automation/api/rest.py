import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from typing import Literal

from fastapi import APIRouter, File, HTTPException, Request, Response, UploadFile
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, or_, text

from pinterest_automation.config.settings import settings
from pinterest_automation.database import db as dbmod
from pinterest_automation.database.models import AnalyticsRow, LearningSignal, Pin
from pinterest_automation.services import analyzer
from pinterest_automation.services import scheduler
from pinterest_automation.services import pin_actions
from pinterest_automation.services.events import publish
from pinterest_automation.main import run_pipeline_once
from pinterest_automation.utils.media_types import EXTENSIONS, image_dimensions
from pinterest_automation.api.ratelimit import limiter, UPLOAD_LIMIT, PIPELINE_LIMIT, READ_LIMIT, WRITE_LIMIT

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api")

APP_VERSION = "1.0.0"
MAX_UPLOAD_BYTES = 30 * 1024 * 1024


@router.get("/health")
def health_check():
    """Basic health check endpoint for load balancers and monitoring."""
    health = {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": APP_VERSION,
        "checks": {}
    }

    # Check database
    try:
        with dbmod.get_session_factory()() as db:
            db.execute(text("SELECT 1"))
        health["checks"]["database"] = "ok"
    except Exception as e:
        health["status"] = "degraded"
        health["checks"]["database"] = f"error: {str(e)[:100]}"

    # Check Pinterest API token
    if settings.pinterest_access_token:
        health["checks"]["pinterest_api"] = "configured"
    else:
        health["checks"]["pinterest_api"] = "not_configured"

    # Check LLM providers
    if settings.llm_providers or settings.openrouter_api_key:
        health["checks"]["llm_providers"] = "configured"
    else:
        health["checks"]["llm_providers"] = "not_configured"

    # Check images directory
    images_path = Path(settings.images_dir)
    if images_path.exists():
        health["checks"]["storage"] = "ok"
    else:
        health["status"] = "degraded"
        health["checks"]["storage"] = "directory_missing"

    return health


@router.get("/health/ready")
def readiness_check():
    """Readiness probe - is the service ready to accept traffic?"""
    checks = {
        "database": False,
        "pinterest_api": bool(settings.pinterest_access_token),
        "llm_providers": bool(settings.llm_providers or settings.openrouter_api_key),
        "storage": Path(settings.images_dir).exists(),
    }

    # Check database connectivity
    try:
        with dbmod.get_session_factory()() as db:
            db.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:
        pass

    ready = all(checks.values())
    return {
        "ready": ready,
        "checks": checks,
    }

# Max Hamming distance for a candidate to count as a duplicate. `image_hash` is a
# 256-bit SHA256 content hash (64 hex chars), not a perceptual hash, so near-zero
# distance means byte-identical content. Tune for perceptual hashes if a phash
# column is ever added at ingestion.
DUPLICATE_HASH_THRESHOLD = 8
MAX_DUPLICATE_RESULTS = 10


def _hash_hamming(a: str, b: str) -> int | None:
    """Hamming distance between two hex hashes, or None if not comparable."""
    try:
        return (int(a, 16) ^ int(b, 16)).bit_count()
    except ValueError:
        return None


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
@limiter.limit(UPLOAD_LIMIT)
async def upload_images(request: Request, files: list[UploadFile] = File(...)):
    folder = Path(settings.images_dir)
    folder.mkdir(parents=True, exist_ok=True)
    added, duplicates, rejected, retried = [], [], [], []
    with dbmod.get_session_factory()() as db:
        existing = {p.image_hash: p for p in db.query(Pin).all()}
        seen = set(existing.keys())

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
            if digest in seen:
                pin = existing.get(digest)
                if pin is not None and (
                    pin.status == "failed" or pin.status.startswith("failed")
                ):
                    # Previously failed upload: reset it and re-process instead of skipping.
                    try:
                        Path(pin.image_path).write_bytes(data)
                    except OSError:
                        pass
                    pin_actions.reset_pin(db, pin.id)
                    retried.append(_to_pin_out(pin))
                else:
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
            seen.add(digest)
            added.append(_to_pin_out(pin))
            publish("image.uploaded", path=str(dest.resolve()), filename=name)
    return {"added": added, "duplicates": duplicates, "retried": retried,
            "rejected": [r.model_dump() for r in rejected]}


@router.post("/pipeline/run")
@limiter.limit(PIPELINE_LIMIT)
def run_pipeline(request: Request) -> dict:
    """Run one full cycle now (scan -> analyze -> schedule -> publish due)."""
    return run_pipeline_once()


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
@limiter.limit(WRITE_LIMIT)
def edit_pin(request: Request, pin_id: int, body: PinEdit):
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
@limiter.limit(READ_LIMIT)
def list_pins(request: Request, status: str | None = None, page: int = 1, per_page: int = 50,
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


@router.get("/pins/{pin_id}/duplicates")
def find_duplicates(pin_id: int):
    with dbmod.get_session_factory()() as db:
        pin = db.get(Pin, pin_id)
        if pin is None:
            raise HTTPException(404)
        target = pin.image_hash
        if not target:
            return []
        others = db.query(Pin).filter(Pin.id != pin_id,
                                      Pin.image_hash != None,
                                      Pin.image_hash != "").all()
        max_bits = len(target) * 4
        candidates = []
        for o in others:
            dist = _hash_hamming(target, o.image_hash)
            if dist is None or dist > DUPLICATE_HASH_THRESHOLD:
                continue
            candidates.append((o, 1 - dist / max_bits))
        candidates.sort(key=lambda c: c[1], reverse=True)
        return [{"id": o.id, "title": o.title,
                 "score": round(score, 4), "status": o.status}
                for o, score in candidates[:MAX_DUPLICATE_RESULTS]]


@router.get("/pins/{pin_id}")
@limiter.limit(READ_LIMIT)
def get_pin(request: Request, pin_id: int):
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


@router.delete("/pins/{pin_id}")
def delete_pin(pin_id: int):
    with dbmod.get_session_factory()() as db:
        if not pin_actions.delete_pin(db, pin_id):
            raise HTTPException(404)
    return Response(status_code=204)


@router.post("/pins/{pin_id}/reset")
def reset_pin(pin_id: int):
    with dbmod.get_session_factory()() as db:
        pin = pin_actions.reset_pin(db, pin_id)
        if pin is None:
            raise HTTPException(404)
        out = _to_pin_out(pin)
    publish("pin.updated", pin_id=out.id, status=out.status)
    return out


@router.post("/pins/{pin_id}/retry")
def retry_pin(pin_id: int):
    token = settings.pinterest_access_token or None
    with dbmod.get_session_factory()() as db:
        pin = pin_actions.retry_pin(db, pin_id, token=token)
        if pin is None:
            raise HTTPException(404)
        out = _to_pin_out(pin)
    publish("pin.updated", pin_id=out.id, status=out.status)
    return out


class BulkAction(BaseModel):
    action: Literal["delete", "reset", "retry"]
    ids: list[int] | None = None


@router.post("/pins/bulk")
def bulk_action(body: BulkAction):
    token = settings.pinterest_access_token or None
    with dbmod.get_session_factory()() as db:
        result = pin_actions.bulk_action(db, body.action, body.ids, token=token)
    return result


@router.get("/stats")
@limiter.limit(READ_LIMIT)
def stats(request: Request):
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
@limiter.limit(READ_LIMIT)
def analytics_summary(request: Request):
    # Pin has no impressions/saves/clicks columns (they live on AnalyticsRow),
    # so top_pins/ctr/series clicks are aggregated from AnalyticsRow.
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

        # Per-day clicks/impressions from AnalyticsRow (last_updated carries the date).
        day_rows = db.query(func.date(AnalyticsRow.last_updated).label("d"),
                            func.sum(AnalyticsRow.clicks).label("clk"),
                            func.sum(AnalyticsRow.impressions).label("imp")) \
            .filter(AnalyticsRow.last_updated >= since).group_by("d").all()
        clk_buckets = {r.d: int(r.clk or 0) for r in day_rows}
        imp_buckets = {r.d: int(r.imp or 0) for r in day_rows}

        series = [{"date": d.isoformat(),
                   "published": buckets.get(d.isoformat(), 0),
                   "clicks": clk_buckets.get(d.isoformat(), 0),
                   "impressions": imp_buckets.get(d.isoformat(), 0)}
                  for d in (today - timedelta(days=i) for i in range(29, -1, -1))]

        # Top 5 pins by total clicks.
        top_rows = db.query(Pin.id, Pin.title,
                            func.sum(AnalyticsRow.impressions).label("imp"),
                            func.sum(AnalyticsRow.saves).label("sav"),
                            func.sum(AnalyticsRow.clicks).label("clk")) \
            .join(AnalyticsRow, AnalyticsRow.pin_id == Pin.id) \
            .group_by(Pin.id, Pin.title) \
            .order_by(func.sum(AnalyticsRow.clicks).desc()) \
            .limit(5).all()
        top_pins = [{"id": r.id, "title": r.title,
                     "impressions": int(r.imp or 0), "saves": int(r.sav or 0),
                     "clicks": int(r.clk or 0)} for r in top_rows]

        # CTR = total clicks / total impressions across all AnalyticsRow.
        agg = db.query(func.sum(AnalyticsRow.clicks),
                       func.sum(AnalyticsRow.impressions)).first()
        total_clicks = int(agg[0] or 0)
        total_impr = int(agg[1] or 0)
        ctr = (total_clicks / total_impr) if total_impr else 0.0

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
        "top_pins": top_pins,
        "series": series,
        "ctr": ctr,
    }


class LearningSignalIn(BaseModel):
    action: str
    pin_id: int | None = None


@router.post("/learning", status_code=201)
def record_learning_signal(body: LearningSignalIn):
    with dbmod.get_session_factory()() as db:
        sig = LearningSignal(action=body.action, pin_id=body.pin_id)
        db.add(sig)
        db.commit()
        db.refresh(sig)
    return {"id": sig.id, "action": sig.action, "pin_id": sig.pin_id}


@router.get("/learning")
def learning_summary():
    with dbmod.get_session_factory()() as db:
        rows = db.query(LearningSignal.action,
                        func.count(LearningSignal.id)).group_by(
                            LearningSignal.action).all()
        counts = {action: int(n) for action, n in rows}
        total = db.query(func.count(LearningSignal.id)).scalar() or 0
    return {"counts": counts, "total": total}
