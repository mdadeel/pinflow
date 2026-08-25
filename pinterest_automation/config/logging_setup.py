import logging
import sys
from pathlib import Path


def setup_logging(log_dir: Path) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    # avoid duplicate handlers if called twice
    if root.handlers:
        return
    for h in (logging.FileHandler(log_dir / "app.log"), logging.StreamHandler(sys.stdout)):
        h.setFormatter(fmt)
        root.addHandler(h)
