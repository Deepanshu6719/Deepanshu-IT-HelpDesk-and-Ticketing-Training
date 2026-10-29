from fastapi import FastAPI, HTTPException
from schema.ticket_schema import TicketCreate, CategoryResponse, TicketResponse
from datetime import datetime
from routes.tickets import router as ticket_router
from routes.category import router as category_router
app = FastAPI()

app.include_router(ticket_router)
app.include_router(category_router)


