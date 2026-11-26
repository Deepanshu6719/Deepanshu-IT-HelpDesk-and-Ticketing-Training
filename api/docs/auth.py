from api.docs.errors import (
    RATE_LIMIT_RESPONSE,
    SERVICE_UNAVAILABLE_RESPONSE,
    error_example_response,
)
from schema.common_schema import ErrorResponse

TOKEN_EXAMPLE = {
    "access_token": "example.jwt.access-token",
    "refresh_token": "example-opaque-refresh-token",
    "token_type": "bearer",
}


def auth_error_example(message: str) -> dict:
    return {
        "success": False,
        "error": {
            "code": "UNAUTHORIZED",
            "message": message,
            "details": None,
        },
        "request_id": "123e4567-e89b-42d3-a456-426614174000",
    }


LOGIN_RESPONSES = {
    200: {
        "description": "Authentication successful. A new device session is created.",
        "content": {
            "application/json": {
                "example": TOKEN_EXAMPLE,
            },
        },
    },
    401: error_example_response(
        code="UNAUTHORIZED",
        message="Incorrect email or password",
        description="Invalid credentials or inactive account.",
    ),
    429: RATE_LIMIT_RESPONSE,
    503: SERVICE_UNAVAILABLE_RESPONSE,
}


REFRESH_RESPONSES = {
    200: {
        "description": "Access token renewed and refresh token rotated.",
        "content": {
            "application/json": {
                "example": TOKEN_EXAMPLE,
            },
        },
    },
    401: {
        "model": ErrorResponse,
        "description": (
            "Invalid, expired or reused refresh token, "
            "invalid session, or inactive user."
        ),
        "content": {
            "application/json": {
                "examples": {
                    "invalid_token": {
                        "summary": "Invalid refresh token",
                        "value": auth_error_example("Invalid refresh token"),
                    },
                    "expired_token": {
                        "summary": "Expired refresh token",
                        "value": auth_error_example("Refresh token has expired"),
                    },
                    "token_reuse": {
                        "summary": "Refresh token reuse detected",
                        "value": auth_error_example(
                            "Refresh token reuse detected. Session revoked."
                        ),
                    },
                    "invalid_session": {
                        "summary": "Invalid session",
                        "value": auth_error_example("Session is no longer valid"),
                    },
                },
            },
        },
    },
}


LOGOUT_RESPONSES = {
    200: {
        "description": "Current device session successfully revoked.",
        "content": {
            "application/json": {
                "example": {
                    "success": True,
                    "data": {
                        "message": "Successfully logged out from this device",
                    },
                },
            },
        },
    },
    401: error_example_response(
        code="UNAUTHORIZED",
        message="Invalid session",
        description=(
            "Missing or invalid authentication credentials, or invalid session."
        ),
    ),
}
