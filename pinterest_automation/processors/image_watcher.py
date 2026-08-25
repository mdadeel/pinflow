import hashlib
import logging
from pathlib import Path

from pinterest_automation.database.models import Pin

log = logging.getLogger(__name__)

EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


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
        batch.append(Pin(image_path=str(p.resolve()), image_hash=digest))
        existing.add(digest)
    if batch:
        db.add_all(batch)
        db.commit()
        log.info("ingested %d new images from %s", len(batch), folder)
    return len(batch)
