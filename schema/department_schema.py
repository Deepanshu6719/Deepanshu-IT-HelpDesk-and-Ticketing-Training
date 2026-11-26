from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from schema.common_schema import StrictRequestModel


class DepartmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    created_at: datetime


class DepartmentCreate(StrictRequestModel):
    name: str = Field(min_length=2, max_length=100)

    @field_validator("name", mode="before")
    @classmethod
    def validate_name(cls, value):
        if isinstance(value, str):
            value = value.strip()

        if not value:
            raise ValueError("Department name cannot be empty")

        return value


class DepartmentPatch(StrictRequestModel):
    name: str | None = Field(
        default=None,
        min_length=2,
        max_length=100,
    )

    @field_validator("name", mode="before")
    @classmethod
    def validate_name(cls, value):
        if value is None:
            return value

        if isinstance(value, str):
            value = value.strip()

        if not value:
            raise ValueError("Department name cannot be empty")

        return value
