from sqlalchemy.orm import Session
from datetime import datetime
from app.integrations.google.oauth import GoogleOAuthService
from app.modules.users.repositories import UserRepository
from app.core.security import create_access_token
from app.modules.auth.schemas import GoogleOAuthResponse, UserResponse


class AuthService:
    
    @staticmethod
    def authenticate_with_google(db: Session, authorization_response: str) -> GoogleOAuthResponse:
        """
        Authenticate user with Google OAuth using the full authorization response URL
        
        Args:
            db: Database session
            authorization_response: Full callback URL from Google
        
        Returns:
            GoogleOAuthResponse with JWT token and user info
        """
        # Fetch credentials and user info from Google
        result = GoogleOAuthService.fetch_credentials_from_callback(authorization_response)
        
        credentials = result['credentials']
        user_info = result['user_info']
        
        # Extract tokens
        access_token = credentials['access_token']
        refresh_token = credentials.get('refresh_token')
        expires_at = credentials.get('expiry')
        
        # Check if user exists by google_id
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
                'google_calendar_connected': True,
                'is_active': True
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
        """Get Google OAuth authorization URL"""
        return GoogleOAuthService.get_authorization_url()