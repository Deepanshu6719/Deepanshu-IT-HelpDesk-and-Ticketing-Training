from datetime import datetime

from fastapi import APIRouter, HTTPException
from schema.ticket_schema import (
    TicketCreate,
    TicketResponse,
    TicketUpdate,
    TicketReplace,
)
from routes.category import categories

router = APIRouter()

tickets = [
    {
        "id": 1,
        "title": "something",
        "description": "something happened",
        "category": {"id": 1, "name": "Hardware"},
        "priority": "medium",
        "status": "open",
        "assigned_to": None,
        "created_at": "2026-10-29T11:59:58.746093",
        "updated_at": "2026-10-29T11:59:58.746093",
    },
]


@router.get("/tickets", response_model=list[TicketResponse])
def get_test_ticket():
    return tickets


@router.post("/tickets", response_model=TicketResponse, status_code=201)
def create_test_ticket(ticket: TicketCreate):
    category = next(
        (item for item in categories if item["name"] == ticket.category), None
    )

    if category is None:
        raise HTTPException(status_code=422, detail="Category not found")

    now = datetime.now()

    new_ticket = {
        "id": len(tickets) + 1,
        "title": ticket.title,
        "description": ticket.description,
        "category": category,
        "priority": ticket.priority,
        "status": "open",
        "assigned_to": None,
        "created_at": now,
        "updated_at": now,
    }

    tickets.append(new_ticket)
    return new_ticket


@router.get("/tickets/{ticket_id}", response_model=TicketResponse)
def get_ticket(ticket_id: int):
    for ticket in tickets:
        if ticket["id"] == ticket_id:
            return ticket
    raise HTTPException(status_code=404, detail=f"Ticket with ID:{ticket_id} not found")


@router.delete("/tickets/{ticket_id}", status_code=204)
def delete_ticket(ticket_id: int):
    tic_del = next((ticket for ticket in tickets if ticket["id"] == ticket_id), None)
    if tic_del is None:
        raise HTTPException(
            status_code=404, detail=f"Ticket with ID:{ticket_id} not found"
        )
    tickets.remove(tic_del)
    return


@router.patch("/tickets/{ticket_id}", response_model=TicketResponse)
def update_ticket(ticket_id: int, ticket_update: TicketUpdate):
    ticket_to_update = next(
        (ticket for ticket in tickets if ticket["id"] == ticket_id), None
    )
    if ticket_to_update is None:
        raise HTTPException(
            status_code=404, detail=f"Ticket with ID:{ticket_id} not found"
        )
    update_data = ticket_update.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="Bad Request")
    if any(value is None for value in update_data.values()):
        raise HTTPException(status_code=422, detail="Unprocessable entity")
    for key, value in update_data.items():
        ticket_to_update[key] = value
    ticket_to_update["updated_at"] = datetime.now()
    return ticket_to_update


@router.put("/tickets/{ticket_id}", response_model=TicketResponse)
def replace_ticket(ticket_id: int, ticket_replace: TicketReplace):
    ticket_to_replace = next(
        (ticket for ticket in tickets if ticket["id"] == ticket_id), None
    )
    if ticket_to_replace is None:
        raise HTTPException(
            status_code=404, detail=f"Ticket with ID:{ticket_id} not found"
        )
    replace_data = ticket_replace.model_dump()
    matching_category = next(
        (
            category
            for category in categories
            if category["name"] == replace_data["category"]
        ),
        None,
    )

    if matching_category is None:
        raise HTTPException(status_code=422, detail="Category not found")

    ticket_to_replace["title"] = replace_data["title"]
    ticket_to_replace["description"] = replace_data["description"]
    ticket_to_replace["category"] = matching_category
    ticket_to_replace["priority"] = replace_data["priority"]
    ticket_to_replace["status"] = replace_data["status"]
    ticket_to_replace["assigned_to"] = replace_data["assigned_to"]
    ticket_to_replace["updated_at"] = datetime.now()
    return ticket_to_replace
