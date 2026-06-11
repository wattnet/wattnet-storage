"""wattnet-storage: Storage client for the Wattnet platform."""

from importlib.metadata import PackageNotFoundError, version

from wattnet.storage.config import StorageConfig
from wattnet.storage.repository.metrics_repository import MetricsRepository

try:
    __version__ = version("wattnet-storage")
except PackageNotFoundError:
    __version__ = "unknown"

__all__ = ["MetricsRepository", "StorageConfig"]
