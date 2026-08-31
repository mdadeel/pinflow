import argparse
import contextlib
import fcntl
import logging
import os
import sys
import time
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler

from pinterest_automation.config.logging_setup import setup_logging
from pinterest_automation.config.settings import settings
from pinterest_automation.database import db as dbmod
from pinterest_automation.database.models import Pin
from pinterest_automation.processors.image_watcher import scan_folder
from pinterest_automation.processors.uploader import publish_pin
from pinterest_automation.services.analyzer import analyze_pending
from pinterest_automation.services.scheduler import assign_schedule_times, run_due

log = logging.getLogger(__name__)


class LockBusy(Exception):
    """Raised when another process already holds the publish lock."""


@contextlib.contextmanager
def _publish_lock():
    # lock file lives next to the logs; default log_dir == pinterest_automation/logs
    lock_path = Path(settings.log_dir) / "publish.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fh = lock_path.open("w")
    try:
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise LockBusy("another run is publishing")
        yield
    finally:
        fh.close()


def cmd_scan() -> None:
    from pinterest_automation.processors.image_watcher import ingest_raw_images
    raw_dir = Path(settings.raw_images_dir)
    watch = Path(settings.watch_dir)
    if raw_dir.exists() and raw_dir.is_dir():
        ingested = ingest_raw_images(raw_dir, watch)
        if ingested > 0:
            log.info("ingested %d raw images from %s to %s", ingested, raw_dir, watch)
    watch.mkdir(parents=True, exist_ok=True)
    db = dbmod.get_session_factory()()
    n = scan_folder(watch, db)
    log.info("ingested %d new images", n)


def cmd_analyze(limit: int | None) -> None:
    db = dbmod.get_session_factory()()
    n = analyze_pending(db, limit=limit)
    log.info("analyzed %d", n)


def _ready_ids(db, limit: int | None) -> list[int]:
    q = db.query(Pin.id).filter(Pin.status == "ready")
    if limit:
        q = q.limit(limit)
    return [pid for (pid,) in q.all()]


def cmd_schedule(limit: int | None) -> None:
    db = dbmod.get_session_factory()()
    n = assign_schedule_times(db, _ready_ids(db, limit))
    log.info("scheduled %d", n)


def cmd_publish_now(pin_id: int) -> int:
    db = dbmod.get_session_factory()()
    pin = db.get(Pin, pin_id)
    if pin is None:
        log.error("pin not found")
        return 2
    try:
        with _publish_lock():
            ok = publish_pin(db, pin)
    except LockBusy as e:
        log.warning(str(e))
        return 1
    if ok:
        log.info("published")
    else:
        log.error("failed: %s", pin.error_message)
    return 0 if ok else 1


def run_pipeline_once() -> dict:
    """Run one full cycle: scan -> analyze -> schedule -> publish due pins."""
    cmd_scan()
    db = dbmod.get_session_factory()()
    analyzed = analyze_pending(db)
    ids = _ready_ids(db, None)
    scheduled = assign_schedule_times(db, ids)
    pub = failed = 0
    locked = False
    try:
        with _publish_lock():
            pub, failed = run_due(db)
    except LockBusy:
        locked = True
        log.warning("run skipped: another run is publishing")
    return {"analyzed": analyzed, "scheduled": scheduled,
            "published": pub, "failed": failed, "locked": locked}


def cmd_run_once() -> int:
    r = run_pipeline_once()
    log.info(
        "analyzed %s, scheduled %s, published %s, failed %s",
        r["analyzed"],
        r["scheduled"],
        r["published"],
        r["failed"],
    )
    return 1 if r["locked"] else 0


def build_pipeline_scheduler() -> BackgroundScheduler:
    sched = BackgroundScheduler()

    sched.add_job(cmd_scan, "interval", minutes=5, id="scan")

    def cycle() -> None:
        # The configured, working automation path is the CSV pipeline
        # (ingest -> Cloudinary upload -> Gemini/LLM metadata -> CSV export).
        # The old scan -> schedule -> publish-to-Pinterest path can't run here:
        # no Pinterest access token is configured, so it silently produced
        # nothing. Route the daemon cycle through the working pipeline instead.
        from pinterest_automation.processors.csv_pipeline import csv_pipeline
        try:
            res = csv_pipeline.run_all()
            log.info(
                "csv cycle done: scanned=%s uploaded=%s analyzed=%s export_success=%s",
                res.get("scanned"),
                res.get("upload", {}).get("uploaded"),
                res.get("analyze", {}).get("analyzed"),
                res.get("export", {}).get("success"),
            )
        except Exception as e:  # noqa: BLE001 - one bad cycle must not kill the daemon
            log.error("csv cycle failed: %s", e)

    # sched.add_job(cycle, "interval", minutes=10, id="cycle", max_instances=1)
    # NOTE: Disabled automatic CSV pipeline cycle to prevent pins from being
    # auto-exported to "exported" status. Uncomment and run `csv_pipeline.run_all()`
    # manually via CLI (`cmd process-csv`) or API (`GET /api/pipeline/csv-run`) when needed.

    def nightly_report() -> None:
        try:
            cmd_report("daily")
        except Exception as e:  # noqa: BLE001 - a report failure must not kill the daemon
            log.error("nightly report failed: %s", e)

    sched.add_job(nightly_report, "cron", hour=23, minute=30, id="daily-report")
    return sched


def cmd_daemon() -> None:
    sched = build_pipeline_scheduler()
    sched.start()
    log.info("daemon running. ctrl-c to stop.")
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        sched.shutdown()


def cmd_sync_analytics(days: int) -> None:
    db = dbmod.get_session_factory()()
    from pinterest_automation.services.analytics_service import sync_published
    n = sync_published(db, lookback_days=days)
    log.info("synced %d pins", n)


def cmd_report(kind: str) -> int:
    from datetime import datetime, timezone

    from pinterest_automation.services.reporting import daily_report, weekly_report, write_report

    today = datetime.now(timezone.utc).date()   # report windows are UTC; local date lies after midnight
    db = dbmod.get_session_factory()()
    if kind == "weekly":
        rep = weekly_report(db, today)
    else:
        rep = daily_report(db, today)
    path = write_report(rep, kind)
    log.info("report written: %s", path)
    return 0


def cmd_serve() -> None:
    import uvicorn
    from pinterest_automation.services.gemini_sidecar import gemini_sidecar

    sched = build_pipeline_scheduler()
    sched.start()
    gemini_sidecar.start()
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))
    try:
        uvicorn.run("pinterest_automation.dashboard.app:app", host=host, port=port)
    finally:
        gemini_sidecar.stop()
        sched.shutdown()


def cmd_web2api() -> None:
    from pinterest_automation.services.gemini_sidecar import gemini_sidecar
    log.info("Starting Gemini-Web2API sidecar...")
    gemini_sidecar.start()
    log.info("Running at %s (model: %s). Press Ctrl+C to stop.", gemini_sidecar.base_url, settings.gemini_web2api_model)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:  # aislop-ignore-line ai-slop/silent-recovery -- clean shutdown, not error recovery
        gemini_sidecar.stop()
        log.info("Stopped.")


def cmd_process_csv() -> None:
    from pinterest_automation.processors.csv_pipeline import csv_pipeline
    res = csv_pipeline.run_all()
    log.info("CSV Pipeline finished: %s", res)


def cmd_export_csv() -> int:
    from pinterest_automation.exporters.csv_export_service import csv_export_service
    db = dbmod.get_session_factory()()
    try:
        path, rec, ids = csv_export_service.export_pins(db)
        log.info("Exported %d pins to %s", rec.record_count, path)
        return 0
    except Exception as e:
        log.error("Export failed: %s", e)
        return 1


def cmd_retry_failed() -> None:
    from pinterest_automation.services.retry_service import retry_service
    db = dbmod.get_session_factory()()
    res = retry_service.retry_all_failed(db)
    log.info("Retried %d failed pins", len(res))


def run(argv: list[str] | None = None) -> int:
    setup_logging(settings.log_dir)
    ap = argparse.ArgumentParser(prog="pinterest-automation")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("scan")
    p_an = sub.add_parser("analyze")
    p_an.add_argument("--limit", type=int)
    p_sc = sub.add_parser("schedule")
    p_sc.add_argument("--limit", type=int)
    p_pn = sub.add_parser("publish-now")
    p_pn.add_argument("--id", type=int, required=True)
    p_sa = sub.add_parser("sync-analytics")
    p_sa.add_argument("--days", type=int, default=30)
    p_rep = sub.add_parser("report")
    p_rep.add_argument("--kind", choices=["daily", "weekly"], default="daily")
    sub.add_parser("run-once")
    sub.add_parser("daemon")
    sub.add_parser("serve")
    sub.add_parser("web2api")
    sub.add_parser("process-csv")
    sub.add_parser("export-csv")
    sub.add_parser("retry-failed")

    args = ap.parse_args(argv)
    if args.cmd == "scan":
        cmd_scan()
        return 0
    if args.cmd == "analyze":
        cmd_analyze(args.limit)
        return 0
    if args.cmd == "schedule":
        cmd_schedule(args.limit)
        return 0
    if args.cmd == "publish-now":
        return cmd_publish_now(args.id)
    if args.cmd == "sync-analytics":
        cmd_sync_analytics(args.days)
        return 0
    if args.cmd == "report":
        return cmd_report(args.kind)
    if args.cmd == "run-once":
        return cmd_run_once()
    if args.cmd == "daemon":
        cmd_daemon()
        return 0
    if args.cmd == "serve":
        cmd_serve()
        return 0
    if args.cmd == "web2api":
        cmd_web2api()
        return 0
    if args.cmd == "process-csv":
        cmd_process_csv()
        return 0
    if args.cmd == "export-csv":
        return cmd_export_csv()
    if args.cmd == "retry-failed":
        cmd_retry_failed()
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(run())

