from unittest.mock import patch

from core.security import verify_password


def test_unknown_email_still_performs_password_verification(
    client,
):
    with patch(
        "routes.auth.verify_password",
        wraps=verify_password,
    ) as mocked_verify:
        response = client.post(
            "/api/v1/auth/login",
            data={
                "username": "nonexistent@example.com",
                "password": "WrongPassword123!",
            },
        )

    assert response.status_code == 401
    mocked_verify.assert_called_once()


def test_inactive_user_still_performs_password_verification(
    client,
    department,
    make_user,
    default_password,
):
    user = make_user(
        department,
        is_active=False,
    )

    with patch(
        "routes.auth.verify_password",
        wraps=verify_password,
    ) as mocked_verify:
        response = client.post(
            "/api/v1/auth/login",
            data={
                "username": user.email,
                "password": default_password,
            },
        )

    assert response.status_code == 401
    mocked_verify.assert_called_once()


def test_password_change_revokes_all_device_sessions(
    client,
    requester_user,
    default_password,
):
    credentials = {
        "username": requester_user.email,
        "password": default_password,
    }

    first_login = client.post(
        "/api/v1/auth/login",
        data=credentials,
    )

    second_login = client.post(
        "/api/v1/auth/login",
        data=credentials,
    )

    assert first_login.status_code == 200
    assert second_login.status_code == 200

    first_tokens = first_login.json()
    second_tokens = second_login.json()

    first_headers = {"Authorization": (f"Bearer {first_tokens['access_token']}")}

    second_headers = {"Authorization": (f"Bearer {second_tokens['access_token']}")}

    # Both devices are authenticated before password change
    for headers in [first_headers, second_headers]:
        response = client.get(
            "/api/v1/tickets",
            headers=headers,
        )

        assert response.status_code == 200

    new_password = "NewSecurePassword123!"

    changed = client.patch(
        "/api/v1/users/me/password",
        headers=first_headers,
        json={
            "current_password": default_password,
            "new_password": new_password,
        },
    )

    assert changed.status_code == 200

    # Both access tokens must be invalid
    for headers in [first_headers, second_headers]:
        response = client.get(
            "/api/v1/tickets",
            headers=headers,
        )

        assert response.status_code == 401

    # Both refresh tokens must also be invalid
    for tokens in [first_tokens, second_tokens]:
        response = client.post(
            "/api/v1/auth/refresh",
            json={
                "refresh_token": tokens["refresh_token"],
            },
        )

        assert response.status_code == 401

    # Old password must fail
    old_login = client.post(
        "/api/v1/auth/login",
        data=credentials,
    )

    assert old_login.status_code == 401

    # New password must work
    new_login = client.post(
        "/api/v1/auth/login",
        data={
            "username": requester_user.email,
            "password": new_password,
        },
    )

    assert new_login.status_code == 200

    new_headers = {"Authorization": (f"Bearer {new_login.json()['access_token']}")}

    response = client.get(
        "/api/v1/tickets",
        headers=new_headers,
    )

    assert response.status_code == 200
