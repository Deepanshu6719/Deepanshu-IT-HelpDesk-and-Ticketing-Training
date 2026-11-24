import uuid

import pytest
from fastapi import HTTPException

from core.rate_limit import check_rate_limit
from database.redis import redis_client
from unittest.mock import patch
from redis.exceptions import RedisError

def test_rate_limit_blocks_requests_after_limit():
    key = f"test:rate_limit:{uuid.uuid4()}"

    try:
        # First five attempts should be allowed.
        for _ in range(5):
            check_rate_limit(
                key=key,
                limit=5,
                window=60,
            )

        # Sixth attempt should be blocked.
        with pytest.raises(HTTPException) as exc_info:
            check_rate_limit(
                key=key,
                limit=5,
                window=60,
            )

        assert exc_info.value.status_code == 429

    finally:
        redis_client.delete(key)

def test_rate_limit_counter_has_expiration():
    key = f"test:rate_limit:{uuid.uuid4()}"

    try:
        check_rate_limit(
            key=key,
            limit=5,
            window=60,
        )

        ttl = redis_client.ttl(key)

        assert 0 < ttl <= 60

    finally:
        redis_client.delete(key)

def test_rate_limit_returns_503_when_redis_fails():
    with patch(
        "core.rate_limit.rate_limit_script",
        side_effect=RedisError("Redis unavailable"),
    ):
        with pytest.raises(HTTPException) as exc_info:
            check_rate_limit(
                key="test:redis_failure",
                limit=5,
                window=60,
            )

    assert exc_info.value.status_code == 503