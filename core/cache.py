import json
import logging
from redis.exceptions import RedisError

from database.redis import redis_client

logger = logging.getLogger(__name__)

def invalidate_cache(pattern: str) -> None:
    try:
        cursor = 0

        while True:
            cursor, keys = redis_client.scan(
                cursor=cursor,
                match=pattern,
                count=100,
            )

            if keys:
                redis_client.delete(*keys)

            if cursor == 0:
                break

    except RedisError:
        logger.exception("Redis cache invalidation failed")

def get_cache(key: str):
    try:
        cached_data = redis_client.get(key)

        if cached_data is None:
            return None
        return json.loads(cached_data)

    except (RedisError, json.JSONDecodeError):
        logger.exception("Redis cache read failed")
        return None

def set_cache(key: str, data, ttl: int = 300) -> None:
    try:
        serialized_data = json.dumps(data)

        redis_client.setex(
            key,
            ttl,
            serialized_data,
        )

    except RedisError:
        logger.exception("Redis cache write failed")