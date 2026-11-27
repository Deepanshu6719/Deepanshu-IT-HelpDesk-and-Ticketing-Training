from sqlalchemy import text

from core.query_profiler import profile_queries


def test_query_profiler_counts_sql_statements(db_session):
    # Initialize the session transaction before profiling.
    db_session.connection()

    bind = db_session.get_bind()

    with profile_queries(bind) as stats:
        db_session.execute(text("SELECT 1"))
        db_session.execute(text("SELECT 2"))
        db_session.execute(text("SELECT 3"))

    assert stats.count == 3
    assert len(stats.statements) == 3
    assert stats.total_duration_ms >= 0

    assert stats.statements == [
        "SELECT 1",
        "SELECT 2",
        "SELECT 3",
    ]


def test_query_profiler_stops_after_context_exit(db_session):
    # Initialize the session transaction before profiling.
    db_session.connection()

    bind = db_session.get_bind()

    with profile_queries(bind) as stats:
        db_session.execute(text("SELECT 1"))

    db_session.execute(text("SELECT 2"))

    assert stats.count == 1
    assert stats.statements == ["SELECT 1"]


def test_query_profiler_handles_no_queries(db_session):
    bind = db_session.get_bind()

    with profile_queries(bind) as stats:
        pass

    assert stats.count == 0
    assert stats.total_duration_ms == 0
    assert stats.average_duration_ms == 0
