import queue
import tempfile
import unittest.mock as mock
from pathlib import Path
from types import SimpleNamespace

from pinterest_automation.database.db import make_session_factory
from pinterest_automation.database.models import Pin


def test_publish_delivers_to_subscribers_and_buffer():
    from pinterest_automation.services import events

    q = events.subscribe()
    try:
        evt = events.publish("pin.published", pin_id=7)
        assert evt["type"] == "pin.published"
        assert evt["payload"] == {"pin_id": 7}
        assert "at" in evt
        assert q.get_nowait() == evt
        assert evt in events.recent_events()
    finally:
        events.unsubscribe(q)


def test_unsubscribe_stops_delivery():
    from pinterest_automation.services import events

    q = events.subscribe()
    events.unsubscribe(q)
    events.publish("image.uploaded", path="/x.png", filename="x.png")
    assert q.empty()


def test_publish_never_raises_to_caller():
    from pinterest_automation.services import events

    class BadQueue(queue.Queue):
        def put_nowait(self, item):
            raise RuntimeError("boom")

    bad = BadQueue()
    with mock.patch.object(events, "_subs", [bad]):
        evt = events.publish("pin.scheduled", pin_id=1)  # must not raise
        assert evt["type"] == "pin.scheduled"


def test_recent_events_respects_limit_and_order():
    from pinterest_automation.services import events

    for i in range(5):
        events.publish("image.uploaded", path=f"/{i}.png", filename=f"{i}.png")
    recent = events.recent_events(limit=3)
    assert len(recent) == 3
    assert recent[0]["payload"]["path"] == "/2.png"  # oldest of the last 3 first


def test_uploader_publish_emits_pin_published():
    from pinterest_automation.processors import uploader
    from pinterest_automation.services import events

    with tempfile.TemporaryDirectory() as d:
        f = make_session_factory(f"sqlite:///{d}/t.db")
        img = Path(d) / "i.png"
        img.write_bytes(b"x")
        with f() as s:
            p = Pin(image_path=str(img), image_hash="h", status="scheduled",
                    title="T", description="D", board_name="B")
            s.add(p)
            s.commit()
            pid = p.id
        seen = []
        q = events.subscribe()
        try:
            with mock.patch.object(uploader, "get_boards",
                                   return_value=[{"id": "b1", "name": "B"}]), \
                 mock.patch.object(uploader, "create_pin",
                                   return_value={"id": "p9", "url": "u"}):
                with f() as s2:
                    pin = s2.get(Pin, pid)
                    uploader.publish_pin(s2, pin)
            while not q.empty():
                seen.append(q.get_nowait())
        finally:
            events.unsubscribe(q)
        types = [e["type"] for e in seen]
        assert "pin.published" in types


def test_analyzer_success_emits_metadata_generated():
    from pinterest_automation.services import analyzer, events

    m = SimpleNamespace(
        title="T", description="D", alt_text="A", primary_keyword="k",
        secondary_keywords=[], tags=[], board="B", category="c",
    )
    with tempfile.TemporaryDirectory() as d:
        f = make_session_factory(f"sqlite:///{d}/t.db")
        img = Path(d) / "i.jpg"
        img.write_bytes(b"x")
        with f() as s:
            s.add(Pin(image_path=str(img), image_hash="h1"))
            s.commit()
        seen = []
        q = events.subscribe()
        try:
            with mock.patch.object(analyzer, "generate_metadata", return_value=m):
                with f() as s2:
                    analyzer.analyze_pending(s2)
            while not q.empty():
                seen.append(q.get_nowait())
        finally:
            events.unsubscribe(q)
        types = [e["type"] for e in seen]
        assert "metadata.generated" in types
