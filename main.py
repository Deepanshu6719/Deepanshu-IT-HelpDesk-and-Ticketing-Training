import time
from uuid import uuid4

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from structlog.contextvars import (
    bind_contextvars,
    clear_contextvars,
)

from core.error_tracking import handle_unhandled_exception
from core.logging import configure_logging
from core.metrics import record_request_metrics
from routes.admin import router as admin_router
from routes.agents import router as agent_router
from routes.auth import router as auth_router
from routes.category import router as category_router
from routes.comments import router as comment_router
from routes.departments import router as department_router
from routes.health import router as health_router
from routes.metrics import router as metrics_router
from routes.tickets import router as ticket_router
from routes.users import router as user_router

configure_logging()

logger = structlog.get_logger(__name__)

app = FastAPI()
app.add_exception_handler(
    Exception,
    handle_unhandled_exception,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    clear_contextvars()

    request_id = str(uuid4())

    bind_contextvars(request_id=request_id)

    request.state.request_id = request_id

    start_time = time.perf_counter()

    status_code = 500

    try:
        logger.info(
            "request_started",
            method=request.method,
            path=request.url.path,
        )

        response = await call_next(request)

        status_code = response.status_code

        duration_ms = (time.perf_counter() - start_time) * 1000

        logger.info(
            "request_completed",
            method=request.method,
            path=request.url.path,
            status_code=status_code,
            duration_ms=round(duration_ms, 2),
        )

        response.headers["X-Request-ID"] = request_id

        return response

    except Exception:
        duration_ms = (time.perf_counter() - start_time) * 1000

        logger.error(
            "request_failed",
            method=request.method,
            path=request.url.path,
            status_code=500,
            duration_ms=round(duration_ms, 2),
        )

        raise

    finally:
        duration_seconds = time.perf_counter() - start_time

        try:
            record_request_metrics(
                request=request,
                status_code=status_code,
                duration_seconds=duration_seconds,
            )
        finally:
            clear_contextvars()


app.include_router(ticket_router)
app.include_router(category_router)
app.include_router(admin_router)
app.include_router(auth_router)
app.include_router(comment_router)
app.include_router(user_router)
app.include_router(department_router)
app.include_router(agent_router)
app.include_router(health_router)
app.include_router(metrics_router)
