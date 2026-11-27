from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base

if TYPE_CHECKING:
    from models.department import Department
    from models.ticket import Ticket


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint(
            "name",
            "department_id",
            name="uq_categories_name_department_id",
        ),
        UniqueConstraint(
            "id",
            "department_id",
            name="uq_categories_id_department_id",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    department_id: Mapped[int] = mapped_column(
        ForeignKey("departments.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        default=True,
        server_default="true",
        nullable=False,
    )
    department: Mapped["Department"] = relationship(back_populates="categories")
    tickets: Mapped[list["Ticket"]] = relationship(
        back_populates="category",
        foreign_keys="Ticket.category_id",
    )
