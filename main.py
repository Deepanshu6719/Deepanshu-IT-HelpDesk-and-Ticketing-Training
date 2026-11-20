from fastapi import FastAPI
from routes.tickets import router as ticket_router
from routes.category import router as category_router
from routes.admin import router as admin_router
from routes.auth import router as auth_router
from routes.comments import router as comment_router
from routes.users import router as user_router
from routes.departments import router as department_router
from routes.agents import router as agent_router
app = FastAPI()

app.include_router(ticket_router)
app.include_router(category_router)
app.include_router(admin_router)
app.include_router(auth_router)
app.include_router(comment_router)
app.include_router(user_router)
app.include_router(department_router)
app.include_router(agent_router)