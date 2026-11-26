import structlog
from fastapi import Request, status
from fastapi.responses import JSONResponse

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

    headers = {}

    if request_id is not None:
        headers["X-Request-ID"] = request_id

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "Internal server error",
            "request_id": request_id,
        },
        headers=headers,
    )
