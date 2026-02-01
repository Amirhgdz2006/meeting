from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class UserResponse(BaseModel):
    id: int
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    picture: Optional[str] = None
    is_active: bool
    is_verified: bool
    google_calendar_connected: bool
    
    class Config:
        from_attributes = True


class GoogleOAuthCallbackRequest(BaseModel):
    code: str


class GoogleOAuthResponse(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    user: UserResponse
