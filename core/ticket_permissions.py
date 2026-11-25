from fastapi import HTTPException, status

from core.permissions import has_role
from models.ticket import Ticket
from models.user import User


def check_ticket_access(ticket: Ticket, current_user: User):

    is_admin = has_role(current_user, "admin")
    is_agent = has_role(current_user, "agent")

    if is_admin:
        return

    if is_agent:
        if (
            ticket.assigned_to == current_user.id
            or ticket.requester_id == current_user.id
        ):
            return

    elif ticket.requester_id == current_user.id:
        return

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Ticket not found",
    )
