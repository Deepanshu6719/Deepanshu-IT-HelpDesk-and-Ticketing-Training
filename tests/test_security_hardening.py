import pytest


@pytest.mark.parametrize(
    "extra_fields",
    [
        {"id": 99999},
        {"requester_id": 99999},
        {"assigned_to": 99999},
        {"department_id": 99999},
        {"status": "resolved"},
        {"is_deleted": True},
        {"created_at": "2026-01-01T00:00:00Z"},
        {"deleted_at": "2026-01-01T00:00:00Z"},
    ],
)
def test_ticket_creation_rejects_mass_assignment(
    client,
    requester_headers,
    category,
    extra_fields,
):
    payload = {
        "title": "Security test ticket",
        "description": "Testing mass assignment protection.",
        "category": category.name,
        "priority": "medium",
        **extra_fields,
    }

    response = client.post(
        "/api/v1/tickets",
        json=payload,
        headers=requester_headers,
    )

    assert response.status_code == 422

    body = response.json()

    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"

    assert any(
        detail["type"] == "extra_forbidden" for detail in body["error"]["details"]
    )


@pytest.mark.parametrize(
    "extra_fields",
    [
        {"requester_id": 99999},
        {"department_id": 99999},
        {"is_deleted": True},
        {"id": 99999},
        {"deleted_at": "2026-01-01T00:00:00Z"},
    ],
)
def test_ticket_update_rejects_mass_assignment(
    client,
    requester_user,
    requester_headers,
    category,
    make_ticket,
    extra_fields,
):
    ticket = make_ticket(requester_user, category)

    response = client.patch(
        f"/api/v1/tickets/{ticket.id}",
        json={
            "title": "Updated security test title",
            **extra_fields,
        },
        headers=requester_headers,
    )

    assert response.status_code == 422

    body = response.json()

    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"

    assert any(
        detail["type"] == "extra_forbidden" for detail in body["error"]["details"]
    )


def test_requester_cannot_create_admin_account(
    client,
    requester_headers,
    department,
):
    response = client.post(
        "/api/v1/users",
        json={
            "email": "unauthorized-admin@example.com",
            "password": "StrongPassword123!",
            "department_id": department.id,
            "role": "admin",
        },
        headers=requester_headers,
    )

    assert response.status_code == 403
    assert response.json()["success"] is False


def test_requester_cannot_promote_themselves(
    client,
    requester_user,
    requester_headers,
):
    response = client.post(
        f"/api/v1/admin/users/{requester_user.id}/roles",
        json={"role": "admin"},
        headers=requester_headers,
    )

    assert response.status_code == 403
    assert response.json()["success"] is False


@pytest.mark.parametrize(
    "extra_fields",
    [
        {"id": 99999},
        {"is_active": False},
        {"is_admin": True},
        {"token_version": 100},
        {"hashed_password": "injected-hash"},
        {"role_assignments": ["admin"]},
    ],
)
def test_user_creation_rejects_mass_assignment(
    client,
    admin_headers,
    department,
    extra_fields,
):
    response = client.post(
        "/api/v1/users",
        json={
            "email": "security-test@example.com",
            "password": "StrongPassword123!",
            "department_id": department.id,
            "role": "requester",
            **extra_fields,
        },
        headers=admin_headers,
    )

    assert response.status_code == 422

    body = response.json()

    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"

    assert any(
        detail["type"] == "extra_forbidden" for detail in body["error"]["details"]
    )


@pytest.mark.parametrize(
    "extra_fields",
    [
        {"id": 99999},
        {"user_id": 99999},
        {"ticket_id": 99999},
        {"created_at": "2026-01-01T00:00:00Z"},
    ],
)
def test_comment_creation_rejects_mass_assignment(
    client,
    requester_user,
    requester_headers,
    category,
    make_ticket,
    extra_fields,
):
    ticket = make_ticket(requester_user, category)

    response = client.post(
        f"/api/v1/tickets/{ticket.id}/comments",
        json={
            "message": "Testing comment security.",
            "is_internal": False,
            **extra_fields,
        },
        headers=requester_headers,
    )

    assert response.status_code == 422

    body = response.json()

    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"

    assert any(
        detail["type"] == "extra_forbidden" for detail in body["error"]["details"]
    )


def test_department_creation_rejects_extra_fields(
    client,
    admin_headers,
):
    response = client.post(
        "/api/v1/departments",
        json={
            "name": "Security Department",
            "id": 99999,
        },
        headers=admin_headers,
    )

    assert response.status_code == 422


def test_department_update_rejects_extra_fields(
    client,
    admin_headers,
    department,
):
    response = client.patch(
        f"/api/v1/departments/{department.id}",
        json={
            "name": "Updated Department",
            "id": 99999,
        },
        headers=admin_headers,
    )

    assert response.status_code == 422


def test_user_status_update_rejects_extra_fields(
    client,
    admin_headers,
    requester_user,
):
    response = client.patch(
        f"/api/v1/users/{requester_user.id}/status",
        json={
            "is_active": False,
            "role": "admin",
        },
        headers=admin_headers,
    )

    assert response.status_code == 422


def test_password_change_rejects_extra_fields(
    client,
    requester_headers,
):
    response = client.patch(
        "/api/v1/users/me/password",
        json={
            "current_password": "ExamplePassword123!",
            "new_password": "NewPassword123!",
            "user_id": 99999,
        },
        headers=requester_headers,
    )

    assert response.status_code == 422


def test_refresh_request_rejects_extra_fields(client):
    response = client.post(
        "/api/v1/auth/refresh",
        json={
            "refresh_token": "example-refresh-token",
            "user_id": 99999,
        },
    )

    assert response.status_code == 422


def test_role_assignment_rejects_extra_fields(
    client,
    admin_headers,
    requester_user,
):
    response = client.post(
        f"/api/v1/admin/users/{requester_user.id}/roles",
        json={
            "role": "agent",
            "user_id": 99999,
        },
        headers=admin_headers,
    )

    assert response.status_code == 422
