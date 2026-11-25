from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.dependencies import require_admin
from database.dependencies import get_db
from models.department import Department
from models.role import Role
from models.user import User
from models.user_role import UserRole
from schema.user_schema import UserResponse

router = APIRouter(tags=["Agents"])


@router.get("/agents", response_model=list[UserResponse])
def get_agents(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    statement = (
        select(User)
        .join(User.role_assignments)
        .join(UserRole.role)
        .where(
            Role.name == "agent",
            User.is_active.is_(True),
        )
        .distinct()
        .order_by(User.id)
    )

    return db.scalars(statement).all()


@router.get(
    "/departments/{department_id}/agents",
    response_model=list[UserResponse],
)
def get_department_agents(
    department_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    department = db.get(Department, department_id)

    if department is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found",
        )

    statement = (
        select(User)
        .join(User.role_assignments)
        .join(UserRole.role)
        .where(
            Role.name == "agent",
            User.department_id == department_id,
            User.is_active.is_(True),
        )
        .distinct()
        .order_by(User.id)
    )

    return db.scalars(statement).all()
