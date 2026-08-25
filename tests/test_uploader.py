import pytest

BOARDS = [{"id": "b1", "name": "Anime Board"}]


@pytest.fixture
def db(tmp_path):
    from pinterest_automation.database.db import make_session_factory
    return make_session_factory(f"sqlite:///{tmp_path}/t.db")


@pytest.fixture
def happy_pt(monkeypatch, tmp_path):
    from pinterest_automation.processors import uploader
    board_fetches = []
    monkeypatch.setattr(uploader, "get_boards", lambda token=None: board_fetches.append(1) or BOARDS)

    def fake_create(board_id, title, description, image_path, link=None, token=None):
        assert board_id == "b1"
        assert image_path.is_file()
        return {"id": "p9", "url": "https://pin.it/x"}

    monkeypatch.setattr(uploader, "create_pin", fake_create)
    img = tmp_path / "i.png"
    img.write_bytes(b"x")
    return img, board_fetches


def _scheduled_pin(db, img):
    from pinterest_automation.database.models import Pin
    with db() as s:
        p = Pin(image_path=str(img), image_hash="h", status="scheduled",
                title="T", description="D", board_name="Anime Board")
        s.add(p)
        s.commit()
        return p.id


def test_publish_success(db, happy_pt):
    from pinterest_automation.database.models import Pin
    from pinterest_automation.processors.uploader import publish_pin
    pid = _scheduled_pin(db, happy_pt[0])
    with db() as s:
        pin = s.get(Pin, pid)
        assert publish_pin(s, pin) is True
        assert pin.status == "published"
        assert pin.pin_id_str == "p9" and pin.pin_url == "https://pin.it/x"
        assert pin.published_time is not None
        assert pin.error_message is None


def test_no_board_mapping_fails(db, happy_pt):
    from pinterest_automation.database.models import Pin
    from pinterest_automation.processors.uploader import publish_pin
    pid = _scheduled_pin(db, happy_pt[0])
    with db() as s:
        pin = s.get(Pin, pid)
        pin.board_name = "Nonexistent Category"
        assert publish_pin(s, pin) is False
        assert pin.status == "failed"
        assert "board" in pin.error_message.lower()


def test_existing_board_id_skips_mapping(db, happy_pt, monkeypatch):
    from pinterest_automation.database.models import Pin
    from pinterest_automation.processors import uploader
    from pinterest_automation.processors.uploader import publish_pin
    pid = _scheduled_pin(db, happy_pt[0])
    with db() as s:
        pin = s.get(Pin, pid)
        pin.board_name = "Whatever"
        pin.board_id = "b1"

        created = {}

        def fake_create(board_id, *a, **k):
            created["board"] = board_id
            return {"id": "p", "url": "u"}

        monkeypatch.setattr(uploader, "create_pin", fake_create)
        assert publish_pin(s, pin) is True
        assert created["board"] == "b1"


def test_api_error_increments_retry_keeps_status(db, happy_pt, monkeypatch):
    from pinterest_automation.database.models import Pin
    from pinterest_automation.processors import uploader
    from pinterest_automation.processors.uploader import publish_pin
    monkeypatch.setattr(uploader, "get_boards", lambda token=None: BOARDS)
    monkeypatch.setattr(uploader, "create_pin",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    pid = _scheduled_pin(db, happy_pt[0])
    with db() as s:
        pin = s.get(Pin, pid)
        assert publish_pin(s, pin) is False
        assert pin.retry_count == 1
        assert pin.status == "scheduled"          # unchanged; scheduler may retry later
        assert "boom" in pin.error_message


def test_boards_arg_reused_not_refetched(db, happy_pt):
    """Passing a pre-fetched boards list must NOT call get_boards again."""
    from pinterest_automation.database.models import Pin
    from pinterest_automation.processors.uploader import publish_pin
    img, board_fetches = happy_pt
    pid = _scheduled_pin(db, img)
    with db() as s:
        pin = s.get(Pin, pid)
        assert publish_pin(s, pin, boards=BOARDS) is True
        assert board_fetches == []                # never fetched


def test_pinterest_error_recorded(db, happy_pt, monkeypatch):
    from pinterest_automation.api.pinterest import PinterestError
    from pinterest_automation.database.models import Pin
    from pinterest_automation.processors import uploader
    from pinterest_automation.processors.uploader import publish_pin
    monkeypatch.setattr(uploader, "get_boards", lambda token=None: BOARDS)

    def boom(*a, **k):
        raise PinterestError("403: denied")

    monkeypatch.setattr(uploader, "create_pin", boom)
    pid = _scheduled_pin(db, happy_pt[0])
    with db() as s:
        pin = s.get(Pin, pid)
        assert publish_pin(s, pin) is False
        assert "denied" in pin.error_message and pin.status == "scheduled"
