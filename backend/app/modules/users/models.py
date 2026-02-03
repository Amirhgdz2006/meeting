from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text
from datetime import datetime
from app.db.session.session import Base

class User(Base):
    __tablename__ = "users"
    
    # User info
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    org_level = Column(String, nullable=True, default=None)
    hire_date = Column(DateTime, nullable=True, default=None)

    
    # User status
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    
    # Google OAuth fields
    google_id = Column(String, unique=True, nullable=True, index=True)
    google_access_token = Column(Text, nullable=True)
    google_refresh_token = Column(Text, nullable=True)
    google_token_expires_at = Column(DateTime, nullable=True)
    google_calendar_connected = Column(Boolean, default=False)
    
    # Profile info from Google
    picture = Column(String, nullable=True)
    locale = Column(String, nullable=True) # fa or en
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login_at = Column(DateTime, nullable=True)