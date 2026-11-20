from sqlalchemy.orm import Mapped, mapped_column,relationship
from sqlalchemy import String
from models.base import Base
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from models.user_role import UserRole

class Role(Base):
    __tablename__ = "roles"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    user_assignments:Mapped[list["UserRole"]]=relationship(back_populates="role")
    #list of user role , one role to multiple users