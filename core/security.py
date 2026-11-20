# PasswordHash instance provides 2 function hash() for generating the passwrod hash
# and verify() verifies password against existing hash in the db
# pwdlib → hashes and verifies passwords.
# PyJWT → creates and verifies JWTs.
# settings → provides the secret key, algorithm, and expiry configuration.
from pwdlib import PasswordHash
import jwt
import secrets
import hashlib
from datetime import datetime, timedelta, timezone
from core.config import settings

password_hash = PasswordHash.recommended()  # uses Argon2id the password hashing config


# password hashing
def get_password_hash(password: str) -> str:
    hashed_password = password_hash.hash(password)
    return hashed_password


# password hash verification
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return password_hash.verify(plain_password, hashed_password)

#creating the token of user with provided user_id as a dictionary
def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    return encoded_jwt
def decode_access_token(token: str):
    payload=jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[settings.ALGORITHM]
    )
    return payload


# Generate a secure refresh token
def create_refresh_token() -> str:
    refresh_token = secrets.token_urlsafe(64)
    return refresh_token


# Hash the refresh token before storing it in the database
def hash_refresh_token(token: str) -> str:
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return token_hash
