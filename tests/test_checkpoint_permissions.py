import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from models.ticket import Ticket


def test_changing_category_updates_ticket_department(
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
    new_category = make_category(
        other_department,
        name="Cross Department Category",
    )

    ticket = make_ticket(
        requester_user,
        category,
    )

    ticket_id = ticket.id
    new_category_id = new_category.id
    new_department_id = other_department.id

    response = client.patch(
        f"/api/v1/tickets/{ticket_id}",
        headers=requester_headers,
        json={
            "category": new_category.name,
        },
    )

    assert response.status_code == 200, response.text

    db_session.expire_all()

    updated_ticket = db_session.scalar(select(Ticket).where(Ticket.id == ticket_id))

    assert updated_ticket.category_id == new_category_id
    assert updated_ticket.department_id == new_department_id

    assert updated_ticket.department_id == updated_ticket.category.department_id


def test_ticket_creation_uses_category_department(
    client,
    db_session,
    requester_headers,
    other_department,
    make_category,
):
    category = make_category(
        other_department,
        name="Different Department Support",
    )

    expected_department_id = other_department.id
    expected_category_id = category.id

    response = client.post(
        "/api/v1/tickets",
        headers=requester_headers,
        json={
            "title": "Cross department support request",
            "description": ("Requesting support from another department."),
            "category": category.name,
            "priority": "medium",
        },
    )

    assert response.status_code == 201, response.text

    ticket_id = response.json()["data"]["id"]

    db_session.expire_all()

    ticket = db_session.scalar(select(Ticket).where(Ticket.id == ticket_id))

    assert ticket.category_id == expected_category_id
    assert ticket.department_id == expected_department_id

    assert ticket.department_id == ticket.category.department_id


def test_requester_cannot_change_assigned_ticket_category(
    client,
    db_session,
    requester_user,
    requester_headers,
    agent_user,
    category,
    other_department,
    make_category,
    make_ticket,
):
    new_category = make_category(
        other_department,
        name="Different Support Category",
    )

    ticket = make_ticket(
        requester_user,
        category,
        assigned_to=agent_user,
    )

    ticket_id = ticket.id
    original_category_id = ticket.category_id
    original_department_id = ticket.department_id

    response = client.patch(
        f"/api/v1/tickets/{ticket_id}",
        headers=requester_headers,
        json={"category": new_category.name},
    )

    assert response.status_code == 404, response.text

    assert response.json()["error"]["code"] == "NOT_FOUND"

    db_session.expire_all()

    updated_ticket = db_session.get(Ticket, ticket_id)

    assert updated_ticket.category_id == original_category_id
    assert updated_ticket.department_id == original_department_id
    assert updated_ticket.assigned_to == agent_user.id


def test_admin_cannot_assign_cross_department_agent(
    client,
    db_session,
    admin_headers,
    requester_user,
    category,
    other_department,
    make_user,
    make_ticket,
):
    other_agent = make_user(
        other_department,
        role="agent",
    )

    ticket = make_ticket(
        requester_user,
        category,
    )

    ticket_id = ticket.id

    response = client.patch(
        f"/api/v1/tickets/{ticket_id}",
        headers=admin_headers,
        json={"assigned_to": other_agent.id},
    )

    assert response.status_code == 422, response.text

    assert response.json()["error"]["message"] == (
        "Agent does not belong to the ticket department"
    )

    db_session.expire_all()

    updated_ticket = db_session.get(Ticket, ticket_id)

    assert updated_ticket.assigned_to is None


def test_category_change_validates_assignment_against_new_department(
    client,
    db_session,
    admin_user,
    admin_headers,
    agent_user,
    category,
    other_department,
    make_category,
    make_ticket,
):
    new_category = make_category(
        other_department,
        name="New Department Category",
    )

    ticket = make_ticket(
        admin_user,
        category,
    )

    ticket_id = ticket.id
    original_category_id = ticket.category_id
    original_department_id = ticket.department_id

    response = client.patch(
        f"/api/v1/tickets/{ticket_id}",
        headers=admin_headers,
        json={
            "category": new_category.name,
            "assigned_to": agent_user.id,
        },
    )

    assert response.status_code == 422, response.text

    assert response.json()["error"]["message"] == (
        "Agent does not belong to the ticket department"
    )

    db_session.expire_all()

    updated_ticket = db_session.get(Ticket, ticket_id)

    assert updated_ticket.category_id == original_category_id
    assert updated_ticket.department_id == original_department_id
    assert updated_ticket.assigned_to is None


def test_category_change_allows_agent_from_new_department(
    client,
    db_session,
    admin_user,
    admin_headers,
    category,
    other_department,
    make_category,
    make_user,
    make_ticket,
):
    new_category = make_category(
        other_department,
        name="New Support Department Category",
    )

    new_agent = make_user(
        other_department,
        role="agent",
    )

    ticket = make_ticket(
        admin_user,
        category,
    )

    ticket_id = ticket.id
    new_category_id = new_category.id
    new_department_id = other_department.id
    new_agent_id = new_agent.id

    response = client.patch(
        f"/api/v1/tickets/{ticket_id}",
        headers=admin_headers,
        json={
            "category": new_category.name,
            "assigned_to": new_agent_id,
        },
    )

    assert response.status_code == 200, response.text

    db_session.expire_all()

    updated_ticket = db_session.get(Ticket, ticket_id)

    assert updated_ticket.category_id == new_category_id
    assert updated_ticket.department_id == new_department_id
    assert updated_ticket.assigned_to == new_agent_id


def test_database_rejects_ticket_category_department_mismatch(
    db_session,
    requester_user,
    category,
    other_department,
):
    ticket = Ticket(
        title="Invalid department ticket",
        description="Testing database integrity protection.",
        category_id=category.id,
        department_id=other_department.id,
        requester_id=requester_user.id,
        requested_priority="medium",
        priority="medium",
        status="open",
    )

    with pytest.raises(IntegrityError) as exc_info, db_session.begin_nested():
        db_session.add(ticket)
        db_session.flush()

    assert exc_info.value.orig.diag.constraint_name == "fk_tickets_category_department"


def test_database_rejects_invalid_ticket_department_update(
    db_session,
    requester_user,
    category,
    other_department,
    make_ticket,
):
    ticket = make_ticket(
        requester_user,
        category,
    )

    ticket_id = ticket.id
    original_department_id = ticket.department_id

    with pytest.raises(IntegrityError) as exc_info, db_session.begin_nested():
        ticket.department_id = other_department.id
        db_session.flush()

    assert exc_info.value.orig.diag.constraint_name == "fk_tickets_category_department"

    db_session.expire_all()

    updated_ticket = db_session.get(Ticket, ticket_id)

    assert updated_ticket.department_id == original_department_id
