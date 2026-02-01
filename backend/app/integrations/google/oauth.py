from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from datetime import datetime, timedelta
from typing import Dict
import os
import requests

from app.core.config.settings import settings


# only for development
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'


class GoogleOAuthService:
    
    SCOPES = [
        'openid',
        'https://www.googleapis.com/auth/userinfo.email',
        'https://www.googleapis.com/auth/userinfo.profile',
        'https://www.googleapis.com/auth/calendar',
        'https://www.googleapis.com/auth/calendar.readonly',
        'https://www.googleapis.com/auth/calendar.events',
    ]

    @staticmethod
    def _create_flow() -> Flow:
        """Create OAuth flow instance"""
        return Flow.from_client_config(
            client_config={
                "web": {
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "auth_uri": "https://accounts.google.com/o/oauth2/v2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                }
            },
            scopes=GoogleOAuthService.SCOPES,
            redirect_uri=settings.GOOGLE_REDIRECT_URI,
        )

    @staticmethod
    def get_authorization_url() -> str:
        """Get Google OAuth authorization URL"""
        flow = GoogleOAuthService._create_flow()
        auth_url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
        )
        return auth_url
    
    @staticmethod
    def fetch_credentials_from_callback(authorization_response: str) -> Dict:
        """
        Exchange authorization response URL for tokens
        
        Args:
            authorization_response: Full callback URL from Google (e.g., http://localhost:8000/callback?code=xxx&scope=xxx)
        
        Returns:
            Dict containing credentials and user info
        """
        flow = GoogleOAuthService._create_flow()
        flow.fetch_token(authorization_response=authorization_response)
        credentials = flow.credentials
        
        # Get user info using the access token
        resp = requests.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {credentials.token}"},
            timeout=10,
        )
        resp.raise_for_status()
        user_info = resp.json()
        
        return {
            'credentials': {
                'access_token': credentials.token,
                'refresh_token': credentials.refresh_token,
                'token_uri': credentials.token_uri,
                'client_id': credentials.client_id,
                'client_secret': credentials.client_secret,
                'scopes': credentials.scopes,
                'expiry': credentials.expiry
            },
            'user_info': {
                'google_id': user_info.get('id'),
                'email': user_info.get('email'),
                'verified_email': user_info.get('verified_email'),
                'given_name': user_info.get('given_name'),
                'family_name': user_info.get('family_name'),
                'picture': user_info.get('picture'),
                'locale': user_info.get('locale')
            }
        }

    @staticmethod
    def refresh_access_token(refresh_token: str) -> Dict:
        """Refresh access token using refresh token"""
        credentials = Credentials(
            None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.GOOGLE_CLIENT_ID,
            client_secret=settings.GOOGLE_CLIENT_SECRET
        )
        
        request = Request()
        credentials.refresh(request)
        
        return {
            'access_token': credentials.token,
            'expiry': credentials.expiry
        }
    
    @staticmethod
    def is_token_expired(expires_at: datetime) -> bool:
        """Check if token is expired"""
        if not expires_at:
            return True
        
        buffer_time = timedelta(minutes=5)
        return datetime.utcnow() + buffer_time >= expires_at
    
    @staticmethod
    def revoke_token(token: str) -> bool:
        """Revoke access token"""
        response = requests.post(
            'https://oauth2.googleapis.com/revoke',
            params={'token': token},
            headers={'content-type': 'application/x-www-form-urlencoded'}
        )
        
        return response.status_code == 200