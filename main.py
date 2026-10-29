from fastapi import FastAPI, HTTPException
from schema.ticket_schema import TicketCreate, CategoryResponse, TicketResponse
from datetime import datetime

app = FastAPI()

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
categories = [
    {"id": 1, "name": "Hardware"},
    {"id": 2, "name": "Software"},
    {"id": 3, "name": "Network"},
]


@app.get("/tickets", response_model=list[TicketResponse])
def get_test_ticket():
    return tickets


@app.post("/tickets", response_model=TicketResponse, status_code=201)
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
