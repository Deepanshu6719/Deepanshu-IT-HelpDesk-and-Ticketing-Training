import json

import structlog
from redis.exceptions import RedisError

from database.redis import redis_client

logger = structlog.get_logger(__name__)


def invalidate_cache(pattern: str) -> None:
    try:
        cursor = 0
        deleted_count = 0

        while True:
            cursor, keys = redis_client.scan(
                cursor=cursor,
                match=pattern,
                count=100,
            )

            if keys:
                deleted_count += redis_client.delete(*keys)

            if cursor == 0:
                break

        logger.debug(
            "cache_invalidated",
            deleted_count=deleted_count,
        )

    except RedisError as exc:
        logger.warning(
            "cache_invalidation_failed",
            error_type=type(exc).__name__,
        )


def get_cache(key: str):
    try:
        cached_data = redis_client.get(key)

        if cached_data is None:
            logger.debug("cache_miss")
            return None

        data = json.loads(cached_data)

        logger.debug("cache_hit")

        return data

    except (RedisError, json.JSONDecodeError) as exc:
        logger.warning(
            "cache_read_failed",
            error_type=type(exc).__name__,
        )

        return None


def set_cache(key: str, data, ttl: int = 300) -> None:
    try:
        serialized_data = json.dumps(data)

        redis_client.setex(
            key,
            ttl,
            serialized_data,
        )

        logger.debug(
            "cache_set",
            ttl_seconds=ttl,
        )

    except RedisError as exc:
        logger.warning(
            "cache_write_failed",
            error_type=type(exc).__name__,
        )
