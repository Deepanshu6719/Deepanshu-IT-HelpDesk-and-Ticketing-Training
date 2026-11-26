from http import HTTPStatus

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from schema.common_schema import (
    ErrorDetail,
    ErrorInfo,
    ErrorResponse,
)

ERROR_CODES = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    422: "VALIDATION_ERROR",
    429: "RATE_LIMIT_EXCEEDED",
    500: "INTERNAL_SERVER_ERROR",
    503: "SERVICE_UNAVAILABLE",
}


def build_error_response(
    request: Request,
    status_code: int,
    message: str,
    details: list[ErrorDetail] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)

    error_response = ErrorResponse(
        error=ErrorInfo(
            code=ERROR_CODES.get(
                status_code,
                f"HTTP_{status_code}",
            ),
            message=message,
            details=details,
        ),
        request_id=request_id,
    )

    response_headers = dict(headers or {})

    if request_id is not None:
        response_headers["X-Request-ID"] = request_id

    return JSONResponse(
        status_code=status_code,
        content=error_response.model_dump(mode="json"),
        headers=response_headers,
    )


async def handle_http_exception(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    if exc.status_code >= 500 and exc.status_code != 503:
        message = "Internal server error"
    elif isinstance(exc.detail, str):
        message = exc.detail
    else:
        try:
            message = HTTPStatus(exc.status_code).phrase
        except ValueError:
            message = "Request failed"

    return build_error_response(
        request=request,
        status_code=exc.status_code,
        message=message,
        headers=exc.headers,
    )


async def handle_validation_exception(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    details = [
        ErrorDetail(
            location=list(error["loc"]),
            message=error["msg"],
            type=error["type"],
        )
        for error in exc.errors()
    ]

    return build_error_response(
        request=request,
        status_code=422,
        message="Request validation failed",
        details=details,
    )
