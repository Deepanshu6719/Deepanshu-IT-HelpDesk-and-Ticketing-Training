from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core.ticket_scope import ticket_visibility_filters
from models.ticket import Ticket
from models.user import User
from schema.dashboard_schema import (
    DashboardPriorityCounts,
    DashboardResponse,
    DashboardStatusCounts,
)


def build_dashboard(
    db: Session,
    current_user: User,
) -> DashboardResponse:
    statement = select(
        func.count().label("total_tickets"),
        func.count().filter(Ticket.status == "open").label("open"),
        func.count().filter(Ticket.status == "under_review").label("under_review"),
        func.count().filter(Ticket.status == "in_progress").label("in_progress"),
        func.count().filter(Ticket.status == "resolved").label("resolved"),
        func.count().filter(Ticket.status == "closed").label("closed"),
        func.count().filter(Ticket.priority == "low").label("low"),
        func.count().filter(Ticket.priority == "medium").label("medium"),
        func.count().filter(Ticket.priority == "high").label("high"),
        func.count().filter(Ticket.priority == "urgent").label("urgent"),
        func.count().filter(Ticket.assigned_to.is_not(None)).label("assigned_tickets"),
        func.count().filter(Ticket.assigned_to.is_(None)).label("unassigned_tickets"),
    ).select_from(Ticket)

    statement = statement.where(*ticket_visibility_filters(current_user))

    result = db.execute(statement).mappings().one()

    return DashboardResponse(
        total_tickets=result["total_tickets"],
        by_status=DashboardStatusCounts(
            open=result["open"],
            under_review=result["under_review"],
            in_progress=result["in_progress"],
            resolved=result["resolved"],
            closed=result["closed"],
        ),
        by_priority=DashboardPriorityCounts(
            low=result["low"],
            medium=result["medium"],
            high=result["high"],
            urgent=result["urgent"],
        ),
        assigned_tickets=result["assigned_tickets"],
        unassigned_tickets=result["unassigned_tickets"],
    )
