"""Structured logging setup using the stdlib logging module + Rich handler."""
import logging
import sys

from rich.logging import RichHandler

_configured = False


def setup_logging(level: str = "INFO") -> None:
    global _configured
    if _configured:
        return
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True, show_path=False)],
        stream=sys.stderr,
    )
    _configured = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
