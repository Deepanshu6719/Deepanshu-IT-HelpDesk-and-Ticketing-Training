from unittest.mock import patch

from core.rate_limit import check_rate_limit
from database.redis import redis_client


def test_refresh_endpoint_enforces_rate_limit(client):
    with patch(
        "routes.auth.check_rate_limit",
        side_effect=check_rate_limit,
    ):
        for _ in range(20):
            response = client.post(
                "/api/v1/auth/refresh",
                json={
                    "refresh_token": "invalid-refresh-token",
                },
            )

            assert response.status_code == 401

        blocked = client.post(
            "/api/v1/auth/refresh",
            json={
                "refresh_token": "invalid-refresh-token",
            },
        )

    assert blocked.status_code == 429

    body = blocked.json()

    assert body["success"] is False
    assert body["error"]["code"] == "RATE_LIMIT_EXCEEDED"


def test_refresh_rate_limit_has_expiration(client):
    with patch(
        "routes.auth.check_rate_limit",
        side_effect=check_rate_limit,
    ):
        response = client.post(
            "/api/v1/auth/refresh",
            json={
                "refresh_token": "invalid-refresh-token",
            },
        )

    assert response.status_code == 401

    keys = list(redis_client.scan_iter(match="helpdesk:rate_limit:refresh:*"))

    assert len(keys) == 1
    assert int(redis_client.get(keys[0])) == 1
    assert 0 < redis_client.ttl(keys[0]) <= 60


def test_login_and_refresh_rate_limits_are_independent(client):
    with patch(
        "routes.auth.check_rate_limit",
        side_effect=check_rate_limit,
    ):
        login = client.post(
            "/api/v1/auth/login",
            data={
                "username": "unknown@example.com",
                "password": "WrongPassword123!",
            },
        )

        refresh = client.post(
            "/api/v1/auth/refresh",
            json={
                "refresh_token": "invalid-refresh-token",
            },
        )

    assert login.status_code == 401
    assert refresh.status_code == 401

    login_keys = list(redis_client.scan_iter(match="helpdesk:rate_limit:login:*"))

    refresh_keys = list(redis_client.scan_iter(match="helpdesk:rate_limit:refresh:*"))

    assert len(login_keys) == 1
    assert len(refresh_keys) == 1

    assert int(redis_client.get(login_keys[0])) == 1
    assert int(redis_client.get(refresh_keys[0])) == 1
