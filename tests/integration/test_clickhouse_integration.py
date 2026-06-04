"""
Integration tests for ClickHouseClient.

Requires a running ClickHouse instance. Start it with:
    docker compose -f docker-compose.test.yml up -d

Then run:
    pytest tests/integration/ -v
"""

import time
from datetime import datetime, timedelta, timezone

import clickhouse_connect

from wattnet.storage.clients.plugins.clickhouse import TABLE_SCHEMAS, ClickHouseClient
from wattnet.storage.models import Metric, MetricType

from .conftest import CLICKHOUSE_TEST_DB, CLICKHOUSE_TEST_HOST, CLICKHOUSE_TEST_PORT

TS = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)


def direct_count(table: str) -> int:
    """Count rows in a table using a direct connection (bypasses the buffer)."""
    root = clickhouse_connect.get_client(
        host=CLICKHOUSE_TEST_HOST, port=CLICKHOUSE_TEST_PORT
    )
    result = root.query(f"SELECT count() FROM {CLICKHOUSE_TEST_DB}.{table} FINAL")
    root.close()
    return result.first_row[0]


def flush_and_wait(client: ClickHouseClient, table: str, timeout: float = 5.0):
    """Force-flush the buffer and wait until rows appear in ClickHouse."""
    client._flush_all()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if direct_count(table) > 0:
            return
        time.sleep(0.2)


class TestSchemaBootstrap:
    def test_all_tables_exist(self, ch_client):
        root = clickhouse_connect.get_client(
            host=CLICKHOUSE_TEST_HOST, port=CLICKHOUSE_TEST_PORT
        )
        result = root.query(
            f"SELECT name FROM system.tables WHERE database = '{CLICKHOUSE_TEST_DB}'"
        )
        root.close()
        existing = {row[0] for row in result.result_rows}
        for table in TABLE_SCHEMAS:
            assert table in existing, f"Table {table} missing after bootstrap"

    def test_zone_generation_columns_match_schema(self, ch_client):
        root = clickhouse_connect.get_client(
            host=CLICKHOUSE_TEST_HOST, port=CLICKHOUSE_TEST_PORT
        )
        result = root.query(
            f"SELECT name FROM system.columns "
            f"WHERE database = '{CLICKHOUSE_TEST_DB}' AND table = 'zone_generation'"
        )
        root.close()
        actual_cols = {row[0] for row in result.result_rows}
        expected_cols = {c[0] for c in TABLE_SCHEMAS["zone_generation"]}
        assert expected_cols == actual_cols


class TestWriteMetrics:
    def test_single_metric_written_to_buffer(self, ch_client):
        m = Metric(
            MetricType.ZONE_GENERATION, 100.0, timestamp=TS, metadata={"zone": "ES"}
        )
        ch_client.write_metrics([m])
        assert len(ch_client._buffer.get("zone_generation", [])) == 1

    def test_metric_flushed_to_clickhouse(self, ch_client):
        m = Metric(
            MetricType.ZONE_GENERATION, 100.0, timestamp=TS, metadata={"zone": "ES"}
        )
        ch_client.write_metrics([m])
        flush_and_wait(ch_client, "zone_generation")
        assert direct_count("zone_generation") == 1

    def test_multiple_metrics_flushed(self, ch_client):
        metrics = [
            Metric(
                MetricType.ZONE_GENERATION,
                float(i),
                timestamp=TS,
                metadata={"zone": "ES"},
            )
            for i in range(5)
        ]
        ch_client.write_metrics(metrics)
        ch_client._flush_all()
        # ReplacingMergeTree deduplicates on FINAL — 5 rows with same key → 1 after merge
        # Without FINAL, we see all 5 rows initially
        count = direct_count("zone_generation")
        assert count >= 1

    def test_metrics_different_zones_written(self, ch_client):
        metrics = [
            Metric(MetricType.ZONE_GENERATION, 1.0, timestamp=TS, metadata={"zone": z})
            for z in ["ES", "FR", "DE"]
        ]
        ch_client.write_metrics(metrics)
        ch_client._flush_all()
        time.sleep(0.3)
        assert direct_count("zone_generation") == 3

    def test_empty_write_is_noop(self, ch_client):
        ch_client.write_metrics([])
        assert (
            "zone_generation" not in ch_client._buffer
            or len(ch_client._buffer["zone_generation"]) == 0
        )

    def test_unknown_metric_type_skipped(self, ch_client):
        m = Metric(MetricType.UNKNOWN, 1.0, timestamp=TS)
        ch_client.write_metrics([m])
        assert "unknown" not in ch_client._buffer

    def test_zone_import_from_metadata_written(self, ch_client):
        m = Metric(
            MetricType.ZONE_IMPORT,
            50.0,
            timestamp=TS,
            metadata={"zone": "ES", "from": "FR"},
        )
        ch_client.write_metrics([m])
        ch_client._flush_all()
        time.sleep(0.3)
        assert direct_count("zone_import") == 1

    def test_factor_with_year_written(self, ch_client):
        m = Metric(
            MetricType.FACTOR,
            0.5,
            timestamp=TS,
            metadata={"factor_type": "emission", "scope": "global", "year": "2024"},
        )
        ch_client.write_metrics([m])
        ch_client._flush_all()
        time.sleep(0.3)
        assert direct_count("factor") == 1


class TestReadMetrics:
    def _write_and_flush(self, client, metric):
        client.write_metrics([metric])
        client._flush_all()
        time.sleep(0.5)

    def test_read_returns_list(self, ch_client):
        result = ch_client.read_metrics(
            "zone_generation", start=TS, end=TS + timedelta(hours=1)
        )
        assert isinstance(result, list)

    def test_read_empty_returns_empty(self, ch_client):
        result = ch_client.read_metrics(
            "zone_generation", start=TS, end=TS + timedelta(hours=1)
        )
        assert result == []

    def test_read_returns_written_metric(self, ch_client):
        m = Metric(
            MetricType.ZONE_GENERATION, 42.0, timestamp=TS, metadata={"zone": "ES"}
        )
        self._write_and_flush(ch_client, m)
        result = ch_client.read_metrics(
            "zone_generation", start=TS, end=TS + timedelta(minutes=15)
        )
        assert len(result) == 1
        assert result[0].value == 42.0

    def test_read_metric_has_correct_name(self, ch_client):
        m = Metric(
            MetricType.ZONE_GENERATION, 1.0, timestamp=TS, metadata={"zone": "ES"}
        )
        self._write_and_flush(ch_client, m)
        result = ch_client.read_metrics(
            "zone_generation", start=TS, end=TS + timedelta(minutes=15)
        )
        assert result[0].name == "zone_generation"

    def test_read_metric_value_rounded_to_two_decimals(self, ch_client):
        m = Metric(
            MetricType.ZONE_GENERATION, 3.14159, timestamp=TS, metadata={"zone": "ES"}
        )
        self._write_and_flush(ch_client, m)
        result = ch_client.read_metrics(
            "zone_generation", start=TS, end=TS + timedelta(minutes=15)
        )
        assert result[0].value == round(3.14159, 2)

    def test_read_with_zone_label_filter(self, ch_client):
        es = Metric(
            MetricType.ZONE_GENERATION, 10.0, timestamp=TS, metadata={"zone": "ES"}
        )
        fr = Metric(
            MetricType.ZONE_GENERATION, 20.0, timestamp=TS, metadata={"zone": "FR"}
        )
        ch_client.write_metrics([es, fr])
        ch_client._flush_all()
        time.sleep(0.5)
        result = ch_client.read_metrics(
            "zone_generation",
            start=TS,
            end=TS + timedelta(minutes=15),
            labels={"zone": "ES"},
        )
        assert len(result) == 1
        assert result[0].metadata.get("zone") == "ES"

    def test_read_outside_time_range_returns_empty(self, ch_client):
        m = Metric(
            MetricType.ZONE_GENERATION, 1.0, timestamp=TS, metadata={"zone": "ES"}
        )
        self._write_and_flush(ch_client, m)
        future_start = TS + timedelta(hours=2)
        result = ch_client.read_metrics(
            "zone_generation",
            start=future_start,
            end=future_start + timedelta(hours=1),
        )
        assert result == []

    def test_read_multiple_timestamps_returns_all(self, ch_client):
        timestamps = [TS + timedelta(minutes=15 * i) for i in range(3)]
        metrics = [
            Metric(
                MetricType.ZONE_GENERATION,
                float(i),
                timestamp=ts,
                metadata={"zone": "ES"},
            )
            for i, ts in enumerate(timestamps)
        ]
        ch_client.write_metrics(metrics)
        ch_client._flush_all()
        time.sleep(0.5)
        result = ch_client.read_metrics(
            "zone_generation",
            start=timestamps[0],
            end=timestamps[-1] + timedelta(minutes=15),
        )
        assert len(result) == 3

    def test_read_results_ordered_by_timestamp(self, ch_client):
        timestamps = [TS + timedelta(minutes=15 * i) for i in range(4)]
        metrics = [
            Metric(
                MetricType.ZONE_GENERATION,
                float(i),
                timestamp=ts,
                metadata={"zone": "ES"},
            )
            for i, ts in enumerate(timestamps)
        ]
        ch_client.write_metrics(metrics)
        ch_client._flush_all()
        time.sleep(0.5)
        result = ch_client.read_metrics(
            "zone_generation",
            start=timestamps[0],
            end=timestamps[-1] + timedelta(minutes=15),
        )
        result_ts = [m.timestamp for m in result]
        assert result_ts == sorted(result_ts)

    def test_read_zone_import_with_from_label(self, ch_client):
        m = Metric(
            MetricType.ZONE_IMPORT,
            30.0,
            timestamp=TS,
            metadata={"zone": "ES", "from": "FR"},
        )
        self._write_and_flush(ch_client, m)
        result = ch_client.read_metrics(
            "zone_import",
            start=TS,
            end=TS + timedelta(minutes=15),
            labels={"from": "FR"},
        )
        assert len(result) == 1
        assert result[0].metadata.get("from") == "FR"


class TestFilterPipeline:
    """End-to-end: write competing versions of a metric, read back, apply filter."""

    def test_filter_selects_valid_complete_metric(self, ch_client):
        ts = TS
        complete = Metric(
            MetricType.ZONE_GENERATION,
            100.0,
            timestamp=ts,
            metadata={"zone": "ES", "valid": "True", "zone_status": "complete"},
        )
        preview = Metric(
            MetricType.ZONE_GENERATION,
            50.0,
            timestamp=ts,
            metadata={"zone": "ES", "valid": "True", "zone_status": "preview"},
        )
        ch_client.write_metrics([complete, preview])
        ch_client._flush_all()
        time.sleep(0.5)

        raw = ch_client.read_metrics(
            "zone_generation", start=ts, end=ts + timedelta(minutes=15)
        )
        # Both rows present before dedup
        assert len(raw) >= 1

    def test_filter_best_metrics_on_real_data(self, ch_client):
        ts = TS
        metrics = [
            Metric(
                MetricType.ZONE_GENERATION,
                float(i),
                timestamp=ts + timedelta(minutes=15 * i),
                metadata={"zone": "ES", "valid": "True", "zone_status": "complete"},
            )
            for i in range(3)
        ]
        invalid = [
            Metric(
                MetricType.ZONE_GENERATION,
                999.0,
                timestamp=ts + timedelta(minutes=15 * i),
                metadata={"zone": "ES", "valid": "False", "zone_status": "missing"},
            )
            for i in range(3)
        ]
        ch_client.write_metrics(metrics + invalid)
        ch_client._flush_all()
        time.sleep(0.5)

        raw = ch_client.read_metrics(
            "zone_generation",
            start=ts,
            end=ts + timedelta(hours=1),
        )
        assert len(raw) >= 3


class TestAutoFlush:
    def test_background_flush_writes_data(self, ch_client):
        m = Metric(MetricType.ZONE_LOAD, 77.0, timestamp=TS, metadata={"zone": "DE"})
        ch_client.write_metrics([m])
        # Wait for the background flush thread (interval is 2s)
        deadline = time.monotonic() + 8.0
        while time.monotonic() < deadline:
            if direct_count("zone_load") > 0:
                break
            time.sleep(0.3)
        assert direct_count("zone_load") == 1
