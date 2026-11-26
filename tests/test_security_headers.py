import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.security_headers import SecurityHeadersMiddleware
from main import app


def assert_security_headers(response):
    assert response.headers["X-Content-Type-Options"] == "nosniff"

    assert response.headers["X-Frame-Options"] == "DENY"

    assert response.headers["Referrer-Policy"] == "no-referrer"

    assert (
        response.headers["Permissions-Policy"]
        == "camera=(), microphone=(), geolocation=()"
    )


@pytest.mark.parametrize(
    "path,expected_status",
    [
        ("/health", 200),
        ("/api/v1/tickets", 401),
        ("/nonexistent-security-test-route", 404),
        ("/docs", 200),
    ],
)
def test_security_headers_on_responses(
    client,
    path,
    expected_status,
):
    response = client.get(path)

    assert response.status_code == expected_status

    assert_security_headers(response)


def test_security_headers_on_validation_error(client):
    response = client.post(
        "/api/v1/auth/refresh",
        json={},
    )

    assert response.status_code == 422

    assert_security_headers(response)


def test_security_headers_on_unhandled_error():
    async def failing_endpoint():
        raise RuntimeError("Simulated security header test")

    app.add_api_route(
        "/security-test-error",
        failing_endpoint,
        methods=["GET"],
        include_in_schema=False,
    )

    try:
        with TestClient(
            app,
            raise_server_exceptions=False,
        ) as client:
            response = client.get("/security-test-error")

        assert response.status_code == 500

        assert_security_headers(response)

    finally:
        app.router.routes[:] = [
            route
            for route in app.router.routes
            if getattr(route, "path", None) != "/security-test-error"
        ]


def create_security_test_app(hsts_enabled):
    test_app = FastAPI()

    test_app.add_middleware(
        SecurityHeadersMiddleware,
        hsts_enabled=hsts_enabled,
        hsts_max_age=31536000,
    )

    @test_app.get("/")
    def root():
        return {"status": "ok"}

    return test_app


@pytest.mark.parametrize(
    "hsts_enabled,scheme,expected",
    [
        (False, "http", False),
        (False, "https", False),
        (True, "http", False),
        (True, "https", True),
    ],
)
def test_hsts_configuration(
    hsts_enabled,
    scheme,
    expected,
):
    test_app = create_security_test_app(hsts_enabled)

    with TestClient(
        test_app,
        base_url=f"{scheme}://testserver",
    ) as client:
        response = client.get("/")

    assert response.status_code == 200

    assert ("Strict-Transport-Security" in response.headers) is expected

    if expected:
        assert response.headers["Strict-Transport-Security"] == "max-age=31536000"
