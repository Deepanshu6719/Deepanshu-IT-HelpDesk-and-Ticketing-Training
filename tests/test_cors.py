import pytest
from pydantic import ValidationError

from core.config import Settings, settings


def test_trusted_origin_is_allowed(client):
    origin = settings.CORS_ALLOWED_ORIGINS[0]

    response = client.get(
        "/health",
        headers={"Origin": origin},
    )

    assert response.status_code == 200

    assert response.headers["Access-Control-Allow-Origin"] == origin


def test_untrusted_origin_is_not_allowed(client):
    response = client.get(
        "/health",
        headers={"Origin": "https://untrusted.example.com"},
    )

    assert response.status_code == 200

    assert "Access-Control-Allow-Origin" not in response.headers


def test_trusted_origin_preflight(client):
    origin = settings.CORS_ALLOWED_ORIGINS[0]

    response = client.options(
        "/api/v1/tickets",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": ("authorization, content-type"),
        },
    )

    assert response.status_code == 200

    assert response.headers["Access-Control-Allow-Origin"] == origin


def test_untrusted_origin_preflight_is_rejected(client):
    response = client.options(
        "/api/v1/tickets",
        headers={
            "Origin": "https://untrusted.example.com",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 400


def test_unapproved_method_is_rejected(client):
    origin = settings.CORS_ALLOWED_ORIGINS[0]

    response = client.options(
        "/api/v1/tickets",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "PUT",
        },
    )

    assert response.status_code == 400


def test_unapproved_header_is_rejected(client):
    origin = settings.CORS_ALLOWED_ORIGINS[0]

    response = client.options(
        "/api/v1/tickets",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": ("x-unauthorized-header"),
        },
    )

    assert response.status_code == 400


def test_cors_credentials_are_disabled(client):
    origin = settings.CORS_ALLOWED_ORIGINS[0]

    response = client.get(
        "/health",
        headers={"Origin": origin},
    )

    assert "Access-Control-Allow-Credentials" not in response.headers


def test_request_id_is_exposed_to_trusted_origins(client):
    origin = settings.CORS_ALLOWED_ORIGINS[0]

    response = client.get(
        "/health",
        headers={"Origin": origin},
    )

    exposed = response.headers["Access-Control-Expose-Headers"]

    assert "x-request-id" in exposed.lower()


def test_wildcard_origin_configuration_is_rejected():
    with pytest.raises(
        ValidationError,
        match="Wildcard CORS origins are not allowed",
    ):
        Settings(CORS_ALLOWED_ORIGINS=["*"])
