from fastapi import FastAPI

app = FastAPI()

tickets = [
    {
        "id": 1,
        "title": "Laptop not working",
        "description": "The laptop does not start.",
        "status": "open",
    },
    {
        "id": 2,
        "title": "Email access issue",
        "description": "The user cannot access their work email.",
        "status": "in_progress",
    },
    {
        "id": 3,
        "title": "Printer not responding",
        "description": "The printer is not responding to print jobs.",
        "status": "closed",
    },
]


@app.get("/")
def home():
    return {"message": "It helpdesk and ticketing"}


@app.get("/tickets")
def get_tickets():
    return tickets

@app.get("/tickets/filter")
def filter_tickets(status: str):
    filtered_tickets = []
    for ticket in tickets:
        if ticket["status"] == status:
            filtered_tickets.append(ticket)
    return filtered_tickets


@app.get("/tickets/{id}")
def get_ticket_by_id(id: int):
    for ticket in tickets:
        if ticket["id"] == id:
            return ticket
    return {"message": "ticket not found"}



