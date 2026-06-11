"""ClickHouse storage client with buffered writes and Arrow-backed reads."""

import logging
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from threading import Event, Lock, Thread, current_thread, local
from typing import Any, List, cast

import clickhouse_connect
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from wattnet.storage.clients.base import BaseStorageClient
from wattnet.storage.config import StorageConfig
from wattnet.storage.models import Metric
from wattnet.storage.models.metric_type import MetricType

LOG = logging.getLogger(__name__)


class ClickHouseConfig(BaseSettings):
    """Configuration for the ClickHouse plugin.

    Reads the following environment variables (CLICKHOUSE_ prefix):
    - CLICKHOUSE_HOST      (default: localhost)
    - CLICKHOUSE_PORT      (default: 8123)
    - CLICKHOUSE_USER      (default: default)
    - CLICKHOUSE_PASSWORD  (default: "")
    - CLICKHOUSE_DATABASE  (default: wattnet)
    - CLICKHOUSE_CONNECT_RETRIES (default: 5)
    - CLICKHOUSE_CONNECT_RETRY_DELAY (default: 3)

    All values can be overridden programmatically via
    StorageConfig.plugin_configs["clickhouse"].
    """

    host: str = "localhost"
    port: int = 8123
    user: str = "default"
    password: str = ""
    database: str = "wattnet"
    connect_retries: int = Field(default=5, ge=1)
    connect_retry_delay: int = Field(default=3, ge=0)

    model_config = SettingsConfigDict(
        env_prefix="CLICKHOUSE_",
        extra="ignore",
    )


# -------------------------------------------------------------------
# Table column definitions
# Each table lists tuples: (column_name, clickhouse_type)
# -------------------------------------------------------------------
TABLE_SCHEMAS = {
    "zone_generation": [
        ("timestamp", "DateTime"),
        ("value", "Float32"),
        ("data_state", "LowCardinality(String)"),
        ("datasource", "LowCardinality(String)"),
        ("production_type", "LowCardinality(String)"),
        ("unit", "LowCardinality(String)"),
        ("valid", "LowCardinality(String)"),
        ("updated_at", "DateTime"),
        ("zone", "LowCardinality(String)"),
        ("zone_status", "LowCardinality(String)"),
    ],
    "zone_import": [
        ("timestamp", "DateTime"),
        ("value", "Float32"),
        ("data_state", "LowCardinality(String)"),
        ("datasource", "LowCardinality(String)"),
        ("from_zone", "LowCardinality(String)"),
        ("unit", "LowCardinality(String)"),
        ("valid", "LowCardinality(String)"),
        ("updated_at", "DateTime"),
        ("zone", "LowCardinality(String)"),
        ("zone_status", "LowCardinality(String)"),
    ],
    "zone_export": [
        ("timestamp", "DateTime"),
        ("value", "Float32"),
        ("data_state", "LowCardinality(String)"),
        ("datasource", "LowCardinality(String)"),
        ("to_zone", "LowCardinality(String)"),
        ("unit", "LowCardinality(String)"),
        ("valid", "LowCardinality(String)"),
        ("updated_at", "DateTime"),
        ("zone", "LowCardinality(String)"),
        ("zone_status", "LowCardinality(String)"),
    ],
    "zone_load": [
        ("timestamp", "DateTime"),
        ("value", "Float32"),
        ("data_state", "LowCardinality(String)"),
        ("datasource", "LowCardinality(String)"),
        ("unit", "LowCardinality(String)"),
        ("valid", "LowCardinality(String)"),
        ("updated_at", "DateTime"),
        ("zone", "LowCardinality(String)"),
        ("zone_status", "LowCardinality(String)"),
    ],
    "zone_mix_generation": [
        ("timestamp", "DateTime"),
        ("value", "Float32"),
        ("data_state", "LowCardinality(String)"),
        ("datasource", "LowCardinality(String)"),
        ("production_type", "LowCardinality(String)"),
        ("unit", "LowCardinality(String)"),
        ("valid", "LowCardinality(String)"),
        ("updated_at", "DateTime"),
        ("zone", "LowCardinality(String)"),
        ("zone_status", "LowCardinality(String)"),
    ],
    "local_footprint": [
        ("timestamp", "DateTime"),
        ("value", "Float32"),
        ("footprint_type", "LowCardinality(String)"),
        ("scope", "LowCardinality(String)"),
        ("unit", "LowCardinality(String)"),
        ("valid", "LowCardinality(String)"),
        ("updated_at", "DateTime"),
        ("zone", "LowCardinality(String)"),
        ("zone_status", "LowCardinality(String)"),
    ],
    "global_footprint": [
        ("timestamp", "DateTime"),
        ("value", "Float32"),
        ("footprint_type", "LowCardinality(String)"),
        ("scope", "LowCardinality(String)"),
        ("unit", "LowCardinality(String)"),
        ("valid", "LowCardinality(String)"),
        ("updated_at", "DateTime"),
        ("zone", "LowCardinality(String)"),
        ("zone_status", "LowCardinality(String)"),
    ],
    "local_impact": [
        ("timestamp", "DateTime"),
        ("value", "Float32"),
        ("impact_type", "LowCardinality(String)"),
        ("scope", "LowCardinality(String)"),
        ("unit", "LowCardinality(String)"),
        ("valid", "LowCardinality(String)"),
        ("updated_at", "DateTime"),
        ("zone", "LowCardinality(String)"),
        ("zone_status", "LowCardinality(String)"),
    ],
    "global_impact": [
        ("timestamp", "DateTime"),
        ("value", "Float32"),
        ("impact_type", "LowCardinality(String)"),
        ("scope", "LowCardinality(String)"),
        ("unit", "LowCardinality(String)"),
        ("valid", "LowCardinality(String)"),
        ("updated_at", "DateTime"),
        ("zone", "LowCardinality(String)"),
        ("zone_status", "LowCardinality(String)"),
    ],
    "local_score": [
        ("timestamp", "DateTime"),
        ("value", "Float32"),
        ("scope", "LowCardinality(String)"),
        ("valid", "LowCardinality(String)"),
        ("updated_at", "DateTime"),
        ("zone", "LowCardinality(String)"),
        ("zone_status", "LowCardinality(String)"),
    ],
    "global_score": [
        ("timestamp", "DateTime"),
        ("value", "Float32"),
        ("scope", "LowCardinality(String)"),
        ("valid", "LowCardinality(String)"),
        ("updated_at", "DateTime"),
        ("zone", "LowCardinality(String)"),
        ("zone_status", "LowCardinality(String)"),
    ],
    "factor": [
        ("timestamp", "DateTime"),
        ("value", "Float32"),
        ("factor_type", "LowCardinality(String)"),
        ("production_type", "LowCardinality(String)"),
        ("scope", "LowCardinality(String)"),
        ("source", "LowCardinality(String)"),
        ("source_link", "String"),
        ("unit", "LowCardinality(String)"),
        ("updated_at", "DateTime"),
        ("year", "Nullable(Int32)"),
    ],
    "flow_share": [
        ("timestamp", "DateTime"),
        ("value", "Float32"),
        ("target", "LowCardinality(String)"),
        ("unit", "LowCardinality(String)"),
        ("valid", "LowCardinality(String)"),
        ("updated_at", "DateTime"),
        ("zone", "LowCardinality(String)"),
        ("zone_status", "LowCardinality(String)"),
    ],
    "mix_share": [
        ("timestamp", "DateTime"),
        ("value", "Float32"),
        ("source", "LowCardinality(String)"),
        ("unit", "LowCardinality(String)"),
        ("valid", "LowCardinality(String)"),
        ("updated_at", "DateTime"),
        ("zone", "LowCardinality(String)"),
        ("zone_status", "LowCardinality(String)"),
    ],
    "footprint_share": [
        ("timestamp", "DateTime"),
        ("value", "Float32"),
        ("footprint_type", "LowCardinality(String)"),
        ("scope", "LowCardinality(String)"),
        ("source", "LowCardinality(String)"),
        ("unit", "LowCardinality(String)"),
        ("valid", "LowCardinality(String)"),
        ("updated_at", "DateTime"),
        ("zone", "LowCardinality(String)"),
        ("zone_status", "LowCardinality(String)"),
    ],
    "impact_share": [
        ("timestamp", "DateTime"),
        ("value", "Float32"),
        ("impact_type", "LowCardinality(String)"),
        ("scope", "LowCardinality(String)"),
        ("source", "LowCardinality(String)"),
        ("unit", "LowCardinality(String)"),
        ("valid", "LowCardinality(String)"),
        ("updated_at", "DateTime"),
        ("zone", "LowCardinality(String)"),
        ("zone_status", "LowCardinality(String)"),
    ],
}

# -------------------------------------------------------------------
# Label name normalization
# -------------------------------------------------------------------
COLUMN_NAME_MAP = {
    "from": "from_zone",
    "to": "to_zone",
}

REVERSE_COLUMN_NAME_MAP = {v: k for k, v in COLUMN_NAME_MAP.items()}

_METRIC_QUERY_TEMPLATE = (
    "SELECT * FROM {table} FINAL"
    " WHERE timestamp >= toDateTime({start:String})"
    "   AND timestamp <  toDateTime({end:String})"
)


class ClickHouseClient(BaseStorageClient):
    """ClickHouse storage client with a write buffer and thread-local connections."""

    config_class = ClickHouseConfig

    # ------------------------------------------------------------------
    # Write buffer tuning
    # Flush when either condition is met: max rows OR max age (seconds).
    # ------------------------------------------------------------------
    _FLUSH_INTERVAL_SECONDS = 2
    _FLUSH_MAX_ROWS = 5_000

    def __init__(self, config: StorageConfig):
        """Initialize the ClickHouse client with a StorageConfig."""
        ch = self.config_class(**config.plugin_configs.get("clickhouse", {}))
        self.host = ch.host
        self.port = ch.port
        self.user = ch.user
        self.password = ch.password
        self.database = ch.database
        self.interval_minutes = config.timeseries_step_minutes
        self._connect_retries = ch.connect_retries
        self._connect_retry_delay = ch.connect_retry_delay

        LOG.info(
            "ClickHouse config — host=%s port=%d user=%s database=%s "
            "password=%s interval_minutes=%d",
            self.host,
            self.port,
            self.user,
            self.database,
            "[set]" if self.password else "[not set]",
            self.interval_minutes,
        )

        # 1. Bootstrap: create DB + tables using a root client (no database)
        for attempt in range(1, self._connect_retries + 1):
            try:
                self._bootstrap_schema()
                break
            except Exception as e:
                if attempt == self._connect_retries:
                    LOG.error(
                        "ClickHouse bootstrap attempt %d/%d failed: %s — giving up.",
                        attempt,
                        self._connect_retries,
                        e,
                    )
                    raise RuntimeError(
                        f"ClickHouse not available at {self.host}:{self.port} "
                        f"after {self._connect_retries} attempts — cannot start."
                    ) from e
                LOG.warning(
                    "ClickHouse bootstrap attempt %d/%d failed: %s "
                    "— retrying in %ds",
                    attempt,
                    self._connect_retries,
                    e,
                    self._connect_retry_delay,
                )
                time.sleep(self._connect_retry_delay)

        # 2. Thread-local client storage — each thread gets its own connection.
        # clickhouse_connect does NOT support concurrent queries on the same session,
        # so we create one client per thread on first use via _get_client().
        self._local = local()

        # 3. Write buffer
        self._buffer: dict[str, list] = defaultdict(list)
        self._buffer_lock = Lock()

        # 4. Flush thread — a permanent daemon thread is more stable than
        # chained Timers for long-running services (no drift, no overlaps).
        self._stop_event = Event()
        self._flush_thread = Thread(target=self._flush_loop, daemon=True)
        self._flush_thread.start()
        LOG.info(
            "Flush thread started (interval=%ds, max_rows=%d)",
            self._FLUSH_INTERVAL_SECONDS,
            self._FLUSH_MAX_ROWS,
        )

    # ------------------------------------------------------------------
    # CLIENT — one instance per thread
    # ------------------------------------------------------------------

    def _get_client(self):
        """Return a clickhouse client for the current thread.

        Creates a new connection on first call per thread and reuses it
        on subsequent calls. This avoids the ProgrammingError raised when
        concurrent queries share the same session.
        """
        if not hasattr(self._local, "client"):
            LOG.debug(
                "Creating new ClickHouse connection for thread '%s'",
                current_thread().name,
            )
            self._local.client = clickhouse_connect.get_client(
                host=self.host,
                port=self.port,
                username=self.user,
                password=self.password,
                database=self.database,
            )
        return self._local.client

    # ------------------------------------------------------------------
    # SCHEMA BOOTSTRAP
    # ------------------------------------------------------------------

    def _bootstrap_schema(self) -> None:
        """Create the database and all tables using a temporary root client.

        Must run before self._client is created so the database exists when
        clickhouse_connect initialises the session.
        """
        LOG.info("Bootstrapping schema for database '%s'", self.database)
        root = clickhouse_connect.get_client(
            host=self.host,
            port=self.port,
            username=self.user,
            password=self.password,
        )
        try:
            root.command(f"CREATE DATABASE IF NOT EXISTS {self.database}")
            LOG.debug("Database '%s' ready", self.database)

            for table_name, cols in TABLE_SCHEMAS.items():
                col_defs = ",\n    ".join(f"{name} {typ}" for name, typ in cols)

                order_cols = ["timestamp"]
                preferred = [
                    "zone",
                    "from_zone",
                    "to_zone",
                    "factor_type",
                    "production_type",
                    "footprint_type",
                    "impact_type",
                    "score_type",
                    "scope",
                    "source",
                    "target",
                ]
                for p in preferred:
                    if p in {c[0] for c in cols}:
                        order_cols.append(p)

                root.command(f"""
                    CREATE TABLE IF NOT EXISTS {self.database}.{table_name} (
                        {col_defs}
                    )
                    ENGINE = ReplacingMergeTree(updated_at)
                    ORDER BY ({", ".join(order_cols)})
                """)
                LOG.debug("Table '%s.%s' ready", self.database, table_name)

            LOG.info("Schema bootstrap complete (%d tables)", len(TABLE_SCHEMAS))
        finally:
            root.close()

    # ------------------------------------------------------------------
    # TIME ALIGNMENT
    # ------------------------------------------------------------------

    def _align_floor(self, dt: datetime) -> datetime:
        """Round down to the nearest interval boundary."""
        discard = timedelta(
            minutes=dt.minute % self.interval_minutes,
            seconds=dt.second,
            microseconds=dt.microsecond,
        )
        return dt - discard

    def _resolve_time_range(
        self,
        start: datetime | None,
        end: datetime | None,
        now: datetime | None = None,
    ) -> tuple[datetime, datetime]:
        """
        Resolve (start, end) into an aligned half-open interval [start, end).

        end is always treated as EXCLUSIVE — the query returns rows where
        timestamp >= start AND timestamp < end.

                         given           resolved
          ──────────────────────────────────────────────────────────────
          (None,  None) → (floor(now),   floor(now) + I)   one bucket
          (None,  end)  → (floor(end),   floor(end) + I)   one bucket
          (start, None) → (floor(start), floor(start) + I) one bucket
          (start, end)  → (floor(start), floor(end))       exact range

        In the (start, end) case end is NOT expanded — floor(end) is the
        exclusive upper boundary as the caller intended.

        Examples with I=15min:
          start=00:00, end=00:15 → [00:00, 00:15) → only the 00:00 bucket
          start=00:00, end=00:30 → [00:00, 00:30) → buckets 00:00 and 00:15

        floor() is a no-op on already-aligned timestamps, so collectors and
        forecast sliding windows that pre-compute exact boundaries are safe.
        """
        now = now or datetime.now(timezone.utc)
        interval = timedelta(minutes=self.interval_minutes)

        if start is None and end is None:
            start = self._align_floor(now)
            end = start + interval
        elif start is None:
            start = self._align_floor(cast(datetime, end))
            end = start + interval
        elif end is None:
            start = self._align_floor(start)
            end = start + interval
        else:
            start = self._align_floor(start)
            # end is exclusive but we want to INCLUDE the bucket that contains end.
            # floor(end) + interval gives the exclusive upper bound for that bucket.
            # Special case: if end is exactly on a boundary (e.g. end=00:15, I=15),
            # floor(end) == end and adding interval would include the next bucket.
            # In that case use floor(end) directly as the exclusive bound.
            floored_end = self._align_floor(end)
            end = floored_end if floored_end == end else floored_end + interval
            if end < start:
                raise ValueError(
                    f"Resolved time range is empty or inverted: "
                    f"start={start}, end={end}"
                )
            # Degenerate equal range — force one bucket.
            if end == start:
                end = start + interval

        return start, end

    # ------------------------------------------------------------------
    # QUERY BUILDER
    # ------------------------------------------------------------------

    def _build_query(
        self,
        metric_name: str,
        start: datetime,
        end: datetime,
        labels: dict | None = None,
    ) -> tuple[str, dict]:
        """Build a parameterized SELECT for clickhouse_connect.

        Column names are validated against TABLE_SCHEMAS; values are parameters.
        """
        if metric_name not in TABLE_SCHEMAS:
            raise ValueError(f"Unknown metric table: {metric_name!r}")

        params = {
            "start": start.strftime("%Y-%m-%d %H:%M:%S"),
            "end": end.strftime("%Y-%m-%d %H:%M:%S"),
        }

        sql = _METRIC_QUERY_TEMPLATE.replace(
            "{table}", self.database + "." + metric_name
        )

        if labels:
            valid_cols = {c[0] for c in TABLE_SCHEMAS[metric_name]}
            for k, v in labels.items():
                mapped_k = COLUMN_NAME_MAP.get(k, k)
                if mapped_k not in valid_cols:
                    continue
                param_key = f"label_{mapped_k}"
                sql += f" AND {mapped_k} = {{{param_key}:String}}"
                params[param_key] = str(v)

        sql += " ORDER BY timestamp ASC"
        return sql, params

    # ------------------------------------------------------------------
    # WRITE — buffered batch path
    # ------------------------------------------------------------------

    def _flush_loop(self) -> None:
        """Permanent daemon thread: flush every _FLUSH_INTERVAL_SECONDS.

        Using a blocking Event instead of chained Timers avoids timer drift
        and guarantees a clean final flush on shutdown (flush() sets the event).
        """
        while not self._stop_event.wait(timeout=self._FLUSH_INTERVAL_SECONDS):
            self._flush_all()
        # Final flush on shutdown
        self._flush_all()

    def _flush_all(self) -> None:
        """Drain the entire buffer and send to ClickHouse."""
        with self._buffer_lock:
            snapshot = dict(self._buffer)
            self._buffer.clear()

        for table_name, rows in snapshot.items():
            if rows:
                LOG.debug("Flushing %d rows to table '%s'", len(rows), table_name)
                try:
                    self._flush_table(table_name, rows)
                except Exception as e:
                    # Log and continue — a failed flush must not kill the thread
                    LOG.error(
                        "Flush failed for table %s (%d rows): %s",
                        table_name,
                        len(rows),
                        e,
                        exc_info=True,
                    )

    def _flush_table(self, table_name: str, rows: list) -> None:
        """Insert a pre-built batch of rows into ClickHouse."""
        columns = [c[0] for c in TABLE_SCHEMAS[table_name]]
        self._get_client().insert(table_name, rows, column_names=columns)

    def _build_row(self, table_name: str, m: Metric) -> list:
        """Serialize a Metric into a row list matching TABLE_SCHEMAS column order."""
        metadata = m.metadata or {}
        row: list[Any] = []
        for col, col_type in TABLE_SCHEMAS[table_name]:
            if col == "timestamp":
                ts = m.timestamp
                if isinstance(ts, str):
                    ts = datetime.fromisoformat(ts)
                row.append(ts)
            elif col == "value":
                row.append(float(m.value))
            elif col == "updated_at":
                row.append(datetime.now(timezone.utc))
            else:
                metadata_key = REVERSE_COLUMN_NAME_MAP.get(col, col)
                v = metadata.get(metadata_key)
                if v is None:
                    row.append(None if "Int" in col_type else "")
                else:
                    row.append(str(v))
        return row

    def write_metrics(self, metrics: List[Metric]) -> None:
        """
        Buffer metrics for batch insertion.

        Rows are grouped by table and appended to the in-memory buffer.
        The buffer is flushed automatically every _FLUSH_INTERVAL_SECONDS
        or immediately when a single table exceeds _FLUSH_MAX_ROWS.
        """
        if not metrics:
            return

        by_table: dict[str, list[Metric]] = defaultdict(list)
        for m in metrics:
            by_table[m.name].append(m)

        flush_batches: list[tuple[str, list]] = []

        with self._buffer_lock:
            for table_name, items in by_table.items():
                if table_name not in TABLE_SCHEMAS:
                    continue

                rows = [self._build_row(table_name, m) for m in items]
                self._buffer[table_name].extend(rows)

                if len(self._buffer[table_name]) >= self._FLUSH_MAX_ROWS:
                    # Collect oversized tables; flush OUTSIDE the lock below
                    flush_batches.append((table_name, self._buffer.pop(table_name)))

        # I/O happens outside the lock — other writers are never blocked by network
        for table_name, rows in flush_batches:
            try:
                self._flush_table(table_name, rows)
            except Exception as e:
                LOG.error(
                    "Immediate flush failed for table %s (%d rows): %s",
                    table_name,
                    len(rows),
                    e,
                    exc_info=True,
                )

    def flush(self) -> None:
        """Force an immediate flush and stop the background flush thread.

        Call this on graceful shutdown to avoid losing buffered rows.
        After calling flush() the client should not be used anymore.
        """
        LOG.info("Graceful shutdown: flushing buffer and stopping flush thread")
        self._stop_event.set()
        self._flush_thread.join(timeout=10)
        LOG.info("Flush thread stopped")

    # ------------------------------------------------------------------
    # READ — Arrow/DataFrame path for fast deserialization
    # ------------------------------------------------------------------

    def read_metrics(
        self,
        metric_name: str,
        start: datetime | None = None,
        end: datetime | None = None,
        labels: dict | None = None,
        params: Any = None,
        _now: datetime | None = None,
    ) -> list[Metric]:
        """
        Read metrics from ClickHouse within a resolved time window.

        Uses query_df (Arrow-backed) instead of query for faster row
        deserialization at high row counts.
        """
        start, end = self._resolve_time_range(start, end, now=_now)
        sql, query_params = self._build_query(metric_name, start, end, labels)

        df = self._get_client().query_df(sql, parameters=query_params)

        if df.empty:
            return []

        metrics = []
        col_names = list(df.columns)

        for row in df.itertuples(index=False):
            ts = row[0]
            val = row[1]

            metadata = dict(zip(col_names[2:], row[2:]))
            normalized = {
                REVERSE_COLUMN_NAME_MAP.get(k, k): v for k, v in metadata.items()
            }

            if "year" in normalized:
                try:
                    normalized["year"] = int(normalized["year"])
                except Exception:
                    normalized["year"] = None

            metrics.append(
                Metric(
                    metric_type=MetricType(metric_name),
                    value=round(float(val), 2),
                    timestamp=ts.to_pydatetime().replace(tzinfo=timezone.utc),
                    metadata=normalized,
                )
            )

        return metrics
