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

[![CI](https://github.com/wattnet/wattnet-storage/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/wattnet/wattnet-storage/actions/workflows/ci.yml)
[![Publish](https://github.com/wattnet/wattnet-storage/actions/workflows/publish.yml/badge.svg)](https://github.com/wattnet/wattnet-storage/actions/workflows/publish.yml)
[![Release Please](https://github.com/wattnet/wattnet-storage/actions/workflows/release-please.yml/badge.svg?branch=main)](https://github.com/wattnet/wattnet-storage/actions/workflows/release-please.yml)
[![codecov](https://codecov.io/gh/wattnet/wattnet-storage/graph/badge.svg)](https://codecov.io/gh/wattnet/wattnet-storage)
[![GitHub stars](https://img.shields.io/github/stars/wattnet/wattnet-storage?style=social)](https://github.com/wattnet/wattnet-storage/stargazers)
[![PyPI version](https://img.shields.io/pypi/v/wattnet-storage)](https://pypi.org/project/wattnet-storage/)
[![PyPI Downloads](https://static.pepy.tech/personalized-badge/wattnet-storage?period=total&units=INTERNATIONAL_SYSTEM&left_color=BLACK&right_color=GREEN&left_text=downloads)](https://pepy.tech/projects/wattnet-storage)
[![Python](https://img.shields.io/pypi/pyversions/wattnet-storage)](https://pypi.org/project/wattnet-storage/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Imports: isort](https://img.shields.io/badge/%20imports-isort-%231674b1?style=flat&labelColor=ef8336)](https://pycqa.github.io/isort/)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://github.com/pre-commit/pre-commit)

`wattnet-storage` provides two things:

- **Storage backend** — a Docker Compose stack with [ClickHouse](https://clickhouse.com/) for time-series metric storage and [Grafana](https://grafana.com/) for visualization.
- **Python client library** — a plugin-based interface to read and write energy metrics (generation, load, carbon footprint, etc.) against the storage backend.

## Purpose

Multiple Wattnet containers compute and expose energy data through their own APIs, each with its own domain model and internal representation. `wattnet-storage` acts as the shared persistence layer between them: it provides a single, uniform interface so that any Wattnet module can persist and retrieve metrics without coupling to a specific storage technology or to the internal data structures of other modules.

To achieve this, metrics are always stored in a **common format** regardless of how they are represented in the originating domain model:

| Field       | Type       | Description                                                    |
| ----------- | ---------- | -------------------------------------------------------------- |
| `name`      | `str`      | Metric identifier (`MetricType` value, e.g. `zone_generation`) |
| `value`     | `float`    | Numeric measurement                                            |
| `timestamp` | `datetime` | Point in time the measurement was taken                        |
| `metadata`  | `dict`     | Arbitrary key-value labels (e.g. `zone`, `source`, `unit`)     |

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

`wattnet-storage` is configured by the calling application through a `StorageConfig` object.
Create the config in your service and pass it to `MetricsRepository`.

```python
from wattnet.storage import StorageConfig

config = StorageConfig(
    timeseries_step_minutes=15,
    storage_clients=["clickhouse"],
    plugin_configs={
        "clickhouse": {
            "host": "localhost",
            "port": 8123,
            "user": "default",
            "password": "",
            "database": "wattnet",
            "connect_retries": 5,
            "connect_retry_delay": 3,
        }
    },
)
```

`StorageConfig` is **immutable**: all fields are frozen at construction time. Attempting to reassign a field raises `FrozenInstanceError`. Validation runs automatically on construction:

- `timeseries_step_minutes` must be a positive integer — `ValueError` is raised otherwise.
- `storage_clients` must not contain duplicate entries — `ValueError` is raised otherwise.

`wattnet-storage` does not load or manage a project-specific `.env` file.
If your application uses a `.env`, it should load it before creating the repository.

Configuration precedence for ClickHouse is:

1. Process environment variables (`CLICKHOUSE_*`) — highest priority
2. `.env` file values (`CLICKHOUSE_*`) — loaded by the consuming application
3. Code defaults in `ClickHouseConfig` — lowest priority

`ClickHouseConfig` does not read `.env` files directly. Consuming applications (wattnet-api, wattnet-core) instantiate `ClickHouseConfig(_env_file=".env")` in their `plugin_settings` mechanism and pass the resolved values to `StorageConfig.plugin_configs`, achieving the priority order above automatically. This means a process-level environment variable (e.g. set in Docker Compose or Kubernetes) always wins over a `.env` file entry.

`StorageConfig.plugin_configs["clickhouse"]` is the highest-priority override but is intended for programmatic use only (e.g. tests or one-off scripts); in normal deployments the values come from the environment.

For ClickHouse, these process environment variables are supported:

| Variable                         | Default     | Description                                   |
| -------------------------------- | ----------- | --------------------------------------------- |
| `CLICKHOUSE_HOST`                | `localhost` | ClickHouse hostname                           |
| `CLICKHOUSE_PORT`                | `8123`      | ClickHouse HTTP port                          |
| `CLICKHOUSE_USER`                | `default`   | ClickHouse username                           |
| `CLICKHOUSE_PASSWORD`            | _(empty)_   | ClickHouse password                           |
| `CLICKHOUSE_DATABASE`            | `wattnet`   | Target database name                          |
| `CLICKHOUSE_CONNECT_RETRIES`     | `5`         | Number of bootstrap attempts before giving up |
| `CLICKHOUSE_CONNECT_RETRY_DELAY` | `3`         | Seconds to wait between bootstrap attempts    |

If ClickHouse is unreachable after all attempts, startup fails with a single `RuntimeError` message indicating the host, port, and number of attempts — no deep traceback from the HTTP layer. This also handles the typical docker-compose race condition where ClickHouse is not yet ready when the API container starts.

### Usage

```python
from datetime import datetime
from wattnet.storage import MetricsRepository, StorageConfig
from wattnet.storage.models import Metric, MetricType

config = StorageConfig(
    timeseries_step_minutes=15,
    storage_clients=["clickhouse"],
    plugin_configs={
        "clickhouse": {
            "host": "localhost",
            "port": 8123,
            "user": "default",
            "password": "",
            "database": "wattnet",
            "connect_retries": 5,
            "connect_retry_delay": 3,
        }
    },
)

repo = MetricsRepository(config)

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

## Logging

`wattnet-storage` follows the [standard library logging recommendation for libraries](https://docs.python.org/3/howto/logging.html#configuring-logging-for-a-library): it adds a `NullHandler` to the `wattnet.storage` logger and never configures handlers itself. This means no log output appears by default, and the calling application remains fully in control.

To see storage logs, configure the `wattnet.storage` logger (or the parent `wattnet` logger) in your application:

```python
import logging

# Minimal setup — output all wattnet.* logs to the console
logging.getLogger("wattnet").setLevel(logging.DEBUG)
logging.getLogger("wattnet").addHandler(logging.StreamHandler())
```

If you use `wattnet-api`, `wattnet-core` or `wattnet-forecast`, their `setup_logging()` call already covers `wattnet.storage.*` logs automatically — no additional configuration is needed.

## Related Projects

Other Wattnet modules that use `wattnet-storage` as their persistence layer:

| Repository                                                      | Description                                                                             |
| --------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| [wattnet-api](https://github.com/wattnet/wattnet-api)           | RESTful API exposing real-time, historical, and forecasted electricity footprint data   |
| [wattnet-core](https://github.com/wattnet/wattnet-core)         | Core service that computes carbon and water footprints from electricity generation data |
| [wattnet-forecast](https://github.com/wattnet/wattnet-forecast) | Forecasting service for electricity carbon footprint across European zones              |

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
