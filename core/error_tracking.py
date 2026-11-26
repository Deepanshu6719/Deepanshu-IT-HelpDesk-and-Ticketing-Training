import structlog
from fastapi import Request
from fastapi.responses import JSONResponse

from core.config import settings
from core.exception_handlers import build_error_response
from core.security_headers import apply_security_headers

logger = structlog.get_logger(__name__)


async def handle_unhandled_exception(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    request_id = getattr(
        request.state,
        "request_id",
        None,
    )

    user_id = getattr(
        request.state,
        "user_id",
        None,
    )

    logger.error(
        "unhandled_exception",
        request_id=request_id,
        user_id=user_id,
        method=request.method,
        path=request.url.path,
        status_code=500,
        error_type=type(exc).__name__,
        exc_info=exc,
    )

    response = build_error_response(
        request=request,
        status_code=500,
        message="Internal server error",
    )
    apply_security_headers(
        response.headers,
        hsts_enabled=settings.SECURITY_HSTS_ENABLED,
        hsts_max_age=settings.SECURITY_HSTS_MAX_AGE,
        is_https=request.url.scheme == "https",
    )

    return response
