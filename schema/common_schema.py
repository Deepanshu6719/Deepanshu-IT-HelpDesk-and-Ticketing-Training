from typing import Literal

from pydantic import BaseModel, Field


class SuccessResponse[T](BaseModel):
    success: Literal[True] = True
    data: T


class ErrorDetail(BaseModel):
    location: list[str | int]
    message: str
    type: str


class ErrorInfo(BaseModel):
    code: str
    message: str
    details: list[ErrorDetail] | None = None


class ErrorResponse(BaseModel):
    success: Literal[False] = False
    error: ErrorInfo
    request_id: str | None = None


class PaginatedResponse[T](BaseModel):
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    limit: int = Field(ge=1, le=100)
    items: list[T]
