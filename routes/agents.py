from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.docs.resources import (
    AGENT_LIST_RESPONSES,
    DEPARTMENT_AGENT_LIST_RESPONSES,
)
from core.dependencies import require_admin
from core.pagination import Pagination
from core.pagination_utils import paginate_query
from database.dependencies import get_db
from models.department import Department
from models.role import Role
from models.user import User
from models.user_role import UserRole
from schema.common_schema import PaginatedResponse, SuccessResponse
from schema.user_schema import UserResponse

router = APIRouter(tags=["Agents"])


@router.get(
    "/agents",
    response_model=SuccessResponse[PaginatedResponse[UserResponse]],
    summary="List active support agents",
    description=(
        "Retrieve active users who have the agent role. "
        "Each agent appears once, including users with multiple roles. "
        "Results are ordered by user ID. "
        "Requires administrator privileges."
    ),
    responses=AGENT_LIST_RESPONSES,
)
def get_agents(
    pagination: Pagination = Depends(Pagination),
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

    items, total = paginate_query(
        db=db,
        statement=statement,
        pagination=pagination,
    )

    return SuccessResponse[PaginatedResponse[UserResponse]](
        data=PaginatedResponse[UserResponse](
            total=total,
            page=pagination.page,
            limit=pagination.limit,
            items=items,
        )
    )


@router.get(
    "/departments/{department_id}/agents",
    response_model=SuccessResponse[PaginatedResponse[UserResponse]],
    summary="List agents in a department",
    description=(
        "Retrieve active support agents belonging to the specified department. "
        "Useful for identifying eligible agents during ticket assignment. "
        "Returns HTTP 404 if the department does not exist. "
        "Requires administrator privileges."
    ),
    responses=DEPARTMENT_AGENT_LIST_RESPONSES,
)
def get_department_agents(
    department_id: int,
    pagination: Pagination = Depends(Pagination),
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
            User.is_active.is_(True),
            User.department_id == department_id,
        )
        .distinct()
        .order_by(User.id)
    )

    items, total = paginate_query(
        db=db,
        statement=statement,
        pagination=pagination,
    )

    return SuccessResponse[PaginatedResponse[UserResponse]](
        data=PaginatedResponse[UserResponse](
            total=total,
            page=pagination.page,
            limit=pagination.limit,
            items=items,
        )
    )
