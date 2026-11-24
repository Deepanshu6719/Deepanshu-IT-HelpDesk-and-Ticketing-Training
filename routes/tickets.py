from datetime import datetime, timezone
from typing import Literal
from sqlalchemy import select, or_, func
from sqlalchemy.orm import Session, selectinload
from fastapi import APIRouter, HTTPException, Depends, status, Query
from schema.ticket_schema import (
    TicketCreate,
    TicketResponse,
    TicketPatch,
    TicketListResponse,
)
from database.dependencies import get_db
from models.user import User
from models.category import Category
from models.ticket import Ticket
from core.dependencies import get_current_user
from core.permissions import has_role
from models.role import Role
from models.user_role import UserRole
from tasks.notification import send_notification

router = APIRouter(tags=["Tickets"])


@router.get("/tickets", response_model=TicketListResponse)
def get_tickets(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    status_filter: (
        Literal[
            "open",
            "under_review",
            "in_progress",
            "resolved",
            "closed",
        ]
        | None
    ) = Query(default=None),
    priority_filter: Literal["low", "medium", "high", "urgent"] | None = Query(
        default=None
    ),
    category_id: int | None = Query(default=None, gt=0),
    department_id: int | None = Query(default=None, gt=0),
    assigned_to: int | None = Query(default=None, gt=0),
    search: str | None = Query(default=None, min_length=1, max_length=100),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
):
    statement = (
        select(Ticket)
        .options(
            selectinload(Ticket.category),
            selectinload(Ticket.requester),
            selectinload(Ticket.assigned_agent),
        )
        .where(Ticket.is_deleted.is_(False))
    )
    is_admin = has_role(current_user, "admin")
    is_agent = has_role(current_user, "agent")
    if is_admin:
        pass
    elif is_agent:
        statement = statement.where(
            or_(
                Ticket.assigned_to == current_user.id,
                Ticket.requester_id == current_user.id,
            )
        )
    else:
        statement = statement.where(Ticket.requester_id == current_user.id)
    if status_filter is not None:
        statement = statement.where(Ticket.status == status_filter)
    if priority_filter is not None:
        statement = statement.where(Ticket.priority == priority_filter)
    if category_id is not None:
        statement = statement.where(Ticket.category_id == category_id)
    if department_id is not None:
        statement = statement.where(Ticket.department_id == department_id)
    if assigned_to is not None:
        if not is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins can filter tickets by assigned agent",
            )
        statement = statement.where(Ticket.assigned_to == assigned_to)

    if search is not None:
        search_term = search.strip()

        if not search_term:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Search cannot contain only whitespace",
            )

        search_term = f"%{search_term}%"

        statement = statement.where(
            or_(
                Ticket.title.ilike(search_term),
                Ticket.description.ilike(search_term),
            )
        )
    total = db.scalar(
        select(func.count()).select_from(statement.order_by(None).subquery())
    )

    offset = (page - 1) * page_size

    statement = statement.order_by(Ticket.created_at.desc(), Ticket.id.desc())
    statement = statement.offset(offset).limit(page_size)

    tickets = db.scalars(statement).all()
    total_pages = (total + page_size - 1) // page_size

    return {
        "items": tickets,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


@router.post(
    "/tickets", response_model=TicketResponse, status_code=status.HTTP_201_CREATED
)
def create_ticket(
    ticket: TicketCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    statement = select(Category).where(Category.name == ticket.category)

    category = db.scalar(statement)

    if category is None or not category.is_active:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid or inactive category",
        )

    new_ticket = Ticket(
        title=ticket.title,
        description=ticket.description,
        category_id=category.id,
        department_id=category.department_id,
        requester_id=current_user.id,
        assigned_to=None,
        requested_priority=ticket.priority,
        priority=ticket.priority,
        status="open",
    )
    admin_statement = (
        select(User.email)
        .join(User.role_assignments)
        .join(UserRole.role)
        .where(
            Role.name == "admin",
            User.is_active.is_(True),
        )
    )

    admin_emails = db.scalars(admin_statement).unique().all()
    try:
        db.add(new_ticket)
        db.commit()
        db.refresh(new_ticket)

    except Exception:
        db.rollback()
        raise
    # Notify all active admins
    for admin_email in admin_emails:
        send_notification.delay(
            admin_email,
            "New ticket created",
            f"A new ticket #{new_ticket.id} has been created "
            f"by {current_user.email}.",
        )

    # Notify the requester
    send_notification.delay(
        current_user.email,
        "Ticket created successfully",
        f"Your ticket #{new_ticket.id} has been created successfully.",
    )
    return new_ticket


@router.get("/tickets/{ticket_id}", response_model=TicketResponse)
def get_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    statement = (
        select(Ticket)
        .options(
            selectinload(Ticket.category),
            selectinload(Ticket.requester),
            selectinload(Ticket.assigned_agent),
        )
        .where(
            Ticket.id == ticket_id,
            Ticket.is_deleted.is_(False),
        )
    )

    ticket = db.scalar(statement)

    if ticket is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found"
        )

    is_admin = has_role(current_user, "admin")
    is_agent = has_role(current_user, "agent")

    if is_admin:
        return ticket

    if is_agent:
        if (
            ticket.assigned_to == current_user.id
            or ticket.requester_id == current_user.id
        ):
            return ticket

    elif ticket.requester_id == current_user.id:
        return ticket

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found"
    )


@router.patch("/tickets/{ticket_id}", response_model=TicketResponse)
def update_ticket(
    ticket_id: int,
    ticket_update: TicketPatch,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    statement = (
        select(Ticket)
        .options(
            selectinload(Ticket.category),
            selectinload(Ticket.requester),
            selectinload(Ticket.assigned_agent),
        )
        .where(
            Ticket.id == ticket_id,
            Ticket.is_deleted.is_(False),
        )
    )

    ticket = db.scalar(statement)

    if ticket is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found",
        )
    previous_assigned_to = ticket.assigned_to

    is_admin = has_role(current_user, "admin")
    is_agent = has_role(current_user, "agent")

    requester_fields = {
        "title",
        "description",
        "category",
        "requested_priority",
    }

    # Determine which fields the current user can update
    if is_admin:
        allowed_fields = {"status", "priority", "assigned_to"}

        # Admin can also edit their own open, unassigned ticket
        if (
            ticket.requester_id == current_user.id
            and ticket.status == "open"
            and ticket.assigned_to is None
        ):
            allowed_fields.update(requester_fields)

    elif is_agent and ticket.assigned_to == current_user.id:
        allowed_fields = {"status"}

    elif (
        ticket.requester_id == current_user.id
        and ticket.status == "open"
        and ticket.assigned_to is None
    ):
        allowed_fields = requester_fields

    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found",
        )

    update_data = ticket_update.model_dump(exclude_unset=True)

    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No fields provided for update",
        )

    # Reject explicit null values, except assigned_to
    for key, value in update_data.items():
        if value is None and key != "assigned_to":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"{key} cannot be null",
            )

    # Check permissions against original client-submitted fields
    submitted_fields = set(update_data.keys())

    if not submitted_fields.issubset(allowed_fields):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not allowed to update these fields",
        )

    # Resolve category name into database IDs
    if "category" in update_data:
        category_statement = select(Category).where(
            Category.name == update_data["category"]
        )

        category = db.scalar(category_statement)

        if category is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid category",
            )

        update_data["category_id"] = category.id
        update_data["department_id"] = category.department_id

        del update_data["category"]

    # Validate assigned agent
    if "assigned_to" in update_data and update_data["assigned_to"] is not None:
        agent = db.get(User, update_data["assigned_to"])

        if agent is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Agent not found",
            )

        if agent.id == ticket.requester_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Requester cannot be assigned as their own agent",
            )

        if not has_role(agent, "agent"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Selected user is not an agent",
            )

        # Do not assign tickets to inactive agents
        if not agent.is_active:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Cannot assign a ticket to an inactive agent",
            )

        target_department_id = update_data.get(
            "department_id",
            ticket.department_id,
        )

        if agent.department_id != target_department_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Agent does not belong to the ticket department",
            )
    # Apply updates
    for key, value in update_data.items():
        setattr(ticket, key, value)

    try:
        db.commit()
        db.refresh(ticket)

    except Exception:
        db.rollback()
        raise

    # Notify only when a ticket is newly assigned or reassigned
    if ticket.assigned_to is not None and ticket.assigned_to != previous_assigned_to:
        assigned_agent = ticket.assigned_agent
        requester = ticket.requester
        # Notify the assigned agent
        send_notification.delay(
            assigned_agent.email,
            "New ticket assigned",
            f"Ticket #{ticket.id} - {ticket.title} has been assigned to you.",
        )

        # Notify the requester
        send_notification.delay(
            requester.email,
            "Ticket assigned",
            f"Your ticket #{ticket.id} has been assigned to an agent.",
        )
    return ticket


@router.delete("/tickets/{ticket_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    statement = (
        select(Ticket)
        .options(
            selectinload(Ticket.category),
            selectinload(Ticket.requester),
            selectinload(Ticket.assigned_agent),
        )
        .where(
            Ticket.id == ticket_id,
            Ticket.is_deleted.is_(False),
        )
    )

    ticket = db.scalar(statement)

    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    is_admin = has_role(current_user, "admin")

    if is_admin:
        pass

    elif (
        ticket.requester_id == current_user.id
        and ticket.status == "open"
        and ticket.assigned_to is None
    ):
        pass

    else:
        raise HTTPException(status_code=404, detail="Ticket not found")

    ticket.is_deleted = True

    ticket.updated_at = datetime.now(timezone.utc)
    ticket.deleted_at = datetime.now(timezone.utc)

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    return None
