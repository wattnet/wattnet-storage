"""Configuration dataclass for wattnet-storage clients."""

from collections import Counter
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class StorageConfig:
    """Generic configuration for wattnet-storage.

    Only holds fields that are meaningful regardless of the storage backend.
    Plugin-specific settings (host, port, credentials, database, …) are owned
    by each plugin, which reads them from environment variables by default.
    Pass plugin_configs to override env vars programmatically (e.g. in tests).

    Example::

        StorageConfig(
            storage_clients=["clickhouse"],
            plugin_configs={"clickhouse": {"host": "myhost", "database": "mydb"}},
        )
    """

    timeseries_step_minutes: int = 15
    storage_clients: list[str] = field(default_factory=list)
    plugin_configs: dict[str, dict[str, Any]] = field(default_factory=dict)

    def __post_init__(self):
        """Validate fields after initialization."""
        if self.timeseries_step_minutes <= 0:
            raise ValueError(
                f"timeseries_step_minutes must be > 0, "
                f"got {self.timeseries_step_minutes}"
            )
        dupes = sorted(c for c, n in Counter(self.storage_clients).items() if n > 1)
        if dupes:
            raise ValueError(f"storage_clients contains duplicate entries: {dupes}")
