from unittest.mock import patch

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from core.cache import set_cache
from core.dashboard_cache import (
    DASHBOARD_CACHE_TTL,
    DASHBOARD_GENERATION_KEY,
    get_dashboard_cache_key,
    get_dashboard_generation,
    invalidate_dashboard_cache,
)
from database.redis import redis_client
from models.ticket import Ticket
from services.dashboard import build_dashboard

DASHBOARD_URL = "/api/v1/dashboard/me"


def get_dashboard(client, headers):
    response = client.get(
        DASHBOARD_URL,
        headers=headers,
    )

    assert response.status_code == 200, response.text

    return response.json()["data"]


def test_dashboard_second_request_uses_cache(
    client,
    requester_user,
    requester_headers,
    category,
    make_ticket,
):
    make_ticket(requester_user, category)

    with patch(
        "routes.dashboard.build_dashboard",
        wraps=build_dashboard,
    ) as dashboard_builder:
        first = get_dashboard(
            client,
            requester_headers,
        )

        second = get_dashboard(
            client,
            requester_headers,
        )

        assert dashboard_builder.call_count == 1

    assert first == second
    assert first["total_tickets"] == 1


def test_dashboard_cache_has_expiry(
    client,
    requester_user,
    requester_headers,
):
    get_dashboard(client, requester_headers)

    generation = redis_client.get(DASHBOARD_GENERATION_KEY)

    assert generation is not None

    cache_key = get_dashboard_cache_key(
        requester_user,
        generation,
    )

    ttl = redis_client.ttl(cache_key)

    assert 0 < ttl <= DASHBOARD_CACHE_TTL


def test_dashboard_cache_is_isolated_between_users(
    client,
    requester_user,
    requester_headers,
    agent_user,
    agent_headers,
    admin_headers,
    category,
    make_ticket,
):
    make_ticket(requester_user, category)

    make_ticket(agent_user, category)
    make_ticket(agent_user, category)

    requester_data = get_dashboard(
        client,
        requester_headers,
    )

    agent_data = get_dashboard(
        client,
        agent_headers,
    )

    admin_data = get_dashboard(
        client,
        admin_headers,
    )

    assert requester_data["total_tickets"] == 1
    assert agent_data["total_tickets"] == 2
    assert admin_data["total_tickets"] == 3

    assert get_dashboard(client, requester_headers) == requester_data

    assert get_dashboard(client, agent_headers) == agent_data

    assert get_dashboard(client, admin_headers) == admin_data


def test_dashboard_invalidated_after_ticket_creation(
    client,
    requester_headers,
    category,
):
    initial = get_dashboard(
        client,
        requester_headers,
    )

    assert initial["total_tickets"] == 0

    old_generation = redis_client.get(DASHBOARD_GENERATION_KEY)

    response = client.post(
        "/api/v1/tickets",
        headers=requester_headers,
        json={
            "title": "Printer connectivity issue",
            "description": ("Printer is not connecting to the computer."),
            "category": category.name,
            "priority": "high",
        },
    )

    assert response.status_code == 201, response.text

    new_generation = redis_client.get(DASHBOARD_GENERATION_KEY)

    assert new_generation is not None
    assert new_generation != old_generation

    updated = get_dashboard(
        client,
        requester_headers,
    )

    assert updated["total_tickets"] == 1
    assert updated["by_status"]["open"] == 1
    assert updated["by_priority"]["high"] == 1


def test_dashboard_invalidated_after_status_update(
    client,
    admin_headers,
    requester_user,
    requester_headers,
    category,
    make_ticket,
):
    ticket = make_ticket(
        requester_user,
        category,
    )

    initial = get_dashboard(
        client,
        requester_headers,
    )

    assert initial["by_status"]["open"] == 1

    response = client.patch(
        f"/api/v1/tickets/{ticket.id}",
        headers=admin_headers,
        json={
            "status": "under_review",
        },
    )

    assert response.status_code == 200, response.text

    updated = get_dashboard(
        client,
        requester_headers,
    )

    assert updated["total_tickets"] == 1
    assert updated["by_status"]["open"] == 0
    assert updated["by_status"]["under_review"] == 1


def test_dashboard_invalidated_after_ticket_deletion(
    client,
    requester_user,
    requester_headers,
    category,
    make_ticket,
):
    ticket = make_ticket(
        requester_user,
        category,
    )

    initial = get_dashboard(
        client,
        requester_headers,
    )

    assert initial["total_tickets"] == 1

    response = client.delete(
        f"/api/v1/tickets/{ticket.id}",
        headers=requester_headers,
    )

    assert response.status_code == 204

    updated = get_dashboard(
        client,
        requester_headers,
    )

    assert updated["total_tickets"] == 0
    assert updated["by_status"]["open"] == 0


def test_dashboard_cache_isolated_between_requesters(
    client,
    requester_user,
    requester_headers,
    department,
    category,
    make_user,
    make_ticket,
    auth_headers,
):
    other_requester = make_user(department)
    other_headers = auth_headers(other_requester)

    make_ticket(requester_user, category)

    for _ in range(3):
        make_ticket(other_requester, category)

    with patch(
        "routes.dashboard.build_dashboard",
        wraps=build_dashboard,
    ) as builder:
        first = get_dashboard(client, requester_headers)

        second = get_dashboard(client, other_headers)

        assert first["total_tickets"] == 1
        assert second["total_tickets"] == 3

        assert get_dashboard(client, requester_headers) == first

        assert get_dashboard(client, other_headers) == second

        assert builder.call_count == 2


def test_dashboard_invalidated_after_agent_assignment(
    client,
    admin_headers,
    agent_user,
    agent_headers,
    requester_user,
    requester_headers,
    category,
    make_ticket,
):
    ticket = make_ticket(
        requester_user,
        category,
    )

    agent_before = get_dashboard(client, agent_headers)

    requester_before = get_dashboard(client, requester_headers)

    assert agent_before["total_tickets"] == 0
    assert requester_before["unassigned_tickets"] == 1

    response = client.patch(
        f"/api/v1/tickets/{ticket.id}",
        headers=admin_headers,
        json={"assigned_to": agent_user.id},
    )

    assert response.status_code == 200, response.text

    agent_after = get_dashboard(client, agent_headers)

    requester_after = get_dashboard(client, requester_headers)

    assert agent_after["total_tickets"] == 1
    assert agent_after["assigned_tickets"] == 1

    assert requester_after["total_tickets"] == 1
    assert requester_after["assigned_tickets"] == 1
    assert requester_after["unassigned_tickets"] == 0


def test_dashboard_invalidated_after_agent_reassignment(
    client,
    admin_headers,
    agent_user,
    agent_headers,
    requester_user,
    department,
    category,
    make_user,
    make_ticket,
    auth_headers,
):
    second_agent = make_user(
        department,
        role="agent",
    )

    second_agent_headers = auth_headers(second_agent)

    ticket = make_ticket(
        requester_user,
        category,
        assigned_to=agent_user,
    )

    assert get_dashboard(client, agent_headers)["total_tickets"] == 1

    assert get_dashboard(client, second_agent_headers)["total_tickets"] == 0

    response = client.patch(
        f"/api/v1/tickets/{ticket.id}",
        headers=admin_headers,
        json={"assigned_to": second_agent.id},
    )

    assert response.status_code == 200, response.text

    assert get_dashboard(client, agent_headers)["total_tickets"] == 0

    assert get_dashboard(client, second_agent_headers)["total_tickets"] == 1


def test_dashboard_invalidated_after_agent_unassignment(
    client,
    admin_headers,
    agent_user,
    agent_headers,
    requester_user,
    requester_headers,
    category,
    make_ticket,
):
    ticket = make_ticket(
        requester_user,
        category,
        assigned_to=agent_user,
    )

    assert get_dashboard(client, agent_headers)["total_tickets"] == 1

    assert get_dashboard(client, requester_headers)["assigned_tickets"] == 1

    response = client.patch(
        f"/api/v1/tickets/{ticket.id}",
        headers=admin_headers,
        json={"assigned_to": None},
    )

    assert response.status_code == 200, response.text

    assert get_dashboard(client, agent_headers)["total_tickets"] == 0

    requester_data = get_dashboard(client, requester_headers)

    assert requester_data["total_tickets"] == 1
    assert requester_data["assigned_tickets"] == 0
    assert requester_data["unassigned_tickets"] == 1


def test_dashboard_invalidated_after_priority_update(
    client,
    admin_headers,
    requester_user,
    requester_headers,
    category,
    make_ticket,
):
    ticket = make_ticket(
        requester_user,
        category,
        priority="medium",
    )

    before = get_dashboard(client, requester_headers)

    assert before["by_priority"]["medium"] == 1
    assert before["by_priority"]["urgent"] == 0

    response = client.patch(
        f"/api/v1/tickets/{ticket.id}",
        headers=admin_headers,
        json={"priority": "urgent"},
    )

    assert response.status_code == 200, response.text

    after = get_dashboard(client, requester_headers)

    assert after["total_tickets"] == 1
    assert after["by_priority"]["medium"] == 0
    assert after["by_priority"]["urgent"] == 1


def test_failed_ticket_update_preserves_dashboard_cache(
    client,
    requester_user,
    requester_headers,
    category,
    make_ticket,
):
    ticket = make_ticket(
        requester_user,
        category,
    )

    with patch(
        "routes.dashboard.build_dashboard",
        wraps=build_dashboard,
    ) as builder:
        before = get_dashboard(client, requester_headers)

        generation_before = redis_client.get(DASHBOARD_GENERATION_KEY)

        assert generation_before is not None

        response = client.patch(
            f"/api/v1/tickets/{ticket.id}",
            headers=requester_headers,
            json={"priority": "urgent"},
        )

        assert response.status_code == 403, response.text

        generation_after = redis_client.get(DASHBOARD_GENERATION_KEY)

        assert generation_before == generation_after

        after = get_dashboard(client, requester_headers)

        assert before == after
        assert builder.call_count == 1


def test_dashboard_falls_back_to_database_when_redis_fails(
    client,
    requester_user,
    requester_headers,
    category,
    make_ticket,
):
    make_ticket(requester_user, category)

    with (
        patch(
            "core.dashboard_cache.redis_client.get",
            side_effect=RedisConnectionError("Simulated Redis failure"),
        ),
        patch(
            "routes.dashboard.build_dashboard",
            wraps=build_dashboard,
        ) as builder,
    ):
        data = get_dashboard(client, requester_headers)

        assert data["total_tickets"] == 1
        assert builder.call_count == 1


def test_dashboard_survives_cache_write_failure(
    client,
    requester_user,
    requester_headers,
    category,
    make_ticket,
):
    make_ticket(requester_user, category)

    with patch(
        "core.cache.redis_client.setex",
        side_effect=RedisConnectionError("Simulated cache write failure"),
    ):
        data = get_dashboard(client, requester_headers)

    assert data["total_tickets"] == 1


@pytest.mark.parametrize(
    "invalid_payload",
    [
        "invalid-json",
        '{"unexpected_field": true}',
    ],
)
def test_dashboard_recovers_from_invalid_cache(
    client,
    requester_user,
    requester_headers,
    category,
    make_ticket,
    invalid_payload,
):
    make_ticket(requester_user, category)

    expected = get_dashboard(client, requester_headers)

    generation = redis_client.get(DASHBOARD_GENERATION_KEY)

    assert generation is not None

    cache_key = get_dashboard_cache_key(
        requester_user,
        generation,
    )

    redis_client.setex(
        cache_key,
        DASHBOARD_CACHE_TTL,
        invalid_payload,
    )

    with patch(
        "routes.dashboard.build_dashboard",
        wraps=build_dashboard,
    ) as builder:
        actual = get_dashboard(client, requester_headers)

        assert actual == expected
        assert builder.call_count == 1

        assert get_dashboard(client, requester_headers) == expected

        assert builder.call_count == 1


def test_old_cache_generation_cannot_override_new_dashboard(
    client,
    requester_user,
    requester_headers,
    category,
    make_ticket,
):
    old_data = get_dashboard(client, requester_headers)

    assert old_data["total_tickets"] == 0

    old_generation = get_dashboard_generation()

    assert old_generation is not None

    old_key = get_dashboard_cache_key(
        requester_user,
        old_generation,
    )

    make_ticket(requester_user, category)

    invalidate_dashboard_cache()

    new_generation = get_dashboard_generation()

    assert new_generation is not None
    assert new_generation != old_generation

    # Simulate an older request finishing after
    # another request invalidated the cache.
    set_cache(
        old_key,
        old_data,
        ttl=DASHBOARD_CACHE_TTL,
    )

    with patch(
        "routes.dashboard.build_dashboard",
        wraps=build_dashboard,
    ) as builder:
        fresh = get_dashboard(client, requester_headers)

        assert fresh["total_tickets"] == 1
        assert builder.call_count == 1


def test_dashboard_updates_after_role_promotion(
    client,
    admin_headers,
    requester_user,
    requester_headers,
    department,
    category,
    make_user,
    make_ticket,
):
    other_user = make_user(department)

    make_ticket(requester_user, category)

    make_ticket(other_user, category)
    make_ticket(other_user, category)

    before = get_dashboard(client, requester_headers)

    assert before["total_tickets"] == 1

    old_generation = redis_client.get(DASHBOARD_GENERATION_KEY)

    assert old_generation is not None

    # Promote requester to agent.
    response = client.post(
        f"/api/v1/admin/users/{requester_user.id}/roles",
        headers=admin_headers,
        json={"role": "agent"},
    )

    assert response.status_code == 201, response.text

    agent_generation = redis_client.get(DASHBOARD_GENERATION_KEY)

    assert agent_generation != old_generation

    agent_data = get_dashboard(client, requester_headers)

    assert agent_data["total_tickets"] == 1

    # Promote agent to administrator.
    response = client.post(
        f"/api/v1/admin/users/{requester_user.id}/roles",
        headers=admin_headers,
        json={"role": "admin"},
    )

    assert response.status_code == 201, response.text

    admin_generation = redis_client.get(DASHBOARD_GENERATION_KEY)

    assert admin_generation != agent_generation

    admin_data = get_dashboard(client, requester_headers)

    assert admin_data["total_tickets"] == 3


def test_inactive_user_cannot_access_cached_dashboard(
    client,
    admin_headers,
    requester_user,
    requester_headers,
    category,
    make_ticket,
):
    make_ticket(requester_user, category)

    before = get_dashboard(client, requester_headers)

    assert before["total_tickets"] == 1

    old_generation = redis_client.get(DASHBOARD_GENERATION_KEY)

    assert old_generation is not None

    response = client.patch(
        f"/api/v1/users/{requester_user.id}/status",
        headers=admin_headers,
        json={"is_active": False},
    )

    assert response.status_code == 200, response.text

    new_generation = redis_client.get(DASHBOARD_GENERATION_KEY)

    assert new_generation != old_generation

    with patch("routes.dashboard.get_dashboard_generation") as generation_reader:
        response = client.get(
            DASHBOARD_URL,
            headers=requester_headers,
        )

        assert response.status_code == 401
        generation_reader.assert_not_called()


def test_ticket_update_survives_dashboard_invalidation_failure(
    client,
    db_session,
    admin_headers,
    requester_user,
    requester_headers,
    category,
    make_ticket,
):
    ticket = make_ticket(requester_user, category)

    ticket_id = ticket.id

    before = get_dashboard(client, requester_headers)

    assert before["by_status"]["open"] == 1

    with patch(
        "core.dashboard_cache.redis_client.set",
        side_effect=RedisConnectionError("Simulated invalidation failure"),
    ):
        response = client.patch(
            f"/api/v1/tickets/{ticket_id}",
            headers=admin_headers,
            json={"status": "under_review"},
        )

    assert response.status_code == 200, response.text

    db_session.expire_all()

    stored_ticket = db_session.get(Ticket, ticket_id)

    assert stored_ticket.status == "under_review"

    # Explicitly restore cache consistency.
    invalidate_dashboard_cache()

    after = get_dashboard(client, requester_headers)

    assert after["by_status"]["open"] == 0
    assert after["by_status"]["under_review"] == 1


def test_lost_generation_key_does_not_reuse_old_cache(
    client,
    requester_user,
    requester_headers,
    category,
    make_ticket,
):
    before = get_dashboard(client, requester_headers)

    assert before["total_tickets"] == 0

    old_generation = get_dashboard_generation()

    assert old_generation is not None

    old_key = get_dashboard_cache_key(
        requester_user,
        old_generation,
    )

    assert redis_client.exists(old_key) == 1

    # Simulate loss of the generation key while
    # the previous dashboard cache still exists.
    redis_client.delete(DASHBOARD_GENERATION_KEY)

    make_ticket(requester_user, category)

    after = get_dashboard(client, requester_headers)

    new_generation = get_dashboard_generation()

    assert new_generation is not None
    assert new_generation != old_generation

    assert after["total_tickets"] == 1

    assert redis_client.exists(old_key) == 1
