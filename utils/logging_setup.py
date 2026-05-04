# forix/utils/logging_setup.py
"""
Forix — Logging Configuration
Writes rotating logs to E:\\System\\logs\\
"""

import logging
import logging.handlers
from pathlib import Path

from core.constants import LOGS_DIR


def setup_logging(level: int = logging.INFO):
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOGS_DIR / "forix.log"

    fmt = logging.Formatter(
        "[%(asctime)s] %(levelname)-8s %(name)-30s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Rotating file handler — 5 MB × 5 files
    fh = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    fh.setFormatter(fmt)
    fh.setLevel(level)

    # Console handler
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    ch.setLevel(logging.WARNING)

    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(fh)
    root.addHandler(ch)
