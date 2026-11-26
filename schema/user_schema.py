from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from schema.common_schema import StrictRequestModel


class UserRoleAssign(StrictRequestModel):
    role: Literal["admin", "agent"]


class UserLogin(StrictRequestModel):
    email: str
    password: str


class UserCreate(StrictRequestModel):
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


class UserStatusUpdate(StrictRequestModel):
    is_active: bool


class PasswordChange(StrictRequestModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=128)


class PasswordChangeResponse(BaseModel):
    message: str


class UserRoleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    role_id: int
