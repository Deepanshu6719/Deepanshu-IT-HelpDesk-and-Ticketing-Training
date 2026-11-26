import pytest
from sqlalchemy import func, select

from models.ticket_comment import TicketComment


@pytest.mark.parametrize(
    "method,path_suffix,payload",
    [
        ("GET", "", None),
        ("PATCH", "", {"title": "Unauthorized update"}),
        ("DELETE", "", None),
        ("GET", "/comments", None),
        (
            "POST",
            "/comments",
            {"message": "Unauthorized comment"},
        ),
    ],
)
def test_requester_cannot_access_another_users_ticket(
    client,
    requester_headers,
    department,
    category,
    make_user,
    make_ticket,
    method,
    path_suffix,
    payload,
):
    other_user = make_user(department)

    ticket = make_ticket(other_user, category)

    response = client.request(
        method,
        f"/api/v1/tickets/{ticket.id}{path_suffix}",
        headers=requester_headers,
        json=payload,
    )

    assert response.status_code == 404

    body = response.json()

    assert body["success"] is False
    assert body["error"]["code"] == "NOT_FOUND"


@pytest.mark.parametrize(
    "method,path_suffix,payload",
    [
        ("GET", "", None),
        ("PATCH", "", {"status": "resolved"}),
        ("DELETE", "", None),
        ("GET", "/comments", None),
        (
            "POST",
            "/comments",
            {"message": "Unauthorized agent comment"},
        ),
    ],
)
def test_unassigned_agent_cannot_access_ticket(
    client,
    agent_headers,
    requester_user,
    category,
    make_ticket,
    method,
    path_suffix,
    payload,
):
    ticket = make_ticket(requester_user, category)

    response = client.request(
        method,
        f"/api/v1/tickets/{ticket.id}{path_suffix}",
        headers=agent_headers,
        json=payload,
    )

    assert response.status_code == 404

    body = response.json()

    assert body["success"] is False
    assert body["error"]["code"] == "NOT_FOUND"


def test_unauthorized_ticket_update_preserves_database_state(
    client,
    db_session,
    requester_headers,
    department,
    category,
    make_user,
    make_ticket,
):
    other_user = make_user(department)

    ticket = make_ticket(other_user, category)

    original_title = ticket.title
    original_status = ticket.status
    original_requester_id = ticket.requester_id

    response = client.patch(
        f"/api/v1/tickets/{ticket.id}",
        json={"title": "Unauthorized update"},
        headers=requester_headers,
    )

    assert response.status_code == 404

    db_session.refresh(ticket)

    assert ticket.title == original_title
    assert ticket.status == original_status
    assert ticket.requester_id == original_requester_id


def test_unauthorized_ticket_delete_preserves_database_state(
    client,
    db_session,
    requester_headers,
    department,
    category,
    make_user,
    make_ticket,
):
    other_user = make_user(department)

    ticket = make_ticket(other_user, category)

    response = client.delete(
        f"/api/v1/tickets/{ticket.id}",
        headers=requester_headers,
    )

    assert response.status_code == 404

    db_session.refresh(ticket)

    assert ticket.is_deleted is False
    assert ticket.deleted_at is None


def test_unauthorized_comment_does_not_create_database_record(
    client,
    db_session,
    requester_headers,
    department,
    category,
    make_user,
    make_ticket,
):
    other_user = make_user(department)

    ticket = make_ticket(other_user, category)

    count_statement = (
        select(func.count())
        .select_from(TicketComment)
        .where(TicketComment.ticket_id == ticket.id)
    )

    before = db_session.scalar(count_statement)

    response = client.post(
        f"/api/v1/tickets/{ticket.id}/comments",
        json={"message": "Unauthorized comment"},
        headers=requester_headers,
    )

    assert response.status_code == 404

    after = db_session.scalar(count_statement)

    assert before == after == 0


def test_requester_pagination_does_not_expose_other_tickets(
    client,
    requester_user,
    requester_headers,
    department,
    category,
    make_user,
    make_ticket,
):
    other_user = make_user(department)

    own_ticket = make_ticket(
        requester_user,
        category,
    )

    make_ticket(other_user, category)
    make_ticket(other_user, category)

    response = client.get(
        "/api/v1/tickets",
        params={"page": 1, "limit": 100},
        headers=requester_headers,
    )

    assert response.status_code == 200

    data = response.json()["data"]

    assert data["total"] == 1

    assert [item["id"] for item in data["items"]] == [
        own_ticket.id,
    ]


def test_inaccessible_and_nonexistent_tickets_return_same_error(
    client,
    requester_headers,
    department,
    category,
    make_user,
    make_ticket,
):
    other_user = make_user(department)

    ticket = make_ticket(other_user, category)

    inaccessible = client.get(
        f"/api/v1/tickets/{ticket.id}",
        headers=requester_headers,
    )

    nonexistent = client.get(
        "/api/v1/tickets/999999",
        headers=requester_headers,
    )

    assert inaccessible.status_code == 404
    assert nonexistent.status_code == 404

    assert inaccessible.json()["error"] == nonexistent.json()["error"]

    assert inaccessible.json()["request_id"] != nonexistent.json()["request_id"]
