from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from schema.common_schema import StrictRequestModel


class CommentCreate(StrictRequestModel):
    message: str = Field(min_length=1, max_length=2000)
    is_internal: bool = False

    @field_validator("message", mode="before")
    @classmethod
    def validate_message(cls, value):
        if isinstance(value, str):
            value = value.strip()

        if not isinstance(value, str) or not value:
            raise ValueError("Comment message cannot be empty")

        return value


class CommentAuthor(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str


class CommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticket_id: int
    user_id: int
    author: CommentAuthor
    message: str
    is_internal: bool
    created_at: datetime
