from datetime import datetime

import pytest

from wattnet.storage.clients.base import BaseStorageClient
from wattnet.storage.models import Metric, MetricType


class TestBaseStorageClientAbstract:
    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            BaseStorageClient()

    def test_missing_read_metrics_raises(self):
        class Incomplete(BaseStorageClient):
            def write_metrics(self, metrics):
                pass

        with pytest.raises(TypeError):
            Incomplete()

    def test_missing_write_metrics_raises(self):
        class Incomplete(BaseStorageClient):
            def read_metrics(self, metric_name, start=None, end=None, labels=None, params=None):
                return []

        with pytest.raises(TypeError):
            Incomplete()

    def test_abstract_methods_are_read_and_write(self):
        abstract = BaseStorageClient.__abstractmethods__
        assert "read_metrics" in abstract
        assert "write_metrics" in abstract


class TestConcreteClient:
    """Verify that a fully implemented subclass works correctly."""

    @pytest.fixture
    def client(self):
        class ConcreteClient(BaseStorageClient):
            def read_metrics(self, metric_name, start=None, end=None, labels=None, params=None):
                return []

            def write_metrics(self, metrics):
                pass

        return ConcreteClient()

    def test_instantiation_succeeds(self, client):
        assert client is not None

    def test_read_metrics_returns_list(self, client):
        result = client.read_metrics("zone_generation")
        assert isinstance(result, list)

    def test_write_metrics_returns_none(self, client):
        m = Metric(MetricType.ZONE_GENERATION, 1.0)
        assert client.write_metrics([m]) is None

    def test_is_instance_of_base(self, client):
        assert isinstance(client, BaseStorageClient)

    def test_read_metrics_accepts_all_params(self, client):
        result = client.read_metrics(
            metric_name="zone_generation",
            start=datetime(2024, 1, 1),
            end=datetime(2024, 1, 2),
            labels={"zone": "ES"},
            params={"extra": True},
        )
        assert result == []


class TestAbstractMethodBodies:
    """The abstract methods have a pass body callable via super()."""

    @pytest.fixture
    def super_caller(self):
        class SuperCaller(BaseStorageClient):
            def read_metrics(
                self, metric_name, start=None, end=None, labels=None, params=None
            ):
                return super().read_metrics(metric_name, start, end, labels, params)

            def write_metrics(self, metrics):
                return super().write_metrics(metrics)

        return SuperCaller()

    def test_super_read_metrics_returns_none(self, super_caller):
        assert super_caller.read_metrics("zone_generation") is None

    def test_super_write_metrics_returns_none(self, super_caller):
        assert super_caller.write_metrics([]) is None
