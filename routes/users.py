from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.docs.resources import (
    PASSWORD_CHANGE_RESPONSES,
    USER_CREATE_RESPONSES,
    USER_DETAIL_RESPONSES,
    USER_LIST_RESPONSES,
    USER_STATUS_RESPONSES,
    request_example,
)
from core.dependencies import get_current_user, require_admin
from core.pagination import Pagination
from core.pagination_utils import paginate_query
from core.security import get_password_hash, verify_password
from database.dependencies import get_db
from models.department import Department
from models.refresh_token import RefreshToken
from models.role import Role
from models.user import User
from models.user_role import UserRole
from models.user_session import UserSession
from schema.common_schema import PaginatedResponse, SuccessResponse
from schema.user_schema import (
    PasswordChange,
    PasswordChangeResponse,
    UserCreate,
    UserResponse,
    UserStatusUpdate,
)

router = APIRouter(tags=["Users"])


@router.post(
    "/users",
    response_model=SuccessResponse[UserResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a user account",
    description=(
        "Create a requester, agent or administrator account. "
        "The email address must be unique and the department must exist. "
        "Passwords are securely hashed before storage. "
        "Requires administrator privileges."
    ),
    responses=USER_CREATE_RESPONSES,
    openapi_extra=request_example(
        {
            "email": "employee@example.com",
            "password": "ExamplePassword123!",
            "department_id": 2,
            "role": "requester",
        }
    ),
)
def create_user(
    user_data: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    # Step 1: Check whether email already exists
    existing_user = db.scalar(select(User).where(User.email == user_data.email))

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    # Step 2: Check whether department exists
    department = db.get(Department, user_data.department_id)

    if department is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found",
        )

    # Step 3: Find the selected role if creating an agent or admin
    selected_role = None

    if user_data.role in ("agent", "admin"):
        selected_role = db.scalar(select(Role).where(Role.name == user_data.role))

        if selected_role is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"{user_data.role.capitalize()} role is not configured",
            )

    # Step 4: Create the user
    new_user = User(
        email=user_data.email,
        hashed_password=get_password_hash(user_data.password),
        department_id=user_data.department_id,
    )

    try:
        db.add(new_user)

        # Generate the user's ID without committing
        db.flush()

        # Step 5: Create role assignment for agent or admin
        if selected_role is not None:
            new_user_role = UserRole(
                user_id=new_user.id,
                role_id=selected_role.id,
            )
            db.add(new_user_role)

        # Step 6: Commit the transaction
        db.commit()
        db.refresh(new_user)

    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Could not create user. Email may already be registered.",
        ) from exc

    return SuccessResponse(data=new_user)


@router.get(
    "/users",
    response_model=SuccessResponse[PaginatedResponse[UserResponse]],
    summary="List user accounts",
    description=(
        "Retrieve user accounts using pagination. "
        "Includes both active and inactive users. "
        "Results are ordered by user ID. "
        "Requires administrator privileges."
    ),
    responses=USER_LIST_RESPONSES,
)
def get_all_users(
    pagination: Pagination = Depends(Pagination),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    statement = select(User).order_by(User.id)

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
    "/users/{user_id}",
    response_model=SuccessResponse[UserResponse],
    summary="Retrieve user account details",
    description=(
        "Retrieve an existing user's account details by user ID. "
        "Password hashes and authentication secrets are not returned. "
        "Requires administrator privileges."
    ),
    responses=USER_DETAIL_RESPONSES,
)
def get_user_by_id(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    user = db.get(User, user_id)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return SuccessResponse(data=user)


@router.patch(
    "/users/{user_id}/status",
    response_model=SuccessResponse[UserResponse],
    summary="Activate or deactivate a user",
    description=(
        "Change the active status of an existing user account. "
        "Administrators cannot change their own account status. "
        "Requesting the account's existing status returns HTTP 409. "
        "Inactive users cannot authenticate successfully. "
        "Requires administrator privileges."
    ),
    responses=USER_STATUS_RESPONSES,
    openapi_extra=request_example(
        {
            "is_active": False,
        }
    ),
)
def update_user_status(
    user_id: int,
    status_data: UserStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    user = db.get(User, user_id)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot change your own account status",
        )

    if user.is_active == status_data.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User already has the requested status",
        )

    user.is_active = status_data.is_active

    try:
        db.commit()
        db.refresh(user)
    except Exception:
        db.rollback()
        raise

    return SuccessResponse(data=user)


@router.patch(
    "/users/me/password",
    response_model=SuccessResponse[PasswordChangeResponse],
    summary="Change the current user's password",
    description=(
        "Change the authenticated user's password after verifying "
        "the current password. "
        "The new password must differ from the current password. "
        "All existing device sessions, access tokens and refresh "
        "tokens are invalidated. "
        "The user must authenticate again on every device."
    ),
    responses=PASSWORD_CHANGE_RESPONSES,
    openapi_extra=request_example(
        {
            "current_password": "ExampleOldPassword123!",
            "new_password": "ExampleNewPassword456!",
        }
    ),
)
def change_password(
    password_data: PasswordChange,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Verify current password
    if not verify_password(
        password_data.current_password,
        current_user.hashed_password,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    # Prevent reusing the current password
    if verify_password(
        password_data.new_password,
        current_user.hashed_password,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from current password",
        )

    try:
        now = datetime.now(UTC)

        session_ids = select(UserSession.id).where(
            UserSession.user_id == current_user.id
        )

        # Revoke every existing device session
        db.execute(
            update(UserSession)
            .where(
                UserSession.user_id == current_user.id,
                UserSession.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )

        # Revoke all remaining refresh tokens
        db.execute(
            update(RefreshToken)
            .where(
                RefreshToken.session_id.in_(session_ids),
                RefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )

        # Update password and invalidate access tokens
        current_user.hashed_password = get_password_hash(password_data.new_password)

        current_user.token_version += 1

        db.commit()

    except Exception:
        db.rollback()
        raise
    return SuccessResponse(
        data={
            "message": "Password changed successfully",
        }
    )
