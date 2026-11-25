"""Step 1 of the module: prove the test setup works end-to-end."""

from sqlalchemy import select, text

from core.config import settings
from models.department import Department


def test_app_responds_and_lists_routes(client):
    # The app has no "/" route, so we use FastAPI's built-in OpenAPI document instead.
    response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/tickets" in paths
    assert "/auth/login" in paths


def test_protected_endpoint_rejects_anonymous_requests(client):
    response = client.get("/tickets")

    assert response.status_code == 401


def test_tests_run_on_the_test_database_not_the_dev_database(db_session):
    current_db = db_session.execute(text("SELECT current_database()")).scalar()

    assert current_db != settings.DB_NAME
    assert "test" in current_db.lower()


# These two tests prove the rollback isolation. The first writes a row, the second checks
# that the row is gone. They pass in any order as long as isolation works.
def test_isolation_part_1_writes_a_row(db_session, make_department):
    make_department("Isolation Check")

    assert db_session.scalar(
        select(Department).where(Department.name == "Isolation Check")
    )


def test_isolation_part_2_row_from_previous_test_is_gone(db_session):
    leftover = db_session.scalar(
        select(Department).where(Department.name == "Isolation Check")
    )

    assert leftover is None
