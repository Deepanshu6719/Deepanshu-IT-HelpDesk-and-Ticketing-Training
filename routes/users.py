from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from database.dependencies import get_db
from core.dependencies import require_admin, get_current_user
from core.security import get_password_hash, verify_password

from models.user import User
from models.department import Department
from models.role import Role
from models.user_role import UserRole

from schema.user_schema import (
    UserCreate,
    UserResponse,
    UserStatusUpdate,
    PasswordChange,
)

router = APIRouter(tags=["Users"])


@router.post(
    "/users",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
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

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Could not create user. Email may already be registered.",
        )

    return new_user


@router.get("/users", response_model=list[UserResponse])
def get_all_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    statement = select(User).order_by(User.id)

    users = db.scalars(statement).all()

    return users


@router.get("/users/{user_id}", response_model=UserResponse)
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

    return user


@router.patch("/users/{user_id}/status", response_model=UserResponse)
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

    return user


@router.patch("/users/me/password")
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
        current_user.hashed_password = get_password_hash(password_data.new_password)

        # Invalidate all previously issued access tokens
        current_user.token_version += 1

        db.commit()

    except Exception:
        db.rollback()
        raise

    return {"message": "Password changed successfully"}
