from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.cache import (
    get_cache,
    invalidate_cache,
    set_cache,
)
from core.dependencies import require_admin
from core.pagination import Pagination
from database.dependencies import get_db
from models.category import Category
from models.department import Department
from models.user import User
from schema.ticket_schema import CategoryCreate, CategoryPatch, CategoryResponse

router = APIRouter(tags=["Category"])


@router.get("/categories", response_model=list[CategoryResponse])
def get_categories(
    pagination: Pagination = Depends(Pagination),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    cache_key = f"helpdesk:categories:{pagination.skip}:{pagination.limit}"
    cached_categories = get_cache(cache_key)

    if cached_categories is not None:
        return cached_categories
    statement = (
        select(Category)
        .where(Category.is_active.is_(True))
        .order_by(Category.id)
        .offset(pagination.skip)
        .limit(pagination.limit)
    )

    categories = db.scalars(statement).all()
    category_data = [
        CategoryResponse.model_validate(category).model_dump()
        for category in categories
    ]

    set_cache(cache_key, category_data)
    return category_data  # or categories


@router.post(
    "/categories",
    response_model=CategoryResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_category(
    category_data: CategoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    department = db.get(Department, category_data.department_id)

    if department is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found",
        )

    new_category = Category(
        name=category_data.name,
        department_id=category_data.department_id,
    )

    db.add(new_category)

    try:
        db.commit()
        db.refresh(new_category)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Category already exists in this department",
        ) from exc
    invalidate_cache("helpdesk:categories:*")
    return new_category


@router.patch(
    "/categories/{category_id}",
    response_model=CategoryResponse,
)
def update_category(
    category_id: int,
    category_data: CategoryPatch,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    category = db.get(Category, category_id)

    if category is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found",
        )

    category.name = category_data.name

    try:
        db.commit()
        db.refresh(category)

    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Category with this name already exists in this department",
        ) from exc
    invalidate_cache("helpdesk:categories:*")
    return category


@router.delete(
    "/categories/{category_id}",
    response_model=CategoryResponse,
    status_code=status.HTTP_200_OK,
)
def deactivate_category(
    category_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    category = db.get(Category, category_id)

    if category is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found",
        )

    if not category.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Category is already inactive",
        )

    category.is_active = False

    db.commit()
    db.refresh(category)
    invalidate_cache("helpdesk:categories:*")
    return category
