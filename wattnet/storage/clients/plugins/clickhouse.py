from datetime import datetime, timedelta
from typing import List

import clickhouse_connect

from wattnet.storage.clients.base import BaseStorageClient
from wattnet.storage.models import Metric
from wattnet.storage.models.metric_type import MetricType
from wattnet.storage.settings import settings

# -------------------------------------------------------------------
# Table column definitions
# Each table lists tuples: (column_name, clickhouse_type)
# -------------------------------------------------------------------
TABLE_SCHEMAS = {
    "zone_generation": [
        ("timestamp", "DateTime"),
        ("value", "Float64"),
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
        ("value", "Float64"),
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
        ("value", "Float64"),
        ("data_state", "LowCardinality(String)"),
        ("datasource", "LowCardinality(String)"),
        ("to_zone", "LowCardinality(String)"),
        ("unit", "LowCardinality(String)"),
        ("valid", "LowCardinality(String)"),
        ("updated_at", "DateTime"),
        ("zone", "LowCardinality(String)"),
        ("zone_status", "LowCardinality(String)"),
    ],
    "local_footprint": [
        ("timestamp", "DateTime"),
        ("value", "Float64"),
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
        ("value", "Float64"),
        ("footprint_type", "LowCardinality(String)"),
        ("scope", "LowCardinality(String)"),
        ("unit", "LowCardinality(String)"),
        ("valid", "LowCardinality(String)"),
        ("updated_at", "DateTime"),
        ("zone", "LowCardinality(String)"),
        ("zone_status", "LowCardinality(String)"),
    ],
    "factor": [
        ("timestamp", "DateTime"),
        ("value", "Float64"),
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
        ("value", "Float64"),
        ("target", "LowCardinality(String)"),
        ("unit", "LowCardinality(String)"),
        ("valid", "LowCardinality(String)"),
        ("updated_at", "DateTime"),
        ("zone", "LowCardinality(String)"),
        ("zone_status", "LowCardinality(String)"),
    ],
    "mix_share": [
        ("timestamp", "DateTime"),
        ("value", "Float64"),
        ("source", "LowCardinality(String)"),
        ("unit", "LowCardinality(String)"),
        ("valid", "LowCardinality(String)"),
        ("updated_at", "DateTime"),
        ("zone", "LowCardinality(String)"),
        ("zone_status", "LowCardinality(String)"),
    ],
    "footprint_share": [
        ("timestamp", "DateTime"),
        ("value", "Float64"),
        ("footprint_type", "LowCardinality(String)"),
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
# Used to map metadata keys to internal DB schema
# -------------------------------------------------------------------
COLUMN_NAME_MAP = {
    "from": "from_zone",
    "to": "to_zone",
}

# Reverse mapping used when reading data back
REVERSE_COLUMN_NAME_MAP = {v: k for k, v in COLUMN_NAME_MAP.items()}


class ClickHouseClient(BaseStorageClient):

    def __init__(
        self,
        host=settings.clickhouse_host,
        port=settings.clickhouse_port,
        user=settings.clickhouse_user,
        password=settings.clickhouse_password,
        database=settings.database,
        interval_minutes=settings.timeseries_step_minutes,
    ):
        """
        Initialize the ClickHouse client and create all required tables
        using ReplacingMergeTree.
        """
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database
        self.interval_minutes = interval_minutes

        # Create database and tables if they don't exist
        client = self._new_root_client()
        client.command(f"CREATE DATABASE IF NOT EXISTS {database}")

        # Create all tables defined in TABLE_SCHEMAS
        for table_name, cols in TABLE_SCHEMAS.items():
            col_defs = ",\n    ".join([f"{name} {typ}" for name, typ in cols])

            # Dynamic ORDER BY: always include timestamp first for best query performance
            order_cols = ["timestamp"]

            # Add preferred ordering columns if present in each table
            preferred = [
                "zone",
                "from_zone",
                "to_zone",
                "factor_type",
                "production_type",
                "footprint_type",
                "scope",
                "source",
                "target",
            ]
            for p in preferred:
                if p in [c[0] for c in cols]:
                    order_cols.append(p)

            sql = f"""
            CREATE TABLE IF NOT EXISTS {self.database}.{table_name} (
                {col_defs}
            )
            ENGINE = ReplacingMergeTree(updated_at)
            ORDER BY ({", ".join(order_cols)})
            """

            client.command(sql)

    def _new_root_client(self):
        return clickhouse_connect.get_client(
            host=self.host,
            port=self.port,
            username=self.user,
            password=self.password,
            # No default database for root client
        )

    def _new_client(self):
        """Create a fresh ClickHouse client instance."""
        return clickhouse_connect.get_client(
            host=self.host,
            port=self.port,
            username=self.user,
            password=self.password,
            database=self.database,
        )

    # ------------------------------------------------------------------
    #                           WRITE METRICS
    # ------------------------------------------------------------------
    def write_metrics(self, metrics: List[Metric]):
        """
        Insert a list of Metric objects into their respective ClickHouse
        tables. Metrics are grouped per table name.
        """
        if not metrics:
            return

        # Group metrics by destination table
        metrics_by_table = {}
        for m in metrics:
            metrics_by_table.setdefault(m.name, []).append(m)

        client = self._new_client()

        for table_name, items in metrics_by_table.items():
            if table_name not in TABLE_SCHEMAS:
                continue

            columns = [c[0] for c in TABLE_SCHEMAS[table_name]]
            rows = []

            for m in items:
                metadata = m.metadata or {}
                row = []

                for col, col_type in TABLE_SCHEMAS[table_name]:

                    if col == "timestamp":
                        ts = m.timestamp
                        # Accept ISO strings too
                        if isinstance(ts, str):
                            ts = datetime.fromisoformat(ts)
                        row.append(ts)

                    elif col == "value":
                        row.append(float(m.value))

                    elif col == "updated_at":
                        row.append(datetime.now())

                    else:
                        # Normalize metadata keys (from → from_zone)
                        metadata_key = REVERSE_COLUMN_NAME_MAP.get(col, col)
                        v = metadata.get(metadata_key)

                        # Default values based on ClickHouse type
                        if v is None:
                            if "String" in col_type:
                                row.append("")
                            elif "Int" in col_type:
                                row.append(None)
                            else:
                                row.append("")
                        else:
                            row.append(str(v))

                rows.append(row)

            # Perform batch insert
            client.insert(table_name, rows, column_names=columns)

    # ------------------------------------------------------------------
    #                           READ METRICS
    # ------------------------------------------------------------------
    def read_metrics(
        self,
        metric_name: str,
        start: datetime | None,
        end: datetime | None,
        labels=None,
        params=None,
    ):
        """
        Read metrics from a ClickHouse table within a time interval.
        Supports:
            - dynamic fallback time windows if start/end are None
            - filtering by label metadata
        """
        client = self._new_client()

        # Handle missing start/end values with a default window
        now = datetime.now()
        interval = timedelta(minutes=self.interval_minutes)

        if start is None and end is None:
            end = now
            start = now - interval
        elif start is None and end is not None:
            start = end - interval
        elif start is not None and end is None:
            end = start + interval

        # Build SELECT query
        sql = f"""
        SELECT *
        FROM {self.database}.{metric_name} FINAL
        WHERE timestamp >= toDateTime('{start.strftime('%Y-%m-%d %H:%M:%S')}')
        AND timestamp <= toDateTime('{end.strftime('%Y-%m-%d %H:%M:%S')}')
        """

        # Apply label filters if provided
        if labels:
            valid_cols = {c[0] for c in TABLE_SCHEMAS[metric_name]}

            for k, v in labels.items():
                mapped_k = COLUMN_NAME_MAP.get(k, k)
                if mapped_k not in valid_cols:
                    continue

                val = f"'{v}'" if isinstance(v, str) else str(v)
                sql += f" AND {mapped_k} = {val}"

        sql += " ORDER BY timestamp ASC"

        result = client.query(sql)

        metrics = []

        for row in result.result_rows:
            ts = row[0]
            val = row[1]

            # Build metadata dict with remaining columns
            metadata = dict(zip(result.column_names[2:], row[2:]))

            # Reverse normalized names (from_zone → from)
            normalized = {}
            for k, v in metadata.items():
                external = REVERSE_COLUMN_NAME_MAP.get(k, k)
                normalized[external] = v

            # Convert year to int when possible
            if "year" in normalized:
                try:
                    normalized["year"] = int(normalized["year"])
                except Exception:
                    normalized["year"] = None

            metrics.append(
                Metric(
                    metric_type=MetricType(metric_name),
                    value=val,
                    timestamp=ts,
                    metadata=normalized,
                )
            )

        return metrics
