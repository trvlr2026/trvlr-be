from fastapi import APIRouter, Depends, HTTPException, status
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth import create_access_token, hash_password, verify_password
from app.config import settings
from app.database import get_db
from app.models import AuthProvider, User

router = APIRouter(prefix="/auth", tags=["auth"])


# --- Schemas ---


class SignupRequest(BaseModel):
    email: str
    password: str
    display_name: str = ""


class SigninRequest(BaseModel):
    email: str
    password: str


class GoogleAuthRequest(BaseModel):
    id_token: str


class AuthResponse(BaseModel):
    user_id: str
    token: str
    display_name: str


# --- Local Auth ---


@router.post("/signup", response_model=AuthResponse, status_code=201)
async def signup(payload: SignupRequest, db: Session = Depends(get_db)):
    """Register with email + password."""
    # Check if email already exists
    existing = db.execute(
        text("SELECT id FROM users WHERE email = :email"),
        {"email": payload.email},
    ).fetchone()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    # Create user
    user = User(
        email=payload.email,
        display_name=payload.display_name or payload.email.split("@")[0],
    )
    db.add(user)
    db.flush()

    # Create auth provider entry
    auth_provider = AuthProvider(
        user_id=user.id,
        provider="local",
        provider_user_id=payload.email,
        password_hash=hash_password(payload.password),
    )
    db.add(auth_provider)
    db.commit()

    token = create_access_token(user.id)
    return AuthResponse(user_id=user.id, token=token, display_name=user.display_name)


@router.post("/signin", response_model=AuthResponse)
async def signin(payload: SigninRequest, db: Session = Depends(get_db)):
    """Sign in with email + password."""
    # Find auth provider for local + email
    result = db.execute(
        text("""
            SELECT ap.user_id, ap.password_hash, u.display_name
            FROM auth_providers ap
            JOIN users u ON u.id = ap.user_id
            WHERE ap.provider = 'local' AND ap.provider_user_id = :email
        """),
        {"email": payload.email},
    ).fetchone()

    if not result or not verify_password(payload.password, result.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    token = create_access_token(result.user_id)
    return AuthResponse(user_id=result.user_id, token=token, display_name=result.display_name)


# --- Google Auth ---


@router.post("/google", response_model=AuthResponse)
async def google_auth(payload: GoogleAuthRequest, db: Session = Depends(get_db)):
    """Authenticate with Google ID token."""
    try:
        idinfo = google_id_token.verify_oauth2_token(
            payload.id_token,
            google_requests.Request(),
            settings.google_client_id,
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google token",
        )

    google_sub = idinfo["sub"]
    email = idinfo.get("email")
    name = idinfo.get("name", "")

    # Check if this Google account is already linked
    existing_provider = db.execute(
        text("""
            SELECT ap.user_id, u.display_name
            FROM auth_providers ap
            JOIN users u ON u.id = ap.user_id
            WHERE ap.provider = 'google' AND ap.provider_user_id = :sub
        """),
        {"sub": google_sub},
    ).fetchone()

    if existing_provider:
        token = create_access_token(existing_provider.user_id)
        return AuthResponse(
            user_id=existing_provider.user_id,
            token=token,
            display_name=existing_provider.display_name,
        )

    # Check if email matches an existing user (link accounts)
    existing_user = None
    if email:
        existing_user = db.execute(
            text("SELECT id, display_name FROM users WHERE email = :email"),
            {"email": email},
        ).fetchone()

    if existing_user:
        # Link Google to existing user
        auth_provider = AuthProvider(
            user_id=existing_user.id,
            provider="google",
            provider_user_id=google_sub,
        )
        db.add(auth_provider)
        db.commit()

        token = create_access_token(existing_user.id)
        return AuthResponse(
            user_id=existing_user.id,
            token=token,
            display_name=existing_user.display_name,
        )

    # Brand new user
    user = User(email=email, display_name=name or (email.split("@")[0] if email else "User"))
    db.add(user)
    db.flush()

    auth_provider = AuthProvider(
        user_id=user.id,
        provider="google",
        provider_user_id=google_sub,
    )
    db.add(auth_provider)
    db.commit()

    token = create_access_token(user.id)
    return AuthResponse(user_id=user.id, token=token, display_name=user.display_name)
