from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.dependencies import require_admin
from database.dependencies import get_db
from models.department import Department
from models.user import User
from schema.department_schema import (
    DepartmentCreate,
    DepartmentPatch,
    DepartmentResponse,
)

router = APIRouter(tags=["Department"])


@router.get(
    "/departments",
    response_model=list[DepartmentResponse],
)
def get_departments(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    statement = select(Department).order_by(Department.id)

    return db.scalars(statement).all()


@router.get(
    "/departments/{department_id}",
    response_model=DepartmentResponse,
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

    return department


@router.post(
    "/departments",
    response_model=DepartmentResponse,
    status_code=status.HTTP_201_CREATED,
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

    return department


@router.patch(
    "/departments/{department_id}",
    response_model=DepartmentResponse,
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

    return department
