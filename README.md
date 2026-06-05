<div align="left">
  <picture>
    <source media="(prefers-color-scheme: dark)"
            srcset="https://github.com/wattnet/.github/raw/main/images/wattnet-logo-full-dark-transparent-cropped.png" />
    <source media="(prefers-color-scheme: light)"
            srcset="https://github.com/wattnet/.github/raw/main/images/wattnet-logo-full-light-transparent-cropped.png" />
    <img src="https://github.com/wattnet/.github/raw/main/images/wattnet-logo-full-light-transparent-cropped.png"
         alt="Wattnet Logo"
         width="300" />
  </picture>
</div>

# Storage Backend and Python Client Interface

`wattnet-storage` provides two things:

- **Storage backend** — a Docker Compose stack with [ClickHouse](https://clickhouse.com/) for time-series metric storage and [Grafana](https://grafana.com/) for visualization.
- **Python client library** — a plugin-based interface to read and write energy metrics (generation, load, carbon footprint, etc.) against the storage backend.

## Purpose

Multiple Wattnet containers compute and expose energy data through their own APIs, each with its own domain model and internal representation. `wattnet-storage` acts as the shared persistence layer between them: it provides a single, uniform interface so that any Wattnet module can persist and retrieve metrics without coupling to a specific storage technology or to the internal data structures of other modules.

To achieve this, metrics are always stored in a **common format** regardless of how they are represented in the originating domain model:

| Field       | Type       | Description                                                  |
|-------------|------------|--------------------------------------------------------------|
| `name`      | `str`      | Metric identifier (`MetricType` value, e.g. `zone_generation`) |
| `value`     | `float`    | Numeric measurement                                          |
| `timestamp` | `datetime` | Point in time the measurement was taken                      |
| `metadata`  | `dict`     | Arbitrary key-value labels (e.g. `zone`, `source`, `unit`)   |

Any Wattnet module that needs to persist data translates its domain objects into this format before writing, and reconstructs its own representation after reading. The storage backend in use (ClickHouse, or any future backend) is fully transparent to the caller.

## Architecture

![Storage component diagram](https://github.com/wattnet/wattnet-architecture/blob/main/diagrams/png/structurizr-1-wattnet_storage.png?raw=true)

For the full system architecture see the [wattnet-architecture](https://github.com/wattnet/wattnet-architecture) repository.

The client layer is plugin-based (via [stevedore](https://docs.openstack.org/stevedore/)). Additional storage backends can be added by implementing `BaseStorageClient` and registering a `wattnet.storage.clients` entry point.

## Requirements

- Python ≥ 3.10
- Docker and Docker Compose (for the storage backend)

## Backend Setup

Start the ClickHouse and Grafana services:

```bash
docker compose up -d
```

| Service    | Default address         |
| ---------- | ----------------------- |
| ClickHouse | `http://localhost:8123` |
| Grafana    | `http://localhost:3000` |

Grafana's default credentials are `admin` / `admin`. The ClickHouse datasource and dashboards are provisioned automatically.

## Python Client

### Installation

```bash
pip install wattnet-storage
```

Or with [Poetry](https://python-poetry.org/):

```bash
poetry add wattnet-storage
```

### Configuration

The client reads settings from environment variables or a `.env` file. Copy the example and adjust as needed:

```bash
cp config/.env.example config/.env.development
```

| Variable                  | Default                      | Description                                             |
| ------------------------- | ---------------------------- | ------------------------------------------------------- |
| `WATTNET_ENV`             | `development`                | Active environment; selects `config/.env.<WATTNET_ENV>` |
| `STORAGE_CLIENTS`         | `[]`                         | Active backend plugins, e.g. `["clickhouse"]`           |
| `CLICKHOUSE_HOST`         | `localhost`                  | ClickHouse hostname                                     |
| `CLICKHOUSE_PORT`         | `9000`                       | ClickHouse native TCP port                              |
| `CLICKHOUSE_USER`         | `default`                    | ClickHouse username                                     |
| `CLICKHOUSE_PASSWORD`     | _(empty)_                    | ClickHouse password                                     |
| `DATABASE`                | `wattnet`                    | Target database name                                    |
| `TIMESERIES_STEP_MINUTES` | `15`                         | Time resolution in minutes                              |
| `LOG_LEVEL`               | `INFO`                       | Logging level (`DEBUG`, `INFO`, `WARNING`, …)           |
| `LOG_HANDLERS`            | `["console"]`                | Log outputs: `"console"` and/or `"file"`                |
| `LOG_FILE`                | `./logs/wattnet-storage.log` | Log file path (only used when `file` handler is active) |

### Usage

```python
from datetime import datetime
from wattnet.storage.repository import MetricsRepository
from wattnet.storage.models import Metric, MetricType

repo = MetricsRepository()

# Write metrics
metrics = [
    Metric(
        metric_type=MetricType.ZONE_GENERATION,
        value=1500.0,
        timestamp=datetime.now(),
        metadata={"zone": "ES", "source": "solar"},
    )
]
repo.write_metrics(metrics)

# Query metrics
results = repo.query_metrics(
    metric_name=MetricType.ZONE_GENERATION.value,
    start=datetime(2025, 1, 1),
    end=datetime(2025, 1, 2),
    labels={"zone": "ES"},
)
```

#### Supported metric types

| `MetricType`          | Value                 | Description                             |
| --------------------- | --------------------- | --------------------------------------- |
| `ZONE_GENERATION`     | `zone_generation`     | Electricity generation in a zone        |
| `ZONE_IMPORT`         | `zone_import`         | Electricity imports                     |
| `ZONE_EXPORT`         | `zone_export`         | Electricity exports                     |
| `ZONE_LOAD`           | `zone_load`           | Electricity consumption / load          |
| `ZONE_MIX_GENERATION` | `zone_mix_generation` | Generation mix per source               |
| `FACTOR`              | `factor`              | Emission factor                         |
| `LOCAL_FOOTPRINT`     | `local_footprint`     | Location-based carbon footprint         |
| `GLOBAL_FOOTPRINT`    | `global_footprint`    | Market-based carbon footprint           |
| `LOCAL_IMPACT`        | `local_impact`        | Location-based carbon impact            |
| `GLOBAL_IMPACT`       | `global_impact`       | Market-based carbon impact              |
| `LOCAL_SCORE`         | `local_score`         | Location-based carbon score             |
| `GLOBAL_SCORE`        | `global_score`        | Market-based carbon score               |
| `FLOW_SHARE`          | `flow_share`          | Share of electricity flow between zones |
| `MIX_SHARE`           | `mix_share`           | Share of generation mix                 |
| `FOOTPRINT_SHARE`     | `footprint_share`     | Share attributed to carbon footprint    |
| `IMPACT_SHARE`        | `impact_share`        | Share attributed to carbon impact       |

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for environment setup, code style, how to run the tests, and how to add a new storage backend.

## License

This repository is licensed under the [Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0).

See the [LICENSE](LICENSE) file for more details.

## Funding and Acknowledgments

This work is funded by the European Union's Horizon Europe research and innovation programme through the **[GreenDIGIT](https://greendigit-project.eu/)** project, under grant agreement **[101131207](https://cordis.europa.eu/project/id/101131207)**.

<div align="left">
  <img src="https://github.com/wattnet/.github/raw/main/images/EN_FundedbytheEU_RGB_POS.png" alt="EU Funded Logo" width="260"/>
  <img src="https://github.com/wattnet/.github/raw/main/images/GreenDIGIT%20logo%20color%20horizontal2.png" alt="GreenDIGIT Logo" width="230"/>
</div>

##### © 2026 Spanish National Research Council (CSIC). All rights reserved.
