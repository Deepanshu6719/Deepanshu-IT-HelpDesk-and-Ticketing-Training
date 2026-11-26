from sqlalchemy import func, select

from models.ticket import Ticket


def test_repeated_ticket_creation_without_idempotency_creates_duplicates(
    client,
    db_session,
    requester_user,
    requester_headers,
    category,
):
    payload = {
        "title": "Duplicate ticket demonstration",
        "description": "The laptop cannot connect to the network.",
        "category": category.name,
        "priority": "medium",
    }

    first = client.post(
        "/api/v1/tickets",
        json=payload,
        headers=requester_headers,
    )

    second = client.post(
        "/api/v1/tickets",
        json=payload,
        headers=requester_headers,
    )

    assert first.status_code == 201
    assert second.status_code == 201

    first_ticket = first.json()["data"]
    second_ticket = second.json()["data"]

    assert first_ticket["id"] != second_ticket["id"]

    assert first_ticket["title"] == second_ticket["title"]
    assert first_ticket["description"] == second_ticket["description"]

    total = db_session.scalar(
        select(func.count())
        .select_from(Ticket)
        .where(
            Ticket.requester_id == requester_user.id,
            Ticket.title == payload["title"],
        )
    )

    assert total == 2

    print(f"First ticket ID: {first_ticket['id']}")
    print(f"Second ticket ID: {second_ticket['id']}")
    print(f"Total matching tickets: {total}")
