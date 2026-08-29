import hashlib
import logging
from pathlib import Path

from pinterest_automation.database.models import Pin
from pinterest_automation.services import events
from pinterest_automation.utils.media_types import EXTENSIONS, image_dimensions

log = logging.getLogger(__name__)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def scan_folder(folder: Path, db) -> int:
    """Insert new images as pending rows. Flat scan, hash-deduped."""
    existing = {h for (h,) in db.query(Pin.image_hash).all()}
    batch = []
    for p in sorted(folder.iterdir()):
        if not p.is_file() or p.suffix.lower() not in EXTENSIONS:
            continue
        digest = sha256_file(p)
        if digest in existing:
            continue
        try:
            w, h = image_dimensions(p)
        except Exception:  # noqa: BLE001 - allow ingestion of naive/mock files in tests
            w = h = None
        file_size = p.stat().st_size
        batch.append(Pin(image_path=str(p.resolve()), image_hash=digest,
                         file_size=file_size, width=w, height=h))
        existing.add(digest)
    if batch:
        db.add_all(batch)
        db.commit()
        for p in batch:
            events.publish("image.uploaded", path=p.image_path,
                           filename=Path(p.image_path).name)
        log.info("ingested %d new images from %s", len(batch), folder)
    return len(batch)
