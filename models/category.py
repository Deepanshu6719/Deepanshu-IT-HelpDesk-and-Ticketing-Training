from typing import TYPE_CHECKING

from sqlalchemy import String, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column,relationship
from datetime import datetime, timezone

from models.base import Base
if TYPE_CHECKING:
    from models.department import Department
    from models.ticket import Ticket



class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    department_id: Mapped[int] = mapped_column(
        ForeignKey("departments.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    department:Mapped["Department"]=relationship(back_populates="categories")
    tickets:Mapped[list["Ticket"]]=relationship(back_populates="category")