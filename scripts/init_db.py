import argparse
from getpass import getpass

import structlog
from email_validator import EmailNotValidError, validate_email
from sqlalchemy import select, text
from sqlalchemy.orm import Session

import models  # noqa: F401 - Register SQLAlchemy models
from core.config import settings
from core.logging import configure_logging
from core.security import get_password_hash
from database.connection import SessionLocal
from models.department import Department
from models.role import Role
from models.user import User
from models.user_role import UserRole

logger = structlog.get_logger(__name__)
BOOTSTRAP_LOCK_ID = 71616005


def initialize_roles(db: Session) -> None:
    for role_name in ("admin", "agent"):
        role = db.scalar(select(Role).where(Role.name == role_name))

        if role is None:
            db.add(Role(name=role_name))
            logger.info("role_created", role=role_name)
        else:
            logger.debug("role_already_exists", role=role_name)


def initialize_department(db: Session) -> Department:
    department = db.scalar(select(Department).where(Department.name == "IT"))

    if department is None:
        department = Department(name="IT")
        db.add(department)
        db.flush()

        logger.info("department_created", department="IT")
    else:
        logger.debug("department_already_exists", department="IT")

    return department


def has_active_administrator(db: Session) -> bool:
    statement = (
        select(User.id)
        .join(UserRole, UserRole.user_id == User.id)
        .join(Role, Role.id == UserRole.role_id)
        .where(
            Role.name == "admin",
            User.is_active.is_(True),
        )
        .limit(1)
    )

    return db.scalar(statement) is not None


def initialize_admin(
    db: Session,
    department: Department,
    *,
    non_interactive: bool = False,
) -> User:
    if non_interactive:
        email = settings.BOOTSTRAP_ADMIN_EMAIL
        password = settings.BOOTSTRAP_ADMIN_PASSWORD

        if not email or not password:
            raise ValueError("Initial administrator credentials are required.")

    else:
        email = input("Enter admin email: ").strip()

        password = getpass("Enter admin password: ")
        confirm_password = getpass("Confirm admin password: ")

        if password != confirm_password:
            raise ValueError("Passwords do not match.")

    try:
        email = validate_email(
            email.strip(),
            check_deliverability=False,
        ).normalized.lower()

    except EmailNotValidError as exc:
        raise ValueError("Invalid administrator email.") from exc

    existing_user = db.scalar(select(User).where(User.email == email))

    if existing_user is not None:
        raise ValueError("Administrator email already belongs to an existing user.")

    if len(password) < 12:
        raise ValueError("Password must contain at least 12 characters.")

    if len(password) > 128:
        raise ValueError("Password must not exceed 128 characters.")

    admin = User(
        email=email,
        hashed_password=get_password_hash(password),
        department_id=department.id,
        is_active=True,
    )

    db.add(admin)
    db.flush()

    return admin


def assign_admin_roles(db: Session, admin: User) -> None:
    for role_name in ("agent", "admin"):
        role = db.scalar(select(Role).where(Role.name == role_name))

        if role is None:
            raise RuntimeError(f"Required role missing: {role_name}")

        db.add(
            UserRole(
                user_id=admin.id,
                role_id=role.id,
            )
        )

        logger.info("role_assigned", role=role_name)


def initialize_database(
    *,
    non_interactive: bool = False,
) -> None:
    with SessionLocal() as db:
        try:
            db.execute(
                text("SELECT pg_advisory_xact_lock(:lock_id)"),
                {"lock_id": BOOTSTRAP_LOCK_ID},
            )

            initialize_roles(db)
            db.flush()

            if has_active_administrator(db):
                db.commit()

                logger.info(
                    "database_initialization_skipped",
                    reason="active_administrator_exists",
                )

                return

            department = initialize_department(db)

            admin = initialize_admin(
                db,
                department,
                non_interactive=non_interactive,
            )

            assign_admin_roles(db, admin)

            db.commit()

            logger.info(
                "database_initialization_completed",
            )

        except Exception:
            db.rollback()

            logger.error(
                "database_initialization_failed",
            )

            raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Initialize Helpdesk database records."
    )

    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Read initial administrator credentials from configuration.",
    )

    args = parser.parse_args()

    configure_logging()

    initialize_database(
        non_interactive=args.non_interactive,
    )
