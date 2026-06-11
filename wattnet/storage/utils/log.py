"""Logging utilities for wattnet-storage."""

import logging

logging.getLogger("wattnet.storage").addHandler(logging.NullHandler())


def get(name: str) -> logging.Logger:
    """Return a logger for the given name.

    Follows the standard library pattern: no handlers are added here.
    The consuming application is responsible for configuring handlers.
    """
    return logging.getLogger(name)
