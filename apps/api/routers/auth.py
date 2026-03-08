"""
Auth Router - User authentication (SaaS mode only).

Base path: /api/v1/auth
"""

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from jose import jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr

from apps.api.config import settings
from apps.api.dependencies import CurrentUser, DbSession, OptionalUser
from apps.api.middleware.error_handler import AuthenticationError

router = APIRouter()

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def wrap_response(data: Any, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    """Wrap response data in standard format."""
    return {
        "data": data,
        "meta": {
            "version": "v1",
            "timestamp": datetime.utcnow().isoformat(),
            **(meta or {}),
        },
    }


# =============================================================================
# Token Creation
# =============================================================================


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.jwt_access_token_expire_minutes))
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(data: dict) -> str:
    """Create a JWT refresh token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=settings.jwt_refresh_token_expire_days)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def hash_password(password: str) -> str:
    """Hash a password."""
    return pwd_context.hash(password)


# =============================================================================
# Request/Response Models
# =============================================================================


class SignupRequest(BaseModel):
    """User signup request."""

    email: EmailStr
    password: str
    name: str | None = None
    organization_name: str | None = None


class LoginRequest(BaseModel):
    """User login request."""

    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Token response."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(BaseModel):
    """Token refresh request."""

    refresh_token: str


class PasswordResetRequest(BaseModel):
    """Password reset request."""

    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Password reset confirmation."""

    token: str
    new_password: str


class ChangePasswordRequest(BaseModel):
    """Change password request."""

    current_password: str
    new_password: str


# =============================================================================
# Authentication Endpoints
# =============================================================================


@router.post("/signup", response_model=dict)
async def signup(
    data: SignupRequest,
    session: DbSession,
):
    """
    Create a new user account.

    If organization_name is provided, a new organization is created.
    Otherwise, the user will need to join an existing organization.
    """
    # TODO: Check if email already exists
    # TODO: Create user in database
    # TODO: Create organization if name provided
    # TODO: Send verification email

    user_id = uuid4()
    org_id = uuid4() if data.organization_name else None

    access_token = create_access_token({
        "sub": str(user_id),
        "email": data.email,
        "org_id": str(org_id) if org_id else None,
        "role": "owner" if org_id else None,
    })
    refresh_token = create_refresh_token({"sub": str(user_id)})

    return wrap_response({
        "user": {
            "id": str(user_id),
            "email": data.email,
            "name": data.name,
            "email_verified": False,
        },
        "organization": {
            "id": str(org_id),
            "name": data.organization_name,
        } if org_id else None,
        "tokens": {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": settings.jwt_access_token_expire_minutes * 60,
        },
    })


@router.post("/login", response_model=dict)
async def login(
    data: LoginRequest,
    session: DbSession,
):
    """
    Log in with email and password.

    Returns access and refresh tokens.
    """
    # TODO: Look up user by email
    # TODO: Verify password
    # TODO: Get user's organization(s)

    # Placeholder - would normally validate against DB
    raise AuthenticationError("Invalid email or password")


@router.post("/token", response_model=dict)
async def login_oauth(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: DbSession = None,
):
    """
    OAuth2 compatible token endpoint.

    For integration with OAuth2 clients.
    """
    # TODO: Validate credentials
    raise AuthenticationError("Invalid credentials")


@router.post("/refresh", response_model=dict)
async def refresh_token(
    data: RefreshRequest,
    session: DbSession,
):
    """
    Refresh an access token using a refresh token.
    """
    try:
        payload = jwt.decode(
            data.refresh_token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )

        if payload.get("type") != "refresh":
            raise AuthenticationError("Invalid refresh token")

        user_id = payload.get("sub")

        # TODO: Look up user and get current org
        # For now, create new tokens with same claims

        access_token = create_access_token({
            "sub": user_id,
            # TODO: Include email, org_id, role from DB
        })

        return wrap_response({
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": settings.jwt_access_token_expire_minutes * 60,
        })

    except jwt.ExpiredSignatureError:
        raise AuthenticationError("Refresh token expired")
    except jwt.JWTError:
        raise AuthenticationError("Invalid refresh token")


@router.post("/logout", response_model=dict)
async def logout(
    user: CurrentUser,
):
    """
    Log out the current user.

    Note: JWTs are stateless, so this is primarily for client-side cleanup.
    For enhanced security, implement a token blacklist.
    """
    # TODO: Add token to blacklist if implementing server-side logout
    return wrap_response({
        "message": "Logged out successfully",
    })


# =============================================================================
# Password Management
# =============================================================================


@router.post("/password/reset", response_model=dict)
async def request_password_reset(
    data: PasswordResetRequest,
    session: DbSession,
):
    """
    Request a password reset.

    Sends a reset link to the user's email.
    """
    # TODO: Generate reset token
    # TODO: Send email with reset link

    return wrap_response({
        "message": "If an account exists with this email, a reset link has been sent.",
    })


@router.post("/password/reset/confirm", response_model=dict)
async def confirm_password_reset(
    data: PasswordResetConfirm,
    session: DbSession,
):
    """
    Confirm a password reset with the token.
    """
    # TODO: Validate reset token
    # TODO: Update password

    return wrap_response({
        "message": "Password reset successfully",
    })


@router.post("/password/change", response_model=dict)
async def change_password(
    data: ChangePasswordRequest,
    user: CurrentUser,
    session: DbSession,
):
    """
    Change the current user's password.
    """
    # TODO: Verify current password
    # TODO: Update password

    return wrap_response({
        "message": "Password changed successfully",
    })


# =============================================================================
# Email Verification
# =============================================================================


@router.post("/email/verify", response_model=dict)
async def verify_email(
    token: str,
    session: DbSession,
):
    """
    Verify a user's email address.
    """
    # TODO: Validate verification token
    # TODO: Mark email as verified

    return wrap_response({
        "message": "Email verified successfully",
    })


@router.post("/email/resend-verification", response_model=dict)
async def resend_verification_email(
    user: CurrentUser,
    session: DbSession,
):
    """
    Resend the email verification link.
    """
    # TODO: Generate new verification token
    # TODO: Send verification email

    return wrap_response({
        "message": "Verification email sent",
    })


# =============================================================================
# Current User
# =============================================================================


@router.get("/me", response_model=dict)
async def get_current_user_info(
    user: CurrentUser,
    session: DbSession,
):
    """
    Get the current user's information.
    """
    return wrap_response({
        "id": str(user.user_id),
        "email": user.email,
        "organization_id": str(user.organization_id),
        "role": user.role,
    })


@router.patch("/me", response_model=dict)
async def update_current_user(
    name: str | None = None,
    user: CurrentUser = None,
    session: DbSession = None,
):
    """
    Update the current user's profile.
    """
    # TODO: Update user in database

    return wrap_response({
        "id": str(user.user_id),
        "message": "Profile updated",
    })
