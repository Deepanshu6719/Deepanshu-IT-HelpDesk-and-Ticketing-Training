import pytest


@pytest.fixture
def list_endpoints(
    department,
    category,
    requester_user,
    make_ticket,
):
    ticket = make_ticket(requester_user, category)

    return [
        "/api/v1/tickets",
        "/api/v1/categories",
        "/api/v1/users",
        "/api/v1/departments",
        "/api/v1/agents",
        f"/api/v1/departments/{department.id}/agents",
        f"/api/v1/tickets/{ticket.id}/comments",
    ]


def test_all_list_endpoints_follow_pagination_contract(
    client,
    admin_headers,
    list_endpoints,
):
    for endpoint in list_endpoints:
        response = client.get(
            endpoint,
            headers=admin_headers,
        )

        assert response.status_code == 200, endpoint

        body = response.json()

        assert body["success"] is True, endpoint

        data = body["data"]

        assert set(data) == {
            "total",
            "page",
            "limit",
            "items",
        }, endpoint

        assert data["page"] == 1, endpoint
        assert data["limit"] == 10, endpoint
        assert isinstance(data["total"], int), endpoint
        assert isinstance(data["items"], list), endpoint
        assert data["total"] >= len(data["items"]), endpoint
        assert len(data["items"]) <= 10, endpoint


def test_all_list_endpoints_return_empty_out_of_range_pages(
    client,
    admin_headers,
    list_endpoints,
):
    for endpoint in list_endpoints:
        initial = client.get(
            endpoint,
            headers=admin_headers,
        )

        assert initial.status_code == 200, endpoint

        total = initial.json()["data"]["total"]

        response = client.get(
            endpoint,
            params={
                "page": total + 1,
                "limit": 1,
            },
            headers=admin_headers,
        )

        assert response.status_code == 200, endpoint

        assert response.json() == {
            "success": True,
            "data": {
                "total": total,
                "page": total + 1,
                "limit": 1,
                "items": [],
            },
        }, endpoint


@pytest.mark.parametrize(
    "params",
    [
        {"page": 0},
        {"page": -1},
        {"limit": 0},
        {"limit": 101},
        {"page": "invalid"},
        {"limit": "invalid"},
    ],
)
def test_all_list_endpoints_reject_invalid_pagination(
    client,
    admin_headers,
    list_endpoints,
    params,
):
    for endpoint in list_endpoints:
        response = client.get(
            endpoint,
            params=params,
            headers=admin_headers,
        )

        assert response.status_code == 422, endpoint

        body = response.json()

        assert body["success"] is False, endpoint

        assert body["error"]["code"] == "VALIDATION_ERROR", endpoint


@pytest.mark.parametrize("limit", [1, 100])
def test_all_list_endpoints_accept_valid_limit_boundaries(
    client,
    admin_headers,
    list_endpoints,
    limit,
):
    for endpoint in list_endpoints:
        response = client.get(
            endpoint,
            params={"page": 1, "limit": limit},
            headers=admin_headers,
        )

        assert response.status_code == 200, endpoint

        data = response.json()["data"]

        assert data["page"] == 1, endpoint
        assert data["limit"] == limit, endpoint
        assert len(data["items"]) <= limit, endpoint

        assert len(data["items"]) == min(
            data["total"],
            limit,
        ), endpoint
