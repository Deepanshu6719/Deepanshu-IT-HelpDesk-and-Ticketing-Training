import pytest

from models.ticket import Ticket


def test_patch_title_preserves_all_other_ticket_fields(
    client,
    db_session,
    requester_user,
    requester_headers,
    category,
    make_ticket,
):
    ticket = make_ticket(
        requester_user,
        category,
    )

    ticket_id = ticket.id

    original_fields = {
        "description": ticket.description,
        "category_id": ticket.category_id,
        "department_id": ticket.department_id,
        "requester_id": ticket.requester_id,
        "assigned_to": ticket.assigned_to,
        "requested_priority": ticket.requested_priority,
        "priority": ticket.priority,
        "status": ticket.status,
        "created_at": ticket.created_at,
        "is_deleted": ticket.is_deleted,
        "deleted_at": ticket.deleted_at,
    }

    response = client.patch(
        f"/api/v1/tickets/{ticket_id}",
        headers=requester_headers,
        json={
            "title": "Updated printer issue",
        },
    )

    assert response.status_code == 200, response.text

    db_session.expire_all()

    updated_ticket = db_session.get(Ticket, ticket_id)

    assert updated_ticket.title == "Updated printer issue"

    for field, original_value in original_fields.items():
        assert getattr(updated_ticket, field) == original_value, (
            f"Unexpected modification of field: {field}"
        )


@pytest.mark.parametrize(
    "field",
    [
        "title",
        "description",
        "category",
        "requested_priority",
    ],
)
def test_patch_rejects_null_requester_fields(
    client,
    db_session,
    requester_user,
    requester_headers,
    category,
    make_ticket,
    field,
):
    ticket = make_ticket(
        requester_user,
        category,
    )

    ticket_id = ticket.id

    database_field = "category_id" if field == "category" else field

    original_value = getattr(ticket, database_field)

    response = client.patch(
        f"/api/v1/tickets/{ticket_id}",
        headers=requester_headers,
        json={field: None},
    )

    assert response.status_code == 422, response.text

    db_session.expire_all()

    updated_ticket = db_session.get(Ticket, ticket_id)

    assert getattr(updated_ticket, database_field) == original_value


def test_combined_search_filters_and_pagination(
    client,
    requester_user,
    requester_headers,
    category,
    make_ticket,
):
    matching_ids = []

    for number in range(5):
        ticket = make_ticket(
            requester_user,
            category,
            title=f"Printer matching issue {number}",
            priority="high",
            status="open",
        )

        matching_ids.append(ticket.id)

    # Excluded because of priority
    make_ticket(
        requester_user,
        category,
        title="Printer low priority issue",
        priority="low",
        status="open",
    )

    # Excluded because of status
    make_ticket(
        requester_user,
        category,
        title="Printer resolved issue",
        priority="high",
        status="resolved",
    )

    # Excluded because of search
    make_ticket(
        requester_user,
        category,
        title="Monitor display issue",
        description="Display keeps flickering.",
        priority="high",
        status="open",
    )

    collected_ids = []

    for page, expected_count in [(1, 2), (2, 2), (3, 1)]:
        response = client.get(
            "/api/v1/tickets",
            headers=requester_headers,
            params={
                "status_filter": "open",
                "priority_filter": "high",
                "search": "printer",
                "category_id": category.id,
                "department_id": category.department_id,
                "page": page,
                "limit": 2,
            },
        )

        assert response.status_code == 200, response.text

        data = response.json()["data"]

        assert data["total"] == 5
        assert data["page"] == page
        assert data["limit"] == 2
        assert len(data["items"]) == expected_count

        collected_ids.extend(item["id"] for item in data["items"])

    assert len(collected_ids) == 5
    assert len(set(collected_ids)) == 5
    assert set(collected_ids) == set(matching_ids)


def test_filtered_results_do_not_expose_unauthorized_tickets(
    client,
    requester_user,
    requester_headers,
    department,
    other_department,
    category,
    make_user,
    make_ticket,
):
    same_department_user = make_user(department)

    different_department_user = make_user(
        other_department,
    )

    own_ticket = make_ticket(
        requester_user,
        category,
        title="Printer shared search issue",
        priority="high",
        status="open",
    )

    own_ticket_id = own_ticket.id

    # Matching ticket owned by another user
    # in the same department
    make_ticket(
        same_department_user,
        category,
        title="Printer shared search issue",
        priority="high",
        status="open",
    )

    # Matching ticket owned by a user
    # from another department
    make_ticket(
        different_department_user,
        category,
        title="Printer shared search issue",
        priority="high",
        status="open",
    )

    response = client.get(
        "/api/v1/tickets",
        headers=requester_headers,
        params={
            "search": "Printer shared search",
            "status_filter": "open",
            "priority_filter": "high",
            "category_id": category.id,
            "department_id": category.department_id,
            "page": 1,
            "limit": 10,
        },
    )

    assert response.status_code == 200, response.text

    data = response.json()["data"]

    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["id"] == own_ticket_id


def test_filtered_page_beyond_available_results(
    client,
    requester_user,
    requester_headers,
    category,
    make_ticket,
):
    for number in range(3):
        make_ticket(
            requester_user,
            category,
            title=f"Printer issue {number}",
            priority="high",
            status="open",
        )

    response = client.get(
        "/api/v1/tickets",
        headers=requester_headers,
        params={
            "status_filter": "open",
            "priority_filter": "high",
            "search": "printer",
            "page": 3,
            "limit": 2,
        },
    )

    assert response.status_code == 200, response.text

    data = response.json()["data"]

    assert data["total"] == 3
    assert data["page"] == 3
    assert data["limit"] == 2
    assert data["items"] == []


def test_soft_deleted_ticket_excluded_from_filtered_results(
    client,
    db_session,
    requester_user,
    requester_headers,
    category,
    make_ticket,
):
    active_ticket = make_ticket(
        requester_user,
        category,
        title="Printer active issue",
        priority="high",
        status="open",
    )

    deleted_ticket = make_ticket(
        requester_user,
        category,
        title="Printer deleted issue",
        priority="high",
        status="open",
    )

    active_ticket_id = active_ticket.id
    deleted_ticket_id = deleted_ticket.id

    delete_response = client.delete(
        f"/api/v1/tickets/{deleted_ticket_id}",
        headers=requester_headers,
    )

    assert delete_response.status_code == 204

    db_session.expire_all()

    stored_ticket = db_session.get(
        Ticket,
        deleted_ticket_id,
    )

    assert stored_ticket.is_deleted is True
    assert stored_ticket.deleted_at is not None

    response = client.get(
        "/api/v1/tickets",
        headers=requester_headers,
        params={
            "search": "printer",
            "status_filter": "open",
            "priority_filter": "high",
            "page": 1,
            "limit": 10,
        },
    )

    assert response.status_code == 200, response.text

    data = response.json()["data"]

    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["id"] == active_ticket_id
