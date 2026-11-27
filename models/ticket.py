from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base

if TYPE_CHECKING:
    from models.category import Category
    from models.department import Department
    from models.ticket_comment import TicketComment
    from models.user import User


class Ticket(Base):
    __tablename__ = "tickets"
    __table_args__ = (
        CheckConstraint(
            "status IN ('open','under_review', 'in_progress', 'resolved', 'closed')",
            name="check_ticket_status",
        ),
        ForeignKeyConstraint(
            ["category_id", "department_id"],
            ["categories.id", "categories.department_id"],
            name="fk_tickets_category_department",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id"), nullable=False
    )
    department_id: Mapped[int] = mapped_column(
        ForeignKey("departments.id"), nullable=False
    )
    requester_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    assigned_to: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    requested_priority: Mapped[str] = mapped_column(
        String(20), default="medium", nullable=False
    )
    priority: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="open", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
    is_deleted: Mapped[bool] = mapped_column(default=False, nullable=False)

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    category: Mapped["Category"] = relationship(
        back_populates="tickets",
        foreign_keys=[category_id],
    )
    department: Mapped["Department"] = relationship(back_populates="tickets")
    requester: Mapped["User"] = relationship(
        "User", foreign_keys=[requester_id], back_populates="requested_tickets"
    )
    assigned_agent: Mapped["User | None"] = relationship(
        "User", foreign_keys=[assigned_to], back_populates="assigned_tickets"
    )
    comments: Mapped[list["TicketComment"]] = relationship(back_populates="ticket")


Index(
    "ix_tickets_active_created_id",
    Ticket.created_at.desc(),
    Ticket.id.desc(),
    postgresql_where=text("is_deleted IS FALSE"),
)

Index(
    "ix_tickets_active_requester_created_id",
    Ticket.requester_id,
    Ticket.created_at.desc(),
    Ticket.id.desc(),
    postgresql_where=text("is_deleted IS FALSE"),
)

Index(
    "ix_tickets_active_assigned_created_id",
    Ticket.assigned_to,
    Ticket.created_at.desc(),
    Ticket.id.desc(),
    postgresql_where=text("is_deleted IS FALSE"),
)
