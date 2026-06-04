import os
import time

import clickhouse_connect
import pytest

from wattnet.storage.clients.plugins.clickhouse import ClickHouseClient

CLICKHOUSE_TEST_HOST = os.getenv("CLICKHOUSE_TEST_HOST", "localhost")
CLICKHOUSE_TEST_PORT = int(os.getenv("CLICKHOUSE_TEST_PORT", "18123"))
CLICKHOUSE_TEST_DB = "wattnet_test"


def _wait_for_clickhouse(host, port, retries=20, delay=1.5):
    for _ in range(retries):
        try:
            c = clickhouse_connect.get_client(host=host, port=port)
            c.command("SELECT 1")
            c.close()
            return True
        except Exception:
            time.sleep(delay)
    return False


@pytest.fixture(scope="session")
def ch_client():
    """
    Session-scoped ClickHouseClient pointing at the test database.

    Start the test container before running:
        docker compose -f docker-compose.test.yml up -d

    Override host/port with env vars CLICKHOUSE_TEST_HOST / CLICKHOUSE_TEST_PORT.
    """
    if not _wait_for_clickhouse(CLICKHOUSE_TEST_HOST, CLICKHOUSE_TEST_PORT):
        pytest.skip(
            f"ClickHouse not reachable at {CLICKHOUSE_TEST_HOST}:{CLICKHOUSE_TEST_PORT}. "
            "Start it with: docker compose -f docker-compose.test.yml up -d"
        )

    client = ClickHouseClient(
        host=CLICKHOUSE_TEST_HOST,
        port=CLICKHOUSE_TEST_PORT,
        user="default",
        password="",
        database=CLICKHOUSE_TEST_DB,
        interval_minutes=15,
    )
    yield client
    client.flush()

    # Drop test database to leave a clean state
    root = clickhouse_connect.get_client(
        host=CLICKHOUSE_TEST_HOST, port=CLICKHOUSE_TEST_PORT
    )
    root.command(f"DROP DATABASE IF EXISTS {CLICKHOUSE_TEST_DB}")
    root.close()


@pytest.fixture(autouse=True)
def truncate_tables(ch_client):
    """Truncate all test tables before each test for isolation."""
    from wattnet.storage.clients.plugins.clickhouse import TABLE_SCHEMAS

    root = clickhouse_connect.get_client(
        host=CLICKHOUSE_TEST_HOST, port=CLICKHOUSE_TEST_PORT
    )
    for table in TABLE_SCHEMAS:
        root.command(f"TRUNCATE TABLE IF EXISTS {CLICKHOUSE_TEST_DB}.{table}")
    root.close()
    yield
