import argparse
import contextlib
import fcntl
import logging
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
            raise RuntimeError("another run is publishing")
        yield
    finally:
        fh.close()


def cmd_scan() -> None:
    watch = Path(settings.watch_dir)
    watch.mkdir(parents=True, exist_ok=True)
    db = dbmod.get_session_factory()()
    n = scan_folder(watch, db)
    print(f"ingested {n} new images")


def cmd_analyze(limit: int | None) -> None:
    db = dbmod.get_session_factory()()
    n = analyze_pending(db, limit=limit)
    print(f"analyzed {n}")


def _ready_ids(db, limit: int | None) -> list[int]:
    q = db.query(Pin.id).filter(Pin.status == "ready")
    if limit:
        q = q.limit(limit)
    return [pid for (pid,) in q.all()]


def cmd_schedule(limit: int | None) -> None:
    db = dbmod.get_session_factory()()
    n = assign_schedule_times(db, _ready_ids(db, limit))
    print(f"scheduled {n}")


def cmd_publish_now(pin_id: int) -> int:
    db = dbmod.get_session_factory()()
    pin = db.get(Pin, pin_id)
    if pin is None:
        print("pin not found")
        return 2
    try:
        with _publish_lock():
            ok = publish_pin(db, pin)
    except RuntimeError as e:
        print(str(e))
        return 1
    print("published" if ok else f"failed: {pin.error_message}")
    return 0 if ok else 1


def cmd_run_once() -> int:
    cmd_scan()
    cmd_analyze(None)
    cmd_schedule(None)
    try:
        with _publish_lock():
            db = dbmod.get_session_factory()()
            pub, failed = run_due(db)
    except RuntimeError as e:
        print(str(e))
        return 1
    print(f"published {pub}, failed {failed}")
    return 0


def cmd_daemon() -> None:
    sched = BackgroundScheduler()

    sched.add_job(cmd_scan, "interval", minutes=5, id="scan")

    def cycle() -> None:
        db = dbmod.get_session_factory()()
        analyze_pending(db)
        ids = _ready_ids(db, settings.posts_per_day * 3)
        assign_schedule_times(db, ids)
        try:
            with _publish_lock():
                pub, failed = run_due(db)
            log.info("cycle done: published %d, failed %d", pub, failed)
        except RuntimeError:
            log.warning("cycle skipped: another run is publishing")

    sched.add_job(cycle, "interval", minutes=10, id="cycle", max_instances=1)

    def nightly_report() -> None:
        try:
            cmd_report("daily")
        except Exception as e:  # noqa: BLE001 - a report failure must not kill the daemon
            log.error("nightly report failed: %s", e)

    sched.add_job(nightly_report, "cron", hour=23, minute=30, id="daily-report")
    sched.start()
    print("daemon running. ctrl-c to stop.")
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        sched.shutdown()


def cmd_sync_analytics(days: int) -> None:
    db = dbmod.get_session_factory()()
    from pinterest_automation.services.analytics_service import sync_published
    n = sync_published(db, lookback_days=days)
    print(f"synced {n} pins")


def cmd_report(kind: str) -> int:
    from datetime import date

    from pinterest_automation.services.reporting import daily_report, weekly_report, write_report

    db = dbmod.get_session_factory()()
    if kind == "weekly":
        rep = weekly_report(db, date.today())
    else:
        rep = daily_report(db, date.today())
    path = write_report(rep, kind)
    print(f"report written: {path}")
    return 0


def cmd_serve() -> None:
    import uvicorn
    uvicorn.run("pinterest_automation.dashboard.app:app", host="127.0.0.1", port=8000)


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
    return 1


if __name__ == "__main__":
    sys.exit(run())
