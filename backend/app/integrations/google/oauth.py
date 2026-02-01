from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from datetime import datetime, timedelta
from typing import Optional, Dict
import os

from app.core.config.settings import settings


# only for development
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'


class GoogleOAuthService:
    
    SCOPES = [
        'https://www.googleapis.com/auth/userinfo.email',
        'https://www.googleapis.com/auth/userinfo.profile',
        'https://www.googleapis.com/auth/calendar',
        'https://www.googleapis.com/auth/calendar.events',
        'openid'
    ]


    @staticmethod
    def get_authorization_url() -> str:

        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [settings.GOOGLE_REDIRECT_URI]
                }
            },
            scopes=GoogleOAuthService.SCOPES,
            redirect_uri=settings.GOOGLE_REDIRECT_URI
        )
        
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent'
        )
        
        return authorization_url
    
    
    @staticmethod
    def exchange_code_for_tokens(code: str) -> Dict:

        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [settings.GOOGLE_REDIRECT_URI]
                }
            },
            scopes=GoogleOAuthService.SCOPES,
            redirect_uri=settings.GOOGLE_REDIRECT_URI
        )
        
        flow.fetch_token(code=code)
        credentials = flow.credentials
        
        return {
            'access_token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes,
            'expiry': credentials.expiry
        }
    

    @staticmethod
    def get_user_info(access_token: str) -> Dict:

        credentials = Credentials(token=access_token)
        
        service = build('oauth2', 'v2', credentials=credentials)
        user_info = service.userinfo().get().execute()
        
        return {
            'google_id': user_info.get('id'),
            'email': user_info.get('email'),
            'verified_email': user_info.get('verified_email'),
            'full_name': user_info.get('name'),
            'given_name': user_info.get('given_name'),
            'family_name': user_info.get('family_name'),
            'picture': user_info.get('picture'),
            'locale': user_info.get('locale')
        }
    

    @staticmethod
    def refresh_access_token(refresh_token: str) -> Dict:

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

        if not expires_at:
            return True
        
        buffer_time = timedelta(minutes=5)
        return datetime.utcnow() + buffer_time >= expires_at
    
    @staticmethod
    def revoke_token(token: str) -> bool:

        import requests
        
        response = requests.post(
            'https://oauth2.googleapis.com/revoke',
            params={'token': token},
            headers={'content-type': 'application/x-www-form-urlencoded'}
        )
        
        return response.status_code == 200