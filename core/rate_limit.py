import structlog
from fastapi import HTTPException, status
from redis.exceptions import RedisError

from database.redis import redis_client

logger = structlog.get_logger(__name__)

RATE_LIMIT_SCRIPT = """
local count = redis.call('INCR', KEYS[1])

if count == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end

return count
"""

rate_limit_script = redis_client.register_script(RATE_LIMIT_SCRIPT)


def check_rate_limit(
    key: str,
    limit: int,
    window: int,
) -> None:
    try:
        count = rate_limit_script(
            keys=[key],
            args=[window],
        )

        if count > limit:
            logger.warning(
                "rate_limit_exceeded",
                request_count=count,
                limit=limit,
                window_seconds=window,
            )

            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please try again later.",
            )

        logger.debug(
            "rate_limit_allowed",
            request_count=count,
            limit=limit,
            window_seconds=window,
        )

    except RedisError as exc:
        logger.error(
            "rate_limit_service_unavailable",
            error_type=type(exc).__name__,
        )

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Rate limiting service is unavailable.",
        ) from exc
