import hashlib
import pytest


@pytest.fixture
def db(tmp_path):
    from pinterest_automation.database.db import make_session_factory
    return make_session_factory(f"sqlite:///{tmp_path}/t.db")


def _img(path, content=b"x"):
    path.write_bytes(content)
    return path


def test_scan_inserts_and_dedups(db, tmp_path):
    from pinterest_automation.processors.image_watcher import scan_folder
    folder = tmp_path / "images"; folder.mkdir()
    _img(folder / "a.png", b"a")
    _img(folder / "b.jpg", b"b")
    _img(folder / "c.txt", b"c")                      # ignored extension
    (folder / "subdir").mkdir()
    _img(folder / "subdir" / "nested.png", b"n")      # not scanned (flat scan)
    with db() as s:
        added = scan_folder(folder, s)
        assert added == 2
        again = scan_folder(folder, s)                # second run: nothing new
        assert again == 0


def test_identical_content_different_name_skipped(db, tmp_path):
    from pinterest_automation.processors.image_watcher import scan_folder
    folder = tmp_path / "images"; folder.mkdir()
    _img(folder / "one.png", b"same-bytes")
    _img(folder / "two.png", b"same-bytes")           # same hash -> duplicate
    with db() as s:
        assert scan_folder(folder, s) == 1


def test_sha256_file_matches_hashlib(tmp_path):
    from pinterest_automation.processors.image_watcher import sha256_file
    p = _img(tmp_path / "x.png", b"hello")
    assert sha256_file(p) == hashlib.sha256(b"hello").hexdigest()


def test_rows_are_pending_with_resolved_paths(db, tmp_path):
    from pinterest_automation.database.models import Pin
    from pinterest_automation.processors.image_watcher import scan_folder
    folder = tmp_path / "images"; folder.mkdir()
    _img(folder / "a.png", b"data1")
    with db() as s:
        scan_folder(folder, s)
        row = s.query(Pin).one()
        assert row.status == "pending"
        assert str(tmp_path.resolve()) in row.image_path
