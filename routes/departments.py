from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.docs.resources import (
    DEPARTMENT_CREATE_RESPONSES,
    DEPARTMENT_DETAIL_RESPONSES,
    DEPARTMENT_LIST_RESPONSES,
    DEPARTMENT_UPDATE_RESPONSES,
    request_example,
)
from core.dependencies import require_admin
from core.pagination import Pagination
from core.pagination_utils import paginate_query
from database.dependencies import get_db
from models.department import Department
from models.user import User
from schema.common_schema import PaginatedResponse, SuccessResponse
from schema.department_schema import (
    DepartmentCreate,
    DepartmentPatch,
    DepartmentResponse,
)

router = APIRouter(tags=["Departments"])


@router.get(
    "/departments",
    response_model=SuccessResponse[PaginatedResponse[DepartmentResponse]],
    summary="List departments",
    description=(
        "Retrieve organizational departments ordered by department ID. "
        "Requires administrator privileges."
    ),
    responses=DEPARTMENT_LIST_RESPONSES,
)
def get_departments(
    pagination: Pagination = Depends(Pagination),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    statement = select(Department).order_by(Department.id)

    items, total = paginate_query(
        db=db,
        statement=statement,
        pagination=pagination,
    )

    return SuccessResponse[PaginatedResponse[DepartmentResponse]](
        data=PaginatedResponse[DepartmentResponse](
            total=total,
            page=pagination.page,
            limit=pagination.limit,
            items=items,
        )
    )


@router.get(
    "/departments/{department_id}",
    response_model=SuccessResponse[DepartmentResponse],
    summary="Retrieve department details",
    description=(
        "Retrieve an existing organizational department by its ID. "
        "Returns HTTP 404 if the department does not exist. "
        "Requires administrator privileges."
    ),
    responses=DEPARTMENT_DETAIL_RESPONSES,
)
def get_department(
    department_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    statement = select(Department).where(Department.id == department_id)

    department = db.scalar(statement)

    if department is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found",
        )

    return SuccessResponse(data=department)


@router.post(
    "/departments",
    response_model=SuccessResponse[DepartmentResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a department",
    description=(
        "Create a new organizational department with a unique name. "
        "Departments are used to organize users, agents and support categories. "
        "Requires administrator privileges."
    ),
    responses=DEPARTMENT_CREATE_RESPONSES,
    openapi_extra=request_example(
        {
            "name": "Network Support",
        }
    ),
)
def create_department(
    department_data: DepartmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    department = Department(name=department_data.name)

    db.add(department)

    try:
        db.commit()
        db.refresh(department)

    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Department already exists",
        ) from exc

    return SuccessResponse(data=department)


@router.patch(
    "/departments/{department_id}",
    response_model=SuccessResponse[DepartmentResponse],
    summary="Rename a department",
    description=(
        "Rename an existing department without changing its ID. "
        "The new name must be unique and cannot be null. "
        "Requires administrator privileges."
    ),
    responses=DEPARTMENT_UPDATE_RESPONSES,
    openapi_extra=request_example(
        {
            "name": "Network Operations",
        }
    ),
)
def update_department(
    department_id: int,
    department_data: DepartmentPatch,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    if "name" not in department_data.model_fields_set:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one field must be provided",
        )

    if department_data.name is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Department name cannot be null",
        )

    statement = select(Department).where(Department.id == department_id)
    department = db.scalar(statement)

    if department is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found",
        )

    department.name = department_data.name

    try:
        db.commit()
        db.refresh(department)

    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Department name already exists",
        ) from exc

    return SuccessResponse(data=department)
