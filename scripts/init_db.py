from getpass import getpass

from email_validator import EmailNotValidError, validate_email
from sqlalchemy import select
from sqlalchemy.orm import Session

import models  # noqa: F401 - Register SQLAlchemy models
from core.security import get_password_hash
from database.connection import SessionLocal
from models.department import Department
from models.role import Role
from models.user import User
from models.user_role import UserRole


def initialize_roles(db: Session) -> None:
    for role_name in ("admin", "agent"):
        role = db.scalar(select(Role).where(Role.name == role_name))

        if role is None:
            db.add(Role(name=role_name))
            print(f"Created role: {role_name}")
        else:
            print(f"Role already exists: {role_name}")


def initialize_department(db: Session) -> Department:
    department = db.scalar(select(Department).where(Department.name == "IT"))

    if department is None:
        department = Department(name="IT")
        db.add(department)
        db.flush()

        print("Created department: IT")
    else:
        print("Department already exists: IT")

    return department


def initialize_admin(
    db: Session,
    department: Department,
) -> User | None:

    email = input("Enter admin email: ").strip()

    try:
        email = validate_email(
            email,
            check_deliverability=False,
        ).normalized.lower()

    except EmailNotValidError as exc:
        raise ValueError(f"Invalid email address: {exc}") from exc

    existing_user = db.scalar(select(User).where(User.email == email))

    if existing_user is not None:
        print("User already exists. Skipping admin creation.")
        return None

    password = getpass("Enter admin password: ")
    confirm_password = getpass("Confirm admin password: ")

    if password != confirm_password:
        raise ValueError("Passwords do not match.")

    if len(password) < 12:
        raise ValueError("Password must contain at least 12 characters.")

    admin = User(
        email=email,
        hashed_password=get_password_hash(password),
        department_id=department.id,
        is_active=True,
    )

    db.add(admin)
    db.flush()

    print(f"Created administrator account: {email}")

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

        print(f"Assigned role: {role_name}")


def initialize_database() -> None:
    with SessionLocal() as db:
        try:
            initialize_roles(db)

            db.flush()

            department = initialize_department(db)

            admin = initialize_admin(db, department)

            if admin is not None:
                assign_admin_roles(db, admin)

            db.commit()

            print("Database initialization completed.")

        except Exception:
            db.rollback()
            raise


if __name__ == "__main__":
    initialize_database()
