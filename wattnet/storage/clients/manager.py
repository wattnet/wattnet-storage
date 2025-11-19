from datetime import datetime

from wattnet.storage.models import Metric
from wattnet.storage.settings import settings
from wattnet.storage.utils import log, plugin_loader

# Get logger
LOG = log.get(__name__)


class StorageClientsManager:

    def __init__(self):
        """Initialize the StorageClientsManager."""
        LOG.info("Initializing StorageClientsManager")

        # Get the list of available storage clients from config
        available_clients = settings.storage_clients

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
        self.storage_client_plugins = [
            (i, plugin_loader.get_storage_clients_extensions()[i])
            for i in available_clients
        ]
        LOG.info(
            f"Loaded storage client plugins: {[i[0] for i in self.storage_client_plugins]}"
        )

        # Start one instance of each storage client
        self.storage_clients = {}
        for client_name, client_plugin in self.storage_client_plugins:
            LOG.info(f"Starting storage client '{client_name}'")
            self.storage_clients[client_name] = client_plugin()
        LOG.info("Storage Client loaded: %s " % ",".join(self.storage_clients.keys()))

    def read_metrics(self, query: str, start: datetime, end: datetime) -> list[Metric]:
        """Read metrics from all storage clients.

        :param query: The query to read metrics
        :type query: str
        :param start: The start datetime
        :type start: datetime
        :param end: The end datetime
        :type end: datetime

        :return: The list of metrics read from all storage clients
        :rtype: list[Metric]
        """
        all_metrics = []
        for client_name, client in self.storage_clients.items():
            LOG.info(f"Reading metrics from storage client '{client_name}'")
            metrics = client.read_metrics(query=query, start=start, end=end)
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
