import pytest
from sqlalchemy import select
from sqlalchemy.orm import lazyload, selectinload

from core.query_profiler import profile_queries
from models.ticket import Ticket


@pytest.mark.parametrize("ticket_count", [1, 10, 50])
def test_compare_lazy_and_eager_loading(
    db_session,
    department,
    category,
    make_user,
    make_ticket,
    ticket_count,
):
    # Each ticket has a different requester.
    for _ in range(ticket_count):
        requester = make_user(department)
        make_ticket(requester, category)

    bind = db_session.get_bind()

    # Initialize the test transaction outside profiling.
    db_session.connection()

    # Remove previously loaded objects.
    db_session.expunge_all()

    # ------------------------------------------
    # BEFORE: Lazy loading (N+1)
    # ------------------------------------------
    lazy_statement = (
        select(Ticket).options(lazyload(Ticket.requester)).order_by(Ticket.id)
    )

    with profile_queries(bind) as lazy_stats:
        lazy_tickets = db_session.scalars(lazy_statement).all()

        lazy_results = [(ticket.id, ticket.requester.email) for ticket in lazy_tickets]

    # Clear the identity map again for a fair comparison.
    db_session.expunge_all()

    # ------------------------------------------
    # AFTER: Eager loading
    # ------------------------------------------
    eager_statement = (
        select(Ticket).options(selectinload(Ticket.requester)).order_by(Ticket.id)
    )

    with profile_queries(bind) as eager_stats:
        eager_tickets = db_session.scalars(eager_statement).all()

        eager_results = [
            (ticket.id, ticket.requester.email) for ticket in eager_tickets
        ]

    # Both approaches must return identical data.
    assert len(lazy_results) == ticket_count
    assert lazy_results == eager_results

    print("\n" + "=" * 60)
    print(f"Tickets: {ticket_count}")
    print(f"Lazy loading queries: {lazy_stats.count}")
    print(f"Eager loading queries: {eager_stats.count}")
    print(f"Lazy SQL duration: {lazy_stats.total_duration_ms:.2f} ms")
    print(f"Eager SQL duration: {eager_stats.total_duration_ms:.2f} ms")

    print("\nLazy loading SQL:")

    for statement in lazy_stats.statements:
        print(statement)

    print("\nEager loading SQL:")

    for statement in eager_stats.statements:
        print(statement)

    print("=" * 60)

    assert lazy_stats.count == ticket_count + 1
    assert eager_stats.count == 2
