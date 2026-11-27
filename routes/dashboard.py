import structlog
from fastapi import APIRouter, Depends
from pydantic import ValidationError
from sqlalchemy.orm import Session

from core.cache import get_cache, set_cache
from core.dashboard_cache import (
    DASHBOARD_CACHE_TTL,
    get_dashboard_cache_key,
    get_dashboard_generation,
)
from core.dependencies import get_current_user
from database.dependencies import get_db
from models.user import User
from schema.common_schema import SuccessResponse
from schema.dashboard_schema import DashboardResponse
from services.dashboard import build_dashboard

router = APIRouter(tags=["Dashboard"])

logger = structlog.get_logger(__name__)


@router.get(
    "/dashboard/me",
    response_model=SuccessResponse[DashboardResponse],
    summary="Get current user's dashboard",
    description=(
        "Retrieve cached ticket statistics based on "
        "the authenticated user's role, ownership "
        "and agent assignments. Soft-deleted tickets "
        "are excluded."
    ),
)
def get_my_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    generation = get_dashboard_generation()

    cache_key = None

    if generation is not None:
        cache_key = get_dashboard_cache_key(
            current_user=current_user,
            generation=generation,
        )

        cached_dashboard = get_cache(cache_key)

        if cached_dashboard is not None:
            try:
                dashboard = DashboardResponse.model_validate(cached_dashboard)

            except ValidationError:
                logger.warning(
                    "invalid_dashboard_cache_payload",
                )

            else:
                logger.debug("dashboard_cache_hit")

                return SuccessResponse[DashboardResponse](
                    data=dashboard,
                )

    logger.debug("dashboard_cache_miss")

    dashboard = build_dashboard(
        db=db,
        current_user=current_user,
    )

    if cache_key is not None:
        set_cache(
            cache_key,
            dashboard.model_dump(mode="json"),
            ttl=DASHBOARD_CACHE_TTL,
        )

    return SuccessResponse[DashboardResponse](
        data=dashboard,
    )
