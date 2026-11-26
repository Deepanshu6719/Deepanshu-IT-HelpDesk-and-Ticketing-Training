import pytest


@pytest.mark.parametrize("role", ["requester", "agent"])
@pytest.mark.parametrize(
    "method,path,payload",
    [
        ("GET", "/users", None),
        ("GET", "/users/{user_id}", None),
        (
            "POST",
            "/users",
            {
                "email": "unauthorized@example.com",
                "password": "StrongPassword123!",
                "department_id": 1,
                "role": "admin",
            },
        ),
        (
            "PATCH",
            "/users/{user_id}/status",
            {"is_active": False},
        ),
        (
            "POST",
            "/admin/users/{user_id}/roles",
            {"role": "admin"},
        ),
        ("GET", "/departments", None),
        ("GET", "/departments/{department_id}", None),
        (
            "POST",
            "/departments",
            {"name": "Unauthorized Department"},
        ),
        (
            "PATCH",
            "/departments/{department_id}",
            {"name": "Unauthorized Rename"},
        ),
        ("GET", "/categories", None),
        (
            "POST",
            "/categories",
            {
                "name": "Unauthorized Category",
                "department_id": 1,
            },
        ),
        (
            "PATCH",
            "/categories/{category_id}",
            {"name": "Unauthorized Rename"},
        ),
        ("DELETE", "/categories/{category_id}", None),
        ("GET", "/agents", None),
        (
            "GET",
            "/departments/{department_id}/agents",
            None,
        ),
    ],
)
def test_non_admin_cannot_access_admin_endpoints(
    client,
    requester_headers,
    agent_headers,
    requester_user,
    department,
    category,
    role,
    method,
    path,
    payload,
):
    headers = requester_headers if role == "requester" else agent_headers

    path = path.format(
        user_id=requester_user.id,
        department_id=department.id,
        category_id=category.id,
    )

    if payload is not None:
        payload = payload.copy()

        if "department_id" in payload:
            payload["department_id"] = department.id

    response = client.request(
        method,
        f"/api/v1{path}",
        headers=headers,
        json=payload,
    )

    assert response.status_code == 403, (role, method, path)

    body = response.json()

    assert body["success"] is False
    assert body["error"]["code"] == "FORBIDDEN"
