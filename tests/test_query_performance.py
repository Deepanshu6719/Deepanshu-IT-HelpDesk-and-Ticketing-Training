import pytest

from core.query_profiler import profile_queries


@pytest.mark.parametrize("ticket_count", [1, 10, 50])
def test_measure_ticket_list_queries(
    client,
    db_session,
    admin_headers,
    department,
    category,
    make_user,
    make_ticket,
    ticket_count,
):
    # Different requesters help expose relationship-loading
    # problems that shared ORM objects might otherwise hide.
    for _ in range(ticket_count):
        requester = make_user(department)

        make_ticket(
            requester,
            category,
        )

    engine = db_session.get_bind()

    # Remove fixture objects from the identity map so that
    # already-loaded relationships do not hide extra queries.
    db_session.expunge_all()

    with profile_queries(engine) as stats:
        response = client.get(
            "/api/v1/tickets",
            params={
                "page": 1,
                "limit": 100,
            },
            headers=admin_headers,
        )

    assert response.status_code == 200

    data = response.json()["data"]

    assert len(data["items"]) == ticket_count
    assert data["total"] == ticket_count

    print("\n" + "=" * 70)
    print(f"Tickets returned: {ticket_count}")
    print(f"SQL queries: {stats.count}")
    print(f"SQL duration: {stats.total_duration_ms:.2f} ms")

    print("\nExecuted SQL statements:")

    for index, statement in enumerate(
        stats.statements,
        start=1,
    ):
        print(f"\nQuery {index}:")
        print(statement)

    print("=" * 70)
    # Prevent N+1 regressions in the ticket-list endpoint.
    assert stats.count <= 7, (
        f"Unexpected query count for {ticket_count} tickets: {stats.count}"
    )
