import structlog
from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from api.docs.common import example_response
from database.connection import engine
from database.redis import redis_client

router = APIRouter(tags=["Health"])

logger = structlog.get_logger(__name__)


@router.get(
    "/health",
    summary="Check application liveness",
    description=(
        "Check whether the API process is responding. "
        "Does not verify external dependency connectivity."
    ),
    responses={
        200: example_response(
            "Application is alive.",
            {"status": "healthy"},
        ),
    },
)
def health_check():
    return {"status": "healthy"}


def check_postgres() -> bool:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        return True

    except SQLAlchemyError as exc:
        logger.warning(
            "readiness_check_failed",
            dependency="postgres",
            error_type=type(exc).__name__,
        )

        return False


def check_redis() -> bool:
    try:
        return bool(redis_client.ping())

    except RedisError as exc:
        logger.warning(
            "readiness_check_failed",
            dependency="redis",
            error_type=type(exc).__name__,
        )

        return False


@router.get(
    "/ready",
    summary="Check application readiness",
    description=(
        "Verify PostgreSQL and Redis connectivity. "
        "Returns HTTP 503 when either dependency is unavailable."
    ),
    responses={
        200: example_response(
            "All required dependencies are available.",
            {
                "status": "ready",
                "checks": {
                    "postgres": "up",
                    "redis": "up",
                },
            },
        ),
        503: example_response(
            "One or more dependencies are unavailable.",
            {
                "status": "not_ready",
                "checks": {
                    "postgres": "down",
                    "redis": "up",
                },
            },
        ),
    },
)
def readiness_check():
    postgres_ready = check_postgres()
    redis_ready = check_redis()

    is_ready = postgres_ready and redis_ready

    return JSONResponse(
        status_code=(
            status.HTTP_200_OK if is_ready else status.HTTP_503_SERVICE_UNAVAILABLE
        ),
        content={
            "status": "ready" if is_ready else "not_ready",
            "checks": {
                "postgres": "up" if postgres_ready else "down",
                "redis": "up" if redis_ready else "down",
            },
        },
    )
