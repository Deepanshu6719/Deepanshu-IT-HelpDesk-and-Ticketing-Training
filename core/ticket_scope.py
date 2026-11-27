from sqlalchemy import or_
from sqlalchemy.sql.elements import ColumnElement

from core.permissions import has_role
from models.ticket import Ticket
from models.user import User


def get_ticket_scope(current_user: User) -> str:
    if has_role(current_user, "admin"):
        return "admin"

    if has_role(current_user, "agent"):
        return "agent"

    return "requester"


def ticket_visibility_filters(
    current_user: User,
) -> list[ColumnElement[bool]]:
    filters = [Ticket.is_deleted.is_(False)]

    scope = get_ticket_scope(current_user)

    if scope == "admin":
        return filters

    if scope == "agent":
        filters.append(
            or_(
                Ticket.assigned_to == current_user.id,
                Ticket.requester_id == current_user.id,
            )
        )
    else:
        filters.append(Ticket.requester_id == current_user.id)

    return filters
