from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional
from app.integrations.google.oauth import GoogleOAuthService
from app.modules.users.repositories import UserRepository
from app.modules.users.models import User
from app.core.security import create_access_token
from app.core.config.settings import settings
from app.modules.auth.schemas import GoogleOAuthResponse, UserResponse


class AuthService:
    
    @staticmethod
    def authenticate_with_google(db: Session, code: str) -> GoogleOAuthResponse:
        """
        Authenticate user with Google OAuth and save/update user data in database
        """
        # Exchange code for tokens
        tokens = GoogleOAuthService.exchange_code_for_tokens(code)
        access_token = tokens['access_token']
        refresh_token = tokens.get('refresh_token')
        expires_at = tokens.get('expiry')
        
        # Get user info from Google
        user_info = GoogleOAuthService.get_user_info(access_token)
        
        # Check if user exists by google_id or email
        user = UserRepository.get_by_google_id(db, user_info['google_id'])
        
        if not user:
            # Check if user exists by email (for linking existing account)
            user = UserRepository.get_by_email(db, user_info['email'])
        
        # Prepare user data
        user_data = {
            'email': user_info['email'],
            'first_name': user_info.get('given_name'),
            'last_name': user_info.get('family_name'),
            'google_id': user_info['google_id'],
            'picture': user_info.get('picture'),
            'locale': user_info.get('locale'),
            'is_verified': user_info.get('verified_email', False),
            'last_login_at': datetime.utcnow()
        }
        
        if user:
            # Update existing user
            user = UserRepository.update(db, user, user_data)
            # Update Google tokens
            UserRepository.update_google_tokens(
                db, 
                user, 
                access_token, 
                refresh_token, 
                expires_at
            )
        else:
            # Create new user
            user_data.update({
                'google_access_token': access_token,
                'google_refresh_token': refresh_token,
                'google_token_expires_at': expires_at,
                'google_calendar_connected': True
            })
            user = UserRepository.create(db, user_data)
        
        # Create JWT access token
        jwt_token = create_access_token(
            data={"sub": str(user.id), "email": user.email}
        )
        
        return GoogleOAuthResponse(
            access_token=jwt_token,
            refresh_token=refresh_token,
            user=UserResponse(
                id=user.id,
                email=user.email,
                first_name=user.first_name,
                last_name=user.last_name,
                picture=user.picture,
                is_active=user.is_active,
                is_verified=user.is_verified,
                google_calendar_connected=user.google_calendar_connected
            )
        )
    
    @staticmethod
    def get_google_authorization_url() -> str:
        """
        Get Google OAuth authorization URL
        """
        return GoogleOAuthService.get_authorization_url()
