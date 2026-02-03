from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from datetime import datetime, timedelta, timezone
from typing import Dict
import os
import requests

from app.core.config.settings import settings


# only for development
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'


# =========================
# OAuth configuration
# =========================

GOOGLE_OAUTH_SCOPES = [
    'openid',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile',
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/calendar.readonly',
    'https://www.googleapis.com/auth/calendar.events',
]


# =========================
# Core OAuth functions
# =========================

def create_google_oauth_flow() -> Flow:
    """
    Create and configure Google OAuth flow instance
    """
    return Flow.from_client_config(
        client_config={
            "web": {
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/v2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=GOOGLE_OAUTH_SCOPES,
        redirect_uri=settings.GOOGLE_REDIRECT_URI,
    )


def get_google_authorization_url() -> str:
    """
    Generate Google OAuth authorization URL
    """
    flow = create_google_oauth_flow()
    authorization_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    return authorization_url


def fetch_google_credentials_from_callback(authorization_response: str) -> Dict:
    """
    Exchange Google OAuth callback URL for access & refresh tokens
    and fetch user profile information.
    """
    flow = create_google_oauth_flow()
    flow.fetch_token(authorization_response=authorization_response)
    credentials = flow.credentials

    # Fetch user info
    response = requests.get("https://www.googleapis.com/oauth2/v2/userinfo", headers={"Authorization": f"Bearer {credentials.token}"}, timeout=10)

    response.raise_for_status()
    user_info = response.json()

    return {
        "credentials": {
            "access_token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "token_uri": credentials.token_uri,
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "scopes": credentials.scopes,
            "expiry": credentials.expiry,
        },
        "user_info": {
            "google_id": user_info.get("id"),
            "email": user_info.get("email"),
            "verified_email": user_info.get("verified_email"),
            "given_name": user_info.get("given_name"),
            "family_name": user_info.get("family_name"),
            "picture": user_info.get("picture"),
            "locale": user_info.get("locale"),
        },
    }


def refresh_google_access_token(refresh_token: str) -> Dict:
    """
    Refresh Google access token using refresh token
    """
    credentials = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
    )

    request = Request()
    credentials.refresh(request)

    return {"access_token": credentials.token, "expiry": credentials.expiry}


def is_google_token_expired(expires_at: datetime) -> bool:
    """
    Check whether the access token is expired (with safety buffer)
    """
    if not expires_at:
        return True

    buffer_time = timedelta(minutes=5)
    now = datetime.now(timezone.utc)  # <-- tz-aware
    return now + buffer_time >= expires_at


def revoke_google_token(token: str) -> bool:
    """
    Revoke Google OAuth token (access or refresh token)
    """
    response = requests.post(
        "https://oauth2.googleapis.com/revoke",
        params={"token": token},
        headers={
            "content-type": "application/x-www-form-urlencoded"
        },
    )
    return response.status_code == 200
