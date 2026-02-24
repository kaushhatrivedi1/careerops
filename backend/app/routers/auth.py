"""
Authentication router.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.models.user import User

router = APIRouter()
bearer_scheme = HTTPBearer(auto_error=False)


class Token(BaseModel):
    access_token: str
    token_type: str


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str
    password: str


class GoogleAuthRequest(BaseModel):
    id_token: str


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: Optional[str]
    auth_provider: str
    created_at: datetime

    class Config:
        from_attributes = True


class AuthResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse


def _create_access_token(user: User) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    token_data = {
        "sub": str(user.id),
        "email": user.email,
        "provider": user.auth_provider,
        "exp": expire,
    }
    return jwt.encode(token_data, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def _to_user_response(user: User) -> UserResponse:
    return UserResponse(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        auth_provider=user.auth_provider,
        created_at=user.created_at,
    )


async def _get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


def _verify_google_id_token(google_id_token: str) -> dict:
    """
    Verify Google ID token and return claims.
    """
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GOOGLE_CLIENT_ID is not configured",
        )

    try:
        from google.auth.transport import requests as google_requests
        from google.oauth2 import id_token as google_id_token_lib
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="google-auth dependency not installed",
        )

    try:
        claims = google_id_token_lib.verify_oauth2_token(
            google_id_token,
            google_requests.Request(),
            settings.GOOGLE_CLIENT_ID,
        )
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Google ID token")

    if claims.get("iss") not in {"accounts.google.com", "https://accounts.google.com"}:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token issuer")
    if not claims.get("email_verified"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Google email not verified")
    return claims


@router.post("/register", response_model=UserResponse)
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    """
    Register local user (placeholder until password auth is implemented).
    """
    existing = await _get_user_by_email(db, user_data.email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        email=user_data.email,
        full_name=user_data.full_name,
        auth_provider="local",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return _to_user_response(user)


@router.post("/token", response_model=Token)
async def login(email: EmailStr, password: str, db: AsyncSession = Depends(get_db)):
    """
    Legacy email/password login endpoint.
    """
    _ = password
    user = await _get_user_by_email(db, str(email))
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = _create_access_token(user)
    return Token(access_token=token, token_type="bearer")


@router.post("/google", response_model=AuthResponse)
async def google_login(payload: GoogleAuthRequest, db: AsyncSession = Depends(get_db)):
    """
    Sign in or register via Google ID token.
    """
    claims = _verify_google_id_token(payload.id_token)
    email = claims.get("email")
    google_sub = claims.get("sub")
    full_name = claims.get("name")

    if not email or not google_sub:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Google token missing identity claims")

    user = await _get_user_by_email(db, email)
    if user is None:
        user = User(
            email=email,
            full_name=full_name,
            auth_provider="google",
            google_sub=google_sub,
            last_login_at=datetime.now(timezone.utc),
        )
        db.add(user)
    else:
        user.auth_provider = "google"
        user.google_sub = google_sub
        if not user.full_name and full_name:
            user.full_name = full_name
        user.last_login_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(user)

    token = _create_access_token(user)
    return AuthResponse(
        access_token=token,
        token_type="bearer",
        user=_to_user_response(user),
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    token: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Get current user from bearer token.
    """
    raw_token = credentials.credentials if credentials else token
    if not raw_token:
        raise HTTPException(status_code=401, detail="Missing token")

    try:
        payload = jwt.decode(raw_token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        user_id = payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return _to_user_response(user)
