from pydantic import BaseModel, Field


class DashboardStatusCounts(BaseModel):
    open: int = Field(default=0, ge=0)
    under_review: int = Field(default=0, ge=0)
    in_progress: int = Field(default=0, ge=0)
    resolved: int = Field(default=0, ge=0)
    closed: int = Field(default=0, ge=0)


class DashboardPriorityCounts(BaseModel):
    low: int = Field(default=0, ge=0)
    medium: int = Field(default=0, ge=0)
    high: int = Field(default=0, ge=0)
    urgent: int = Field(default=0, ge=0)


class DashboardResponse(BaseModel):
    total_tickets: int = Field(ge=0)
    by_status: DashboardStatusCounts
    by_priority: DashboardPriorityCounts
    assigned_tickets: int = Field(ge=0)
    unassigned_tickets: int = Field(ge=0)
