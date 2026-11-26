from schema.common_schema import ErrorResponse


def error_example_response(
    code: str,
    message: str,
    description: str,
    details: list[dict] | None = None,
) -> dict:
    return {
        "model": ErrorResponse,
        "description": description,
        "content": {
            "application/json": {
                "example": {
                    "success": False,
                    "error": {
                        "code": code,
                        "message": message,
                        "details": details,
                    },
                    "request_id": ("123e4567-e89b-42d3-a456-426614174000"),
                }
            }
        },
    }


BAD_REQUEST_RESPONSE = error_example_response(
    code="BAD_REQUEST",
    message="Invalid request",
    description="The requested operation is invalid.",
)

UNAUTHORIZED_RESPONSE = error_example_response(
    code="UNAUTHORIZED",
    message="Not authenticated",
    description="Missing, invalid or expired authentication credentials.",
)

FORBIDDEN_RESPONSE = error_example_response(
    code="FORBIDDEN",
    message="You are not allowed to perform this operation",
    description="Insufficient permissions.",
)

NOT_FOUND_RESPONSE = error_example_response(
    code="NOT_FOUND",
    message="Resource not found",
    description="The requested resource does not exist or is inaccessible.",
)

CONFLICT_RESPONSE = error_example_response(
    code="CONFLICT",
    message="Resource already exists",
    description="The operation conflicts with the current resource state.",
)

VALIDATION_ERROR_RESPONSE = error_example_response(
    code="VALIDATION_ERROR",
    message="Request validation failed",
    description="Invalid request parameters or request body.",
    details=[
        {
            "location": ["body", "title"],
            "message": "Field required",
            "type": "missing",
        }
    ],
)

RATE_LIMIT_RESPONSE = error_example_response(
    code="RATE_LIMIT_EXCEEDED",
    message="Too many requests. Please try again later.",
    description="The client has exceeded the allowed request rate.",
)

INTERNAL_SERVER_ERROR_RESPONSE = error_example_response(
    code="INTERNAL_SERVER_ERROR",
    message="Internal server error",
    description="An unexpected server error occurred.",
)

SERVICE_UNAVAILABLE_RESPONSE = error_example_response(
    code="SERVICE_UNAVAILABLE",
    message="Rate limiting service is unavailable.",
    description="A required service is temporarily unavailable.",
)
