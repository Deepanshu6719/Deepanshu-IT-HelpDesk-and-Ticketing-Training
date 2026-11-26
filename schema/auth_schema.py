from typing import Literal

from pydantic import BaseModel, Field


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class TokenResponse(BaseModel):
    access_token: str = Field(
        description="JWT access token used to authenticate protected API requests.",
    )

    refresh_token: str = Field(
        description="Opaque refresh token used to obtain a new token pair.",
    )

    token_type: Literal["bearer"] = Field(
        default="bearer",
        description="Authentication scheme used by protected endpoints.",
    )


class LogoutResponse(BaseModel):
    message: str = Field(
        description="Confirmation that the current device session was revoked.",
    )
