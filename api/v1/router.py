from fastapi import APIRouter

from api.docs.errors import (
    INTERNAL_SERVER_ERROR_RESPONSE,
    VALIDATION_ERROR_RESPONSE,
)
from routes.admin import router as admin_router
from routes.agents import router as agent_router
from routes.auth import router as auth_router
from routes.category import router as category_router
from routes.comments import router as comment_router
from routes.departments import router as department_router
from routes.tickets import router as ticket_router
from routes.users import router as user_router

router = APIRouter(
    prefix="/api/v1",
    responses={
        422: VALIDATION_ERROR_RESPONSE,
        500: INTERNAL_SERVER_ERROR_RESPONSE,
    },
)

router.include_router(auth_router)
router.include_router(ticket_router)
router.include_router(category_router)
router.include_router(admin_router)
router.include_router(comment_router)
router.include_router(user_router)
router.include_router(department_router)
router.include_router(agent_router)
