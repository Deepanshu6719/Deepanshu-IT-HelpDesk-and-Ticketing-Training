from sqlalchemy import text
from sqlalchemy.pool import QueuePool

from core.config import settings
from database.connection import engine


def test_engine_uses_queue_pool():
    assert isinstance(engine.pool, QueuePool)


def test_pool_size_matches_settings():
    assert engine.pool.size() == settings.DB_POOL_SIZE


def test_pool_timeout_matches_settings():
    assert engine.pool.timeout() == settings.DB_POOL_TIMEOUT


def test_database_connections_return_to_pool(db_session):
    bind = db_session.get_bind()
    test_engine = bind.engine
    pool = test_engine.pool

    checked_out_before = pool.checkedout()

    with test_engine.connect() as connection:
        result = connection.execute(text("SELECT 1"))

        assert result.scalar_one() == 1
        assert pool.checkedout() == checked_out_before + 1

    assert pool.checkedout() == checked_out_before
