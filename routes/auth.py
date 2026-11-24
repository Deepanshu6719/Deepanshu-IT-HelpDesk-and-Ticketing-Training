from datetime import datetime, timedelta, timezone
from core.rate_limit import check_rate_limit
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from database.dependencies import get_db
from models.user import User
from models.user_session import UserSession
from models.refresh_token import RefreshToken
from schema.auth_schema import RefreshTokenRequest
from core.security import (
    verify_password,
    create_access_token,
    create_refresh_token,
    hash_refresh_token,
    decode_access_token,
)
from core.config import settings
from core.dependencies import get_current_user, oauth2_scheme

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login")
def login(
    request: Request,
    user_credentials: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    check_rate_limit(
        key=f"helpdesk:rate_limit:login:{request.client.host}",
        limit=5,
        window=60,
    )
    # 1. Find the user
    statement = select(User).where(User.email == user_credentials.username)
    user = db.scalar(statement)

    # 2. Verify user credentials
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    if not verify_password(
        user_credentials.password,
        user.hashed_password,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    # 3. Calculate session and refresh-token expiration
    now = datetime.now(timezone.utc)

    session_expiry = now + timedelta(days=settings.SESSION_EXPIRE_DAYS)

    refresh_expiry = min(
        now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        session_expiry,
    )

    # 4. Create a new device session
    new_session = UserSession(
        user_id=user.id,
        expires_at=session_expiry,
    )

    db.add(new_session)

    try:
        # Generate the session ID by inserting the session
        # into the current transaction.
        db.flush()

        # 5. Generate the refresh token
        refresh_token = create_refresh_token()

        # 6. Store only its hash in the database
        refresh_token_record = RefreshToken(
            session_id=new_session.id,
            token_hash=hash_refresh_token(refresh_token),
            expires_at=refresh_expiry,
        )

        db.add(refresh_token_record)

        # 7. Create access token with user ID, token version and session ID
        access_token = create_access_token(
            data={
                "sub": str(user.id),
                "ver": user.token_version,
                "sid": new_session.id,
            }
        )

        # 8. Save session and refresh-token record together
        db.commit()

    except SQLAlchemyError:
        db.rollback()
        raise

    # 9. Return tokens to the client
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


@router.post("/refresh")
def refresh_access_token(
    request: RefreshTokenRequest,
    db: Session = Depends(get_db),
):
    try:
        # 1. Hash the refresh token received from the client
        token_hash = hash_refresh_token(request.refresh_token)

        # 2. Find the refresh token without locking it yet
        token_statement = select(RefreshToken).where(
            RefreshToken.token_hash == token_hash
        )

        token_reference = db.scalar(token_statement)

        if token_reference is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )

        # 3. Lock the associated session FIRST
        session_statement = (
            select(UserSession)
            .where(UserSession.id == token_reference.session_id)
            .with_for_update()
        )

        user_session = db.scalar(session_statement)

        # Get current time after acquiring the session lock
        now = datetime.now(timezone.utc)

        if (
            user_session is None
            or user_session.revoked_at is not None
            or user_session.expires_at <= now
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session is no longer valid",
            )

        # 4. Lock the refresh-token row SECOND
        locked_token_statement = (
            select(RefreshToken)
            .where(
                RefreshToken.id == token_reference.id,
                RefreshToken.token_hash == token_hash,
            )
            .execution_options(populate_existing=True)
            .with_for_update()
        )

        old_token = db.scalar(locked_token_statement)

        if old_token is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )

        # 5. Detect reuse of an already-revoked refresh token
        if old_token.revoked_at is not None:

            # Revoke the entire device session
            user_session.revoked_at = now

            # Revoke every remaining active refresh token
            db.execute(
                update(RefreshToken)
                .where(
                    RefreshToken.session_id == user_session.id,
                    RefreshToken.revoked_at.is_(None),
                )
                .values(revoked_at=now)
            )

            # Commit revocation before returning the error
            db.commit()

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token reuse detected. Session revoked.",
            )

        # 6. Check refresh-token expiration
        if old_token.expires_at <= now:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token has expired",
            )

        # 7. Retrieve and validate the user
        user = db.get(User, user_session.user_id)

        if user is None or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User is no longer active",
            )

        # 8. Generate a new refresh token
        new_refresh_token = create_refresh_token()

        new_refresh_expiry = min(
            now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
            user_session.expires_at,
        )

        new_token_record = RefreshToken(
            session_id=user_session.id,
            token_hash=hash_refresh_token(new_refresh_token),
            expires_at=new_refresh_expiry,
        )

        db.add(new_token_record)

        # Generate the new database ID
        db.flush()

        # 9. Revoke the old token and link it to its replacement
        old_token.revoked_at = now
        old_token.replaced_by_id = new_token_record.id

        # 10. Generate a new access token for the same session
        new_access_token = create_access_token(
            data={
                "sub": str(user.id),
                "ver": user.token_version,
                "sid": user_session.id,
            }
        )

        # 11. Commit rotation atomically
        db.commit()

        return {
            "access_token": new_access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer",
        }

    except SQLAlchemyError:
        db.rollback()
        raise


@router.post("/logout")
def logout(
    token: str = Depends(oauth2_scheme),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    now = datetime.now(timezone.utc)

    try:
        # 1. Extract the session ID from the validated access token
        payload = decode_access_token(token)
        session_id = payload.get("sid")

        # 2. Retrieve the current device session
        session_statement = (
            select(UserSession)
            .where(
                UserSession.id == session_id,
                UserSession.user_id == current_user.id,
            )
            .with_for_update()
        )

        user_session = db.scalar(session_statement)

        if user_session is None or user_session.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid session",
            )

        # 3. Revoke the current device session
        user_session.revoked_at = now

        # 4. Revoke all active refresh tokens for this session
        db.execute(
            update(RefreshToken)
            .where(
                RefreshToken.session_id == session_id,
                RefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )

        # 5. Save changes
        db.commit()

        return {"message": "Successfully logged out from this device"}

    except SQLAlchemyError:
        db.rollback()
        raise
