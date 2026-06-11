from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from wattnet.storage.clients.plugins.clickhouse import (
    COLUMN_NAME_MAP,
    REVERSE_COLUMN_NAME_MAP,
    TABLE_SCHEMAS,
    ClickHouseClient,
    ClickHouseConfig,
)
from wattnet.storage.config import StorageConfig
from wattnet.storage.models import Metric, MetricType


def _make_config(**kwargs) -> StorageConfig:
    ch_kwargs = {
        "host": kwargs.pop("clickhouse_host", "localhost"),
        "port": kwargs.pop("clickhouse_port", 8123),
        "user": kwargs.pop("clickhouse_user", "default"),
        "password": kwargs.pop("clickhouse_password", ""),
        "database": kwargs.pop("database", "test"),
    }
    return StorageConfig(
        timeseries_step_minutes=kwargs.pop("timeseries_step_minutes", 15),
        plugin_configs={"clickhouse": ch_kwargs},
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_ch_connect():
    """Patch clickhouse_connect.get_client globally so no real DB is needed."""
    mock_client = MagicMock()
    with patch("clickhouse_connect.get_client", return_value=mock_client):
        yield mock_client


@pytest.fixture
def ch(mock_ch_connect):
    """ClickHouseClient with mocked DB; flush thread stopped after test."""
    client = ClickHouseClient(config=_make_config())
    yield client
    client._stop_event.set()
    client._flush_thread.join(timeout=1)


# ---------------------------------------------------------------------------
# TABLE_SCHEMAS
# ---------------------------------------------------------------------------


class TestTableSchemas:
    def test_all_non_unknown_metric_types_have_table(self):
        known = {mt.value for mt in MetricType if mt != MetricType.UNKNOWN}
        assert known.issubset(set(TABLE_SCHEMAS.keys()))

    def test_each_table_has_timestamp_first(self):
        for name, cols in TABLE_SCHEMAS.items():
            assert cols[0][0] == "timestamp", f"{name}: first col is not timestamp"

    def test_each_table_has_value_second(self):
        for name, cols in TABLE_SCHEMAS.items():
            assert cols[1][0] == "value", f"{name}: second col is not value"

    def test_each_table_has_updated_at(self):
        for name, cols in TABLE_SCHEMAS.items():
            col_names = [c[0] for c in cols]
            assert "updated_at" in col_names, f"{name}: missing updated_at"

    def test_value_column_type_is_float32(self):
        for name, cols in TABLE_SCHEMAS.items():
            assert cols[1][1] == "Float32", f"{name}: value is not Float32"

    def test_zone_generation_has_zone_column(self):
        cols = [c[0] for c in TABLE_SCHEMAS["zone_generation"]]
        assert "zone" in cols

    def test_zone_import_has_from_zone(self):
        cols = [c[0] for c in TABLE_SCHEMAS["zone_import"]]
        assert "from_zone" in cols

    def test_zone_export_has_to_zone(self):
        cols = [c[0] for c in TABLE_SCHEMAS["zone_export"]]
        assert "to_zone" in cols

    def test_factor_has_nullable_year(self):
        col_map = dict(TABLE_SCHEMAS["factor"])
        assert col_map.get("year") == "Nullable(Int32)"


# ---------------------------------------------------------------------------
# COLUMN_NAME_MAP / REVERSE_COLUMN_NAME_MAP
# ---------------------------------------------------------------------------


class TestColumnNameMap:
    def test_from_maps_to_from_zone(self):
        assert COLUMN_NAME_MAP["from"] == "from_zone"

    def test_to_maps_to_to_zone(self):
        assert COLUMN_NAME_MAP["to"] == "to_zone"

    def test_reverse_from_zone_to_from(self):
        assert REVERSE_COLUMN_NAME_MAP["from_zone"] == "from"

    def test_reverse_to_zone_to_to(self):
        assert REVERSE_COLUMN_NAME_MAP["to_zone"] == "to"

    def test_roundtrip_forward_then_reverse(self):
        for k, v in COLUMN_NAME_MAP.items():
            assert REVERSE_COLUMN_NAME_MAP[v] == k

    def test_roundtrip_reverse_then_forward(self):
        for k, v in REVERSE_COLUMN_NAME_MAP.items():
            assert COLUMN_NAME_MAP[v] == k


# ---------------------------------------------------------------------------
# _align_floor
# ---------------------------------------------------------------------------


class TestAlignFloor:
    def test_already_aligned_unchanged(self, ch):
        dt = datetime(2024, 1, 1, 12, 0, 0)
        assert ch._align_floor(dt) == dt

    def test_rounds_down_to_previous_interval(self, ch):
        dt = datetime(2024, 1, 1, 12, 5, 0)
        expected = datetime(2024, 1, 1, 12, 0, 0)
        assert ch._align_floor(dt) == expected

    def test_14_minutes_59_seconds_floors_to_0(self, ch):
        dt = datetime(2024, 1, 1, 12, 14, 59)
        expected = datetime(2024, 1, 1, 12, 0, 0)
        assert ch._align_floor(dt) == expected

    def test_seconds_stripped(self, ch):
        dt = datetime(2024, 1, 1, 12, 0, 45)
        expected = datetime(2024, 1, 1, 12, 0, 0)
        assert ch._align_floor(dt) == expected

    def test_microseconds_stripped(self, ch):
        dt = datetime(2024, 1, 1, 12, 0, 0, 999999)
        expected = datetime(2024, 1, 1, 12, 0, 0)
        assert ch._align_floor(dt) == expected

    def test_30_minute_interval(self, mock_ch_connect):
        client = ClickHouseClient(config=_make_config(timeseries_step_minutes=30))
        try:
            dt = datetime(2024, 1, 1, 12, 20, 0)
            assert client._align_floor(dt) == datetime(2024, 1, 1, 12, 0, 0)
        finally:
            client._stop_event.set()
            client._flush_thread.join(timeout=1)

    def test_60_minute_interval(self, mock_ch_connect):
        client = ClickHouseClient(config=_make_config(timeseries_step_minutes=60))
        try:
            dt = datetime(2024, 1, 1, 12, 45, 30)
            assert client._align_floor(dt) == datetime(2024, 1, 1, 12, 0, 0)
        finally:
            client._stop_event.set()
            client._flush_thread.join(timeout=1)

    def test_preserves_timezone(self, ch):
        dt = datetime(2024, 1, 1, 12, 7, 0, tzinfo=timezone.utc)
        result = ch._align_floor(dt)
        assert result.tzinfo == timezone.utc
        assert result == datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# _resolve_time_range
# ---------------------------------------------------------------------------


class TestResolveTimeRange:
    INTERVAL = timedelta(minutes=15)

    def test_none_none_returns_one_bucket_from_now(self, ch):
        now = datetime(2024, 1, 1, 12, 7, 0, tzinfo=timezone.utc)
        start, end = ch._resolve_time_range(None, None, now=now)
        assert start == datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        assert end == start + self.INTERVAL

    def test_none_end_returns_one_bucket_from_floor_end(self, ch):
        end = datetime(2024, 1, 1, 12, 10, 0)
        start, result_end = ch._resolve_time_range(None, end)
        assert start == datetime(2024, 1, 1, 12, 0, 0)
        assert result_end == start + self.INTERVAL

    def test_start_none_returns_one_bucket_from_floor_start(self, ch):
        start = datetime(2024, 1, 1, 12, 10, 0)
        result_start, end = ch._resolve_time_range(start, None)
        assert result_start == datetime(2024, 1, 1, 12, 0, 0)
        assert end == result_start + self.INTERVAL

    def test_exact_boundaries_preserved(self, ch):
        start = datetime(2024, 1, 1, 12, 0, 0)
        end = datetime(2024, 1, 1, 12, 30, 0)
        result_start, result_end = ch._resolve_time_range(start, end)
        assert result_start == start
        assert result_end == end

    def test_end_not_on_boundary_expands_to_include_bucket(self, ch):
        start = datetime(2024, 1, 1, 12, 0, 0)
        end = datetime(2024, 1, 1, 12, 20, 0)  # falls in 12:15 bucket
        result_start, result_end = ch._resolve_time_range(start, end)
        assert result_start == datetime(2024, 1, 1, 12, 0, 0)
        assert result_end == datetime(2024, 1, 1, 12, 30, 0)

    def test_same_bucket_forces_one_bucket(self, ch):
        start = datetime(2024, 1, 1, 12, 5, 0)
        end = datetime(2024, 1, 1, 12, 10, 0)
        result_start, result_end = ch._resolve_time_range(start, end)
        assert result_start == datetime(2024, 1, 1, 12, 0, 0)
        assert result_end == datetime(2024, 1, 1, 12, 15, 0)

    def test_start_equals_end_on_boundary_forces_one_bucket(self, ch):
        ts = datetime(2024, 1, 1, 12, 0, 0)
        result_start, result_end = ch._resolve_time_range(ts, ts)
        assert result_end == result_start + self.INTERVAL

    def test_multi_bucket_range(self, ch):
        start = datetime(2024, 1, 1, 12, 0, 0)
        end = datetime(2024, 1, 1, 13, 0, 0)
        result_start, result_end = ch._resolve_time_range(start, end)
        assert result_start == start
        assert result_end == end
        # 4 buckets of 15 min = 1 hour
        assert (result_end - result_start) == timedelta(hours=1)

    def test_result_always_has_end_greater_than_start(self, ch):
        cases = [
            (None, None),
            (datetime(2024, 1, 1, 12, 5), None),
            (None, datetime(2024, 1, 1, 12, 5)),
            (datetime(2024, 1, 1, 12, 0), datetime(2024, 1, 1, 12, 30)),
        ]
        for start, end in cases:
            now = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
            rs, re = ch._resolve_time_range(start, end, now=now)
            assert re > rs


# ---------------------------------------------------------------------------
# _build_query
# ---------------------------------------------------------------------------


class TestBuildQuery:
    def test_returns_tuple_of_sql_and_params(self, ch):
        start = datetime(2024, 1, 1, 12, 0, 0)
        end = datetime(2024, 1, 1, 12, 15, 0)
        result = ch._build_query("zone_generation", start, end)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_sql_contains_table_name(self, ch):
        start = datetime(2024, 1, 1, 12, 0)
        end = datetime(2024, 1, 1, 12, 15)
        sql, _ = ch._build_query("zone_generation", start, end)
        assert "zone_generation" in sql

    def test_sql_contains_where_timestamp(self, ch):
        start = datetime(2024, 1, 1, 12, 0)
        end = datetime(2024, 1, 1, 12, 15)
        sql, _ = ch._build_query("zone_generation", start, end)
        assert "WHERE timestamp" in sql

    def test_sql_contains_order_by(self, ch):
        start = datetime(2024, 1, 1, 12, 0)
        end = datetime(2024, 1, 1, 12, 15)
        sql, _ = ch._build_query("zone_generation", start, end)
        assert "ORDER BY timestamp ASC" in sql

    def test_params_contain_start_and_end(self, ch):
        start = datetime(2024, 1, 1, 12, 0, 0)
        end = datetime(2024, 1, 1, 12, 15, 0)
        _, params = ch._build_query("zone_generation", start, end)
        assert "start" in params
        assert "end" in params

    def test_params_start_formatted_correctly(self, ch):
        start = datetime(2024, 6, 15, 8, 30, 0)
        end = datetime(2024, 6, 15, 8, 45, 0)
        _, params = ch._build_query("zone_generation", start, end)
        assert params["start"] == "2024-06-15 08:30:00"

    def test_no_labels_no_extra_and_clause(self, ch):
        start = datetime(2024, 1, 1, 12, 0)
        end = datetime(2024, 1, 1, 12, 15)
        sql, params = ch._build_query("zone_generation", start, end)
        assert "label_" not in sql
        assert len(params) == 2  # only start and end

    def test_valid_label_adds_and_clause(self, ch):
        start = datetime(2024, 1, 1, 12, 0)
        end = datetime(2024, 1, 1, 12, 15)
        sql, params = ch._build_query(
            "zone_generation", start, end, labels={"zone": "ES"}
        )
        assert "zone" in sql
        assert "label_zone" in params
        assert params["label_zone"] == "ES"

    def test_invalid_label_not_in_schema_is_skipped(self, ch):
        start = datetime(2024, 1, 1, 12, 0)
        end = datetime(2024, 1, 1, 12, 15)
        sql, params = ch._build_query(
            "zone_generation", start, end, labels={"not_a_column": "value"}
        )
        assert "not_a_column" not in sql
        assert len(params) == 2

    def test_from_label_mapped_to_from_zone_in_sql(self, ch):
        start = datetime(2024, 1, 1, 12, 0)
        end = datetime(2024, 1, 1, 12, 15)
        sql, params = ch._build_query("zone_import", start, end, labels={"from": "ES"})
        assert "from_zone" in sql
        assert "label_from_zone" in params

    def test_sql_uses_final_keyword(self, ch):
        start = datetime(2024, 1, 1, 12, 0)
        end = datetime(2024, 1, 1, 12, 15)
        sql, _ = ch._build_query("zone_generation", start, end)
        assert "FINAL" in sql


# ---------------------------------------------------------------------------
# _build_row
# ---------------------------------------------------------------------------


class TestBuildRow:
    def _metric(self, mt=MetricType.ZONE_GENERATION, value=10.0, metadata=None):
        ts = datetime(2024, 1, 1, 12, 0, 0)
        m = Metric(mt, value, timestamp=ts, metadata=metadata or {})
        return m

    def test_row_length_matches_schema(self, ch):
        m = self._metric()
        row = ch._build_row("zone_generation", m)
        assert len(row) == len(TABLE_SCHEMAS["zone_generation"])

    def test_first_column_is_timestamp(self, ch):
        ts = datetime(2024, 6, 1, 10, 0, 0)
        m = Metric(MetricType.ZONE_GENERATION, 1.0, timestamp=ts)
        row = ch._build_row("zone_generation", m)
        assert row[0] == ts

    def test_second_column_is_float_value(self, ch):
        m = self._metric(value=42.5)
        row = ch._build_row("zone_generation", m)
        assert row[1] == 42.5
        assert isinstance(row[1], float)

    def test_updated_at_is_datetime(self, ch):
        m = self._metric()
        row = ch._build_row("zone_generation", m)
        col_names = [c[0] for c in TABLE_SCHEMAS["zone_generation"]]
        idx = col_names.index("updated_at")
        assert isinstance(row[idx], datetime)

    def test_metadata_mapped_to_correct_column(self, ch):
        m = self._metric(metadata={"zone": "ES"})
        row = ch._build_row("zone_generation", m)
        col_names = [c[0] for c in TABLE_SCHEMAS["zone_generation"]]
        idx = col_names.index("zone")
        assert row[idx] == "ES"

    def test_missing_string_metadata_defaults_to_empty_string(self, ch):
        m = self._metric(metadata={})  # no zone
        row = ch._build_row("zone_generation", m)
        col_names = [c[0] for c in TABLE_SCHEMAS["zone_generation"]]
        idx = col_names.index("zone")
        assert row[idx] == ""

    def test_missing_nullable_int_defaults_to_none(self, ch):
        m = Metric(MetricType.FACTOR, 1.0)
        row = ch._build_row("factor", m)
        col_names = [c[0] for c in TABLE_SCHEMAS["factor"]]
        idx = col_names.index("year")
        assert row[idx] is None

    def test_from_zone_column_reads_from_key_in_metadata(self, ch):
        m = Metric(MetricType.ZONE_IMPORT, 1.0, metadata={"from": "ES"})
        row = ch._build_row("zone_import", m)
        col_names = [c[0] for c in TABLE_SCHEMAS["zone_import"]]
        idx = col_names.index("from_zone")
        assert row[idx] == "ES"

    def test_string_timestamp_parsed(self, ch):
        m = self._metric()
        m.timestamp = "2024-01-01T12:00:00"
        row = ch._build_row("zone_generation", m)
        assert isinstance(row[0], datetime)


# ---------------------------------------------------------------------------
# write_metrics
# ---------------------------------------------------------------------------


class TestWriteMetrics:
    def test_empty_list_returns_immediately(self, ch):
        ch.write_metrics([])
        assert all(len(v) == 0 for v in ch._buffer.values())

    def test_unknown_table_name_skipped(self, ch):
        m = Metric(MetricType.UNKNOWN, 1.0)
        ch.write_metrics([m])
        assert "unknown" not in ch._buffer

    def test_single_valid_metric_added_to_buffer(self, ch):
        m = Metric(MetricType.ZONE_GENERATION, 5.0)
        ch.write_metrics([m])
        assert len(ch._buffer["zone_generation"]) == 1

    def test_multiple_metrics_same_table_added_to_buffer(self, ch):
        metrics = [Metric(MetricType.ZONE_GENERATION, float(i)) for i in range(5)]
        ch.write_metrics(metrics)
        assert len(ch._buffer["zone_generation"]) == 5

    def test_metrics_different_tables_added_to_correct_buffers(self, ch):
        m_gen = Metric(MetricType.ZONE_GENERATION, 1.0)
        m_load = Metric(MetricType.ZONE_LOAD, 2.0)
        ch.write_metrics([m_gen, m_load])
        assert len(ch._buffer["zone_generation"]) == 1
        assert len(ch._buffer["zone_load"]) == 1

    def test_oversized_buffer_triggers_immediate_flush(self, ch):
        with patch.object(ch, "_flush_table") as mock_flush:
            metrics = [
                Metric(MetricType.ZONE_GENERATION, float(i))
                for i in range(ClickHouseClient._FLUSH_MAX_ROWS + 1)
            ]
            ch.write_metrics(metrics)
            mock_flush.assert_called_once_with(
                "zone_generation", mock_flush.call_args[0][1]
            )
            # After immediate flush, buffer for that table is empty
            assert (
                "zone_generation" not in ch._buffer
                or len(ch._buffer["zone_generation"]) == 0
            )

    def test_immediate_flush_exception_does_not_propagate(self, ch):
        with patch.object(ch, "_flush_table", side_effect=RuntimeError("write error")):
            metrics = [
                Metric(MetricType.ZONE_GENERATION, float(i))
                for i in range(ClickHouseClient._FLUSH_MAX_ROWS + 1)
            ]
            ch.write_metrics(metrics)  # must not raise


# ---------------------------------------------------------------------------
# _resolve_time_range — error paths
# ---------------------------------------------------------------------------


class TestResolveTimeRangeErrors:
    def test_inverted_range_raises_value_error(self, ch):
        start = datetime(2024, 1, 1, 13, 0, 0, tzinfo=timezone.utc)
        end = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        with pytest.raises(ValueError, match="empty or inverted"):
            ch._resolve_time_range(start, end)


class TestClickHouseConfig:
    def test_default_port_is_8123(self, monkeypatch):
        monkeypatch.delenv("CLICKHOUSE_PORT", raising=False)
        assert ClickHouseConfig().port == 8123

    def test_default_host_is_localhost(self, monkeypatch):
        monkeypatch.delenv("CLICKHOUSE_HOST", raising=False)
        assert ClickHouseConfig().host == "localhost"

    def test_env_var_overrides_port(self, monkeypatch):
        monkeypatch.setenv("CLICKHOUSE_PORT", "9000")
        assert ClickHouseConfig().port == 9000

    def test_default_connect_retries_is_5(self, monkeypatch):
        monkeypatch.delenv("CLICKHOUSE_CONNECT_RETRIES", raising=False)
        assert ClickHouseConfig().connect_retries == 5

    def test_default_connect_retry_delay_is_3(self, monkeypatch):
        monkeypatch.delenv("CLICKHOUSE_CONNECT_RETRY_DELAY", raising=False)
        assert ClickHouseConfig().connect_retry_delay == 3

    def test_env_var_overrides_connect_retries(self, monkeypatch):
        monkeypatch.setenv("CLICKHOUSE_CONNECT_RETRIES", "10")
        assert ClickHouseConfig().connect_retries == 10

    def test_env_var_overrides_connect_retry_delay(self, monkeypatch):
        monkeypatch.setenv("CLICKHOUSE_CONNECT_RETRY_DELAY", "7")
        assert ClickHouseConfig().connect_retry_delay == 7


# ---------------------------------------------------------------------------
# _build_query — validation
# ---------------------------------------------------------------------------


class TestBuildQueryValidation:
    def test_unknown_table_raises_value_error(self, ch):
        with pytest.raises(ValueError, match="Unknown metric table"):
            ch._build_query(
                "nonexistent_table",
                datetime(2024, 1, 1, 12, 0),
                datetime(2024, 1, 1, 12, 15),
            )


# ---------------------------------------------------------------------------
# _flush_all — exception handler
# ---------------------------------------------------------------------------


class TestFlushAll:
    def test_flush_table_exception_is_logged_not_raised(self, ch):
        ch._stop_event.set()
        ch._flush_thread.join(timeout=1)
        ch._buffer["zone_generation"].append(["dummy_row"])
        with patch.object(ch, "_flush_table", side_effect=RuntimeError("db error")):
            ch._flush_all()  # must not raise


# ---------------------------------------------------------------------------
# _flush_loop
# ---------------------------------------------------------------------------


class TestFlushLoop:
    def test_loop_body_executes_before_stop(self, mock_ch_connect):
        client = ClickHouseClient(config=_make_config())
        client._stop_event.set()
        client._flush_thread.join(timeout=1)

        calls = []
        with patch.object(client, "_flush_all", side_effect=lambda: calls.append(1)):
            with patch.object(client._stop_event, "wait", side_effect=[False, True]):
                client._flush_loop()

        # First call from loop body, second from final-flush-on-shutdown
        assert len(calls) == 2


# ---------------------------------------------------------------------------
# flush()
# ---------------------------------------------------------------------------


class TestFlush:
    def test_flush_stops_flush_thread(self, ch):
        ch.flush()
        assert not ch._flush_thread.is_alive()

    def test_flush_sets_stop_event(self, ch):
        ch.flush()
        assert ch._stop_event.is_set()


# ---------------------------------------------------------------------------
# read_metrics
# ---------------------------------------------------------------------------


class TestReadMetrics:
    def test_empty_dataframe_returns_empty_list(self, ch, mock_ch_connect):
        import pandas as pd

        mock_ch_connect.query_df.return_value = pd.DataFrame()
        result = ch.read_metrics(
            "zone_generation",
            start=datetime(2024, 1, 1, 12, 0),
            end=datetime(2024, 1, 1, 12, 15),
        )
        assert result == []

    def test_returns_metric_objects(self, ch, mock_ch_connect):
        import pandas as pd

        df = pd.DataFrame(
            {
                "timestamp": [pd.Timestamp("2024-01-01 12:00:00")],
                "value": [42.5],
                "zone": ["ES"],
            }
        )
        mock_ch_connect.query_df.return_value = df
        result = ch.read_metrics(
            "zone_generation",
            start=datetime(2024, 1, 1, 12, 0),
            end=datetime(2024, 1, 1, 12, 15),
        )
        assert len(result) == 1
        assert isinstance(result[0], Metric)

    def test_value_rounded_to_two_decimals(self, ch, mock_ch_connect):
        import pandas as pd

        df = pd.DataFrame(
            {
                "timestamp": [pd.Timestamp("2024-01-01 12:00:00")],
                "value": [42.567],
            }
        )
        mock_ch_connect.query_df.return_value = df
        result = ch.read_metrics(
            "zone_generation",
            start=datetime(2024, 1, 1, 12, 0),
            end=datetime(2024, 1, 1, 12, 15),
        )
        assert result[0].value == 42.57

    def test_timestamp_gets_utc_timezone(self, ch, mock_ch_connect):
        import pandas as pd

        df = pd.DataFrame(
            {
                "timestamp": [pd.Timestamp("2024-01-01 12:00:00")],
                "value": [1.0],
            }
        )
        mock_ch_connect.query_df.return_value = df
        result = ch.read_metrics(
            "zone_generation",
            start=datetime(2024, 1, 1, 12, 0),
            end=datetime(2024, 1, 1, 12, 15),
        )
        assert result[0].timestamp.tzinfo == timezone.utc

    def test_from_zone_column_reversed_to_from_in_metadata(self, ch, mock_ch_connect):
        import pandas as pd

        df = pd.DataFrame(
            {
                "timestamp": [pd.Timestamp("2024-01-01 12:00:00")],
                "value": [1.0],
                "from_zone": ["ES"],
            }
        )
        mock_ch_connect.query_df.return_value = df
        result = ch.read_metrics(
            "zone_import",
            start=datetime(2024, 1, 1, 12, 0),
            end=datetime(2024, 1, 1, 12, 15),
        )
        assert result[0].metadata.get("from") == "ES"

    def test_year_field_converted_to_int(self, ch, mock_ch_connect):
        import pandas as pd

        df = pd.DataFrame(
            {
                "timestamp": [pd.Timestamp("2024-01-01 12:00:00")],
                "value": [1.0],
                "year": [2024],
            }
        )
        mock_ch_connect.query_df.return_value = df
        result = ch.read_metrics(
            "factor",
            start=datetime(2024, 1, 1, 12, 0),
            end=datetime(2024, 1, 1, 12, 15),
        )
        assert result[0].metadata["year"] == 2024
        assert isinstance(result[0].metadata["year"], int)

    def test_year_field_invalid_becomes_none(self, ch, mock_ch_connect):
        import pandas as pd

        df = pd.DataFrame(
            {
                "timestamp": [pd.Timestamp("2024-01-01 12:00:00")],
                "value": [1.0],
                "year": ["not_a_year"],
            }
        )
        mock_ch_connect.query_df.return_value = df
        result = ch.read_metrics(
            "factor",
            start=datetime(2024, 1, 1, 12, 0),
            end=datetime(2024, 1, 1, 12, 15),
        )
        assert result[0].metadata["year"] is None

    def test_multiple_rows_all_deserialized(self, ch, mock_ch_connect):
        import pandas as pd

        df = pd.DataFrame(
            {
                "timestamp": [
                    pd.Timestamp("2024-01-01 12:00:00"),
                    pd.Timestamp("2024-01-01 12:15:00"),
                ],
                "value": [1.0, 2.0],
            }
        )
        mock_ch_connect.query_df.return_value = df
        result = ch.read_metrics(
            "zone_generation",
            start=datetime(2024, 1, 1, 12, 0),
            end=datetime(2024, 1, 1, 12, 30),
        )
        assert len(result) == 2
        assert result[0].value == 1.0
        assert result[1].value == 2.0

    def test_metric_name_set_from_metric_name_arg(self, ch, mock_ch_connect):
        import pandas as pd

        df = pd.DataFrame(
            {
                "timestamp": [pd.Timestamp("2024-01-01 12:00:00")],
                "value": [1.0],
            }
        )
        mock_ch_connect.query_df.return_value = df
        result = ch.read_metrics(
            "zone_generation",
            start=datetime(2024, 1, 1, 12, 0),
            end=datetime(2024, 1, 1, 12, 15),
        )
        assert result[0].name == MetricType.ZONE_GENERATION.value


# ---------------------------------------------------------------------------
# Bootstrap retry logic
# ---------------------------------------------------------------------------


class TestBootstrapRetryLogic:
    """Tests for the connection retry loop in ClickHouseClient.__init__."""

    _SLEEP_PATH = "wattnet.storage.clients.plugins.clickhouse.time.sleep"

    def _retry_config(self, retries=3, delay=2):
        return StorageConfig(
            timeseries_step_minutes=15,
            plugin_configs={
                "clickhouse": {
                    "host": "localhost",
                    "port": 8123,
                    "user": "default",
                    "password": "",
                    "database": "test",
                    "connect_retries": retries,
                    "connect_retry_delay": delay,
                }
            },
        )

    def _make_client(self, config):
        client = ClickHouseClient(config=config)
        client._stop_event.set()
        client._flush_thread.join(timeout=1)
        return client

    def test_success_on_first_attempt_no_sleep(self):
        with patch("clickhouse_connect.get_client", return_value=MagicMock()):
            with patch(self._SLEEP_PATH) as mock_sleep:
                self._make_client(self._retry_config())
            mock_sleep.assert_not_called()

    def test_retries_until_success_sleeps_between_attempts(self):
        with patch("clickhouse_connect.get_client", return_value=MagicMock()):
            with patch(self._SLEEP_PATH) as mock_sleep:
                with patch.object(
                    ClickHouseClient,
                    "_bootstrap_schema",
                    side_effect=[Exception("fail"), None],
                ):
                    self._make_client(self._retry_config(retries=3, delay=5))
            mock_sleep.assert_called_once_with(5)

    def test_all_retries_exhausted_raises_runtime_error(self):
        with patch("clickhouse_connect.get_client", return_value=MagicMock()):
            with patch(self._SLEEP_PATH):
                with patch.object(
                    ClickHouseClient,
                    "_bootstrap_schema",
                    side_effect=Exception("connection refused"),
                ):
                    with pytest.raises(RuntimeError, match="after 3 attempts"):
                        self._make_client(self._retry_config(retries=3))

    def test_sleep_called_n_minus_one_times_on_total_failure(self):
        with patch("clickhouse_connect.get_client", return_value=MagicMock()):
            with patch(self._SLEEP_PATH) as mock_sleep:
                with patch.object(
                    ClickHouseClient,
                    "_bootstrap_schema",
                    side_effect=Exception("fail"),
                ):
                    with pytest.raises(RuntimeError):
                        self._make_client(self._retry_config(retries=4, delay=3))
            # 4 attempts → sleep only between attempts, not after the last one
            assert mock_sleep.call_count == 3

    def test_sleep_uses_configured_delay_on_every_retry(self):
        with patch("clickhouse_connect.get_client", return_value=MagicMock()):
            with patch(self._SLEEP_PATH) as mock_sleep:
                with patch.object(
                    ClickHouseClient,
                    "_bootstrap_schema",
                    side_effect=[Exception("fail"), Exception("fail"), None],
                ):
                    self._make_client(self._retry_config(retries=5, delay=9))
            assert all(call.args[0] == 9 for call in mock_sleep.call_args_list)

    def test_runtime_error_message_includes_host_and_port(self):
        with patch("clickhouse_connect.get_client", return_value=MagicMock()):
            with patch(self._SLEEP_PATH):
                with patch.object(
                    ClickHouseClient,
                    "_bootstrap_schema",
                    side_effect=Exception("fail"),
                ):
                    with pytest.raises(RuntimeError) as exc_info:
                        self._make_client(self._retry_config(retries=2))
            assert "localhost" in str(exc_info.value)
            assert "8123" in str(exc_info.value)

    def test_exception_chain_is_preserved_in_runtime_error(self):
        original = Exception("original connection error")
        with patch("clickhouse_connect.get_client", return_value=MagicMock()):
            with patch(self._SLEEP_PATH):
                with patch.object(
                    ClickHouseClient,
                    "_bootstrap_schema",
                    side_effect=original,
                ):
                    with pytest.raises(RuntimeError) as exc_info:
                        self._make_client(self._retry_config(retries=1))
            assert exc_info.value.__cause__ is original

    def test_plugin_config_connect_retries_respected(self):
        with patch("clickhouse_connect.get_client", return_value=MagicMock()):
            with patch(self._SLEEP_PATH) as mock_sleep:
                with patch.object(
                    ClickHouseClient,
                    "_bootstrap_schema",
                    side_effect=Exception("fail"),
                ):
                    with pytest.raises(RuntimeError, match="after 2 attempts"):
                        self._make_client(self._retry_config(retries=2))
            assert mock_sleep.call_count == 1

    def test_single_retry_raises_immediately_without_sleep(self):
        with patch("clickhouse_connect.get_client", return_value=MagicMock()):
            with patch(self._SLEEP_PATH) as mock_sleep:
                with patch.object(
                    ClickHouseClient,
                    "_bootstrap_schema",
                    side_effect=Exception("fail"),
                ):
                    with pytest.raises(RuntimeError):
                        self._make_client(self._retry_config(retries=1))
            mock_sleep.assert_not_called()
