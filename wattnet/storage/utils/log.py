"""Logging utilities with colorized console output and optional file handler."""

import logging

from wattnet.storage.settings import settings


class CustomFormatter(logging.Formatter):
    """Custom colorized formatter for console output."""

    COLORS = {
        logging.DEBUG: "\x1b[38;5;10m",  # green
        logging.INFO: "\x1b[38;5;39m",  # blue
        logging.WARNING: "\x1b[38;5;226m",  # yellow
        logging.ERROR: "\x1b[31;1m",  # bold red
        logging.CRITICAL: "\x1b[38;5;196m",  # red
    }
    RESET = "\x1b[0m"

    def __init__(self, fmt: str):
        """Initialize the formatter with a format string."""
        super().__init__()
        self.fmt = fmt

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record with ANSI color codes."""
        color = self.COLORS.get(record.levelno, self.RESET)
        formatter = logging.Formatter(
            color + self.fmt + self.RESET, datefmt="%d-%m-%Y %H:%M:%S"
        )
        return formatter.format(record)


def _get_level(level: str) -> int:
    """Return a logging level constant from string."""
    return getattr(logging, level.upper(), logging.INFO)


def get(name: str) -> logging.Logger:
    """Return a configured logger."""
    logger = logging.getLogger(name)
    logger.handlers.clear()  # prevent duplicate handlers

    # --- Base config ---
    fmt = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    level = _get_level(getattr(settings, "log_level", "INFO"))
    handlers = getattr(settings, "log_handlers", ["console"])
    logger.setLevel(level)

    # --- Console handler ---
    if "console" in handlers:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_handler.setFormatter(CustomFormatter(fmt))
        logger.addHandler(console_handler)

    # --- File handler ---
    if "file" in handlers and getattr(settings, "log_file", None):
        log_file = settings.log_file
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, mode="a")
        file_handler.setLevel(level)
        file_handler.setFormatter(logging.Formatter(fmt, datefmt="%d-%m-%Y %H:%M:%S"))
        logger.addHandler(file_handler)

    return logger
