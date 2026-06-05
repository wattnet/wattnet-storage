# Contributing to wattnet-storage

Thank you for your interest in contributing. This document covers how to set up your environment, the code standards we follow, and the process for submitting changes.

## Prerequisites

- Python ≥ 3.10
- [Poetry](https://python-poetry.org/) ≥ 2.0
- Docker and Docker Compose (for integration tests)
- Git

## Getting Started

1. Fork the repository and clone your fork:

   ```bash
   git clone https://github.com/<your-username>/wattnet-storage.git
   cd wattnet-storage
   ```

2. Install all dependency groups:

   ```bash
   poetry install --with dev,test,lint,format,types,security
   ```

3. Install the pre-commit hooks:

   ```bash
   pre-commit install
   ```

## Running the Tests

**Unit tests** (no external services needed):

```bash
pytest
```

**Integration tests** (requires a running ClickHouse instance):

```bash
docker compose -f tests/docker-compose.test.yml up -d
pytest -m integration
```

**Full tox matrix** (lint, type-check, security, unit + integration):

```bash
tox
```

## Code Style

We enforce a consistent style automatically. Before opening a PR, run:

```bash
# Format code
black .
isort .

# Lint
flake8 .

# Type-check
mypy .

# Security scan
bandit -r wattnet/
```

All of these also run via pre-commit on every commit and are verified in CI.

Key rules:
- Line length: 88 characters (Black default).
- Import order: standard library → third-party → first-party (`isort` with Black profile).
- Docstrings: required on all public modules, classes, and functions (`pydocstyle`).

## Submitting a Pull Request

1. Create a branch from `main` with a descriptive name:

   ```bash
   git checkout -b feat/my-new-feature
   ```

2. Make your changes, ensuring all tests pass and the linter is clean.

3. Push your branch and open a PR against `main`. Fill in the PR template.

4. A maintainer will review your PR. Please address any requested changes promptly.

## Adding a New Storage Backend

`wattnet-storage` uses a plugin system based on [stevedore](https://docs.openstack.org/stevedore/). To add a new backend:

1. Implement `BaseStorageClient` in your package:

   ```python
   from datetime import datetime
   from wattnet.storage.clients.base import BaseStorageClient
   from wattnet.storage.models import Metric

   class MyBackendClient(BaseStorageClient):

       def read_metrics(
           self,
           metric_name: str,
           start: datetime | None = None,
           end: datetime | None = None,
           labels: dict | None = None,
           params: dict | None = None,
       ) -> list[Metric]:
           ...

       def write_metrics(self, metrics: list[Metric]) -> None:
           ...
   ```

2. Register the plugin as a `wattnet.storage.clients` entry point in your `pyproject.toml`:

   ```toml
   [tool.poetry.plugins."wattnet.storage.clients"]
   mybackend = "mypackage.client:MyBackendClient"
   ```

3. Activate it via configuration:

   ```bash
   STORAGE_CLIENTS=["mybackend"]
   ```

`StorageClientsManager` will discover and load the plugin automatically at startup.

## Reporting Issues

Please use the GitHub issue templates for bug reports and feature requests. For security vulnerabilities, see [SECURITY.md](SECURITY.md).

## License

By contributing, you agree that your contributions will be licensed under the [Apache License 2.0](LICENSE).
