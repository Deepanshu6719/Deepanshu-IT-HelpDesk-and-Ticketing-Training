from fastapi import HTTPException, status
from redis.exceptions import RedisError

from database.redis import redis_client

RATE_LIMIT_SCRIPT = """
local count = redis.call('INCR', KEYS[1])

if count == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end

return count
"""

rate_limit_script = redis_client.register_script(
    RATE_LIMIT_SCRIPT
)
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
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please try again later.",
            )

    except RedisError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Rate limiting service is unavailable.",
        )