from fastapi import FastAPI,Request
from fastapi.middleware.cors import CORSMiddleware
import time
from routes.tickets import router as ticket_router
from routes.category import router as category_router
from routes.admin import router as admin_router
from routes.auth import router as auth_router
from routes.comments import router as comment_router
from routes.users import router as user_router
from routes.departments import router as department_router
from routes.agents import router as agent_router
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.perf_counter()

    print(f"Request received: {request.method} {request.url}")

    response = await call_next(request)

    process_time = time.perf_counter() - start_time

    print(f"Response status: {response.status_code}")
    print(f"Request completed in: {process_time:.4f} seconds")

    return response

app.include_router(ticket_router)
app.include_router(category_router)
app.include_router(admin_router)
app.include_router(auth_router)
app.include_router(comment_router)
app.include_router(user_router)
app.include_router(department_router)
app.include_router(agent_router)