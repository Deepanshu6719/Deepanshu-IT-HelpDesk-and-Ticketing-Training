from contextlib import contextmanager
from dataclasses import dataclass, field
from time import perf_counter

from sqlalchemy import event
from sqlalchemy.engine import Connection, Engine


@dataclass
class QueryStats:
    count: int = 0
    total_duration_ms: float = 0.0
    statements: list[str] = field(default_factory=list)

    @property
    def average_duration_ms(self) -> float:
        if self.count == 0:
            return 0.0

        return self.total_duration_ms / self.count


@contextmanager
def profile_queries(engine: Engine | Connection):
    stats = QueryStats()

    def before_cursor_execute(
        conn,
        cursor,
        statement,
        parameters,
        context,
        executemany,
    ):
        context._profile_started_at = perf_counter()

        stats.count += 1
        stats.statements.append(statement)

    def after_cursor_execute(
        conn,
        cursor,
        statement,
        parameters,
        context,
        executemany,
    ):
        started_at = getattr(
            context,
            "_profile_started_at",
            None,
        )

        if started_at is not None:
            stats.total_duration_ms += (perf_counter() - started_at) * 1000

    event.listen(
        engine,
        "before_cursor_execute",
        before_cursor_execute,
    )

    event.listen(
        engine,
        "after_cursor_execute",
        after_cursor_execute,
    )

    try:
        yield stats

    finally:
        event.remove(
            engine,
            "before_cursor_execute",
            before_cursor_execute,
        )

        event.remove(
            engine,
            "after_cursor_execute",
            after_cursor_execute,
        )
