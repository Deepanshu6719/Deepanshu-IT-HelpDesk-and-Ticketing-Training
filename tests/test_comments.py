"""
Ticket comments. Domain rule worth protecting: INTERNAL notes are staff-only and must
never leak to the requester - neither when posting nor when reading.
"""

import pytest


def comments_url(ticket):
    return f"/tickets/{ticket.id}/comments"


# ================================ POST comment ================================ #
def test_requester_posts_public_comment_on_own_ticket(
    client, requester_user, requester_headers, category, make_ticket
):
    ticket = make_ticket(requester_user, category)

    response = client.post(
        comments_url(ticket),
        json={"message": "  Still broken, please help  "},
        headers=requester_headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["message"] == "Still broken, please help"  # whitespace trimmed
    assert body["is_internal"] is False
    assert body["ticket_id"] == ticket.id
    assert body["user_id"] == requester_user.id
    assert body["author"]["email"] == requester_user.email


def test_requester_cannot_post_internal_comment(
    client, requester_user, requester_headers, category, make_ticket
):
    ticket = make_ticket(requester_user, category)

    response = client.post(
        comments_url(ticket),
        json={"message": "Secret staff note", "is_internal": True},
        headers=requester_headers,
    )

    assert response.status_code == 403
    assert (
        response.json()["detail"] == "You are not allowed to create internal comments"
    )


def test_assigned_agent_and_admin_can_post_internal_comments(
    client,
    requester_user,
    agent_user,
    agent_headers,
    admin_headers,
    category,
    make_ticket,
):
    ticket = make_ticket(requester_user, category, assigned_to=agent_user)

    for headers in (agent_headers, admin_headers):
        response = client.post(
            comments_url(ticket),
            json={"message": "Internal note", "is_internal": True},
            headers=headers,
        )

        assert response.status_code == 201
        assert response.json()["is_internal"] is True


def test_stranger_cannot_comment_on_someone_elses_ticket(
    client, requester_user, category, make_ticket, make_user, department, auth_headers
):
    ticket = make_ticket(requester_user, category)
    stranger_headers = auth_headers(make_user(department))

    response = client.post(
        comments_url(ticket), json={"message": "Hello?"}, headers=stranger_headers
    )

    assert response.status_code == 404


def test_unassigned_agent_cannot_comment(
    client, requester_user, agent_headers, category, make_ticket
):
    ticket = make_ticket(requester_user, category)

    response = client.post(
        comments_url(ticket), json={"message": "Hello?"}, headers=agent_headers
    )

    assert response.status_code == 404


def test_cannot_comment_on_unknown_or_deleted_ticket(
    client, db_session, requester_user, requester_headers, category, make_ticket
):
    deleted = make_ticket(requester_user, category)
    deleted.is_deleted = True
    db_session.commit()

    unknown = client.post(
        "/tickets/999999/comments", json={"message": "Hi"}, headers=requester_headers
    )
    removed = client.post(
        comments_url(deleted), json={"message": "Hi"}, headers=requester_headers
    )

    assert unknown.status_code == 404
    assert removed.status_code == 404


@pytest.mark.parametrize(
    "payload",
    [
        {},  # message missing
        {"message": ""},
        {"message": "     "},  # only whitespace
        {"message": "x" * 2001},  # too long
        {"message": "ok", "unexpected": True},  # unknown field
        {"message": "ok", "is_internal": "maybe"},  # not a boolean
    ],
)
def test_invalid_comment_payload_returns_422(
    client, requester_user, requester_headers, category, make_ticket, payload
):
    ticket = make_ticket(requester_user, category)

    response = client.post(
        comments_url(ticket), json=payload, headers=requester_headers
    )

    assert response.status_code == 422


def test_comment_at_exactly_2000_characters_is_accepted(
    client, requester_user, requester_headers, category, make_ticket
):
    ticket = make_ticket(requester_user, category)

    response = client.post(
        comments_url(ticket), json={"message": "x" * 2000}, headers=requester_headers
    )

    assert response.status_code == 201


def test_posting_a_comment_requires_authentication(
    client, requester_user, category, make_ticket
):
    ticket = make_ticket(requester_user, category)

    assert client.post(comments_url(ticket), json={"message": "Hi"}).status_code == 401


# ================================ GET comments ================================ #
def test_comments_are_returned_oldest_first(
    client, requester_user, requester_headers, category, make_ticket, make_comment
):
    ticket = make_ticket(requester_user, category)
    for text in ("first", "second", "third"):
        make_comment(ticket, requester_user, text)

    response = client.get(comments_url(ticket), headers=requester_headers)

    assert response.status_code == 200
    assert [c["message"] for c in response.json()] == ["first", "second", "third"]


def test_requester_never_sees_internal_comments(
    client,
    requester_user,
    agent_user,
    requester_headers,
    category,
    make_ticket,
    make_comment,
):
    ticket = make_ticket(requester_user, category, assigned_to=agent_user)
    make_comment(ticket, requester_user, "public question")
    make_comment(ticket, agent_user, "internal diagnosis", is_internal=True)
    make_comment(ticket, agent_user, "public answer")

    response = client.get(comments_url(ticket), headers=requester_headers)

    messages = [c["message"] for c in response.json()]
    assert messages == ["public question", "public answer"]
    assert "internal diagnosis" not in response.text


def test_agent_and_admin_see_internal_comments(
    client,
    requester_user,
    agent_user,
    agent_headers,
    admin_headers,
    category,
    make_ticket,
    make_comment,
):
    ticket = make_ticket(requester_user, category, assigned_to=agent_user)
    make_comment(ticket, requester_user, "public question")
    make_comment(ticket, agent_user, "internal diagnosis", is_internal=True)

    for headers in (agent_headers, admin_headers):
        response = client.get(comments_url(ticket), headers=headers)

        assert [c["message"] for c in response.json()] == [
            "public question",
            "internal diagnosis",
        ]


def test_ticket_with_no_comments_returns_empty_list(
    client, requester_user, requester_headers, category, make_ticket
):
    ticket = make_ticket(requester_user, category)

    response = client.get(comments_url(ticket), headers=requester_headers)

    assert response.status_code == 200
    assert response.json() == []


def test_stranger_cannot_read_comments(
    client,
    requester_user,
    category,
    make_ticket,
    make_comment,
    make_user,
    department,
    auth_headers,
):
    ticket = make_ticket(requester_user, category)
    make_comment(ticket, requester_user, "private details")
    stranger_headers = auth_headers(make_user(department))

    response = client.get(comments_url(ticket), headers=stranger_headers)

    assert response.status_code == 404
    assert "private details" not in response.text


def test_cannot_read_comments_of_unknown_or_deleted_ticket(
    client, db_session, requester_user, admin_headers, category, make_ticket
):
    deleted = make_ticket(requester_user, category)
    deleted.is_deleted = True
    db_session.commit()

    assert (
        client.get("/tickets/999999/comments", headers=admin_headers).status_code == 404
    )
    assert client.get(comments_url(deleted), headers=admin_headers).status_code == 404


def test_reading_comments_requires_authentication(
    client, requester_user, category, make_ticket
):
    ticket = make_ticket(requester_user, category)

    assert client.get(comments_url(ticket)).status_code == 401
