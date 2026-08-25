import sqlite3


def test_new_columns_exist_on_fresh_db(tmp_path):
    from pinterest_automation.database.db import make_session_factory

    make_session_factory(f"sqlite:///{tmp_path}/t.db")
    con = sqlite3.connect(tmp_path / "t.db")
    cols = {r[1] for r in con.execute("PRAGMA table_info(pins)")}
    assert {"file_size", "width", "height"} <= cols


def test_migration_adds_columns_to_legacy_pins_table(tmp_path):
    """A hand-made legacy pins table gains tracked columns without crashing."""
    from pinterest_automation.database.db import make_session_factory

    p = tmp_path / "old.db"
    con = sqlite3.connect(p)
    con.execute("CREATE TABLE pins (id INTEGER PRIMARY KEY, image_path VARCHAR(500), image_hash VARCHAR(64))")
    con.commit()
    con.close()
    make_session_factory(f"sqlite:///{p}")
    con = sqlite3.connect(p)
    cols = {r[1] for r in con.execute("PRAGMA table_info(pins)")}
    assert {"file_size", "width", "height"} <= cols


def test_migration_noops_when_columns_present(tmp_path):
    from pinterest_automation.database.db import make_session_factory

    url = f"sqlite:///{tmp_path}/t.db"
    make_session_factory(url)
    make_session_factory(url)          # second call must not raise (duplicate ALTER)
    assert True


def test_pin_roundtrip_with_size_fields(tmp_path):
    from pinterest_automation.database.db import make_session_factory
    from pinterest_automation.database.models import Pin

    f = make_session_factory(f"sqlite:///{tmp_path}/t.db")
    with f() as s:
        s.add(Pin(image_path="/x.png", image_hash="h", file_size=123, width=800, height=600))
        s.commit()
        row = s.query(Pin).one()
        assert (row.file_size, row.width, row.height) == (123, 800, 600)


def test_image_dimensions_png(tmp_path):
    from PIL import Image

    from pinterest_automation.utils.media_types import image_dimensions

    p = tmp_path / "a.png"
    Image.new("RGB", (640, 360)).save(p)
    assert image_dimensions(p) == (640, 360)


def test_image_dimensions_jpeg(tmp_path):
    from PIL import Image

    from pinterest_automation.utils.media_types import image_dimensions

    p = tmp_path / "a.jpg"
    Image.new("RGB", (100, 50)).save(p)
    assert image_dimensions(p) == (100, 50)
