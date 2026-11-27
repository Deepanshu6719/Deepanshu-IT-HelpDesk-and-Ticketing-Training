import pytest
from sqlalchemy import func, select

from core.security import verify_password
from models.department import Department
from models.role import Role
from models.user import User
from models.user_role import UserRole
from scripts import init_db

ADMIN_EMAIL = "bootstrap-admin@example.com"
ADMIN_PASSWORD = "Bootstrap-Test-Password-2026"


@pytest.fixture
def bootstrap_environment(db_session, monkeypatch):
    monkeypatch.setattr(
        init_db,
        "SessionLocal",
        lambda: db_session,
    )

    monkeypatch.setattr(
        init_db.settings,
        "BOOTSTRAP_ADMIN_EMAIL",
        ADMIN_EMAIL,
    )

    monkeypatch.setattr(
        init_db.settings,
        "BOOTSTRAP_ADMIN_PASSWORD",
        ADMIN_PASSWORD,
    )

    return db_session


def test_bootstrap_creates_initial_administrator(
    bootstrap_environment,
):
    db = bootstrap_environment

    init_db.initialize_database(
        non_interactive=True,
    )

    admin = db.scalar(select(User).where(User.email == ADMIN_EMAIL))

    assert admin is not None
    assert admin.is_active is True

    assert admin.hashed_password != ADMIN_PASSWORD

    assert verify_password(
        ADMIN_PASSWORD,
        admin.hashed_password,
    )

    department = db.get(
        Department,
        admin.department_id,
    )

    assert department.name == "IT"

    roles = set(
        db.scalars(
            select(Role.name)
            .join(
                UserRole,
                UserRole.role_id == Role.id,
            )
            .where(UserRole.user_id == admin.id)
        ).all()
    )

    assert roles == {"admin", "agent"}


def test_repeated_bootstrap_does_not_duplicate_records(
    bootstrap_environment,
):
    db = bootstrap_environment

    init_db.initialize_database(
        non_interactive=True,
    )

    original_admin = db.scalar(select(User).where(User.email == ADMIN_EMAIL))

    original_id = original_admin.id
    original_hash = original_admin.hashed_password

    init_db.initialize_database(
        non_interactive=True,
    )

    db.expire_all()

    admin = db.scalar(select(User).where(User.email == ADMIN_EMAIL))

    assert admin.id == original_id
    assert admin.hashed_password == original_hash

    assert (
        db.scalar(
            select(func.count()).select_from(User).where(User.email == ADMIN_EMAIL)
        )
        == 1
    )

    assert (
        db.scalar(
            select(func.count()).select_from(Department).where(Department.name == "IT")
        )
        == 1
    )

    assert (
        db.scalar(
            select(func.count())
            .select_from(UserRole)
            .where(UserRole.user_id == original_id)
        )
        == 2
    )


@pytest.mark.parametrize(
    "missing_setting",
    [
        "BOOTSTRAP_ADMIN_EMAIL",
        "BOOTSTRAP_ADMIN_PASSWORD",
    ],
)
def test_bootstrap_rejects_missing_credentials(
    bootstrap_environment,
    monkeypatch,
    missing_setting,
):
    db = bootstrap_environment

    monkeypatch.setattr(
        init_db.settings,
        missing_setting,
        None,
    )

    with pytest.raises(
        ValueError,
        match="credentials are required",
    ):
        init_db.initialize_database(
            non_interactive=True,
        )

    assert db.scalar(select(func.count()).select_from(User)) == 0


def test_bootstrap_rejects_invalid_email(
    bootstrap_environment,
    monkeypatch,
):
    db = bootstrap_environment

    monkeypatch.setattr(
        init_db.settings,
        "BOOTSTRAP_ADMIN_EMAIL",
        "invalid-email",
    )

    with pytest.raises(
        ValueError,
        match="Invalid administrator email",
    ):
        init_db.initialize_database(
            non_interactive=True,
        )

    assert db.scalar(select(func.count()).select_from(User)) == 0


@pytest.mark.parametrize(
    "password",
    [
        "short",
        "a" * 129,
    ],
)
def test_bootstrap_rejects_invalid_password_length(
    bootstrap_environment,
    monkeypatch,
    password,
):
    db = bootstrap_environment

    monkeypatch.setattr(
        init_db.settings,
        "BOOTSTRAP_ADMIN_PASSWORD",
        password,
    )

    with pytest.raises(ValueError):
        init_db.initialize_database(
            non_interactive=True,
        )

    assert db.scalar(select(func.count()).select_from(User)) == 0


def test_bootstrap_preserves_existing_administrator(
    bootstrap_environment,
    admin_user,
    monkeypatch,
):
    db = bootstrap_environment

    original_hash = admin_user.hashed_password
    original_id = admin_user.id

    monkeypatch.setattr(
        init_db.settings,
        "BOOTSTRAP_ADMIN_EMAIL",
        None,
    )

    monkeypatch.setattr(
        init_db.settings,
        "BOOTSTRAP_ADMIN_PASSWORD",
        None,
    )

    init_db.initialize_database(
        non_interactive=True,
    )

    db.expire_all()

    existing_admin = db.get(
        User,
        original_id,
    )

    assert existing_admin.hashed_password == original_hash
    assert existing_admin.is_active is True

    assert db.scalar(select(User).where(User.email == ADMIN_EMAIL)) is None


def test_bootstrap_does_not_promote_existing_requester(
    bootstrap_environment,
    requester_user,
    monkeypatch,
):
    db = bootstrap_environment

    requester_id = requester_user.id
    original_hash = requester_user.hashed_password

    monkeypatch.setattr(
        init_db.settings,
        "BOOTSTRAP_ADMIN_EMAIL",
        requester_user.email,
    )

    with pytest.raises(
        ValueError,
        match="already belongs to an existing user",
    ):
        init_db.initialize_database(
            non_interactive=True,
        )

    db.expire_all()

    requester = db.get(User, requester_id)

    assert requester.hashed_password == original_hash

    assert (
        db.scalar(
            select(func.count())
            .select_from(UserRole)
            .where(UserRole.user_id == requester_id)
        )
        == 0
    )


def test_bootstrap_rolls_back_when_role_assignment_fails(
    bootstrap_environment,
    monkeypatch,
):
    db = bootstrap_environment

    department_count = db.scalar(select(func.count()).select_from(Department))

    role_count = db.scalar(select(func.count()).select_from(Role))

    def fail_role_assignment(*args, **kwargs):
        raise RuntimeError("Simulated role assignment failure")

    monkeypatch.setattr(
        init_db,
        "assign_admin_roles",
        fail_role_assignment,
    )

    with pytest.raises(
        RuntimeError,
        match="Simulated role assignment failure",
    ):
        init_db.initialize_database(
            non_interactive=True,
        )

    assert db.scalar(select(User).where(User.email == ADMIN_EMAIL)) is None

    assert db.scalar(select(func.count()).select_from(Department)) == department_count

    assert db.scalar(select(func.count()).select_from(Role)) == role_count
