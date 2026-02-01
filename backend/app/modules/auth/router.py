from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session.session import get_db
from app.modules.auth.services import AuthService
from app.modules.auth.schemas import GoogleOAuthCallbackRequest, GoogleOAuthResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.get("/google/login", response_model=dict)
async def google_login():
    """
    Get Google OAuth authorization URL
    """
    try:
        auth_url = AuthService.get_google_authorization_url()
        return {"authorization_url": auth_url}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate authorization URL: {str(e)}"
        )


@router.post("/google/callback", response_model=GoogleOAuthResponse)
async def google_callback(
    request: GoogleOAuthCallbackRequest,
    db: Session = Depends(get_db)
):
    """
    Handle Google OAuth callback and authenticate user
    """
    try:
        result = AuthService.authenticate_with_google(db, request.code)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Authentication failed: {str(e)}"
        )
