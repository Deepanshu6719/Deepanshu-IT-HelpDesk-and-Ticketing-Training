import pytest

from tests.response_helpers import success_data


@pytest.mark.parametrize(
    ("method", "path", "status_code", "error_code"),
    [
        (
            "GET",
            "/api/v1/tickets",
            401,
            "UNAUTHORIZED",
        ),
        (
            "GET",
            "/unknown-endpoint",
            404,
            "NOT_FOUND",
        ),
        (
            "POST",
            "/health",
            405,
            "METHOD_NOT_ALLOWED",
        ),
        (
            "POST",
            "/api/v1/auth/login",
            422,
            "VALIDATION_ERROR",
        ),
        (
            "POST",
            "/api/v1/auth/refresh",
            422,
            "VALIDATION_ERROR",
        ),
    ],
)
def test_standard_error_envelope(
    client,
    method,
    path,
    status_code,
    error_code,
):
    response = client.request(method, path)

    assert response.status_code == status_code

    body = response.json()

    assert set(body) == {
        "success",
        "error",
        "request_id",
    }

    assert body["success"] is False

    assert set(body["error"]) == {
        "code",
        "message",
        "details",
    }

    assert body["error"]["code"] == error_code
    assert isinstance(body["error"]["message"], str)

    assert body["request_id"]
    assert body["request_id"] == response.headers["X-Request-ID"]


def test_unauthorized_response_preserves_authenticate_header(client):
    response = client.get("/api/v1/tickets")

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_method_not_allowed_preserves_allow_header(client):
    response = client.post("/health")

    assert response.status_code == 405
    assert "GET" in response.headers["Allow"]


def test_validation_error_does_not_expose_sensitive_input(client):
    sensitive_value = "sensitive-example-password"

    response = client.post(
        "/api/v1/auth/refresh",
        json={
            "refresh_token": {
                "unexpected": sensitive_value,
            },
        },
    )

    assert response.status_code == 422

    body = response.json()

    assert body["error"]["code"] == "VALIDATION_ERROR"

    details = body["error"]["details"]

    assert isinstance(details, list)
    assert len(details) > 0

    for detail in details:
        assert set(detail) == {
            "location",
            "message",
            "type",
        }

    assert sensitive_value not in response.text


def test_validation_error_identifies_missing_login_fields(client):
    response = client.post("/api/v1/auth/login")

    assert response.status_code == 422

    details = response.json()["error"]["details"]

    locations = {tuple(detail["location"]) for detail in details}

    assert ("body", "username") in locations
    assert ("body", "password") in locations


def test_success_response_contract(client, admin_headers):
    response = client.get(
        "/api/v1/departments",
        headers=admin_headers,
    )

    assert response.status_code == 200

    data = success_data(response)

    assert isinstance(data, dict)

    assert set(data) == {
        "total",
        "page",
        "limit",
        "items",
    }

    assert isinstance(data["items"], list)
    assert set(response.json()) == {"success", "data"}
