from datetime import datetime, timedelta, timezone

import requests
from prometheus_api_client import PrometheusConnect

from wattnet.storage.clients.base import BaseStorageClient
from wattnet.storage.models.metric import Metric
from wattnet.storage.models.metric_type import MetricType
from wattnet.storage.settings import settings
from wattnet.storage.utils import log

LOG = log.get(__name__)

MAX_POINTS = 30000 - 1  # VictoriaMetrics default max points per query


class VictoriaMetricsStorageClient(BaseStorageClient):
    """Client for reading/writing metrics from/to VictoriaMetrics."""

    def __init__(self):
        LOG.info("Initializing Storage Client...")
        self.storage_db_url = settings.storage_db_url
        LOG.debug(f"Storage URL: {self.storage_db_url}")

        self.storage = PrometheusConnect(url=self.storage_db_url, disable_ssl=True)

        if not self.check_connection():
            LOG.error("Failed to connect to storage")
            raise ConnectionError("Failed to connect to storage")
        else:
            LOG.info("Connected to storage")

        # Set step size in seconds
        self.step = int(settings.timeseries_step_minutes) * 60

    # ----------------------------
    # READ
    # ----------------------------
    def read_metrics(self, query, start=None, end=None, params=None) -> list[Metric]:
        """Retrieve metrics from storage based on the provided query and time range."""
        original_start = start
        start = self._align_start(start)
        LOG.debug(f"Adjusted start time: {start}")

        params = self._prepare_query_params(params)

        if start and end:
            if self._needs_splitting(start, end):
                raw_results = self._query_in_chunks(
                    query, start, end, original_start, params
                )
            else:
                raw_results = self._query_single_range(
                    query, start, end, original_start, params
                )
        else:
            raw_results = self.storage.custom_query(query=query, params=params)

        return self._parse_to_metrics(raw_results)

    # ----------------------------
    # WRITE
    # ----------------------------
    def write_metrics(self, metrics: list[Metric]) -> None:
        """Push metrics to VictoriaMetrics."""
        if not metrics:
            LOG.info("No metrics to push.")
            return

        LOG.info(f"Pushing {len(metrics)} metrics to storage...")
        lines = [self._metric_to_prometheus_line(m) for m in metrics]

        data = "\n".join(lines) + "\n"
        endpoint = f"{self.storage_db_url.rstrip('/')}/api/v1/import/prometheus"

        try:
            response = requests.post(endpoint, data=data)
            if response.status_code not in (200, 204):
                LOG.error(
                    f"Failed to push metrics: {response.status_code} {response.text}"
                )
            else:
                LOG.info("Metrics successfully pushed.")
        except requests.RequestException as e:
            LOG.error(f"Error pushing metrics: {e}")

    # ---------- Auxiliary methods ----------

    def _metric_to_prometheus_line(self, metric: Metric) -> str:
        ts = (
            metric.timestamp.timestamp()
            if isinstance(metric.timestamp, datetime)
            else float(metric.timestamp)
        )
        ts_ms = int(ts * 1000)

        labels = ",".join(f'{k}="{v}"' for k, v in metric.metadata.items())
        labels = (
            f'{{app="wattnet",version="v1.0.0",{labels}}}'
            if labels
            else '{app="wattnet",version="v1.0.0"}'
        )

        return f"{metric.name}{labels} {metric.value} {ts_ms}"

    def _align_start(self, start: datetime) -> datetime | None:
        if not start:
            return None
        ts = start.timestamp()
        aligned = (ts // self.step) * self.step
        return datetime.fromtimestamp(aligned, tz=start.tzinfo)

    def _prepare_query_params(self, params):
        params = params or {}
        params.update({"dedup": "false", "downsampling": "0", "maxPoints": "0"})
        return params

    def _needs_splitting(self, start, end):
        return (end - start).total_seconds() / self.step > MAX_POINTS

    def _query_single_range(self, query, start, end, original_start, params):
        result = self.storage.custom_query_range(
            query=query, start_time=start, end_time=end, step=self.step, params=params
        )
        return self._adjust_first_timestamp(result, original_start)

    def _query_in_chunks(self, query, start, end, original_start, params):
        LOG.warning(f"Query exceeds max points ({MAX_POINTS}). Splitting...")
        results = []
        max_chunk = timedelta(seconds=self.step * MAX_POINTS)
        current_start = start
        while current_start < end:
            current_end = min(current_start + max_chunk, end)
            partial = self.storage.custom_query_range(
                query=query,
                start_time=current_start,
                end_time=current_end,
                step=self.step,
                params=params,
            )
            if current_start == start:
                partial = self._adjust_first_timestamp(partial, original_start)
            results.append(partial)
            current_start = current_end
        return self._merge_results(results)

    def _merge_results(self, results):
        merged = {}
        for result in results:
            for series in result:
                key = (series["metric"].get("__name__", ""),) + tuple(
                    sorted(series["metric"].items())
                )
                if key not in merged:
                    merged[key] = {"metric": series["metric"], "values": []}
                merged[key]["values"].extend(series["values"])
        return list(merged.values())

    def _adjust_first_timestamp(self, result, new_timestamp):
        if not result:
            return result
        series_list = (
            result
            if isinstance(result, list)
            else result.get("data", {}).get("result", [])
        )
        for series in series_list:
            if series.get("values"):
                series["values"][0][0] = new_timestamp.timestamp()
        return result

    def _parse_to_metrics(self, raw_results) -> list[Metric]:
        metrics = []
        if not raw_results:
            return metrics
        series_list = (
            raw_results
            if isinstance(raw_results, list)
            else raw_results.get("data", {}).get("result", [])
        )
        for series in series_list:
            metric_name = series.get("metric", {}).get("__name__", "unknown")
            values = series.get("values", [])
            labels = {
                k: v
                for k, v in series.get("metric", {}).items()
                if k != "__name__"  # quitamos __name__ del metadata
            }
            labels["valid"] = str(labels.get("valid", "false")).lower() == "true"
            labels["zone_status"] = labels.get("zone_status", "missing")
            for ts_str, val_str in values:
                metrics.append(
                    Metric(
                        metric_type=MetricType(metric_name),
                        value=float(val_str),
                        timestamp=datetime.fromtimestamp(
                            float(ts_str), tz=timezone.utc
                        ),
                        metadata=labels,
                    )
                )
        return metrics

    def check_connection(self) -> bool:
        try:
            self.storage.custom_query(query="up")
            LOG.info("Storage connection healthy")
            return True
        except Exception as e:
            LOG.error(f"Storage connection failed: {e}")
            return False
