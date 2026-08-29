import json
from calendar import monthrange
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import desc, func

from pinterest_automation.api.rest import router as rest_router
from pinterest_automation.api.ws import router as ws_router
from pinterest_automation.api.ratelimit import limiter
from pinterest_automation.api.auth import APIKeyAuthMiddleware
from pinterest_automation.config.settings import settings
from pinterest_automation.database import db as dbmod
from pinterest_automation.database.models import AnalyticsRow, Pin

app = FastAPI(title="PinFlow")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(APIKeyAuthMiddleware)
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)
app.include_router(rest_router)
app.include_router(ws_router)


@app.get("/", response_class=HTMLResponse)
def overview(request: Request):
    with dbmod.get_session_factory()() as db:
        total = db.query(func.count(Pin.id)).scalar() or 0
        counts = dict(db.query(Pin.status, func.count(Pin.id)).group_by(Pin.status).all())
        return templates.TemplateResponse(request, "overview.html", {
            "total_images": total,
            "pending": counts.get("pending", 0) + counts.get("ready", 0),
            "scheduled": counts.get("scheduled", 0),
            "published": counts.get("published", 0),
            "failed": counts.get("failed", 0),
        })


@app.get("/library", response_class=HTMLResponse)
def library(request: Request, status: str | None = None, page: int = 1):
    with dbmod.get_session_factory()() as db:
        PER_PAGE = 50
        q = db.query(Pin).order_by(Pin.created_at.desc())
        if status:
            q = q.filter(Pin.status == status)
        items = q.offset((page - 1) * PER_PAGE).limit(PER_PAGE).all()
        for p in items:
            p.keywords = json.loads(p.secondary_keywords) if p.secondary_keywords else []
        return templates.TemplateResponse(request, "library.html", {
            "pins": items, "status": status or "", "page": page,
        })


@app.get("/calendar", response_class=HTMLResponse)
def calendar_view(request: Request, month: str | None = None):
    now = datetime.now(timezone.utc)
    try:
        year, mon = (int(x) for x in month.split("-"))
        if not (1 <= mon <= 12):
            raise ValueError
    except (AttributeError, TypeError, ValueError):
        year, mon = now.year, now.month
    start = datetime(year, mon, 1, tzinfo=timezone.utc)
    end = datetime(year, mon, monthrange(year, mon)[1], 23, 59, 59, tzinfo=timezone.utc)
    with dbmod.get_session_factory()() as db:
        events = (db.query(Pin)
                    .filter((Pin.scheduled_time.between(start, end)) |
                            (Pin.published_time.between(start, end)))
                    .all())
        by_day: dict[int, list] = {}
        for p in events:
            t = p.scheduled_time or p.published_time
            by_day.setdefault(t.day, []).append(p)
        prev_y, prev_m = (year - 1, 12) if mon == 1 else (year, mon - 1)
        next_y, next_m = (year + 1, 1) if mon == 12 else (year, mon + 1)
        return templates.TemplateResponse(request, "calendar.html", {
            "year": year, "month": mon, "days": monthrange(year, mon)[1],
            "by_day": by_day, "today": now,
            "prev": f"{prev_y}-{prev_m:02d}", "next": f"{next_y}-{next_m:02d}",
        })


@app.get("/analytics", response_class=HTMLResponse)
def analytics(request: Request):
    with dbmod.get_session_factory()() as db:
        sums = dict(
            zip(("impressions", "clicks", "saves", "outbound"),
                db.query(func.sum(AnalyticsRow.impressions),
                         func.sum(AnalyticsRow.clicks),
                         func.sum(AnalyticsRow.saves),
                         func.sum(AnalyticsRow.outbound_clicks)).first()))
        imp, clk = sums["impressions"] or 0, sums["clicks"] or 0
        top = (db.query(Pin, AnalyticsRow)
                 .join(AnalyticsRow, AnalyticsRow.pin_id == Pin.id)
                 .order_by(desc(AnalyticsRow.clicks)).limit(10).all())
        return templates.TemplateResponse(request, "analytics.html", {
            "impressions": imp, "clicks": clk,
            "saves": sums["saves"] or 0, "outbound_clicks": sums["outbound"] or 0,
            "ctr": clk / imp if imp else 0.0, "top": top,
        })


@app.get("/media/{pin_id}")
def media(pin_id: int):
    with dbmod.get_session_factory()() as db:
        pin = db.get(Pin, pin_id)
        if pin is None:
            raise HTTPException(404)
        path = Path(pin.image_path)
        if not path.is_file():
            raise HTTPException(404)
        return FileResponse(path)
