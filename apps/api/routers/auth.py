"""
Auth Router - User authentication (SaaS mode only).

Base path: /api/v1/auth
"""

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from jose import jwt
from pydantic import BaseModel, EmailStr
from sqlalchemy import text

from apps.api.config import settings
from apps.api.dependencies import CurrentUser, DbSession, OptionalUser
from apps.api.middleware.error_handler import AuthenticationError

router = APIRouter()


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
    return bcrypt.checkpw(
        plain_password.encode('utf-8'),
        hashed_password.encode('utf-8')
    )


def hash_password(password: str) -> str:
    """Hash a password."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')


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
    # Check if email already exists
    check_query = text("SELECT id FROM users WHERE email = :email")
    existing = await session.execute(check_query, {"email": data.email})
    if existing.fetchone():
        raise HTTPException(status_code=400, detail="Email already registered")

    user_id = uuid4()
    org_id = uuid4() if data.organization_name else None
    password_hash = hash_password(data.password)

    # Create user
    user_query = text("""
        INSERT INTO users (id, email, password_hash, name, email_verified, is_active, created_at, updated_at)
        VALUES (:id, :email, :password_hash, :name, 0, 1, NOW(), NOW())
    """)
    await session.execute(user_query, {
        "id": str(user_id),
        "email": data.email,
        "password_hash": password_hash,
        "name": data.name,
    })

    # Create organization if name provided
    if org_id and data.organization_name:
        # Create slug from name
        slug = data.organization_name.lower().replace(" ", "-")[:100]

        org_query = text("""
            INSERT INTO organizations (id, name, slug, plan_tier, created_at, updated_at)
            VALUES (:id, :name, :slug, 'free', NOW(), NOW())
        """)
        await session.execute(org_query, {
            "id": str(org_id),
            "name": data.organization_name,
            "slug": slug,
        })

        # Add user as owner
        member_query = text("""
            INSERT INTO org_members (id, organization_id, user_id, role, joined_at)
            VALUES (:id, :org_id, :user_id, 'owner', NOW())
        """)
        await session.execute(member_query, {
            "id": str(uuid4()),
            "org_id": str(org_id),
            "user_id": str(user_id),
        })

    await session.commit()

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
    # Look up user by email
    user_query = text("""
        SELECT id, email, password_hash, name, is_active
        FROM users
        WHERE email = :email
    """)
    result = await session.execute(user_query, {"email": data.email})
    user_row = result.fetchone()

    if not user_row:
        raise AuthenticationError("Invalid email or password")

    user = dict(user_row._mapping)

    if not user["is_active"]:
        raise AuthenticationError("Account is disabled")

    # Verify password
    if not verify_password(data.password, user["password_hash"]):
        raise AuthenticationError("Invalid email or password")

    # Get user's organization(s) - return first one
    org_query = text("""
        SELECT om.organization_id, om.role, o.name as org_name
        FROM org_members om
        JOIN organizations o ON om.organization_id = o.id
        WHERE om.user_id = :user_id
        LIMIT 1
    """)
    org_result = await session.execute(org_query, {"user_id": user["id"]})
    org_row = org_result.fetchone()

    org_id = None
    role = None
    org_name = None
    if org_row:
        org_data = dict(org_row._mapping)
        org_id = org_data["organization_id"]
        role = org_data["role"]
        org_name = org_data["org_name"]

    access_token = create_access_token({
        "sub": user["id"],
        "email": user["email"],
        "org_id": org_id,
        "role": role,
    })
    refresh_token = create_refresh_token({"sub": user["id"]})

    return wrap_response({
        "user": {
            "id": user["id"],
            "email": user["email"],
            "name": user["name"],
        },
        "organization": {
            "id": org_id,
            "name": org_name,
            "role": role,
        } if org_id else None,
        "tokens": {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": settings.jwt_access_token_expire_minutes * 60,
        },
    })


@router.post("/token", response_model=dict)
async def login_oauth(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: DbSession = None,
):
    """
    OAuth2 compatible token endpoint.

    For integration with OAuth2 clients.
    """
    # Use the same login logic
    login_data = LoginRequest(email=form_data.username, password=form_data.password)
    return await login(login_data, session)


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

        # Look up user and get current org
        user_query = text("SELECT id, email FROM users WHERE id = :id AND is_active = 1")
        user_result = await session.execute(user_query, {"id": user_id})
        user_row = user_result.fetchone()

        if not user_row:
            raise AuthenticationError("User not found")

        user = dict(user_row._mapping)

        # Get org info
        org_query = text("""
            SELECT om.organization_id, om.role
            FROM org_members om
            WHERE om.user_id = :user_id
            LIMIT 1
        """)
        org_result = await session.execute(org_query, {"user_id": user_id})
        org_row = org_result.fetchone()

        org_id = None
        role = None
        if org_row:
            org_data = dict(org_row._mapping)
            org_id = org_data["organization_id"]
            role = org_data["role"]

        access_token = create_access_token({
            "sub": user_id,
            "email": user["email"],
            "org_id": org_id,
            "role": role,
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
    # Get current password hash
    query = text("SELECT password_hash FROM users WHERE id = :id")
    result = await session.execute(query, {"id": str(user.user_id)})
    row = result.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="User not found")

    row_dict = dict(row._mapping)

    # Verify current password
    if not verify_password(data.current_password, row_dict["password_hash"]):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    # Update password
    new_hash = hash_password(data.new_password)
    update_query = text("""
        UPDATE users SET password_hash = :hash, updated_at = NOW() WHERE id = :id
    """)
    await session.execute(update_query, {"hash": new_hash, "id": str(user.user_id)})
    await session.commit()

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
    # Get full user info from database
    query = text("""
        SELECT id, email, name, email_verified, created_at
        FROM users WHERE id = :id
    """)
    result = await session.execute(query, {"id": str(user.user_id)})
    row = result.fetchone()

    if row:
        user_data = dict(row._mapping)
        return wrap_response({
            "id": user_data["id"],
            "email": user_data["email"],
            "name": user_data["name"],
            "email_verified": bool(user_data["email_verified"]),
            "organization_id": str(user.organization_id),
            "role": user.role,
            "created_at": user_data["created_at"].isoformat() if user_data["created_at"] else None,
        })

    return wrap_response({
        "id": str(user.user_id),
        "email": user.email,
        "organization_id": str(user.organization_id),
        "role": user.role,
    })


class UpdateProfileRequest(BaseModel):
    name: str | None = None


@router.patch("/me", response_model=dict)
async def update_current_user(
    data: UpdateProfileRequest,
    user: CurrentUser,
    session: DbSession,
):
    """
    Update the current user's profile.
    """
    if data.name:
        query = text("UPDATE users SET name = :name, updated_at = NOW() WHERE id = :id")
        await session.execute(query, {"name": data.name, "id": str(user.user_id)})
        await session.commit()

    return wrap_response({
        "id": str(user.user_id),
        "message": "Profile updated",
    })
