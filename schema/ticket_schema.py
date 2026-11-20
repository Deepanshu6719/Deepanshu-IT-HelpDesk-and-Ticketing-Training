from pydantic import BaseModel, Field, field_validator, ConfigDict,model_validator
from typing import Literal
from datetime import datetime


class CategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str

class CategoryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=100)
    department_id: int = Field(gt=0)

    @field_validator("name", mode="before")
    @classmethod
    def validate_name(cls, value):
        if isinstance(value, str):
            value = value.strip()

        if not isinstance(value, str) or not value:
            raise ValueError("Category name cannot be empty")

        return value

class CategoryPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=2, max_length=100)

    @field_validator("name", mode="before")
    @classmethod
    def validate_name(cls, value):
        if isinstance(value, str):
            value = value.strip()

        if not isinstance(value, str) or not value:
            raise ValueError("Category name cannot be empty")

        return value

    @model_validator(mode="after")
    def validate_at_least_one_field(self):
        if self.name is None:
            raise ValueError("At least one field must be provided")
        return self


class UserSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str


class TicketCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=5, max_length=50)
    description: str = Field(min_length=10, max_length=150)
    category: str
    priority: Literal["low", "medium", "high", "urgent"] = "medium"

    @field_validator("title", mode="before")
    @classmethod
    def title_validator(cls, value: str) -> str:
        if isinstance(value, str):
            if len(value.strip()) >= 5:
                return value.strip()
            raise ValueError("title legth must be >=5")
        return value

    @field_validator("description", mode="before")
    @classmethod
    def description_validator(cls, value: str) -> str:
        if isinstance(value, str):
            if len(value.strip()) >= 10:
                return value.strip()
            raise ValueError("description legth must be >=5")
        return value


class TicketResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str
    category: CategoryResponse
    requested_priority: Literal["low", "medium", "high", "urgent"]
    priority: Literal["low", "medium", "high", "urgent"]
    status: str

    assigned_to: UserSummary | None = Field(
        default=None, validation_alias="assigned_agent"
    )

    requester_id: int
    requester: UserSummary

    created_at: datetime
    updated_at: datetime

class TicketPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=5, max_length=50)
    description: str | None = Field(default=None, min_length=10, max_length=150)
    category: str | None = None

    requested_priority: Literal[
        "low", "medium", "high", "urgent"
    ] | None = None

    status: Literal[
        "open", "under_review", "in_progress", "resolved", "closed"
    ] | None = None

    priority: Literal["low", "medium", "high", "urgent"] | None = None
    assigned_to: int | None = None

    @field_validator("title", mode="before")
    @classmethod
    def validate_title(cls, value):
        if isinstance(value, str):
            value = value.strip()
            if len(value) < 5:
                raise ValueError("Title must contain at least 5 characters")
        return value

    @field_validator("description", mode="before")
    @classmethod
    def validate_description(cls, value):
        if isinstance(value, str):
            value = value.strip()
            if len(value) < 10:
                raise ValueError("Description must contain at least 10 characters")
        return value

class TicketListResponse(BaseModel):
    items: list[TicketResponse]
    total: int
    page: int
    page_size: int
    total_pages: int