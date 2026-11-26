def test_ticket_cannot_be_moved_to_inactive_category(
    client,
    db_session,
    requester_user,
    requester_headers,
    department,
    category,
    make_category,
    make_ticket,
):
    ticket = make_ticket(requester_user, category)

    inactive = make_category(
        department,
        name="Inactive security category",
        is_active=False,
    )

    original_category_id = ticket.category_id

    response = client.patch(
        f"/api/v1/tickets/{ticket.id}",
        json={"category": inactive.name},
        headers=requester_headers,
    )

    assert response.status_code == 422

    db_session.refresh(ticket)

    assert ticket.category_id == original_category_id


def test_ticket_creation_rejects_ambiguous_category(
    client,
    requester_headers,
    department,
    other_department,
    make_category,
):
    make_category(
        department,
        name="Shared category",
    )

    make_category(
        other_department,
        name="Shared category",
    )

    response = client.post(
        "/api/v1/tickets",
        json={
            "title": "Ambiguous category ticket",
            "description": "Testing ambiguous category protection.",
            "category": "Shared category",
        },
        headers=requester_headers,
    )

    assert response.status_code == 422


def test_ticket_update_rejects_ambiguous_category(
    client,
    db_session,
    requester_user,
    requester_headers,
    department,
    other_department,
    category,
    make_category,
    make_ticket,
):
    ticket = make_ticket(requester_user, category)

    original_category_id = ticket.category_id
    original_department_id = ticket.department_id

    make_category(
        department,
        name="Shared category",
    )

    make_category(
        other_department,
        name="Shared category",
    )

    response = client.patch(
        f"/api/v1/tickets/{ticket.id}",
        json={"category": "Shared category"},
        headers=requester_headers,
    )

    assert response.status_code == 422

    db_session.refresh(ticket)

    assert ticket.category_id == original_category_id
    assert ticket.department_id == original_department_id
