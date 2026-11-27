from uuid import uuid4

import structlog
from redis.exceptions import RedisError

from core.ticket_scope import get_ticket_scope
from database.redis import redis_client
from models.user import User

logger = structlog.get_logger(__name__)

DASHBOARD_CACHE_PREFIX = "helpdesk:dashboard:v1"
DASHBOARD_GENERATION_KEY = f"{DASHBOARD_CACHE_PREFIX}:generation"
DASHBOARD_CACHE_TTL = 60


def get_dashboard_generation() -> str | None:
    try:
        generation = redis_client.get(DASHBOARD_GENERATION_KEY)

        if generation is not None:
            return generation

        new_generation = uuid4().hex

        redis_client.set(
            DASHBOARD_GENERATION_KEY,
            new_generation,
            nx=True,
        )

        return redis_client.get(DASHBOARD_GENERATION_KEY)

    except RedisError as exc:
        logger.warning(
            "dashboard_generation_read_failed",
            error_type=type(exc).__name__,
        )

        return None


def get_dashboard_cache_key(
    current_user: User,
    generation: str,
) -> str:
    scope = get_ticket_scope(current_user)

    return f"{DASHBOARD_CACHE_PREFIX}:{generation}:{scope}:{current_user.id}"


def invalidate_dashboard_cache() -> None:
    try:
        redis_client.set(
            DASHBOARD_GENERATION_KEY,
            uuid4().hex,
        )

        logger.debug(
            "dashboard_cache_invalidated",
        )

    except RedisError as exc:
        logger.warning(
            "dashboard_cache_invalidation_failed",
            error_type=type(exc).__name__,
        )
