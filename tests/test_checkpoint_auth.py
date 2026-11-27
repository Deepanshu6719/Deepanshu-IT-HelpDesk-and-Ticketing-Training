import jwt

from core.config import settings


def test_access_token_contains_only_expected_claims(
    client,
    requester_user,
    default_password,
):
    response = client.post(
        "/api/v1/auth/login",
        data={
            "username": requester_user.email,
            "password": default_password,
        },
    )

    assert response.status_code == 200

    tokens = response.json()

    payload = jwt.decode(
        tokens["access_token"],
        settings.SECRET_KEY,
        algorithms=[settings.ALGORITHM],
    )

    assert set(payload) == {
        "sub",
        "exp",
        "ver",
        "sid",
    }

    assert payload["sub"] == str(requester_user.id)
    assert payload["ver"] == requester_user.token_version
    assert isinstance(payload["sid"], str)
    assert payload["sid"]
    assert isinstance(payload["exp"], int)


def test_refresh_token_is_not_access_token(
    client,
    requester_user,
    default_password,
):
    response = client.post(
        "/api/v1/auth/login",
        data={
            "username": requester_user.email,
            "password": default_password,
        },
    )

    assert response.status_code == 200

    tokens = response.json()

    assert tokens["access_token"] != tokens["refresh_token"]

    protected_response = client.get(
        "/api/v1/tickets",
        headers={
            "Authorization": (f"Bearer {tokens['refresh_token']}"),
        },
    )

    assert protected_response.status_code == 401
