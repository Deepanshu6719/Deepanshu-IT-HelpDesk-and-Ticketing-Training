from fastapi import Request
from prometheus_client import Counter, Histogram

HTTP_REQUESTS_TOTAL = Counter(
    "helpdesk_http_requests_total",
    "Total HTTP requests processed by the Helpdesk API",
    ["method", "route", "status_code"],
)

HTTP_REQUEST_DURATION = Histogram(
    "helpdesk_http_request_duration_seconds",
    "HTTP request processing duration in seconds",
    ["method", "route"],
    buckets=(
        0.005,
        0.01,
        0.025,
        0.05,
        0.1,
        0.25,
        0.5,
        1.0,
        2.5,
        5.0,
        10.0,
    ),
)


def get_route_template(request: Request) -> str:
    fastapi_scope = request.scope.get("fastapi", {})

    effective_route = fastapi_scope.get("effective_route_context")

    effective_path = getattr(
        effective_route,
        "path",
        None,
    )

    if effective_path:
        return effective_path

    route = request.scope.get("route")

    return getattr(route, "path", "unmatched")


def record_request_metrics(
    request: Request,
    status_code: int,
    duration_seconds: float,
) -> None:
    route_path = get_route_template(request)

    if route_path == "/metrics":
        return

    HTTP_REQUESTS_TOTAL.labels(
        method=request.method,
        route=route_path,
        status_code=str(status_code),
    ).inc()

    HTTP_REQUEST_DURATION.labels(
        method=request.method,
        route=route_path,
    ).observe(duration_seconds)
