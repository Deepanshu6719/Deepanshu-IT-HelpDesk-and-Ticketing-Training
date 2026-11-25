"""
Authentication: login, refresh-token rotation (with reuse detection), logout,
and every way an access token can be rejected by get_current_user.
"""

import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from sqlalchemy import select

from core.config import settings
from core.security import create_access_token, hash_refresh_token
from models.refresh_token import RefreshToken
from models.user_session import UserSession


def login(client, email, password):
    return client.post("/auth/login", data={"username": email, "password": password})


def login_tokens(client, user, password):
    response = login(client, user.email, password)
    assert response.status_code == 200
    return response.json()


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def refresh(client, refresh_token):
    return client.post("/auth/refresh", json={"refresh_token": refresh_token})


def in_the_past():
    return datetime.now(UTC) - timedelta(minutes=1)


# ================================== LOGIN ================================== #
def test_login_success_returns_tokens_and_stores_session(
    client, db_session, requester_user, default_password
):
    response = login(client, requester_user.email, default_password)

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["refresh_token"]

    sessions = db_session.scalars(select(UserSession)).all()
    assert len(sessions) == 1
    stored = db_session.scalars(select(RefreshToken)).all()
    assert len(stored) == 1
    # Only the HASH of the refresh token is stored, never the token itself.
    assert stored[0].token_hash == hash_refresh_token(body["refresh_token"])
    assert stored[0].token_hash != body["refresh_token"]


def test_access_token_from_login_works_on_protected_endpoint(
    client, requester_user, default_password
):
    tokens = login_tokens(client, requester_user, default_password)

    response = client.get("/tickets", headers=bearer(tokens["access_token"]))

    assert response.status_code == 200


def test_login_with_wrong_password_returns_401_and_creates_no_session(
    client, db_session, requester_user
):
    response = login(client, requester_user.email, "WrongPassword123!")

    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password"
    assert db_session.scalars(select(UserSession)).all() == []


def test_login_does_not_reveal_whether_the_email_exists(client, requester_user):
    unknown_email = login(client, "nobody@example.com", "WhateverPass123!")
    wrong_password = login(client, requester_user.email, "WrongPassword123!")

    assert unknown_email.status_code == wrong_password.status_code == 401
    assert unknown_email.json() == wrong_password.json()


def test_deactivated_user_cannot_log_in(
    client, make_user, department, default_password
):
    inactive = make_user(department, is_active=False)

    response = login(client, inactive.email, default_password)

    assert response.status_code == 401


def test_login_without_password_returns_422(client, requester_user):
    response = client.post("/auth/login", data={"username": requester_user.email})

    assert response.status_code == 422


# ================================= REFRESH ================================= #
def test_refresh_rotates_the_token_and_links_old_to_new(
    client, db_session, requester_user, default_password
):
    tokens = login_tokens(client, requester_user, default_password)

    response = refresh(client, tokens["refresh_token"])

    assert response.status_code == 200
    new_tokens = response.json()
    assert new_tokens["refresh_token"] != tokens["refresh_token"]

    old_record = db_session.scalar(
        select(RefreshToken).where(
            RefreshToken.token_hash == hash_refresh_token(tokens["refresh_token"])
        )
    )
    new_record = db_session.scalar(
        select(RefreshToken).where(
            RefreshToken.token_hash == hash_refresh_token(new_tokens["refresh_token"])
        )
    )
    assert old_record.revoked_at is not None
    assert old_record.replaced_by_id == new_record.id
    assert new_record.revoked_at is None

    # the new access token is usable
    assert (
        client.get("/tickets", headers=bearer(new_tokens["access_token"])).status_code
        == 200
    )


def test_refresh_with_unknown_token_returns_401(client):
    response = refresh(client, "this-token-was-never-issued")

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid refresh token"


def test_refresh_with_empty_token_returns_422(client):
    assert refresh(client, "").status_code == 422


def test_reusing_an_old_refresh_token_revokes_the_whole_session(
    client, db_session, requester_user, default_password
):
    """Token-theft protection: replaying a rotated token must kill the session."""
    tokens = login_tokens(client, requester_user, default_password)
    newest = refresh(client, tokens["refresh_token"]).json()

    replay = refresh(client, tokens["refresh_token"])  # attacker replays the OLD token

    assert replay.status_code == 401
    assert "reuse" in replay.json()["detail"].lower()
    # Even the legitimately-issued newest token is now dead...
    assert refresh(client, newest["refresh_token"]).status_code == 401
    # ...and so is the newest access token.
    assert (
        client.get("/tickets", headers=bearer(newest["access_token"])).status_code
        == 401
    )
    assert db_session.scalar(select(UserSession)).revoked_at is not None


def test_refresh_with_expired_refresh_token_returns_401(
    client, db_session, requester_user, default_password
):
    tokens = login_tokens(client, requester_user, default_password)
    record = db_session.scalar(select(RefreshToken))
    record.expires_at = in_the_past()
    db_session.commit()

    response = refresh(client, tokens["refresh_token"])

    assert response.status_code == 401
    assert response.json()["detail"] == "Refresh token has expired"


def test_refresh_with_expired_session_returns_401(
    client, db_session, requester_user, default_password
):
    tokens = login_tokens(client, requester_user, default_password)
    user_session = db_session.scalar(select(UserSession))
    user_session.expires_at = in_the_past()
    db_session.commit()

    response = refresh(client, tokens["refresh_token"])

    assert response.status_code == 401
    assert response.json()["detail"] == "Session is no longer valid"


def test_refresh_fails_after_user_is_deactivated(
    client, db_session, requester_user, default_password
):
    tokens = login_tokens(client, requester_user, default_password)
    requester_user.is_active = False
    db_session.commit()

    response = refresh(client, tokens["refresh_token"])

    assert response.status_code == 401
    assert response.json()["detail"] == "User is no longer active"


# ================================= LOGOUT ================================== #
def test_logout_revokes_session_refresh_token_and_access_token(
    client, db_session, requester_user, default_password
):
    tokens = login_tokens(client, requester_user, default_password)
    headers = bearer(tokens["access_token"])

    response = client.post("/auth/logout", headers=headers)

    assert response.status_code == 200
    assert db_session.scalar(select(UserSession)).revoked_at is not None
    assert db_session.scalar(select(RefreshToken)).revoked_at is not None
    # The same access token and refresh token are useless afterwards.
    assert client.get("/tickets", headers=headers).status_code == 401
    assert client.post("/auth/logout", headers=headers).status_code == 401
    assert refresh(client, tokens["refresh_token"]).status_code == 401


def test_logout_without_token_returns_401(client):
    assert client.post("/auth/logout").status_code == 401


def test_logout_only_ends_the_current_device_session(
    client, requester_user, default_password
):
    phone = login_tokens(client, requester_user, default_password)
    laptop = login_tokens(client, requester_user, default_password)

    client.post("/auth/logout", headers=bearer(phone["access_token"]))

    assert (
        client.get("/tickets", headers=bearer(phone["access_token"])).status_code == 401
    )
    assert (
        client.get("/tickets", headers=bearer(laptop["access_token"])).status_code
        == 200
    )


# ===================== ACCESS-TOKEN VALIDATION (get_current_user) ===================== #
def build_token(user, drop=(), **overrides):
    """Builds a signed JWT. By default the claims are valid except for an unknown session id."""
    claims = {"sub": str(user.id), "ver": user.token_version, "sid": str(uuid.uuid4())}
    claims.update(overrides)
    for claim in drop:
        claims.pop(claim)
    return create_access_token(claims)


def test_request_without_authorization_header_returns_401(client):
    assert client.get("/tickets").status_code == 401


def test_garbage_token_returns_401(client):
    response = client.get("/tickets", headers=bearer("not.a.jwt"))

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or expired authentication credentials"


def test_expired_access_token_returns_401(client, requester_user):
    expired = jwt.encode(
        {
            "sub": str(requester_user.id),
            "ver": requester_user.token_version,
            "sid": str(uuid.uuid4()),
            "exp": in_the_past(),
        },
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )

    response = client.get("/tickets", headers=bearer(expired))

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or expired authentication credentials"


def test_token_signed_with_wrong_secret_returns_401(client, requester_user):
    forged = jwt.encode(
        {
            "sub": str(requester_user.id),
            "ver": requester_user.token_version,
            "sid": str(uuid.uuid4()),
            "exp": datetime.now(UTC) + timedelta(minutes=5),
        },
        "a-completely-different-secret-key-1234567890",
        algorithm=settings.ALGORITHM,
    )

    assert client.get("/tickets", headers=bearer(forged)).status_code == 401


@pytest.mark.parametrize(
    "overrides, expected_detail",
    [
        ({"sub": "abc"}, "Invalid authentication credentials"),  # not a number
        ({"sub": "0"}, "Invalid authentication credentials"),  # not a positive id
        ({"sub": "-3"}, "Invalid authentication credentials"),
        ({"sub": "999999"}, "Invalid authentication credentials"),  # no such user
        ({"ver": 999}, "Token is no longer valid"),  # wrong token version
        ({"ver": "1"}, "Token is no longer valid"),  # version must be an int
        ({"sid": "not-a-uuid"}, "Invalid authentication credentials"),
        ({"sid": 12345}, "Invalid authentication credentials"),
        ({"sid": str(uuid.uuid4())}, "Session is no longer valid"),  # unknown session
    ],
)
def test_token_with_bad_claims_is_rejected(
    client, requester_user, overrides, expected_detail
):
    response = client.get(
        "/tickets", headers=bearer(build_token(requester_user, **overrides))
    )

    assert response.status_code == 401
    assert response.json()["detail"] == expected_detail


@pytest.mark.parametrize(
    "missing_claim, expected_detail",
    [
        ("sub", "Invalid authentication credentials"),
        ("ver", "Token is no longer valid"),
        ("sid", "Invalid authentication credentials"),
    ],
)
def test_token_missing_a_required_claim_is_rejected(
    client, requester_user, missing_claim, expected_detail
):
    token = build_token(requester_user, drop=(missing_claim,))

    response = client.get("/tickets", headers=bearer(token))

    assert response.status_code == 401
    assert response.json()["detail"] == expected_detail


def test_valid_token_is_rejected_after_user_is_deactivated(
    client, db_session, requester_user, requester_headers
):
    requester_user.is_active = False
    db_session.commit()

    assert client.get("/tickets", headers=requester_headers).status_code == 401


def test_token_is_rejected_when_its_session_was_revoked(
    client, db_session, requester_user, requester_headers
):
    db_session.scalar(select(UserSession)).revoked_at = datetime.now(UTC)
    db_session.commit()

    response = client.get("/tickets", headers=requester_headers)

    assert response.status_code == 401
    assert response.json()["detail"] == "Session is no longer valid"


def test_token_is_rejected_when_its_session_expired(
    client, db_session, requester_user, requester_headers
):
    db_session.scalar(select(UserSession)).expires_at = in_the_past()
    db_session.commit()

    assert client.get("/tickets", headers=requester_headers).status_code == 401


def test_token_cannot_use_another_users_session(
    client, db_session, requester_user, agent_user, auth_headers
):
    auth_headers(agent_user)  # creates a valid session that belongs to the agent
    agents_session = db_session.scalar(
        select(UserSession).where(UserSession.user_id == agent_user.id)
    )
    stolen_session_id = agents_session.id
    token = build_token(requester_user, sid=stolen_session_id)

    response = client.get("/tickets", headers=bearer(token))

    assert response.status_code == 401
    assert response.json()["detail"] == "Session is no longer valid"
