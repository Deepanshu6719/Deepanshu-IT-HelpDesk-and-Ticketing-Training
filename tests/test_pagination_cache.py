import json

from database.redis import redis_client


def test_category_cache_stores_paginated_data(
    client,
    admin_headers,
    category,
):
    cache_key = "helpdesk:categories:v2:1:10"

    assert redis_client.get(cache_key) is None

    first = client.get(
        "/api/v1/categories",
        headers=admin_headers,
    )

    assert first.status_code == 200

    cached = redis_client.get(cache_key)

    assert cached is not None

    cached_data = json.loads(cached)

    assert cached_data == first.json()["data"]

    assert cached_data["page"] == 1
    assert cached_data["limit"] == 10
    assert cached_data["total"] >= 1

    assert 0 < redis_client.ttl(cache_key) <= 300

    second = client.get(
        "/api/v1/categories",
        headers=admin_headers,
    )

    assert second.status_code == 200
    assert second.json() == first.json()


def test_category_update_invalidates_paginated_cache(
    client,
    admin_headers,
    category,
):
    cache_key = "helpdesk:categories:v2:1:10"

    response = client.get(
        "/api/v1/categories",
        headers=admin_headers,
    )

    assert response.status_code == 200
    assert redis_client.exists(cache_key) == 1

    updated = client.patch(
        f"/api/v1/categories/{category.id}",
        json={"name": "Updated Hardware"},
        headers=admin_headers,
    )

    assert updated.status_code == 200
    assert redis_client.exists(cache_key) == 0

    refreshed = client.get(
        "/api/v1/categories",
        headers=admin_headers,
    )

    assert refreshed.status_code == 200

    items = refreshed.json()["data"]["items"]

    assert any(
        item["id"] == category.id and item["name"] == "Updated Hardware"
        for item in items
    )

    assert redis_client.exists(cache_key) == 1
