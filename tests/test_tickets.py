"""
Tickets - the core of the helpdesk. Covers create / read / list / update / delete and the
domain rules that decide WHO may do WHAT:

* requesters see and edit only their own tickets, and only until work starts
* agents see only tickets assigned to (or requested by) them and may only change the status
* admins see everything, set priority/status and assign agents (with 5 assignment rules)
* deleting is a "soft delete": the row stays but disappears from every API response
"""

import pytest

from models.ticket import Ticket


def ticket_payload(for_category, **overrides):
    payload = {
        "title": "Laptop will not boot",
        "description": "My laptop shows a black screen on startup.",
        "category": for_category.name,
        "priority": "medium",
    }
    payload.update(overrides)
    return payload


def mark_deleted(db_session, ticket):
    ticket.is_deleted = True
    db_session.commit()


# ============================= CREATE: POST /tickets ============================= #
def test_requester_creates_ticket(
    client, db_session, requester_user, requester_headers, category
):
    response = client.post(
        "/tickets",
        json=ticket_payload(category, priority="high"),
        headers=requester_headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Laptop will not boot"
    assert body["status"] == "open"
    assert body["priority"] == body["requested_priority"] == "high"
    assert body["assigned_to"] is None
    assert body["requester_id"] == requester_user.id
    assert body["category"]["name"] == category.name

    stored = db_session.get(Ticket, body["id"])
    assert (
        stored.department_id == category.department_id
    )  # department comes from the category
    assert stored.is_deleted is False


def test_priority_defaults_to_medium(client, requester_headers, category):
    payload = ticket_payload(category)
    del payload["priority"]

    response = client.post("/tickets", json=payload, headers=requester_headers)

    assert response.status_code == 201
    assert response.json()["priority"] == "medium"


def test_creating_a_ticket_notifies_requester_and_active_admins_only(
    client,
    notifications,
    requester_user,
    requester_headers,
    admin_user,
    make_user,
    department,
    category,
):
    inactive_admin = make_user(department, role="admin", is_active=False)

    response = client.post(
        "/tickets", json=ticket_payload(category), headers=requester_headers
    )

    assert response.status_code == 201
    assert notifications.recipients == {requester_user.email, admin_user.email}
    assert inactive_admin.email not in notifications.recipients


def test_create_ticket_with_unknown_category_returns_422(
    client, requester_headers, category
):
    payload = ticket_payload(category, category="Does Not Exist")

    response = client.post("/tickets", json=payload, headers=requester_headers)

    assert response.status_code == 422
    assert response.json()["detail"] == "Invalid or inactive category"


def test_cannot_create_ticket_in_deactivated_category(
    client, requester_headers, make_category, department
):
    retired = make_category(department, "Legacy Fax Machines", is_active=False)

    response = client.post(
        "/tickets", json=ticket_payload(retired), headers=requester_headers
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    "overrides",
    [
        {"title": "abc"},
        {"title": "x" * 51},
        {"description": "too short"},
        {"description": "x" * 151},
        {"priority": "critical"},
        {"status": "closed"},  # clients may not set status on creation
        {"assigned_to": 1},  # ...or assign an agent
    ],
)
def test_create_ticket_with_invalid_payload_returns_422(
    client, requester_headers, category, overrides
):
    response = client.post(
        "/tickets",
        json=ticket_payload(category, **overrides),
        headers=requester_headers,
    )

    assert response.status_code == 422


def test_create_ticket_requires_authentication(client, category):
    assert client.post("/tickets", json=ticket_payload(category)).status_code == 401


# ============================ READ ONE: GET /tickets/{id} ============================ #
def test_requester_can_view_own_ticket(
    client, requester_user, requester_headers, category, make_ticket
):
    ticket = make_ticket(requester_user, category)

    response = client.get(f"/tickets/{ticket.id}", headers=requester_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == ticket.id
    assert body["requester"]["email"] == requester_user.email
    assert body["category"]["name"] == category.name
    assert body["assigned_to"] is None


def test_ticket_shows_assigned_agent(
    client, requester_user, requester_headers, agent_user, category, make_ticket
):
    ticket = make_ticket(requester_user, category, assigned_to=agent_user)

    body = client.get(f"/tickets/{ticket.id}", headers=requester_headers).json()

    assert body["assigned_to"]["email"] == agent_user.email


def test_admin_can_view_any_ticket(
    client, requester_user, admin_headers, category, make_ticket
):
    ticket = make_ticket(requester_user, category)

    assert client.get(f"/tickets/{ticket.id}", headers=admin_headers).status_code == 200


def test_assigned_agent_can_view_ticket(
    client, requester_user, agent_user, agent_headers, category, make_ticket
):
    ticket = make_ticket(requester_user, category, assigned_to=agent_user)

    assert client.get(f"/tickets/{ticket.id}", headers=agent_headers).status_code == 200


def test_agent_can_view_a_ticket_they_requested_themselves(
    client, agent_user, agent_headers, category, make_ticket
):
    ticket = make_ticket(agent_user, category)

    assert client.get(f"/tickets/{ticket.id}", headers=agent_headers).status_code == 200


def test_other_requester_gets_404_not_403(
    client, requester_user, category, make_ticket, make_user, department, auth_headers
):
    """404 (not 403) so strangers cannot even discover that a ticket id exists."""
    ticket = make_ticket(requester_user, category)
    stranger_headers = auth_headers(make_user(department))

    response = client.get(f"/tickets/{ticket.id}", headers=stranger_headers)

    assert response.status_code == 404


def test_unassigned_agent_gets_404(
    client, requester_user, agent_headers, category, make_ticket
):
    ticket = make_ticket(requester_user, category)  # not assigned to the agent

    assert client.get(f"/tickets/{ticket.id}", headers=agent_headers).status_code == 404


def test_soft_deleted_ticket_is_404_even_for_admin(
    client, db_session, requester_user, admin_headers, category, make_ticket
):
    ticket = make_ticket(requester_user, category)
    mark_deleted(db_session, ticket)

    assert client.get(f"/tickets/{ticket.id}", headers=admin_headers).status_code == 404


def test_unknown_ticket_returns_404(client, admin_headers):
    assert client.get("/tickets/999999", headers=admin_headers).status_code == 404


def test_non_numeric_ticket_id_returns_422(client, admin_headers):
    assert client.get("/tickets/abc", headers=admin_headers).status_code == 422


def test_get_ticket_requires_authentication(
    client, requester_user, category, make_ticket
):
    ticket = make_ticket(requester_user, category)

    assert client.get(f"/tickets/{ticket.id}").status_code == 401


# =============================== LIST: GET /tickets =============================== #
def ids_of(response):
    return [item["id"] for item in response.json()["items"]]


def test_requester_only_sees_own_tickets(
    client,
    requester_user,
    requester_headers,
    category,
    make_ticket,
    make_user,
    department,
):
    mine = make_ticket(requester_user, category, title="My own ticket")
    make_ticket(make_user(department), category, title="Somebody else's ticket")

    response = client.get("/tickets", headers=requester_headers)

    assert response.status_code == 200
    assert ids_of(response) == [mine.id]
    assert response.json()["total"] == 1


def test_agent_sees_assigned_and_own_tickets_only(
    client, requester_user, agent_user, agent_headers, category, make_ticket
):
    assigned = make_ticket(
        requester_user, category, title="Assigned to agent", assigned_to=agent_user
    )
    own = make_ticket(agent_user, category, title="Requested by agent")
    make_ticket(requester_user, category, title="Unrelated ticket")

    response = client.get("/tickets", headers=agent_headers)

    assert set(ids_of(response)) == {assigned.id, own.id}


def test_admin_sees_all_tickets(
    client, requester_user, agent_user, admin_headers, category, make_ticket
):
    created = [
        make_ticket(requester_user, category, title="Ticket one"),
        make_ticket(agent_user, category, title="Ticket two"),
    ]

    response = client.get("/tickets", headers=admin_headers)

    assert set(ids_of(response)) == {t.id for t in created}


def test_soft_deleted_tickets_are_excluded_from_list_and_total(
    client, db_session, requester_user, requester_headers, category, make_ticket
):
    keep = make_ticket(requester_user, category, title="Keep me")
    gone = make_ticket(requester_user, category, title="Delete me")
    mark_deleted(db_session, gone)

    response = client.get("/tickets", headers=requester_headers)

    assert ids_of(response) == [keep.id]
    assert response.json()["total"] == 1


def test_empty_list_has_zero_total_and_zero_pages(client, requester_headers):
    body = client.get("/tickets", headers=requester_headers).json()

    assert body == {
        "items": [],
        "total": 0,
        "page": 1,
        "page_size": 10,
        "total_pages": 0,
    }


def test_tickets_are_listed_newest_first_and_paginated(
    client, requester_user, requester_headers, category, make_ticket
):
    oldest = make_ticket(requester_user, category, title="Oldest ticket")
    middle = make_ticket(requester_user, category, title="Middle ticket")
    newest = make_ticket(requester_user, category, title="Newest ticket")

    page_1 = client.get(
        "/tickets", params={"page": 1, "page_size": 2}, headers=requester_headers
    )
    page_2 = client.get(
        "/tickets", params={"page": 2, "page_size": 2}, headers=requester_headers
    )

    body = page_1.json()
    assert (body["total"], body["page"], body["page_size"], body["total_pages"]) == (
        3,
        1,
        2,
        2,
    )
    assert ids_of(page_1) == [newest.id, middle.id]
    assert ids_of(page_2) == [oldest.id]


@pytest.mark.parametrize(
    "params",
    [
        {"page": 0},
        {"page_size": 0},
        {"page_size": 101},
        {"status_filter": "done"},
        {"priority_filter": "critical"},
        {"category_id": 0},
    ],
)
def test_list_rejects_invalid_query_parameters(client, requester_headers, params):
    assert (
        client.get("/tickets", params=params, headers=requester_headers).status_code
        == 422
    )


def test_filter_by_status_and_priority(
    client, requester_user, requester_headers, category, make_ticket
):
    open_low = make_ticket(requester_user, category, title="Open low", priority="low")
    resolved_high = make_ticket(
        requester_user,
        category,
        title="Resolved high",
        priority="high",
        status="resolved",
    )

    by_status = client.get(
        "/tickets", params={"status_filter": "resolved"}, headers=requester_headers
    )
    by_priority = client.get(
        "/tickets", params={"priority_filter": "low"}, headers=requester_headers
    )

    assert ids_of(by_status) == [resolved_high.id]
    assert ids_of(by_priority) == [open_low.id]


def test_filter_by_category_and_department(
    client,
    requester_user,
    requester_headers,
    category,
    make_category,
    other_department,
    make_ticket,
):
    other_category = make_category(other_department, "Cleaning")
    in_it = make_ticket(requester_user, category, title="IT ticket")
    in_facilities = make_ticket(
        requester_user, other_category, title="Facilities ticket"
    )

    by_category = client.get(
        "/tickets", params={"category_id": other_category.id}, headers=requester_headers
    )
    by_department = client.get(
        "/tickets",
        params={"department_id": category.department_id},
        headers=requester_headers,
    )

    assert ids_of(by_category) == [in_facilities.id]
    assert ids_of(by_department) == [in_it.id]


def test_search_matches_title_and_description_case_insensitively(
    client, requester_user, requester_headers, category, make_ticket
):
    by_title = make_ticket(requester_user, category, title="VPN connection drops")
    by_description = make_ticket(
        requester_user,
        category,
        title="Cannot work remotely",
        description="The vpn client disconnects every hour.",
    )
    make_ticket(requester_user, category, title="Printer jam")

    response = client.get(
        "/tickets", params={"search": "Vpn"}, headers=requester_headers
    )

    assert set(ids_of(response)) == {by_title.id, by_description.id}


def test_search_with_only_whitespace_returns_422(client, requester_headers):
    response = client.get(
        "/tickets", params={"search": "   "}, headers=requester_headers
    )

    assert response.status_code == 422


def test_only_admins_can_filter_by_assigned_agent(
    client,
    requester_user,
    agent_user,
    requester_headers,
    agent_headers,
    admin_headers,
    category,
    make_ticket,
):
    assigned = make_ticket(
        requester_user, category, title="Assigned one", assigned_to=agent_user
    )
    make_ticket(requester_user, category, title="Unassigned one")
    params = {"assigned_to": agent_user.id}

    assert (
        client.get("/tickets", params=params, headers=requester_headers).status_code
        == 403
    )
    assert (
        client.get("/tickets", params=params, headers=agent_headers).status_code == 403
    )
    admin_response = client.get("/tickets", params=params, headers=admin_headers)
    assert admin_response.status_code == 200
    assert ids_of(admin_response) == [assigned.id]


def test_list_requires_authentication(client):
    assert client.get("/tickets").status_code == 401


# ============================ UPDATE: PATCH /tickets/{id} ============================ #
def patch(client, ticket, headers, **fields):
    return client.patch(f"/tickets/{ticket.id}", json=fields, headers=headers)


# ---- requester rules ---- #
def test_requester_can_edit_own_open_unassigned_ticket(
    client, db_session, requester_user, requester_headers, category, make_ticket
):
    ticket = make_ticket(requester_user, category)

    response = patch(client, ticket, requester_headers, title="Updated printer problem")

    assert response.status_code == 200
    assert response.json()["title"] == "Updated printer problem"
    db_session.refresh(ticket)
    assert ticket.title == "Updated printer problem"


def test_changing_requested_priority_does_not_change_real_priority(
    client, requester_user, requester_headers, category, make_ticket
):
    """Requesters can ASK for a priority, only admins decide the real one."""
    ticket = make_ticket(requester_user, category, priority="low")

    body = patch(client, ticket, requester_headers, requested_priority="urgent").json()

    assert body["requested_priority"] == "urgent"
    assert body["priority"] == "low"


def test_changing_category_also_moves_the_ticket_to_that_categorys_department(
    client,
    db_session,
    requester_user,
    requester_headers,
    category,
    make_category,
    other_department,
    make_ticket,
):
    new_category = make_category(other_department, "Cleaning")
    ticket = make_ticket(requester_user, category)

    response = patch(client, ticket, requester_headers, category=new_category.name)

    assert response.status_code == 200
    db_session.refresh(ticket)
    assert ticket.category_id == new_category.id
    assert ticket.department_id == other_department.id


def test_changing_to_unknown_category_returns_422(
    client, requester_user, requester_headers, category, make_ticket
):
    ticket = make_ticket(requester_user, category)

    response = patch(client, ticket, requester_headers, category="Nope")

    assert response.status_code == 422
    assert response.json()["detail"] == "Invalid category"


@pytest.mark.parametrize(
    "fields",
    [{"status": "resolved"}, {"priority": "urgent"}, {"assigned_to": 1}],
)
def test_requester_cannot_change_staff_only_fields(
    client, requester_user, requester_headers, category, make_ticket, fields
):
    ticket = make_ticket(requester_user, category)

    response = patch(client, ticket, requester_headers, **fields)

    assert response.status_code == 403
    assert response.json()["detail"] == "You are not allowed to update these fields"


def test_update_with_one_forbidden_field_changes_nothing(
    client, db_session, requester_user, requester_headers, category, make_ticket
):
    ticket = make_ticket(requester_user, category, title="Original title")

    response = patch(
        client, ticket, requester_headers, title="Sneaky new title", status="closed"
    )

    assert response.status_code == 403
    db_session.refresh(ticket)
    assert ticket.title == "Original title"
    assert ticket.status == "open"


def test_requester_loses_edit_rights_once_ticket_is_assigned(
    client, requester_user, requester_headers, agent_user, category, make_ticket
):
    ticket = make_ticket(requester_user, category, assigned_to=agent_user)

    assert (
        patch(client, ticket, requester_headers, title="Too late to edit").status_code
        == 404
    )


def test_requester_loses_edit_rights_once_work_has_started(
    client, requester_user, requester_headers, category, make_ticket
):
    ticket = make_ticket(requester_user, category, status="under_review")

    assert (
        patch(client, ticket, requester_headers, title="Too late to edit").status_code
        == 404
    )


def test_other_requester_cannot_edit_ticket(
    client, requester_user, category, make_ticket, make_user, department, auth_headers
):
    ticket = make_ticket(requester_user, category)
    stranger_headers = auth_headers(make_user(department))

    assert (
        patch(client, ticket, stranger_headers, title="Hijacked title").status_code
        == 404
    )


# ---- agent rules ---- #
def test_assigned_agent_can_change_status(
    client, db_session, requester_user, agent_user, agent_headers, category, make_ticket
):
    ticket = make_ticket(requester_user, category, assigned_to=agent_user)

    response = patch(client, ticket, agent_headers, status="in_progress")

    assert response.status_code == 200
    db_session.refresh(ticket)
    assert ticket.status == "in_progress"


@pytest.mark.parametrize(
    "fields",
    [{"priority": "urgent"}, {"title": "Agent renamed it"}, {"assigned_to": None}],
)
def test_assigned_agent_can_only_change_status(
    client, requester_user, agent_user, agent_headers, category, make_ticket, fields
):
    ticket = make_ticket(requester_user, category, assigned_to=agent_user)

    assert patch(client, ticket, agent_headers, **fields).status_code == 403


def test_unassigned_agent_cannot_update_ticket(
    client, requester_user, agent_headers, category, make_ticket
):
    ticket = make_ticket(requester_user, category)

    assert patch(client, ticket, agent_headers, status="resolved").status_code == 404


# ---- admin rules ---- #
def test_admin_can_set_priority_and_status(
    client, requester_user, admin_headers, category, make_ticket
):
    ticket = make_ticket(requester_user, category)

    body = patch(
        client, ticket, admin_headers, priority="urgent", status="under_review"
    ).json()

    assert body["priority"] == "urgent"
    assert body["status"] == "under_review"


def test_admin_cannot_edit_the_content_of_someone_elses_ticket(
    client, requester_user, admin_headers, category, make_ticket
):
    ticket = make_ticket(requester_user, category)

    assert (
        patch(client, ticket, admin_headers, title="Admin rewrote it").status_code
        == 403
    )


def test_admin_can_edit_content_of_their_own_open_unassigned_ticket(
    client, admin_user, admin_headers, category, make_ticket
):
    ticket = make_ticket(admin_user, category)

    assert (
        patch(client, ticket, admin_headers, title="Admin edits own ticket").status_code
        == 200
    )


def test_admin_cannot_edit_content_of_their_own_ticket_once_assigned(
    client, admin_user, agent_user, admin_headers, category, make_ticket
):
    ticket = make_ticket(admin_user, category, assigned_to=agent_user)

    assert (
        patch(client, ticket, admin_headers, title="Too late to edit").status_code
        == 403
    )


# ---- general PATCH validation ---- #
def test_update_with_empty_body_returns_422(
    client, requester_user, requester_headers, category, make_ticket
):
    ticket = make_ticket(requester_user, category)

    response = patch(client, ticket, requester_headers)

    assert response.status_code == 422
    assert response.json()["detail"] == "No fields provided for update"


def test_explicit_null_is_rejected_for_normal_fields(
    client, requester_user, admin_headers, category, make_ticket
):
    ticket = make_ticket(requester_user, category)

    response = patch(client, ticket, admin_headers, status=None)

    assert response.status_code == 422
    assert response.json()["detail"] == "status cannot be null"


@pytest.mark.parametrize(
    "fields",
    [
        {"status": "finished"},  # not an allowed status
        {"priority": "critical"},
        {"title": "abc"},
        {"description": "too short"},
        {"unknown_field": "x"},
    ],
)
def test_update_with_invalid_values_returns_422(
    client, requester_user, admin_headers, category, make_ticket, fields
):
    ticket = make_ticket(requester_user, category)

    assert patch(client, ticket, admin_headers, **fields).status_code == 422


def test_update_unknown_or_deleted_ticket_returns_404(
    client, db_session, requester_user, admin_headers, category, make_ticket
):
    deleted = make_ticket(requester_user, category)
    mark_deleted(db_session, deleted)

    assert (
        client.patch(
            "/tickets/999999", json={"status": "closed"}, headers=admin_headers
        ).status_code
        == 404
    )
    assert patch(client, deleted, admin_headers, status="closed").status_code == 404


def test_update_requires_authentication(client, requester_user, category, make_ticket):
    ticket = make_ticket(requester_user, category)

    assert (
        client.patch(f"/tickets/{ticket.id}", json={"status": "closed"}).status_code
        == 401
    )


# ---- ASSIGNING AN AGENT: the domain-specific rules ---- #
def test_admin_assigns_agent_and_both_people_are_notified(
    client,
    db_session,
    notifications,
    requester_user,
    agent_user,
    admin_headers,
    category,
    make_ticket,
):
    ticket = make_ticket(requester_user, category)

    response = patch(client, ticket, admin_headers, assigned_to=agent_user.id)

    assert response.status_code == 200
    assert response.json()["assigned_to"]["id"] == agent_user.id
    assert notifications.recipients == {agent_user.email, requester_user.email}
    assert len(notifications.calls) == 2


def test_cannot_assign_a_user_that_does_not_exist(
    client, requester_user, admin_headers, category, make_ticket
):
    ticket = make_ticket(requester_user, category)

    response = patch(client, ticket, admin_headers, assigned_to=999999)

    assert response.status_code == 422
    assert response.json()["detail"] == "Agent not found"


def test_cannot_assign_a_user_who_is_not_an_agent(
    client,
    requester_user,
    admin_user,
    admin_headers,
    category,
    make_ticket,
    make_user,
    department,
):
    ticket = make_ticket(requester_user, category)
    plain_user = make_user(department)

    for not_an_agent in (plain_user, admin_user):  # admin_user has NO agent role
        response = patch(client, ticket, admin_headers, assigned_to=not_an_agent.id)

        assert response.status_code == 422
        assert response.json()["detail"] == "Selected user is not an agent"


def test_requester_cannot_be_assigned_as_their_own_agent(
    client, admin_headers, category, make_ticket, make_user, department
):
    agent_who_requested = make_user(department, role="agent")
    ticket = make_ticket(agent_who_requested, category)

    response = patch(client, ticket, admin_headers, assigned_to=agent_who_requested.id)

    assert response.status_code == 422
    assert (
        response.json()["detail"] == "Requester cannot be assigned as their own agent"
    )


def test_cannot_assign_an_inactive_agent(
    client, requester_user, admin_headers, category, make_ticket, make_user, department
):
    inactive_agent = make_user(department, role="agent", is_active=False)
    ticket = make_ticket(requester_user, category)

    response = patch(client, ticket, admin_headers, assigned_to=inactive_agent.id)

    assert response.status_code == 422
    assert response.json()["detail"] == "Cannot assign a ticket to an inactive agent"


def test_cannot_assign_an_agent_from_a_different_department(
    client,
    requester_user,
    admin_headers,
    category,
    make_ticket,
    make_user,
    other_department,
):
    facilities_agent = make_user(other_department, role="agent")
    ticket = make_ticket(requester_user, category)  # ticket belongs to IT Support

    response = patch(client, ticket, admin_headers, assigned_to=facilities_agent.id)

    assert response.status_code == 422
    assert response.json()["detail"] == "Agent does not belong to the ticket department"


def test_failed_assignment_leaves_ticket_unassigned_and_sends_no_notifications(
    client,
    db_session,
    notifications,
    requester_user,
    admin_headers,
    category,
    make_ticket,
    make_user,
    other_department,
):
    facilities_agent = make_user(other_department, role="agent")
    ticket = make_ticket(requester_user, category)

    patch(client, ticket, admin_headers, assigned_to=facilities_agent.id)

    db_session.refresh(ticket)
    assert ticket.assigned_to is None
    assert notifications.calls == []


def test_reassigning_the_same_agent_sends_no_new_notifications(
    client,
    notifications,
    requester_user,
    agent_user,
    admin_headers,
    category,
    make_ticket,
):
    ticket = make_ticket(requester_user, category, assigned_to=agent_user)

    response = patch(client, ticket, admin_headers, assigned_to=agent_user.id)

    assert response.status_code == 200
    assert notifications.calls == []


def test_admin_can_unassign_a_ticket(
    client,
    notifications,
    requester_user,
    agent_user,
    admin_headers,
    category,
    make_ticket,
):
    ticket = make_ticket(requester_user, category, assigned_to=agent_user)

    response = patch(client, ticket, admin_headers, assigned_to=None)

    assert response.status_code == 200
    assert response.json()["assigned_to"] is None
    assert notifications.calls == []


# ============================ DELETE: DELETE /tickets/{id} ============================ #
def test_requester_soft_deletes_own_open_unassigned_ticket(
    client, db_session, requester_user, requester_headers, category, make_ticket
):
    ticket = make_ticket(requester_user, category)
    ticket_id = ticket.id

    response = client.delete(f"/tickets/{ticket_id}", headers=requester_headers)

    assert response.status_code == 204
    assert response.content == b""
    # The row still exists (soft delete) but is flagged...
    db_session.expire_all()
    row = db_session.get(Ticket, ticket_id)
    assert row is not None
    assert row.is_deleted is True
    assert row.deleted_at is not None
    # ...and has vanished from the API.
    assert (
        client.get(f"/tickets/{ticket_id}", headers=requester_headers).status_code
        == 404
    )
    assert ids_of(client.get("/tickets", headers=requester_headers)) == []


def test_deleting_twice_returns_404_the_second_time(
    client, requester_user, requester_headers, category, make_ticket
):
    ticket = make_ticket(requester_user, category)

    assert (
        client.delete(f"/tickets/{ticket.id}", headers=requester_headers).status_code
        == 204
    )
    assert (
        client.delete(f"/tickets/{ticket.id}", headers=requester_headers).status_code
        == 404
    )


def test_requester_cannot_delete_assigned_ticket(
    client, requester_user, requester_headers, agent_user, category, make_ticket
):
    ticket = make_ticket(requester_user, category, assigned_to=agent_user)

    assert (
        client.delete(f"/tickets/{ticket.id}", headers=requester_headers).status_code
        == 404
    )


def test_requester_cannot_delete_ticket_once_work_has_started(
    client, requester_user, requester_headers, category, make_ticket
):
    ticket = make_ticket(requester_user, category, status="in_progress")

    assert (
        client.delete(f"/tickets/{ticket.id}", headers=requester_headers).status_code
        == 404
    )


def test_other_requester_cannot_delete_ticket(
    client, requester_user, category, make_ticket, make_user, department, auth_headers
):
    ticket = make_ticket(requester_user, category)
    stranger_headers = auth_headers(make_user(department))

    assert (
        client.delete(f"/tickets/{ticket.id}", headers=stranger_headers).status_code
        == 404
    )


def test_assigned_agent_cannot_delete_ticket(
    client, requester_user, agent_user, agent_headers, category, make_ticket
):
    ticket = make_ticket(requester_user, category, assigned_to=agent_user)

    assert (
        client.delete(f"/tickets/{ticket.id}", headers=agent_headers).status_code == 404
    )


def test_admin_can_delete_any_ticket_even_in_progress(
    client, requester_user, agent_user, admin_headers, category, make_ticket
):
    ticket = make_ticket(
        requester_user, category, status="in_progress", assigned_to=agent_user
    )

    assert (
        client.delete(f"/tickets/{ticket.id}", headers=admin_headers).status_code == 204
    )


def test_delete_unknown_ticket_returns_404(client, admin_headers):
    assert client.delete("/tickets/999999", headers=admin_headers).status_code == 404


def test_delete_requires_authentication(client, requester_user, category, make_ticket):
    ticket = make_ticket(requester_user, category)

    assert client.delete(f"/tickets/{ticket.id}").status_code == 401
