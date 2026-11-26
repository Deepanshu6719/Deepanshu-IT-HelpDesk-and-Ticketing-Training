import time
from uuid import uuid4

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from structlog.contextvars import (
    bind_contextvars,
    clear_contextvars,
)

from api.v1.router import router as api_v1_router
from core.config import settings
from core.error_tracking import handle_unhandled_exception
from core.exception_handlers import (
    handle_http_exception,
    handle_validation_exception,
)
from core.logging import configure_logging
from core.metrics import record_request_metrics
from core.openapi import (
    API_DESCRIPTION,
    API_TITLE,
    API_VERSION,
    OPENAPI_TAGS,
)
from core.security_headers import SecurityHeadersMiddleware
from routes.health import router as health_router
from routes.metrics import router as metrics_router

configure_logging()

logger = structlog.get_logger(__name__)

app = FastAPI(
    title=API_TITLE,
    description=API_DESCRIPTION,
    version=API_VERSION,
    openapi_tags=OPENAPI_TAGS,
    swagger_ui_parameters={
        "docExpansion": "none",
        "displayRequestDuration": True,
        "filter": True,
        "persistAuthorization": False,
    },
)


app.add_exception_handler(
    StarletteHTTPException,
    handle_http_exception,
)

app.add_exception_handler(
    RequestValidationError,
    handle_validation_exception,
)

app.add_exception_handler(
    Exception,
    handle_unhandled_exception,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=[
        "GET",
        "POST",
        "PATCH",
        "DELETE",
        "OPTIONS",
    ],
    allow_headers=[
        "Authorization",
        "Content-Type",
    ],
    expose_headers=[
        "X-Request-ID",
    ],
    max_age=600,
)
app.add_middleware(
    SecurityHeadersMiddleware,
    hsts_enabled=settings.SECURITY_HSTS_ENABLED,
    hsts_max_age=settings.SECURITY_HSTS_MAX_AGE,
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


app.include_router(api_v1_router)
app.include_router(health_router)
app.include_router(metrics_router)
