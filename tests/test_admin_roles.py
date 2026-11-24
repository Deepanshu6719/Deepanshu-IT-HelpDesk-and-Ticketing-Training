"""POST /admin/users/{id}/roles - role assignment and its domain rule: admin requires agent first."""
import pytest

from core.permissions import has_role


def assign(client, user_id, role, headers):
    return client.post(f"/admin/users/{user_id}/roles", json={"role": role}, headers=headers)


def test_admin_assigns_agent_role(client, db_session, admin_headers, requester_user):
    response = assign(client, requester_user.id, "agent", admin_headers)

    assert response.status_code == 201
    db_session.refresh(requester_user)
    assert has_role(requester_user, "agent") is True


def test_user_must_be_an_agent_before_becoming_admin(
    client, db_session, admin_headers, requester_user
):
    response = assign(client, requester_user.id, "admin", admin_headers)

    assert response.status_code == 400
    assert response.json()["detail"] == "User must be an agent before becoming an admin"
    db_session.refresh(requester_user)
    assert has_role(requester_user, "admin") is False


def test_agent_can_be_promoted_to_admin(client, db_session, admin_headers, agent_user):
    response = assign(client, agent_user.id, "admin", admin_headers)

    assert response.status_code == 201
    db_session.refresh(agent_user)
    assert has_role(agent_user, "admin") is True
    assert has_role(agent_user, "agent") is True  # keeps the agent role


def test_assigning_the_same_role_twice_returns_409(
    client, db_session, admin_headers, requester_user
):
    url_user_id = requester_user.id  # read the id now: expunge_all() below detaches objects
    assert assign(client, url_user_id, "agent", admin_headers).status_code == 201

    # In production every request gets a brand-new session. Clearing the identity map makes
    # the test session behave the same way, so the database's duplicate-key error is hit.
    db_session.expunge_all()
    response = assign(client, url_user_id, "agent", admin_headers)

    assert response.status_code == 409
    assert response.json()["detail"] == "User already has this role"


def test_assign_role_to_unknown_user_returns_404(client, admin_headers):
    assert assign(client, 999999, "agent", admin_headers).status_code == 404


def test_assign_invalid_role_returns_422(client, admin_headers, requester_user):
    assert assign(client, requester_user.id, "superadmin", admin_headers).status_code == 422


@pytest.mark.parametrize("headers_fixture", ["requester_headers", "agent_headers"])
def test_only_admins_can_assign_roles(client, request, requester_user, headers_fixture):
    headers = request.getfixturevalue(headers_fixture)

    assert assign(client, requester_user.id, "agent", headers).status_code == 403


def test_assign_role_requires_authentication(client, requester_user):
    response = client.post(f"/admin/users/{requester_user.id}/roles", json={"role": "agent"})

    assert response.status_code == 401
