"""Departments and ticket categories (admin-only configuration endpoints)."""
import pytest

from models.category import Category


# ================================ DEPARTMENTS ================================ #
def test_admin_creates_department_and_name_is_trimmed(client, admin_headers):
    response = client.post("/departments", json={"name": "  Finance  "}, headers=admin_headers)

    assert response.status_code == 201
    assert response.json()["name"] == "Finance"


def test_duplicate_department_name_returns_409(client, admin_headers, make_department):
    make_department("Finance")

    response = client.post("/departments", json={"name": "Finance"}, headers=admin_headers)

    assert response.status_code == 409
    assert response.json()["detail"] == "Department already exists"


@pytest.mark.parametrize("name", ["A", "   ", "x" * 101])
def test_invalid_department_name_returns_422(client, admin_headers, name):
    assert client.post("/departments", json={"name": name}, headers=admin_headers).status_code == 422


def test_department_endpoints_require_admin(client, requester_headers, department):
    assert client.post("/departments", json={"name": "Legal"}).status_code == 401
    assert client.post("/departments", json={"name": "Legal"}, headers=requester_headers).status_code == 403
    assert client.get("/departments", headers=requester_headers).status_code == 403
    assert client.get(f"/departments/{department.id}", headers=requester_headers).status_code == 403
    assert client.patch(f"/departments/{department.id}", json={"name": "Legal"}, headers=requester_headers).status_code == 403


def test_admin_lists_and_reads_departments(client, admin_headers, department, other_department):
    listing = client.get("/departments", headers=admin_headers)
    single = client.get(f"/departments/{department.id}", headers=admin_headers)

    assert listing.status_code == 200
    assert {d["name"] for d in listing.json()} >= {"IT Support", "Facilities"}
    assert single.status_code == 200
    assert single.json()["name"] == "IT Support"


def test_unknown_department_returns_404(client, admin_headers):
    assert client.get("/departments/999999", headers=admin_headers).status_code == 404
    assert client.patch("/departments/999999", json={"name": "Anything"}, headers=admin_headers).status_code == 404


def test_admin_renames_department(client, admin_headers, department):
    response = client.patch(f"/departments/{department.id}", json={"name": "Helpdesk"}, headers=admin_headers)

    assert response.status_code == 200
    assert response.json()["name"] == "Helpdesk"


def test_rename_to_existing_department_name_returns_409(
    client, admin_headers, department, other_department
):
    response = client.patch(
        f"/departments/{department.id}", json={"name": "Facilities"}, headers=admin_headers
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Department name already exists"


def test_department_patch_needs_a_name(client, admin_headers, department):
    empty = client.patch(f"/departments/{department.id}", json={}, headers=admin_headers)
    null = client.patch(f"/departments/{department.id}", json={"name": None}, headers=admin_headers)

    assert empty.status_code == 400
    assert null.status_code == 422


# ================================ CATEGORIES ================================ #
def test_admin_creates_category(client, db_session, admin_headers, department):
    response = client.post(
        "/categories", json={"name": "Network", "department_id": department.id}, headers=admin_headers
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Network"
    assert db_session.get(Category, body["id"]).is_active is True


def test_category_names_are_unique_per_department_not_globally(
    client, admin_headers, department, other_department, category
):
    same_dept = client.post(
        "/categories", json={"name": category.name, "department_id": department.id}, headers=admin_headers
    )
    other_dept = client.post(
        "/categories", json={"name": category.name, "department_id": other_department.id}, headers=admin_headers
    )

    assert same_dept.status_code == 409
    assert same_dept.json()["detail"] == "Category already exists in this department"
    assert other_dept.status_code == 201  # same name is fine in a different department


def test_create_category_in_unknown_department_returns_404(client, admin_headers):
    response = client.post(
        "/categories", json={"name": "Network", "department_id": 999999}, headers=admin_headers
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Department not found"


@pytest.mark.parametrize(
    "payload",
    [
        {"name": "N", "department_id": 1},  # name too short
        {"name": "   ", "department_id": 1},  # blank
        {"name": "Network", "department_id": 0},  # id must be > 0
        {"name": "Network"},  # department missing
        {"name": "Network", "department_id": 1, "is_active": False},  # unknown field
    ],
)
def test_invalid_category_payload_returns_422(client, admin_headers, payload):
    assert client.post("/categories", json=payload, headers=admin_headers).status_code == 422


def test_category_endpoints_require_admin(client, requester_headers, agent_headers, category):
    payload = {"name": "Network", "department_id": category.department_id}

    assert client.post("/categories", json=payload).status_code == 401
    for headers in (requester_headers, agent_headers):
        assert client.post("/categories", json=payload, headers=headers).status_code == 403
        assert client.get("/categories", headers=headers).status_code == 403
        assert client.patch(f"/categories/{category.id}", json={"name": "Renamed"}, headers=headers).status_code == 403
        assert client.delete(f"/categories/{category.id}", headers=headers).status_code == 403


def test_admin_lists_only_active_categories_with_pagination(
    client, admin_headers, department, make_category
):
    active_one = make_category(department, "Active one")
    active_two = make_category(department, "Active two")
    make_category(department, "Retired", is_active=False)

    everything = client.get("/categories", headers=admin_headers).json()
    first_only = client.get("/categories", params={"limit": 1}, headers=admin_headers).json()

    assert {c["name"] for c in everything} == {"Active one", "Active two"}
    assert [c["id"] for c in everything] == [active_one.id, active_two.id]
    assert len(first_only) == 1


def test_admin_renames_category(client, admin_headers, category):
    response = client.patch(f"/categories/{category.id}", json={"name": "Devices"}, headers=admin_headers)

    assert response.status_code == 200
    assert response.json()["name"] == "Devices"


def test_rename_category_to_existing_name_in_same_department_returns_409(
    client, admin_headers, department, category, make_category
):
    make_category(department, "Software")

    response = client.patch(f"/categories/{category.id}", json={"name": "Software"}, headers=admin_headers)

    assert response.status_code == 409


@pytest.mark.parametrize("payload", [{}, {"name": None}, {"name": "x"}, {"other": 1}])
def test_invalid_category_patch_returns_422(client, admin_headers, category, payload):
    assert client.patch(f"/categories/{category.id}", json=payload, headers=admin_headers).status_code == 422


def test_rename_unknown_category_returns_404(client, admin_headers):
    assert client.patch("/categories/999999", json={"name": "Whatever"}, headers=admin_headers).status_code == 404


def test_delete_deactivates_category_instead_of_removing_it(
    client, db_session, admin_headers, category
):
    category_id = category.id

    response = client.delete(f"/categories/{category_id}", headers=admin_headers)

    assert response.status_code == 200
    db_session.expire_all()
    assert db_session.get(Category, category_id).is_active is False  # row is kept
    listing = client.get("/categories", headers=admin_headers).json()
    assert category_id not in [c["id"] for c in listing]


def test_deactivating_twice_returns_409(client, admin_headers, category):
    assert client.delete(f"/categories/{category.id}", headers=admin_headers).status_code == 200

    response = client.delete(f"/categories/{category.id}", headers=admin_headers)

    assert response.status_code == 409
    assert response.json()["detail"] == "Category is already inactive"


def test_deactivate_unknown_category_returns_404(client, admin_headers):
    assert client.delete("/categories/999999", headers=admin_headers).status_code == 404
