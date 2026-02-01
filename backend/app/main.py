from fastapi import FastAPI
from app.db.session.session import engine, Base
from app.modules.auth.router import router as auth_router

app = FastAPI(
    title="Meeting Management API",
    description="API for managing meetings with Google Calendar integration",
    version="1.0.0"
)

# Include routers
app.include_router(auth_router, prefix="/api/v1")


