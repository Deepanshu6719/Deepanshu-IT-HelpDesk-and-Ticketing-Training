from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserRoleAssign(BaseModel):
    role: Literal["admin", "agent"]


class UserLogin(BaseModel):
    email: str
    password: str


class UserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    department_id: int = Field(gt=0)
    role: Literal["requester", "agent", "admin"]


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    department_id: int
    is_active: bool


class UserStatusUpdate(BaseModel):
    is_active: bool


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=128)
