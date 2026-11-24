"""
Shared test setup for the whole suite (pytest loads this file automatically).

HOW ISOLATION WORKS
-------------------
1. All tests run against a SEPARATE Postgres database (default name: helpdesk_test,
   override with the TEST_DB_NAME env var). Your dev database is never touched.
2. The tables are created once per test run (Base.metadata.create_all) and dropped at the end.
3. Every test runs inside ONE outer transaction that is ROLLED BACK when the test ends.
   Your routes call db.commit() - that only releases a SAVEPOINT here
   (join_transaction_mode="create_savepoint"), so nothing is ever really saved.
   Result: each test starts with an empty database and tests cannot affect each other.
4. The app's `get_db` dependency is overridden to hand the routes that same test session.

TWO RULES TO REMEMBER WHEN WRITING TESTS
----------------------------------------
* After you change an object inside a test (e.g. `user.is_active = False`),
  call `db_session.commit()` so the change is visible to the endpoint you call next.
* Never hard-code row ids (sequences are not rolled back). Use `thing.id`.
"""

import itertools
import uuid
from datetime import datetime, timedelta, timezone
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import URL, create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

import models  # noqa: F401  (importing the package registers every model on Base.metadata)
from core.config import settings
from core.security import create_access_token, get_password_hash
from database.dependencies import get_db
from main import app
from models.base import Base
from models.category import Category
from models.department import Department
from models.role import Role
from models.ticket import Ticket
from models.ticket_comment import TicketComment
from models.user import User
from models.user_role import UserRole
from models.user_session import UserSession

TEST_DB_NAME = os.getenv("TEST_DB_NAME", "test")
DEFAULT_PASSWORD = "StrongPass123!"

_counter = itertools.count(1)  # used to generate unique emails / names


# --------------------------------------------------------------------------- #
# Database + app wiring
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="session")
def engine():
    """Engine for the TEST database. Creates the tables once, drops them at the end."""
    # Safety net: never let create_all/drop_all run against the dev database.
    if TEST_DB_NAME == settings.DB_NAME or "test" not in TEST_DB_NAME.lower():
        pytest.exit(
            f"Refusing to run: TEST_DB_NAME='{TEST_DB_NAME}' must differ from the dev "
            f"database ('{settings.DB_NAME}') and contain the word 'test'.",
            returncode=2,
        )

    url = URL.create(
        drivername="postgresql+psycopg",
        username=settings.DB_USER,
        password=settings.DB_PASSWORD,
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        database=TEST_DB_NAME,
    )
    test_engine = create_engine(url)

    try:
        with test_engine.connect():
            pass
    except OperationalError:
        pytest.exit(
            f"Cannot connect to test database '{TEST_DB_NAME}'. Create it first, e.g.:\n"
            f'  sudo -u postgres psql -c "CREATE DATABASE {TEST_DB_NAME} OWNER {settings.DB_USER};"',
            returncode=2,
        )

    Base.metadata.drop_all(test_engine)  # start from a clean slate
    Base.metadata.create_all(test_engine)
    yield test_engine
    Base.metadata.drop_all(test_engine)
    test_engine.dispose()


@pytest.fixture()
def db_session(engine):
    """A session wrapped in a transaction that is rolled back after every test."""
    connection = engine.connect()
    outer_transaction = connection.begin()
    session = Session(
        bind=connection,
        autoflush=False,  # same as the app's SessionLocal
        join_transaction_mode="create_savepoint",  # commit() only releases a savepoint
    )
    try:
        yield session
    finally:
        session.close()
        outer_transaction.rollback()
        connection.close()


@pytest.fixture()
def client(db_session):
    """FastAPI TestClient whose routes use the isolated test session."""

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


class NotificationRecorder:
    """Records Celery notification task calls during tests."""

    def __init__(self):
        self.calls = []

    def delay(self, recipient_email, subject, message):
        self.calls.append(
            {
                "to": recipient_email,
                "subject": subject,
                "message": message,
            }
        )

    @property
    def recipients(self):
        return {call["to"] for call in self.calls}


@pytest.fixture(autouse=True)
def notifications(monkeypatch):
    """Replaces the Celery notification task in routes/tickets.py for every test."""
    recorder = NotificationRecorder()
    monkeypatch.setattr("routes.tickets.send_notification", recorder)
    return recorder

@pytest.fixture(autouse=True)
def disable_rate_limit_for_tests(monkeypatch):
    """Disable login rate limiting during ordinary tests."""
    monkeypatch.setattr("routes.auth.check_rate_limit", lambda **kwargs: None)

# --------------------------------------------------------------------------- #
# Data factories (call them inside tests to build exactly the data you need)
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="session")
def default_password():
    return DEFAULT_PASSWORD


@pytest.fixture(scope="session")
def hashed_default_password():
    # Argon2 is intentionally slow, so hash the shared test password only once.
    return get_password_hash(DEFAULT_PASSWORD)


@pytest.fixture()
def roles(db_session):
    """The two roles your app expects to exist: 'admin' and 'agent'."""
    admin_role = Role(name="admin")
    agent_role = Role(name="agent")
    db_session.add_all([admin_role, agent_role])
    db_session.commit()
    return {"admin": admin_role, "agent": agent_role}


@pytest.fixture()
def make_department(db_session):
    def _make(name=None):
        department = Department(name=name or f"Department {next(_counter)}")
        db_session.add(department)
        db_session.commit()
        return department

    return _make


@pytest.fixture()
def make_category(db_session):
    def _make(department, name=None, is_active=True):
        category = Category(
            name=name or f"Category {next(_counter)}",
            department_id=department.id,
            is_active=is_active,
        )
        db_session.add(category)
        db_session.commit()
        return category

    return _make


@pytest.fixture()
def make_user(db_session, roles, hashed_default_password):
    """make_user(department, role="agent" | "admin" | ["agent", "admin"] | None, ...)"""

    def _make(department, role=None, email=None, password=None, is_active=True):
        role_names = [role] if isinstance(role, str) else list(role or [])
        user = User(
            email=email or f"user{next(_counter)}@example.com",
            hashed_password=(
                get_password_hash(password) if password else hashed_default_password
            ),
            department_id=department.id,
            is_active=is_active,
        )
        db_session.add(user)
        db_session.flush()
        for role_name in role_names:
            db_session.add(UserRole(user_id=user.id, role_id=roles[role_name].id))
        db_session.commit()
        return user

    return _make


@pytest.fixture()
def make_ticket(db_session):
    """Creates a ticket directly in the DB (bypasses the API and its validation)."""

    def _make(
        requester,
        category,
        title="Printer is not working",
        description="The office printer jams on every page.",
        priority="medium",
        status="open",
        assigned_to=None,
    ):
        ticket = Ticket(
            title=title,
            description=description,
            category_id=category.id,
            department_id=category.department_id,
            requester_id=requester.id,
            assigned_to=assigned_to.id if assigned_to else None,
            requested_priority=priority,
            priority=priority,
            status=status,
        )
        db_session.add(ticket)
        db_session.commit()
        return ticket

    return _make


@pytest.fixture()
def make_comment(db_session):
    def _make(ticket, author, message="A comment", is_internal=False):
        comment = TicketComment(
            ticket_id=ticket.id,
            user_id=author.id,
            message=message,
            is_internal=is_internal,
        )
        db_session.add(comment)
        db_session.commit()
        return comment

    return _make


# --------------------------------------------------------------------------- #
# Authentication helpers ("mocking auth")
# --------------------------------------------------------------------------- #
@pytest.fixture()
def auth_headers(db_session):
    """auth_headers(user) -> {"Authorization": "Bearer <valid token>"}

    Creates a real UserSession row and signs a real JWT, exactly like /auth/login does,
    but without calling the login endpoint (so other tests don't depend on it).
    """

    def _headers(user):
        new_session = UserSession(
            user_id=user.id,
            expires_at=datetime.now(timezone.utc) + timedelta(days=1),
        )
        db_session.add(new_session)
        db_session.flush()
        session_id = new_session.id
        token = create_access_token(
            {"sub": str(user.id), "ver": user.token_version, "sid": session_id}
        )
        db_session.commit()
        return {"Authorization": f"Bearer {token}"}

    return _headers


# --------------------------------------------------------------------------- #
# Ready-made scenario: one department with an admin, an agent and a requester
# --------------------------------------------------------------------------- #
@pytest.fixture()
def department(make_department):
    return make_department("IT Support")


@pytest.fixture()
def other_department(make_department):
    return make_department("Facilities")


@pytest.fixture()
def category(make_category, department):
    return make_category(department, "Hardware")


@pytest.fixture()
def admin_user(make_user, department):
    return make_user(department, role="admin", email="admin@example.com")


@pytest.fixture()
def agent_user(make_user, department):
    return make_user(department, role="agent", email="agent@example.com")


@pytest.fixture()
def requester_user(make_user, department):
    return make_user(department, email="requester@example.com")


@pytest.fixture()
def admin_headers(auth_headers, admin_user):
    return auth_headers(admin_user)


@pytest.fixture()
def agent_headers(auth_headers, agent_user):
    return auth_headers(agent_user)


@pytest.fixture()
def requester_headers(auth_headers, requester_user):
    return auth_headers(requester_user)
