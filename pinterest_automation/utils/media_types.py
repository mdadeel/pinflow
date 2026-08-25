# single source of truth for supported image types (watcher, upload mime, vision mime)
EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}

from PIL import Image


def image_dimensions(path):
    """(width, height) via Pillow; caller guarantees a real image path."""
    with Image.open(path) as im:
        return im.size
