import asyncio
import logging
from uuid import UUID

from fastapi import Depends
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from structlog.contextvars import get_contextvars

from core.dependencies import get_current_user
from main import app
from models.user import User


def test_unhandled_exception_returns_request_id():
    def trigger_error():
        raise RuntimeError("Synthetic observability test")

    original_routes = list(app.router.routes)

    app.add_api_route(
        "/_test/observability-error",
        trigger_error,
        methods=["GET"],
        include_in_schema=False,
    )

    try:
        with TestClient(
            app,
            raise_server_exceptions=False,
        ) as client:
            response = client.get("/_test/observability-error")

        assert response.status_code == 500

        request_id = response.headers["X-Request-ID"]

        assert UUID(request_id).version == 4

        assert response.json() == {
            "detail": "Internal server error",
            "request_id": request_id,
        }

        assert "Synthetic observability test" not in response.text

    finally:
        app.router.routes[:] = original_routes


def test_concurrent_requests_have_isolated_context():
    both_started = asyncio.Event()
    started_count = 0

    async def inspect_context():
        nonlocal started_count

        request_id_before = get_contextvars().get("request_id")

        started_count += 1

        if started_count == 2:
            both_started.set()

        await asyncio.wait_for(
            both_started.wait(),
            timeout=5,
        )

        request_id_after = get_contextvars().get("request_id")

        return {
            "before": request_id_before,
            "after": request_id_after,
        }

    original_routes = list(app.router.routes)

    app.add_api_route(
        "/_test/request-context",
        inspect_context,
        methods=["GET"],
        include_in_schema=False,
    )

    async def run_concurrent_requests():
        transport = ASGITransport(app=app)

        async with AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            return await asyncio.gather(
                client.get("/_test/request-context"),
                client.get("/_test/request-context"),
            )

    try:
        first, second = asyncio.run(run_concurrent_requests())

        assert first.status_code == 200
        assert second.status_code == 200

        first_id = first.headers["X-Request-ID"]
        second_id = second.headers["X-Request-ID"]

        assert first_id != second_id

        assert first.json() == {
            "before": first_id,
            "after": first_id,
        }

        assert second.json() == {
            "before": second_id,
            "after": second_id,
        }

    finally:
        app.router.routes[:] = original_routes


def test_authenticated_exception_logs_user_context(
    client,
    requester_user,
    requester_headers,
    caplog,
):
    def trigger_authenticated_error(
        current_user: User = Depends(get_current_user),
    ):
        raise RuntimeError("Authenticated observability test")

    original_routes = list(app.router.routes)

    app.add_api_route(
        "/_test/authenticated-error",
        trigger_authenticated_error,
        methods=["GET"],
        include_in_schema=False,
    )

    try:
        caplog.clear()

        with (
            caplog.at_level(
                logging.ERROR,
                logger="core.error_tracking",
            ),
            TestClient(
                app,
                raise_server_exceptions=False,
            ) as error_client,
        ):
            response = error_client.get(
                "/_test/authenticated-error",
                headers=requester_headers,
            )

        assert response.status_code == 500

        request_id = response.headers["X-Request-ID"]

        assert response.json() == {
            "detail": "Internal server error",
            "request_id": request_id,
        }

        error_events = [
            record.msg
            for record in caplog.records
            if record.name == "core.error_tracking"
            and isinstance(record.msg, dict)
            and record.msg.get("event") == "unhandled_exception"
            and record.msg.get("request_id") == request_id
        ]

        assert len(error_events) == 1

        error_event = error_events[0]

        assert error_event["user_id"] == requester_user.id
        assert error_event["status_code"] == 500
        assert error_event["error_type"] == "RuntimeError"
        assert error_event["method"] == "GET"
        assert error_event["path"] == "/_test/authenticated-error"

        exception = error_event["exc_info"]

        assert isinstance(exception, RuntimeError)
        assert str(exception) == "Authenticated observability test"
        assert exception.__traceback__ is not None

        assert "Authenticated observability test" not in response.text

    finally:
        app.router.routes[:] = original_routes
