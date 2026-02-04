from fastapi import FastAPI
from app.modules.auth.router import router as auth_router, callback_router
from app.modules.meetings.router import router as meetings_router  # اضافه شه

app = FastAPI(
    title="Meeting Management API",
    description="API for managing meetings with Google Calendar integration",
    version="1.0.0"
)

# Include routers
app.include_router(auth_router, prefix="/api/v1")
app.include_router(callback_router)
app.include_router(meetings_router, prefix="/api/v1")  # اضافه شه