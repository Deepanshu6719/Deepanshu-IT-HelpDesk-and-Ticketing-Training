
from fastapi import APIRouter, HTTPException, Depends
from schema.user_schema import UserRoleAssign
from sqlalchemy import select
from sqlalchemy.orm import Session
from database.dependencies import get_db
from models.user import User
from models.role import Role
from models.user_role import UserRole
from core.dependencies import require_admin
from sqlalchemy.exc import IntegrityError

router = APIRouter(tags=["Assign role"])


@router.post("/admin/users/{user_id}/roles", status_code=201)
def assign_user_role(
    role: UserRoleAssign,
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    # Step 1: Check whether the user exists
    user_statement = select(User).where(User.id == user_id)
    db_user = db.scalar(user_statement)

    if db_user is None:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )

    # Step 2: Find the requested role
    role_statement = select(Role).where(Role.name == role.role)
    db_role = db.scalar(role_statement)

    if db_role is None:
        raise HTTPException(
            status_code=404,
            detail="Role not found",
        )

    # Step 3: If assigning admin, verify that the user is already an agent
    if role.role == "admin":
        agent_role_statement = select(Role).where(Role.name == "agent")
        agent_role = db.scalar(agent_role_statement)

        if agent_role is None:
            raise HTTPException(
                status_code=500,
                detail="Agent role is not configured",
            )

        agent_assignment_statement = select(UserRole).where(
            UserRole.user_id == db_user.id,
            UserRole.role_id == agent_role.id,
        )

        existing_agent_assignment = db.scalar(
            agent_assignment_statement
        )

        if existing_agent_assignment is None:
            raise HTTPException(
                status_code=400,
                detail="User must be an agent before becoming an admin",
            )

    # Step 4: Create the user-role association
    user_role = UserRole(
        user_id=db_user.id,
        role_id=db_role.id,
    )

    # Step 5: Save the association
    try:
        db.add(user_role)
        db.commit()
        db.refresh(user_role)

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="User already has this role",
        )

    return user_role
