"""Storage clients manager: dispatches reads/writes to all configured clients."""

from datetime import datetime
from typing import Any

from wattnet.storage.config import StorageConfig
from wattnet.storage.models import Metric
from wattnet.storage.utils import log, plugin_loader

# Get logger
LOG = log.get(__name__)


class StorageClientsManager:
    """Manages a pool of storage client plugins and dispatches I/O to all of them."""

    def __init__(self, config: StorageConfig):
        """Initialize the StorageClientsManager."""
        LOG.info(
            "Initializing StorageClientsManager"
            " — clients=%s timeseries_step_minutes=%d",
            config.storage_clients,
            config.timeseries_step_minutes,
        )

        self.storage_clients: dict[str, Any] = {}

        # Get the list of available storage clients from config
        available_clients = config.storage_clients

        # Check that we have at least one storage client configured
        if not available_clients:
            LOG.error("No storage clients configured")
            return

        # Check if storage clients are installed
        for client in available_clients:
            if client not in plugin_loader.get_storage_clients_names():
                LOG.error(f"Storage client '{client}' is not installed")
                raise ImportError(f"Storage client '{client}' is not installed")

        # Load storage client extensions
        client_plugins = [
            (i, plugin_loader.get_storage_clients_extensions()[i])
            for i in available_clients
        ]
        plugin_names = [name for name, _ in client_plugins]
        LOG.info("Loaded storage client plugins: %s", plugin_names)

        # Start one instance of each storage client
        for client_name, client_plugin in client_plugins:
            LOG.info(f"Starting storage client '{client_name}'")
            self.storage_clients[client_name] = client_plugin(config)
        LOG.info("Storage Client loaded: %s " % ",".join(self.storage_clients.keys()))

    def read_metrics(
        self,
        metric_name: str,
        start: datetime | None = None,
        end: datetime | None = None,
        labels: dict | None = None,
        params: dict | None = None,
    ) -> list[Metric]:
        """Read metrics from all storage clients.

        :param metric_name: The name of the metric to read
        :type metric_name: str
        :param start: The start datetime for the query
        :type start: datetime, optional
        :param end: The end datetime for the query
        :type end: datetime, optional
        :param labels: Optional labels to filter the metrics
        :type labels: dict, optional
        :param params: Additional query parameters
        :type params: dict, optional

        :return: The list of metrics read from all storage clients
        :rtype: list[Metric]
        """
        all_metrics = []
        for client_name, client in self.storage_clients.items():
            LOG.info(f"Reading metrics from storage client '{client_name}'")
            metrics = client.read_metrics(metric_name, start, end, labels, params)
            all_metrics.extend(metrics)
        return all_metrics

    def write_metrics(self, metrics: list[Metric]) -> None:
        """Write metrics to all storage clients.

        :param metrics: The list of metrics to write
        :type metrics: list[Metric]
        """
        for client_name, client in self.storage_clients.items():
            LOG.info(f"Writing metrics to storage client '{client_name}'")
            client.write_metrics(metrics)
