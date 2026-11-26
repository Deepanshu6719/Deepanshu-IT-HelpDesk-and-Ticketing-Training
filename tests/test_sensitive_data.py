SENSITIVE_FIELDS = {
    "password",
    "hashed_password",
    "token_version",
    "token_hash",
    "secret_key",
    "role_assignments",
    "refresh_tokens",
    "sessions",
}


def assert_no_sensitive_fields(data):
    if isinstance(data, dict):
        exposed_fields = SENSITIVE_FIELDS.intersection(data)

        assert not exposed_fields, f"Sensitive fields exposed: {exposed_fields}"

        for value in data.values():
            assert_no_sensitive_fields(value)

    elif isinstance(data, list):
        for item in data:
            assert_no_sensitive_fields(item)


def test_user_detail_does_not_expose_sensitive_fields(
    client,
    admin_headers,
    requester_user,
):
    response = client.get(
        f"/api/v1/users/{requester_user.id}",
        headers=admin_headers,
    )

    assert response.status_code == 200

    data = response.json()["data"]

    assert set(data) == {
        "id",
        "email",
        "department_id",
        "is_active",
    }

    assert_no_sensitive_fields(data)


def test_user_listing_does_not_expose_sensitive_fields(
    client,
    admin_headers,
):
    response = client.get(
        "/api/v1/users",
        headers=admin_headers,
    )

    assert response.status_code == 200

    data = response.json()["data"]

    assert data["items"]

    assert_no_sensitive_fields(data)


def test_agent_listing_does_not_expose_sensitive_fields(
    client,
    admin_headers,
    agent_user,
):
    response = client.get(
        "/api/v1/agents",
        headers=admin_headers,
    )

    assert response.status_code == 200

    data = response.json()["data"]

    assert any(item["id"] == agent_user.id for item in data["items"])

    assert_no_sensitive_fields(data)


def test_ticket_detail_does_not_expose_sensitive_fields(
    client,
    requester_user,
    requester_headers,
    category,
    make_ticket,
):
    ticket = make_ticket(requester_user, category)

    response = client.get(
        f"/api/v1/tickets/{ticket.id}",
        headers=requester_headers,
    )

    assert response.status_code == 200

    data = response.json()["data"]

    assert set(data["requester"]) == {
        "id",
        "email",
    }

    assert_no_sensitive_fields(data)


def test_ticket_listing_does_not_expose_sensitive_fields(
    client,
    requester_user,
    requester_headers,
    category,
    make_ticket,
):
    make_ticket(requester_user, category)

    response = client.get(
        "/api/v1/tickets",
        headers=requester_headers,
    )

    assert response.status_code == 200

    data = response.json()["data"]

    assert data["items"]

    assert_no_sensitive_fields(data)


def test_comment_author_does_not_expose_sensitive_fields(
    client,
    requester_user,
    requester_headers,
    category,
    make_ticket,
):
    ticket = make_ticket(requester_user, category)

    created = client.post(
        f"/api/v1/tickets/{ticket.id}/comments",
        headers=requester_headers,
        json={
            "message": "Checking sensitive data protection.",
        },
    )

    assert created.status_code == 201

    created_data = created.json()["data"]

    assert set(created_data["author"]) == {
        "id",
        "email",
    }

    assert_no_sensitive_fields(created_data)

    response = client.get(
        f"/api/v1/tickets/{ticket.id}/comments",
        headers=requester_headers,
    )

    assert response.status_code == 200

    data = response.json()["data"]

    assert data["items"]

    assert_no_sensitive_fields(data)
