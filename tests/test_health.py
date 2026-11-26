import pytest
from fastapi.testclient import TestClient
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy.exc import OperationalError

from main import app
from routes import health


@pytest.mark.parametrize(
    (
        "postgres_ready",
        "redis_ready",
        "expected_status",
    ),
    [
        (True, True, 200),
        (False, True, 503),
        (True, False, 503),
        (False, False, 503),
    ],
)
def test_readiness(
    monkeypatch,
    postgres_ready,
    redis_ready,
    expected_status,
):
    monkeypatch.setattr(
        health,
        "check_postgres",
        lambda: postgres_ready,
    )

    monkeypatch.setattr(
        health,
        "check_redis",
        lambda: redis_ready,
    )

    with TestClient(app) as client:
        response = client.get("/ready")

    assert response.status_code == expected_status

    assert response.json() == {
        "status": ("ready" if expected_status == 200 else "not_ready"),
        "checks": {
            "postgres": "up" if postgres_ready else "down",
            "redis": "up" if redis_ready else "down",
        },
    }


def test_health_independent_of_dependencies(monkeypatch):
    def unavailable():
        pytest.fail("Health must not check dependencies")

    monkeypatch.setattr(
        health,
        "check_postgres",
        unavailable,
    )

    monkeypatch.setattr(
        health,
        "check_redis",
        unavailable,
    )

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_postgres_connection_failure(monkeypatch):
    def connection_failed():
        raise OperationalError(
            None,
            None,
            Exception("Simulated PostgreSQL failure"),
        )

    monkeypatch.setattr(
        health.engine,
        "connect",
        connection_failed,
    )

    assert health.check_postgres() is False


def test_redis_connection_failure(monkeypatch):
    def connection_failed():
        raise RedisConnectionError("Simulated Redis failure")

    monkeypatch.setattr(
        health.redis_client,
        "ping",
        connection_failed,
    )

    assert health.check_redis() is False
