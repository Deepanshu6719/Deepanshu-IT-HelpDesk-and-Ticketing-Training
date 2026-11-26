from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.docs.resources import (
    CATEGORY_CREATE_RESPONSES,
    CATEGORY_DELETE_RESPONSES,
    CATEGORY_LIST_RESPONSES,
    CATEGORY_UPDATE_RESPONSES,
    request_example,
)
from core.cache import (
    get_cache,
    invalidate_cache,
    set_cache,
)
from core.dependencies import require_admin
from core.pagination import Pagination
from core.pagination_utils import paginate_query
from database.dependencies import get_db
from models.category import Category
from models.department import Department
from models.user import User
from schema.common_schema import PaginatedResponse, SuccessResponse
from schema.ticket_schema import CategoryCreate, CategoryPatch, CategoryResponse

router = APIRouter(tags=["Categories"])


@router.get(
    "/categories",
    response_model=SuccessResponse[PaginatedResponse[CategoryResponse]],
    summary="List active categories",
    description=(
        "Retrieve active support categories using pagination. "
        "Results are ordered by category ID and cached in Redis. "
        "Requires administrator privileges."
    ),
    responses=CATEGORY_LIST_RESPONSES,
)
def get_categories(
    pagination: Pagination = Depends(Pagination),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    cache_key = f"helpdesk:categories:v2:{pagination.page}:{pagination.limit}"

    cached_categories = get_cache(cache_key)

    if cached_categories is not None:
        return SuccessResponse[PaginatedResponse[CategoryResponse]](
            data=cached_categories,
        )

    statement = (
        select(Category).where(Category.is_active.is_(True)).order_by(Category.id)
    )

    items, total = paginate_query(
        db=db,
        statement=statement,
        pagination=pagination,
    )

    category_data = PaginatedResponse[CategoryResponse](
        total=total,
        page=pagination.page,
        limit=pagination.limit,
        items=items,
    )

    set_cache(
        cache_key,
        category_data.model_dump(mode="json"),
    )

    return SuccessResponse[PaginatedResponse[CategoryResponse]](
        data=category_data,
    )  # or categories


@router.post(
    "/categories",
    response_model=SuccessResponse[CategoryResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a support category",
    description=(
        "Create a support category within an existing department. "
        "Category names must be unique within their department. "
        "Invalidates the category cache after successful creation. "
        "Requires administrator privileges."
    ),
    responses=CATEGORY_CREATE_RESPONSES,
    openapi_extra=request_example(
        {
            "name": "Wi-Fi Connectivity",
            "department_id": 2,
        }
    ),
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
    return SuccessResponse(data=new_category)


@router.patch(
    "/categories/{category_id}",
    response_model=SuccessResponse[CategoryResponse],
    summary="Rename a support category",
    description=(
        "Update the name of an existing support category. "
        "The category remains in its original department. "
        "The new name must be unique within that department. "
        "Requires administrator privileges."
    ),
    responses=CATEGORY_UPDATE_RESPONSES,
    openapi_extra=request_example(
        {
            "name": "Wireless Network Connectivity",
        }
    ),
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
    return SuccessResponse(data=category)


@router.delete(
    "/categories/{category_id}",
    response_model=SuccessResponse[CategoryResponse],
    status_code=status.HTTP_200_OK,
    summary="Deactivate a support category",
    description=(
        "Deactivate a category without physically deleting its record. "
        "Inactive categories are excluded from the active category list. "
        "Attempting to deactivate an already inactive category returns HTTP 409. "
        "Requires administrator privileges."
    ),
    responses=CATEGORY_DELETE_RESPONSES,
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
    return SuccessResponse(data=category)
