import pytest

DASHBOARD_URL = "/api/v1/dashboard/me"


def get_dashboard(client, headers):
    response = client.get(
        DASHBOARD_URL,
        headers=headers,
    )

    assert response.status_code == 200, response.text

    payload = response.json()

    assert payload["success"] is True

    return payload["data"]


def assert_consistent_counts(data):
    total = data["total_tickets"]

    assert sum(data["by_status"].values()) == total
    assert sum(data["by_priority"].values()) == total

    assert data["assigned_tickets"] + data["unassigned_tickets"] == total


def test_empty_dashboard_returns_zero_counts(
    client,
    requester_headers,
):
    data = get_dashboard(
        client,
        requester_headers,
    )

    assert data == {
        "total_tickets": 0,
        "by_status": {
            "open": 0,
            "under_review": 0,
            "in_progress": 0,
            "resolved": 0,
            "closed": 0,
        },
        "by_priority": {
            "low": 0,
            "medium": 0,
            "high": 0,
            "urgent": 0,
        },
        "assigned_tickets": 0,
        "unassigned_tickets": 0,
    }


def test_dashboard_requires_authentication(client):
    response = client.get(DASHBOARD_URL)

    assert response.status_code == 401


def test_requester_dashboard_excludes_other_users_tickets(
    client,
    requester_user,
    requester_headers,
    department,
    category,
    make_user,
    make_ticket,
):
    other_user = make_user(department)

    make_ticket(
        requester_user,
        category,
        priority="high",
        status="open",
    )

    make_ticket(
        requester_user,
        category,
        priority="medium",
        status="resolved",
    )

    make_ticket(
        other_user,
        category,
        priority="urgent",
        status="in_progress",
    )

    data = get_dashboard(client, requester_headers)

    assert data["total_tickets"] == 2

    assert data["by_status"]["open"] == 1
    assert data["by_status"]["resolved"] == 1
    assert data["by_status"]["in_progress"] == 0

    assert data["by_priority"]["high"] == 1
    assert data["by_priority"]["medium"] == 1
    assert data["by_priority"]["urgent"] == 0

    assert_consistent_counts(data)


def test_agent_dashboard_counts_assigned_and_own_tickets(
    client,
    agent_user,
    agent_headers,
    requester_user,
    category,
    make_ticket,
):
    # Assigned to the agent
    make_ticket(
        requester_user,
        category,
        assigned_to=agent_user,
        status="in_progress",
    )

    # Requested by the agent
    make_ticket(
        agent_user,
        category,
        status="open",
    )

    # Unrelated ticket
    make_ticket(
        requester_user,
        category,
        status="under_review",
    )

    data = get_dashboard(client, agent_headers)

    assert data["total_tickets"] == 2

    assert data["by_status"]["in_progress"] == 1
    assert data["by_status"]["open"] == 1
    assert data["by_status"]["under_review"] == 0

    assert data["assigned_tickets"] == 1
    assert data["unassigned_tickets"] == 1

    assert_consistent_counts(data)


def test_admin_dashboard_counts_all_accessible_tickets(
    client,
    admin_headers,
    requester_user,
    agent_user,
    category,
    make_ticket,
):
    make_ticket(
        requester_user,
        category,
        status="open",
        priority="low",
    )

    make_ticket(
        requester_user,
        category,
        assigned_to=agent_user,
        status="in_progress",
        priority="urgent",
    )

    make_ticket(
        agent_user,
        category,
        status="closed",
        priority="medium",
    )

    data = get_dashboard(client, admin_headers)

    assert data["total_tickets"] == 3

    assert data["by_status"]["open"] == 1
    assert data["by_status"]["in_progress"] == 1
    assert data["by_status"]["closed"] == 1

    assert data["by_priority"]["low"] == 1
    assert data["by_priority"]["urgent"] == 1
    assert data["by_priority"]["medium"] == 1

    assert data["assigned_tickets"] == 1
    assert data["unassigned_tickets"] == 2

    assert_consistent_counts(data)


@pytest.mark.parametrize(
    "header_fixture",
    [
        "admin_headers",
        "agent_headers",
        "requester_headers",
    ],
)
def test_dashboard_excludes_soft_deleted_tickets(
    client,
    db_session,
    request,
    header_fixture,
    requester_user,
    agent_user,
    category,
    make_ticket,
):
    ticket = make_ticket(
        requester_user,
        category,
        assigned_to=agent_user,
    )

    ticket.is_deleted = True

    db_session.commit()

    headers = request.getfixturevalue(header_fixture)

    data = get_dashboard(client, headers)

    assert data["total_tickets"] == 0
    assert data["assigned_tickets"] == 0
    assert data["unassigned_tickets"] == 0

    assert_consistent_counts(data)


@pytest.mark.parametrize(
    "header_fixture",
    [
        "admin_headers",
        "agent_headers",
        "requester_headers",
    ],
)
def test_dashboard_total_matches_ticket_list_total(
    client,
    request,
    header_fixture,
    requester_user,
    agent_user,
    category,
    make_ticket,
):
    make_ticket(
        requester_user,
        category,
    )

    make_ticket(
        requester_user,
        category,
        assigned_to=agent_user,
    )

    make_ticket(
        agent_user,
        category,
    )

    headers = request.getfixturevalue(header_fixture)

    dashboard = get_dashboard(client, headers)

    response = client.get(
        "/api/v1/tickets",
        headers=headers,
        params={
            "page": 1,
            "limit": 1,
        },
    )

    assert response.status_code == 200, response.text

    ticket_data = response.json()["data"]

    assert dashboard["total_tickets"] == ticket_data["total"]
