# this module connects users to their roles as a intermediate file
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base

if TYPE_CHECKING:
    from models.role import Role
    from models.user import User


class UserRole(Base):
    __tablename__ = "user_roles"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), primary_key=True)
    user: Mapped["User"] = relationship(
        back_populates="role_assignments"
    )  # each role belongs to one user
    # one userrole per user
    role: Mapped["Role"] = relationship(back_populates="user_assignments")
    # each userrole record that is combo of both field in this model belongs to one role
