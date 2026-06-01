"""
Centralized logging for Project F.R.I.D.A.Y.

Every module imports get_logger() from here instead of calling
logging.getLogger() directly with ad-hoc configuration.

Usage:
    from src.utils.logger import get_logger
    logger = get_logger("friday.brain")
"""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

from src.utils.constants import LOGS_DIR

LOG_FORMAT = "%(asctime)s | %(name)-30s | %(levelname)-8s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_configured = False


def setup_logging(level: str = "INFO", log_to_file: bool = True) -> None:
    """
    Configure the root logger with console + optional rotating file handler.

    Safe to call multiple times — subsequent calls are no-ops.
    """
    global _configured
    if _configured:
        return

    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Console handler
    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    root.addHandler(console)

    # Rotating file handler
    if log_to_file:
        log_dir = Path(LOGS_DIR)
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_dir / "friday.log",
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
        root.addHandler(file_handler)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """
    Return a named logger, ensuring setup_logging() has been called.

    Use this instead of logging.getLogger() everywhere in the codebase.
    """
    if not _configured:
        setup_logging()
    return logging.getLogger(name)
