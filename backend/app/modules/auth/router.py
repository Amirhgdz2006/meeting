from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.db.session.session import get_db
from app.modules.auth.services import authenticate_with_google
from app.integrations.google.oauth import get_google_authorization_url

router = APIRouter(prefix="/auth", tags=["Authentication"])

# OAuth callback router without prefix (for root level endpoints)
callback_router = APIRouter(tags=["OAuth Callback"])


@router.get("/google/login")
async def google_login():
    """
    Redirect user to Google OAuth authorization page
    """
    try:
        auth_url = get_google_authorization_url()
        return RedirectResponse(url=auth_url)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate authorization URL: {str(e)}"
        )


@callback_router.get("/oauth2callback")
async def oauth2callback(request: Request, db: Session = Depends(get_db)):
    """
    Handle Google OAuth callback
    This endpoint matches the redirect_uri registered in Google Console
    """
    try:
        # Get the full callback URL (includes code, scope, etc.)
        authorization_response = str(request.url)
        
        # Authenticate user with the full authorization response
        result = authenticate_with_google(db, authorization_response)
        
        # Return JSON response
        return {
            "success": True,
            "message": "Authentication successful",
            "data": {
                "access_token": result.access_token,
                "token_type": result.token_type,
                "user": {
                    "id": result.user.id,
                    "email": result.user.email,
                    "first_name": result.user.first_name,
                    "last_name": result.user.last_name,
                    "picture": result.user.picture,
                    "is_verified": result.user.is_verified,
                    "google_calendar_connected": result.user.google_calendar_connected
                }
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Authentication failed: {str(e)}"
        )


@router.get("/google/callback")
async def google_callback(request: Request, db: Session = Depends(get_db)):
    """
    Handle Google OAuth callback
    Google redirects here with the authorization code and other parameters
    """
    try:
        # Get the full callback URL (includes code, scope, etc.)
        authorization_response = str(request.url)
        
        # Authenticate user with the full authorization response
        result = authenticate_with_google(db, authorization_response)
        
        # Return JSON response
        return {
            "success": True,
            "message": "Authentication successful",
            "data": {
                "access_token": result.access_token,
                "token_type": result.token_type,
                "user": {
                    "id": result.user.id,
                    "email": result.user.email,
                    "first_name": result.user.first_name,
                    "last_name": result.user.last_name,
                    "picture": result.user.picture,
                    "is_verified": result.user.is_verified,
                    "google_calendar_connected": result.user.google_calendar_connected
                }
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Authentication failed: {str(e)}"
        )