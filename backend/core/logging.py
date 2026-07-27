"""
core/logging.py
---------------
Centralised logging configuration for CodeGraphRAG.

Usage (anywhere in the codebase):

    from core.logging import get_logger

    logger = get_logger(__name__)
    logger.info("Something happened")
    logger.warning("Watch out: %s", detail)
    logger.error("Failed to do X", exc_info=True)
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


# ── Format ────────────────────────────────────────────────────────────────────

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# ── Log file settings ────────────────────────────────────────────────────────

_LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
_LOG_FILE = _LOG_DIR / "app.log"
_MAX_BYTES = 5 * 1024 * 1024  # 5 MB per file
_BACKUP_COUNT = 5             # keep 5 rotated backups


# ── Internal flag — only configure root logger once ───────────────────────────

_configured = False


def configure_logging(level: str = "INFO") -> None:
    """
    Call this once at application startup (in main.py lifespan).

    Parameters
    ----------
    level : str
        Log level string from settings, e.g. "DEBUG", "INFO", "WARNING".
    """
    global _configured
    if _configured:
        return

    numeric_level = getattr(logging, level.upper(), logging.INFO)
    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    # ── Console handler (stdout) ──────────────────────────────────────────
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)

    # ── File handler (rotating) ───────────────────────────────────────────
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        _LOG_FILE,
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(numeric_level)
    file_handler.setFormatter(formatter)

    # Configure the root logger — all child loggers inherit this.
    root = logging.getLogger()
    root.setLevel(numeric_level)
    root.addHandler(console_handler)
    root.addHandler(file_handler)

    # Quieten noisy third-party libraries at WARNING unless we're in DEBUG.
    if numeric_level > logging.DEBUG:
        for noisy_lib in ("httpx", "httpcore", "urllib3", "asyncio"):
            logging.getLogger(noisy_lib).setLevel(logging.WARNING)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """
    Return a named logger.  Import and call this at module level:

        logger = get_logger(__name__)

    Parameters
    ----------
    name : str
        Typically ``__name__`` so log lines include the module path.
    """
    return logging.getLogger(name)
