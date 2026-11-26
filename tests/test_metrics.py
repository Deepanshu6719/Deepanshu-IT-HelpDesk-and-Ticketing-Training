from fastapi.testclient import TestClient
from prometheus_client.parser import (
    text_string_to_metric_families,
)

from main import app


def get_metric_value(
    client: TestClient,
    metric_name: str,
    labels: dict[str, str],
) -> float:
    response = client.get("/metrics")

    assert response.status_code == 200

    for family in text_string_to_metric_families(response.text):
        for sample in family.samples:
            if sample.name == metric_name and sample.labels == labels:
                return sample.value

    return 0.0


def test_successful_request_increments_counter():
    labels = {
        "method": "GET",
        "route": "/health",
        "status_code": "200",
    }

    with TestClient(app) as client:
        before = get_metric_value(
            client,
            "helpdesk_http_requests_total",
            labels,
        )

        response = client.get("/health")

        assert response.status_code == 200

        after = get_metric_value(
            client,
            "helpdesk_http_requests_total",
            labels,
        )

        assert after == before + 1


def test_unmatched_request_increments_counter():
    labels = {
        "method": "GET",
        "route": "unmatched",
        "status_code": "404",
    }

    with TestClient(app) as client:
        before = get_metric_value(
            client,
            "helpdesk_http_requests_total",
            labels,
        )

        response = client.get("/nonexistent-test-route")

        assert response.status_code == 404

        after = get_metric_value(
            client,
            "helpdesk_http_requests_total",
            labels,
        )

        assert after == before + 1


def test_request_duration_is_recorded():
    labels = {
        "method": "GET",
        "route": "/health",
    }

    with TestClient(app) as client:
        count_before = get_metric_value(
            client,
            "helpdesk_http_request_duration_seconds_count",
            labels,
        )

        sum_before = get_metric_value(
            client,
            "helpdesk_http_request_duration_seconds_sum",
            labels,
        )

        response = client.get("/health")

        assert response.status_code == 200

        count_after = get_metric_value(
            client,
            "helpdesk_http_request_duration_seconds_count",
            labels,
        )

        sum_after = get_metric_value(
            client,
            "helpdesk_http_request_duration_seconds_sum",
            labels,
        )

        assert count_after == count_before + 1
        assert sum_after > sum_before


def test_metrics_endpoint_is_not_counted():
    labels = {
        "method": "GET",
        "route": "/metrics",
        "status_code": "200",
    }

    with TestClient(app) as client:
        for _ in range(3):
            response = client.get("/metrics")

            assert response.status_code == 200

        count = get_metric_value(
            client,
            "helpdesk_http_requests_total",
            labels,
        )

        assert count == 0


def test_unhandled_exception_increments_counter():
    def trigger_error():
        raise RuntimeError("Synthetic metrics test")

    original_routes = list(app.router.routes)

    app.add_api_route(
        "/_test/metrics-error",
        trigger_error,
        methods=["GET"],
        include_in_schema=False,
    )

    labels = {
        "method": "GET",
        "route": "/_test/metrics-error",
        "status_code": "500",
    }

    try:
        with TestClient(
            app,
            raise_server_exceptions=False,
        ) as client:
            before = get_metric_value(
                client,
                "helpdesk_http_requests_total",
                labels,
            )

            response = client.get("/_test/metrics-error")

            assert response.status_code == 500

            after = get_metric_value(
                client,
                "helpdesk_http_requests_total",
                labels,
            )

            assert after == before + 1

    finally:
        app.router.routes[:] = original_routes


def test_dynamic_route_uses_route_template():
    labels = {
        "method": "GET",
        "route": "/api/v1/tickets/{ticket_id}",
        "status_code": "401",
    }

    with TestClient(app) as client:
        before = get_metric_value(
            client,
            "helpdesk_http_requests_total",
            labels,
        )

        response_one = client.get("/api/v1/tickets/123")
        response_two = client.get("/api/v1/tickets/456")

        assert response_one.status_code == 401
        assert response_two.status_code == 401

        after = get_metric_value(
            client,
            "helpdesk_http_requests_total",
            labels,
        )

        assert after == before + 2
