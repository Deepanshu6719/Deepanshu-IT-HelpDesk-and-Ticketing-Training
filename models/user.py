from sqlalchemy import String, DateTime, ForeignKey, Boolean
from datetime import datetime, timezone
from models.base import Base
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models.department import Department
    from models.ticket import Ticket
    from models.ticket_comment import TicketComment
    from models.user_role import UserRole
    from models.user_session import UserSession


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)

    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    department_id: Mapped[int] = mapped_column(
        ForeignKey("departments.id"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    token_version: Mapped[int] = mapped_column(
        default=1,
        server_default="1",
        nullable=False,
    )
    department: Mapped["Department"] = relationship(back_populates="users")
    requested_tickets: Mapped[list["Ticket"]] = relationship(
        back_populates="requester", foreign_keys="Ticket.requester_id"
    )  # tickets this user created
    assigned_tickets: Mapped[list["Ticket"]] = relationship(
        back_populates="assigned_agent", foreign_keys="Ticket.assigned_to"
    )  # tickets assigned to this user for solving
    comments: Mapped[list["TicketComment"]] = relationship(back_populates="author")
    role_assignments: Mapped[list["UserRole"]] = relationship(back_populates="user")
    # List of role assignments belonging to this user
    sessions: Mapped[list["UserSession"]] = relationship(back_populates="user")
