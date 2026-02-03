from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
from app.modules.users.models import User


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """Get user by email address"""
    return db.query(User).filter(User.email == email).first()


def get_user_by_google_id(db: Session, google_id: str) -> Optional[User]:
    """Get user by Google ID"""
    return db.query(User).filter(User.google_id == google_id).first()


def create_user(db: Session, user_data: dict) -> User:
    """Create a new user"""
    user = User(**user_data)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update_user(db: Session, user: User, update_data: dict) -> User:
    """Update user information"""
    for key, value in update_data.items():
        setattr(user, key, value)
    db.commit()
    db.refresh(user)
    return user


def update_user_google_tokens(db: Session, user: User, access_token: str, refresh_token: Optional[str] = None, expires_at: Optional[datetime] = None) -> User:
    """Update user's Google OAuth tokens"""
    user.google_access_token = access_token
    
    if refresh_token:
        user.google_refresh_token = refresh_token
    if expires_at:
        user.google_token_expires_at = expires_at
    user.google_calendar_connected = True
    db.commit()
    db.refresh(user)
    return user