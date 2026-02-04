from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime
from app.modules.users.models import User


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """Get user by email address"""
    return db.query(User).filter(User.email == email).first()


def get_user_by_google_id(db: Session, google_id: str) -> Optional[User]:
    """Get user by Google ID"""
    return db.query(User).filter(User.google_id == google_id).first()


def get_users_by_emails(db: Session, emails: List[str]) -> List[User]:
    """Get multiple users by their email addresses"""
    return db.query(User).filter(User.email.in_(emails)).all()


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


def update_user_google_tokens(
    db: Session, 
    user: User, 
    access_token: str, 
    refresh_token: Optional[str] = None, 
    expires_at: Optional[datetime] = None
) -> User:
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


def check_and_refresh_google_token(db: Session, user: User) -> User:
    """
    Check if user's Google token is expired and refresh if needed
    Returns updated user object
    """
    from app.integrations.google.oauth import is_google_token_expired, refresh_google_access_token
    
    if not user.google_refresh_token:
        raise ValueError("User does not have a refresh token")
    
    # Check if token is expired
    if is_google_token_expired(user.google_token_expires_at):
        # Refresh the token
        new_tokens = refresh_google_access_token(user.google_refresh_token)
        
        # Update user with new tokens
        user = update_user_google_tokens(
            db, 
            user, 
            new_tokens['access_token'],
            expires_at=new_tokens['expiry']
        )
    
    return user