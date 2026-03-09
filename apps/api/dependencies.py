"""
FastAPI Dependencies - Dependency injection for auth, database, and services.
"""

import hashlib
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.config import settings
from apps.api.core.bead_store import BeadStore, get_session_factory
from apps.api.middleware.error_handler import AuthenticationError, AuthorizationError

# Forward reference for Mayor (imported in function to avoid circular imports)
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from apps.api.core.mayor import Mayor

# Security scheme
security = HTTPBearer(auto_error=False)


# =============================================================================
# Database Session
# =============================================================================


async def get_db_session() -> AsyncSession:
    """Get a database session."""
    session_factory = get_session_factory()
    async with session_factory() as session:
        yield session


# =============================================================================
# Authentication
# =============================================================================


class TokenData:
    """Parsed JWT token data."""

    def __init__(
        self,
        user_id: UUID,
        organization_id: UUID,
        email: str,
        role: str,
    ):
        self.user_id = user_id
        self.organization_id = organization_id
        self.email = email
        self.role = role


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    x_api_key: Annotated[str | None, Header()] = None,
) -> TokenData:
    """
    Authenticate user via JWT token or API key.

    Supports two auth methods:
    1. Bearer token (JWT) - for UI users
    2. X-API-Key header - for programmatic access
    """
    # Skip auth in self-hosted mode if no credentials provided
    if not settings.is_saas and not credentials and not x_api_key:
        # Return a default "admin" user for self-hosted mode
        return TokenData(
            user_id=UUID("00000000-0000-0000-0000-000000000000"),
            organization_id=UUID("00000000-0000-0000-0000-000000000001"),
            email="admin@localhost",
            role="owner",
        )

    # Try API key first
    if x_api_key and x_api_key.startswith(settings.api_key_prefix):
        return await _authenticate_api_key(x_api_key)

    # Try JWT token
    if credentials:
        return await _authenticate_jwt(credentials.credentials)

    raise AuthenticationError("Authentication required")


async def _authenticate_jwt(token: str) -> TokenData:
    """Authenticate via JWT token."""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )

        user_id = payload.get("sub")
        organization_id = payload.get("org_id")
        email = payload.get("email")
        role = payload.get("role")

        if not all([user_id, organization_id, email]):
            raise AuthenticationError("Invalid token")

        return TokenData(
            user_id=UUID(user_id),
            organization_id=UUID(organization_id),
            email=email,
            role=role or "member",
        )

    except JWTError as e:
        raise AuthenticationError(f"Invalid token: {e}")


async def _authenticate_api_key(api_key: str) -> TokenData:
    """
    Authenticate via API key.

    API keys are stored as SHA256 hashes. The key_prefix column allows
    quick lookup before hash comparison.
    """
    # Extract prefix (e.g., "rtk_abc123..." -> "rtk_abc123")
    # The prefix includes the rtk_ and first 8 chars of the key
    if len(api_key) < 12:
        raise AuthenticationError("Invalid API key format")

    key_prefix = api_key[:12]  # "rtk_" + 8 chars

    # Hash the full key for comparison
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()

    # Look up in database
    session_factory = get_session_factory()
    async with session_factory() as session:
        query = text("""
            SELECT ak.id, ak.organization_id, ak.key_hash, ak.is_active,
                   ak.expires_at, ak.scopes, ak.created_by,
                   o.name as org_name
            FROM api_keys ak
            JOIN organizations o ON ak.organization_id = o.id
            WHERE ak.key_prefix = :key_prefix
            AND ak.is_active = 1
        """)

        result = await session.execute(query, {"key_prefix": key_prefix})
        row = result.fetchone()

        if not row:
            raise AuthenticationError("Invalid API key")

        row_dict = dict(row._mapping)

        # Verify hash matches
        if row_dict["key_hash"] != key_hash:
            raise AuthenticationError("Invalid API key")

        # Check expiration
        if row_dict["expires_at"] and row_dict["expires_at"] < datetime.utcnow():
            raise AuthenticationError("API key has expired")

        # Update last_used_at
        update_query = text("""
            UPDATE api_keys SET last_used_at = NOW() WHERE id = :key_id
        """)
        await session.execute(update_query, {"key_id": row_dict["id"]})
        await session.commit()

        return TokenData(
            user_id=UUID(row_dict["created_by"]),
            organization_id=UUID(row_dict["organization_id"]),
            email=f"api-key@{row_dict['org_name'].lower().replace(' ', '-')}.local",
            role="api",  # API keys get a special role
        )


async def get_current_user_optional(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    x_api_key: Annotated[str | None, Header()] = None,
) -> TokenData | None:
    """Get current user if authenticated, None otherwise."""
    try:
        return await get_current_user(credentials, x_api_key)
    except AuthenticationError:
        return None


def require_role(required_roles: list[str]):
    """Dependency factory for role-based access control."""

    async def check_role(user: Annotated[TokenData, Depends(get_current_user)]) -> TokenData:
        if user.role not in required_roles:
            raise AuthorizationError(f"Required role: {', '.join(required_roles)}")
        return user

    return check_role


# =============================================================================
# BeadStore with Organization Scope
# =============================================================================


async def get_bead_store(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    user: Annotated[TokenData, Depends(get_current_user)],
) -> BeadStore:
    """Get a BeadStore scoped to the current user's organization."""
    return BeadStore(session, user.organization_id)


async def get_bead_store_unscoped(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> BeadStore:
    """Get an unscoped BeadStore (for admin/system operations)."""
    return BeadStore(session, None)


# =============================================================================
# Type Aliases for Common Dependencies
# =============================================================================

CurrentUser = Annotated[TokenData, Depends(get_current_user)]
OptionalUser = Annotated[TokenData | None, Depends(get_current_user_optional)]
DbSession = Annotated[AsyncSession, Depends(get_db_session)]
ScopedBeadStore = Annotated[BeadStore, Depends(get_bead_store)]

# Role-based dependencies
AdminUser = Annotated[TokenData, Depends(require_role(["owner", "admin"]))]
OwnerUser = Annotated[TokenData, Depends(require_role(["owner"]))]


# =============================================================================
# Mayor (GTM Orchestration)
# =============================================================================


async def get_mayor(
    store: Annotated[BeadStore, Depends(get_bead_store)],
    user: Annotated[TokenData, Depends(get_current_user)],
):
    """Get a Mayor instance scoped to the current organization."""
    from apps.api.core.mayor import Mayor

    return Mayor(
        bead_store=store,
        organization_id=user.organization_id,
    )


ScopedMayor = Annotated["Mayor", Depends(get_mayor)]
