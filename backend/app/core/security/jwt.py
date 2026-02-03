from datetime import datetime, timedelta, timezone
from typing import Optional
import jwt as pyjwt
from app.core.config.settings import settings


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})

    encoded_jwt = pyjwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    return encoded_jwt


def verify_token(token: str) -> Optional[dict]:
    try:
        payload = pyjwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

        return payload
        
    except pyjwt.ExpiredSignatureError:
        return None
    except pyjwt.InvalidTokenError:
        return None
