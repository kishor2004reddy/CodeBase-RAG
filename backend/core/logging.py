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


# ── Format ────────────────────────────────────────────────────────────────────

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


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

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(numeric_level)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT))

    # Configure the root logger — all child loggers inherit this.
    root = logging.getLogger()
    root.setLevel(numeric_level)
    root.addHandler(handler)

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
