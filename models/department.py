from sqlalchemy import String, DateTime

from models.base import Base
from datetime import datetime, timezone
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models.user import User
    from models.category import Category
    from models.ticket import Ticket
class Department(Base):
    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True,nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    users: Mapped[list["User"]] = relationship(back_populates="department")
    categories:Mapped[list["Category"]]=relationship(back_populates="department")
    tickets:Mapped[list["Ticket"]]=relationship(back_populates="department")