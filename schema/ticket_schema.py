from pydantic import BaseModel, Field, field_validator , ConfigDict
from typing import Literal
from datetime import datetime


class CategoryResponse(BaseModel):
    id: int
    name: str


class UserSummary(BaseModel):
    id: int
    name: str


class TicketCreate(BaseModel):
    model_config=ConfigDict(extra="forbid")
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
    id: int
    title: str
    description: str
    category: CategoryResponse
    priority: Literal["low", "medium", "high", "urgent"]
    status: str
    assigned_to: UserSummary | None = None
    created_at: datetime
    updated_at: datetime


