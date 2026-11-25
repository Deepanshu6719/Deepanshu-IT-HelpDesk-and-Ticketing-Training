"""User management (admin only) and the "change my password" flow."""

import pytest
from sqlalchemy import select

from core.permissions import has_role
from core.security import verify_password
from models.user import User


def new_user_payload(department, **overrides):
    payload = {
        "email": "new.person@example.com",
        "password": "StrongPass123!",
        "department_id": department.id,
        "role": "requester",
    }
    payload.update(overrides)
    return payload


def login(client, email, password):
    return client.post("/auth/login", data={"username": email, "password": password})


# ============================== POST /users ============================== #
def test_admin_creates_requester(client, db_session, admin_headers, department):
    response = client.post(
        "/users", json=new_user_payload(department), headers=admin_headers
    )

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "new.person@example.com"
    assert body["department_id"] == department.id
    assert body["is_active"] is True
    # The response must never leak password data.
    assert "password" not in body
    assert "hashed_password" not in body

    created = db_session.scalar(
        select(User).where(User.email == "new.person@example.com")
    )
    assert created.hashed_password != "StrongPass123!"
    assert verify_password("StrongPass123!", created.hashed_password)
    assert created.role_assignments == []  # plain requesters have no role row


@pytest.mark.parametrize("role", ["agent", "admin"])
def test_admin_creates_user_with_privileged_role(
    client, db_session, admin_headers, department, role
):
    response = client.post(
        "/users", json=new_user_payload(department, role=role), headers=admin_headers
    )

    assert response.status_code == 201
    created = db_session.scalar(
        select(User).where(User.email == "new.person@example.com")
    )
    assert has_role(created, role) is True


def test_create_user_with_existing_email_returns_409(
    client, admin_headers, department, requester_user
):
    payload = new_user_payload(department, email=requester_user.email)

    response = client.post("/users", json=payload, headers=admin_headers)

    assert response.status_code == 409
    assert response.json()["detail"] == "Email already registered"


def test_create_user_in_unknown_department_returns_404(
    client, admin_headers, department
):
    payload = new_user_payload(department, department_id=999999)

    response = client.post("/users", json=payload, headers=admin_headers)

    assert response.status_code == 404
    assert response.json()["detail"] == "Department not found"


@pytest.mark.parametrize(
    "overrides",
    [
        {"email": "not-an-email"},
        {"password": "short"},
        {"department_id": 0},
        {"role": "superuser"},
        {"is_active": False},  # unknown field is forbidden
    ],
)
def test_create_user_with_invalid_payload_returns_422(
    client, admin_headers, department, overrides
):
    response = client.post(
        "/users", json=new_user_payload(department, **overrides), headers=admin_headers
    )

    assert response.status_code == 422


def test_create_user_requires_admin_role(
    client, department, requester_headers, agent_headers
):
    payload = new_user_payload(department)

    assert client.post("/users", json=payload).status_code == 401
    assert (
        client.post("/users", json=payload, headers=requester_headers).status_code
        == 403
    )
    assert client.post("/users", json=payload, headers=agent_headers).status_code == 403


# ============================== GET /users ============================== #
def test_admin_lists_users_in_id_order_with_pagination(
    client, admin_user, agent_user, requester_user, admin_headers
):
    everyone = client.get("/users", headers=admin_headers).json()
    ids = [u["id"] for u in everyone]
    assert ids == sorted(ids)
    assert {u["email"] for u in everyone} >= {
        admin_user.email,
        agent_user.email,
        requester_user.email,
    }

    first_page = client.get(
        "/users", params={"skip": 0, "limit": 2}, headers=admin_headers
    ).json()
    second_page = client.get(
        "/users", params={"skip": 2, "limit": 2}, headers=admin_headers
    ).json()
    assert len(first_page) == 2
    assert [u["id"] for u in first_page + second_page] == ids[
        : len(first_page + second_page)
    ]


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 101}, {"skip": -1}])
def test_list_users_rejects_invalid_pagination(client, admin_headers, params):
    assert client.get("/users", params=params, headers=admin_headers).status_code == 422


def test_list_users_requires_admin(client, requester_headers):
    assert client.get("/users", headers=requester_headers).status_code == 403


# ============================ GET /users/{id} ============================ #
def test_admin_gets_user_by_id(client, admin_headers, requester_user):
    response = client.get(f"/users/{requester_user.id}", headers=admin_headers)

    assert response.status_code == 200
    assert response.json()["email"] == requester_user.email


def test_get_unknown_user_returns_404(client, admin_headers):
    assert client.get("/users/999999", headers=admin_headers).status_code == 404


def test_requester_cannot_read_other_users(client, requester_headers, admin_user):
    assert (
        client.get(f"/users/{admin_user.id}", headers=requester_headers).status_code
        == 403
    )


# ======================== PATCH /users/{id}/status ======================== #
def test_admin_deactivates_user_and_that_user_is_locked_out(
    client,
    db_session,
    admin_headers,
    requester_user,
    requester_headers,
    default_password,
):
    response = client.patch(
        f"/users/{requester_user.id}/status",
        json={"is_active": False},
        headers=admin_headers,
    )

    assert response.status_code == 200
    assert response.json()["is_active"] is False
    # Domain consequence: no new logins AND the already-issued token stops working.
    assert login(client, requester_user.email, default_password).status_code == 401
    assert client.get("/tickets", headers=requester_headers).status_code == 401


def test_admin_can_reactivate_a_user(
    client, make_user, department, admin_headers, default_password
):
    inactive = make_user(department, is_active=False)

    response = client.patch(
        f"/users/{inactive.id}/status", json={"is_active": True}, headers=admin_headers
    )

    assert response.status_code == 200
    assert login(client, inactive.email, default_password).status_code == 200


def test_admin_cannot_change_their_own_status(client, admin_user, admin_headers):
    response = client.patch(
        f"/users/{admin_user.id}/status",
        json={"is_active": False},
        headers=admin_headers,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "You cannot change your own account status"


def test_setting_the_same_status_returns_409(client, admin_headers, requester_user):
    response = client.patch(
        f"/users/{requester_user.id}/status",
        json={"is_active": True},
        headers=admin_headers,
    )

    assert response.status_code == 409


def test_status_update_for_unknown_user_returns_404(client, admin_headers):
    response = client.patch(
        "/users/999999/status", json={"is_active": False}, headers=admin_headers
    )

    assert response.status_code == 404


def test_status_update_requires_admin_and_a_body(
    client, requester_headers, admin_headers, agent_user
):
    url = f"/users/{agent_user.id}/status"

    assert (
        client.patch(
            url, json={"is_active": False}, headers=requester_headers
        ).status_code
        == 403
    )
    assert client.patch(url, json={}, headers=admin_headers).status_code == 422


# ========================= PATCH /users/me/password ========================= #
def test_change_password_success_invalidates_old_tokens(
    client, db_session, requester_user, requester_headers, default_password
):
    response = client.patch(
        "/users/me/password",
        json={"current_password": default_password, "new_password": "BrandNewPass456!"},
        headers=requester_headers,
    )

    assert response.status_code == 200
    db_session.refresh(requester_user)
    assert requester_user.token_version == 2
    # Old password and old access token are dead; the new password works.
    assert login(client, requester_user.email, default_password).status_code == 401
    assert login(client, requester_user.email, "BrandNewPass456!").status_code == 200
    stale = client.get("/tickets", headers=requester_headers)
    assert stale.status_code == 401
    assert stale.json()["detail"] == "Token is no longer valid"


def test_change_password_with_wrong_current_password_returns_400(
    client, requester_headers
):
    response = client.patch(
        "/users/me/password",
        json={
            "current_password": "NotMyPassword1!",
            "new_password": "BrandNewPass456!",
        },
        headers=requester_headers,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Current password is incorrect"


def test_new_password_must_differ_from_current_password(
    client, requester_headers, default_password
):
    response = client.patch(
        "/users/me/password",
        json={"current_password": default_password, "new_password": default_password},
        headers=requester_headers,
    )

    assert response.status_code == 400
    assert (
        response.json()["detail"]
        == "New password must be different from current password"
    )


def test_new_password_must_be_at_least_8_characters(
    client, requester_headers, default_password
):
    response = client.patch(
        "/users/me/password",
        json={"current_password": default_password, "new_password": "short"},
        headers=requester_headers,
    )

    assert response.status_code == 422


def test_change_password_requires_authentication(client, default_password):
    response = client.patch(
        "/users/me/password",
        json={"current_password": default_password, "new_password": "BrandNewPass456!"},
    )

    assert response.status_code == 401
