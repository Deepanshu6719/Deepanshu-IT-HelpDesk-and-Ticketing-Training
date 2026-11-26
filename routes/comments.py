from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from api.docs.resources import (
    COMMENT_CREATE_RESPONSES,
    COMMENT_LIST_RESPONSES,
    request_example,
)
from core.dependencies import get_current_user
from core.pagination import Pagination
from core.pagination_utils import paginate_query
from core.permissions import has_role
from core.ticket_permissions import check_ticket_access
from database.dependencies import get_db
from models.ticket import Ticket
from models.ticket_comment import TicketComment
from models.user import User
from schema.comment_schema import CommentCreate, CommentResponse
from schema.common_schema import PaginatedResponse, SuccessResponse

router = APIRouter(tags=["Comments"])


@router.post(
    "/tickets/{ticket_id}/comments",
    response_model=SuccessResponse[CommentResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Add a ticket comment",
    description=(
        "Add a comment to an accessible, non-deleted ticket. "
        "Only admins and agents can create internal comments. "
        "Requesters can create public comments only."
    ),
    responses=COMMENT_CREATE_RESPONSES,
    openapi_extra=request_example(
        {
            "message": "The issue still occurs after restarting the laptop.",
            "is_internal": False,
        }
    ),
)
def create_comment(
    ticket_id: int,
    comment_data: CommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ticket = db.get(Ticket, ticket_id)

    if ticket is None or ticket.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found",
        )

    check_ticket_access(ticket, current_user)

    is_admin = has_role(current_user, "admin")
    is_agent = has_role(current_user, "agent")

    # Only admins and agents can create internal comments
    if comment_data.is_internal and not (is_admin or is_agent):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not allowed to create internal comments",
        )

    new_comment = TicketComment(
        ticket_id=ticket.id,
        user_id=current_user.id,
        message=comment_data.message,
        is_internal=comment_data.is_internal,
    )
    new_comment.author = current_user
    try:
        db.add(new_comment)
        db.commit()
        db.refresh(new_comment)

    except Exception:
        db.rollback()
        raise

    return SuccessResponse(data=new_comment)


@router.get(
    "/tickets/{ticket_id}/comments",
    response_model=SuccessResponse[PaginatedResponse[CommentResponse]],
    summary="List ticket comments",
    description=(
        "Retrieve comments for an accessible, non-deleted ticket. "
        "Comments are ordered from oldest to newest. "
        "Internal comments are visible only to admins and agents "
        "who have access to the ticket."
    ),
    responses=COMMENT_LIST_RESPONSES,
)
def get_comments(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    pagination: Pagination = Depends(Pagination),
):
    ticket = db.get(Ticket, ticket_id)

    if ticket is None or ticket.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found",
        )

    check_ticket_access(ticket, current_user)

    can_view_internal = has_role(current_user, "admin") or has_role(
        current_user, "agent"
    )

    statement = (
        select(TicketComment)
        .options(selectinload(TicketComment.author))
        .where(TicketComment.ticket_id == ticket.id)
    )

    # Requesters can only see public comments
    if not can_view_internal:
        statement = statement.where(TicketComment.is_internal.is_(False))

    # Return oldest comments first, with deterministic ordering
    statement = statement.order_by(
        TicketComment.created_at.asc(),
        TicketComment.id.asc(),
    )

    items, total = paginate_query(
        db=db,
        statement=statement,
        pagination=pagination,
    )

    return SuccessResponse[PaginatedResponse[CommentResponse]](
        data=PaginatedResponse[CommentResponse](
            total=total,
            page=pagination.page,
            limit=pagination.limit,
            items=items,
        )
    )
