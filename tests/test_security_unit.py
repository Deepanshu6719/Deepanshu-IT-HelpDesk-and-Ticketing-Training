"""
Pure unit tests: no database, no HTTP. They are fast and pinpoint exactly which
function is broken (hashing, JWTs, schema validation, permission helpers).
"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import jwt
import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from core.config import settings
from core.permissions import has_role
from core.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    get_password_hash,
    hash_refresh_token,
    verify_password,
)
from core.ticket_permissions import check_ticket_access
from schema.comment_schema import CommentCreate
from schema.ticket_schema import TicketCreate, TicketPatch
from schema.user_schema import UserCreate


# ----------------------------- passwords & tokens ----------------------------- #
def test_password_hash_is_not_the_plain_password_and_verifies():
    hashed = get_password_hash("CorrectHorse1!")

    assert hashed != "CorrectHorse1!"
    assert verify_password("CorrectHorse1!", hashed) is True


def test_wrong_password_does_not_verify():
    hashed = get_password_hash("CorrectHorse1!")

    assert verify_password("WrongHorse1!", hashed) is False


def test_same_password_hashes_differently_each_time_because_of_salt():
    assert get_password_hash("SamePassword1!") != get_password_hash("SamePassword1!")


def test_access_token_round_trip_keeps_claims_and_sets_expiry():
    token = create_access_token({"sub": "42", "ver": 3, "sid": "abc"})

    payload = decode_access_token(token)

    assert payload["sub"] == "42"
    assert payload["ver"] == 3
    assert payload["sid"] == "abc"
    assert payload["exp"] > datetime.now(timezone.utc).timestamp()


def test_expired_access_token_is_rejected():
    expired = jwt.encode(
        {"sub": "1", "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )

    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(expired)


def test_access_token_signed_with_another_key_is_rejected():
    forged = jwt.encode(
        {"sub": "1", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        "some-other-secret-key-that-is-long-enough-123456",
        algorithm=settings.ALGORITHM,
    )

    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(forged)


def test_refresh_tokens_are_unique_and_only_their_hash_is_stored():
    first = create_refresh_token()
    second = create_refresh_token()

    assert first != second
    assert len(first) >= 64
    assert hash_refresh_token(first) == hash_refresh_token(first)  # deterministic
    assert hash_refresh_token(first) != first
    assert len(hash_refresh_token(first)) == 64  # sha256 hex digest


# ------------------------------ schema validation ------------------------------ #
def test_ticket_create_strips_whitespace_from_title_and_description():
    ticket = TicketCreate(
        title="  Printer is down  ",
        description="  The printer on floor 2 is down  ",
        category="Hardware",
    )

    assert ticket.title == "Printer is down"
    assert ticket.description == "The printer on floor 2 is down"
    assert ticket.priority == "medium"  # default


@pytest.mark.parametrize(
    "overrides",
    [
        {"title": "abc"},  # shorter than 5
        {"title": "     "},  # only whitespace
        {"title": "x" * 51},  # longer than 50
        {"description": "too short"},  # shorter than 10
        {"description": "x" * 151},  # longer than 150
        {"priority": "critical"},  # not an allowed priority
        {"status": "closed"},  # extra field is forbidden
    ],
)
def test_ticket_create_rejects_invalid_input(overrides):
    data = {
        "title": "Valid title",
        "description": "A perfectly valid description.",
        "category": "Hardware",
    }
    data.update(overrides)

    with pytest.raises(ValidationError):
        TicketCreate(**data)


def test_ticket_patch_with_no_fields_is_empty():
    assert TicketPatch().model_dump(exclude_unset=True) == {}


@pytest.mark.parametrize(
    "overrides",
    [
        {"email": "not-an-email"},
        {"password": "short"},  # fewer than 8 characters
        {"department_id": 0},  # must be > 0
        {"role": "superuser"},  # not requester/agent/admin
    ],
)
def test_user_create_rejects_invalid_input(overrides):
    data = {
        "email": "person@example.com",
        "password": "LongEnough123",
        "department_id": 1,
        "role": "requester",
    }
    data.update(overrides)

    with pytest.raises(ValidationError):
        UserCreate(**data)


def test_comment_create_strips_message_and_rejects_blank_or_huge_messages():
    assert CommentCreate(message="  hello  ").message == "hello"

    with pytest.raises(ValidationError):
        CommentCreate(message="    ")
    with pytest.raises(ValidationError):
        CommentCreate(message="x" * 2001)
    with pytest.raises(ValidationError):
        CommentCreate(message="ok", unexpected_field=True)


# ------------------------- permission helpers (fake objects) ------------------------- #
def fake_user(user_id, *role_names):
    return SimpleNamespace(
        id=user_id,
        role_assignments=[SimpleNamespace(role=SimpleNamespace(name=n)) for n in role_names],
    )


def fake_ticket(requester_id, assigned_to=None):
    return SimpleNamespace(requester_id=requester_id, assigned_to=assigned_to)


def test_has_role_checks_role_names():
    user = fake_user(1, "agent")

    assert has_role(user, "agent") is True
    assert has_role(user, "admin") is False
    assert has_role(fake_user(2), "agent") is False


@pytest.mark.parametrize(
    "user",
    [
        fake_user(99, "admin"),  # admin sees everything
        fake_user(10),  # the requester
        fake_user(20, "agent"),  # the assigned agent
    ],
)
def test_check_ticket_access_allows_admin_requester_and_assigned_agent(user):
    check_ticket_access(fake_ticket(requester_id=10, assigned_to=20), user)  # must not raise


@pytest.mark.parametrize(
    "user",
    [
        fake_user(11),  # a different requester
        fake_user(21, "agent"),  # an agent who is not assigned
    ],
)
def test_check_ticket_access_hides_ticket_from_everyone_else_with_404(user):
    with pytest.raises(HTTPException) as error:
        check_ticket_access(fake_ticket(requester_id=10, assigned_to=20), user)

    assert error.value.status_code == 404  # 404, not 403: don't reveal the ticket exists
