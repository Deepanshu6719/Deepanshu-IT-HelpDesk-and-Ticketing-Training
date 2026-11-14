from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session
from fastapi import APIRouter, HTTPException, Depends
from schema.ticket_schema import (
    TicketCreate,
    TicketResponse,
    TicketUpdate,
    TicketReplace,
)
from database.dependencies import get_db
from models.category import Category
from models.ticket import Ticket

router = APIRouter()

@router.get("/tickets", response_model=list[TicketResponse])
def get_tickets(db: Session = Depends(get_db)):
    statement = select(Ticket).where(Ticket.is_deleted.is_(False))
    tickets = db.scalars(statement).all()
    return tickets

@router.post(
    "/tickets",
    response_model=TicketResponse,
    status_code=201,
)
def create_ticket(ticket: TicketCreate, db: Session = Depends(get_db)):
    statement = select(Category).where(Category.name == ticket.category)
    category = db.scalar(
        statement
    )  # retrieving the category from the db which is given in the request
    # and now we use it to get the category_id and department_id of that category in the ticket object
    if category is None:
        raise HTTPException(status_code=422, detail="Category not found")
    new_ticket = Ticket(
        title=ticket.title,
        description=ticket.description,
        category_id=category.id,
        department_id=category.department_id,
        requester_id=1,
        assigned_to=None,
        requested_priority=ticket.priority,
        priority=ticket.priority,
        status="open",
    )
    try:
        db.add(new_ticket)
        db.commit()
        db.refresh(new_ticket)
    except Exception:
        db.rollback()
        raise
    return new_ticket

@router.get("/tickets/{ticket_id}", response_model=TicketResponse)
def get_ticket(ticket_id: int, db: Session = Depends(get_db)):
    statement = select(Ticket).where(
        Ticket.id == ticket_id, Ticket.is_deleted.is_(False)
    )
    ticket = db.scalar(statement)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket

@router.delete("/tickets/{ticket_id}", status_code=204)
def delete_ticket(ticket_id: int,db:Session=Depends(get_db)):
    statement = select(Ticket).where(
        Ticket.id == ticket_id,
        Ticket.is_deleted.is_(False),
        Ticket.status == "open",
        Ticket.assigned_to.is_(None),
        Ticket.requester_id
        == 1,  # Temporary test requester; replace with authenticated user ID later
    )
    ticket = db.scalar(statement)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    ticket.is_deleted=True
    ticket.deleted_at=datetime.now(timezone.utc)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    return

@router.patch("/tickets/{ticket_id}", response_model=TicketResponse)
def update_ticket(
    ticket_id: int, ticket_update: TicketUpdate, db: Session = Depends(get_db)
):
    statement = select(Ticket).where(
        Ticket.id == ticket_id, Ticket.is_deleted.is_(False)
    )
    ticket = db.scalar(statement)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    update_data = ticket_update.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=422, detail="No fields provided for update")
    # First validate all supplied values
    for key, value in update_data.items():
        if value is None:
            raise HTTPException(status_code=422, detail=f"{key} cannot be null")
    # Then update the object
    for key, value in update_data.items():
        setattr(ticket, key, value)
    try:
        db.commit()
        db.refresh(ticket)
    except Exception:
        db.rollback()
        raise
    return ticket

@router.put("/tickets/{ticket_id}", response_model=TicketResponse)
def replace_ticket(
    ticket_id: int, ticket_replace: TicketReplace, db: Session = Depends(get_db)
):
    statement = select(Ticket).where(
        Ticket.id == ticket_id,
        Ticket.is_deleted.is_(False),
        Ticket.status == "open",
        Ticket.assigned_to.is_(None),
        Ticket.requester_id
        == 1,  # Temporary test requester; replace with authenticated user ID later
    )
    ticket = db.scalar(statement)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    edit_data = ticket_replace.model_dump()
    category_statement = select(Category).where(
        Category.name == ticket_replace.category
    )
    category_query = db.scalar(category_statement)

    if category_query is None:
        raise HTTPException(status_code=422, detail="Invalid Category")

    ticket.title=edit_data["title"]
    ticket.description=edit_data["description"]
    ticket.category_id=category_query.id
    ticket.department_id=category_query.department_id
    ticket.requested_priority=edit_data["priority"]
    try:
        db.commit()
        db.refresh(ticket)
    except Exception:
        db.rollback()
        raise
    return ticket
