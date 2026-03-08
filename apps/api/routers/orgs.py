"""
Organizations Router - Organization management (SaaS mode only).

Base path: /api/v1/orgs
"""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Query
from pydantic import BaseModel, EmailStr

from apps.api.dependencies import AdminUser, CurrentUser, DbSession, OwnerUser, ScopedBeadStore

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
# Models
# =============================================================================


class OrganizationCreate(BaseModel):
    """Create a new organization."""

    name: str
    slug: str | None = None


class OrganizationUpdate(BaseModel):
    """Update an organization."""

    name: str | None = None
    slug: str | None = None
    settings: dict[str, Any] | None = None


class InviteMemberRequest(BaseModel):
    """Invite a member to the organization."""

    email: EmailStr
    role: str = "member"  # owner, admin, member


class UpdateMemberRequest(BaseModel):
    """Update a member's role."""

    role: str


# =============================================================================
# Organization CRUD
# =============================================================================


@router.get("/current", response_model=dict)
async def get_current_organization(
    user: CurrentUser,
    session: DbSession,
):
    """Get the current user's organization."""
    # TODO: Look up organization from user.organization_id
    return wrap_response({
        "id": str(user.organization_id),
        "name": "My Organization",
        "slug": "my-org",
        "plan_tier": "free",
        "settings": {},
    })


@router.patch("/current", response_model=dict)
async def update_current_organization(
    data: OrganizationUpdate,
    user: AdminUser,
    session: DbSession,
):
    """Update the current organization."""
    # TODO: Update organization in database
    return wrap_response({
        "id": str(user.organization_id),
        "message": "Organization updated",
    })


@router.get("/current/settings", response_model=dict)
async def get_organization_settings(
    user: CurrentUser,
    session: DbSession,
):
    """Get organization settings."""
    return wrap_response({
        "approval_thresholds": {
            "content": {"auto_approve": False, "min_score": 0.8},
            "outreach": {"auto_approve": False, "min_score": 0.9},
            "pr_pitch": {"auto_approve": False},  # Never auto-approve
            "sms": {"auto_approve": False},  # Never auto-approve
        },
        "rig_settings": {
            "content_factory": {"enabled": True, "concurrency": 5},
            "sdr_hive": {"enabled": True, "concurrency": 10},
            "social_command": {"enabled": True, "concurrency": 5},
            "press_room": {"enabled": True, "concurrency": 3},
            "intelligence_station": {"enabled": True, "concurrency": 5},
            "landing_pad": {"enabled": True, "concurrency": 3},
            "wire": {"enabled": True, "concurrency": 2},
            "repo_watch": {"enabled": True, "concurrency": 5},
        },
        "brand_voice": {
            "tone": "professional",
            "guidelines": "",
        },
        "budget_guardrails": {
            "daily_limit_usd": None,
            "monthly_limit_usd": None,
        },
    })


@router.patch("/current/settings", response_model=dict)
async def update_organization_settings(
    settings: dict[str, Any],
    user: AdminUser,
    session: DbSession,
):
    """Update organization settings."""
    # TODO: Update settings in database
    return wrap_response({
        "message": "Settings updated",
    })


# =============================================================================
# Member Management
# =============================================================================


@router.get("/current/members", response_model=dict)
async def list_members(
    user: CurrentUser,
    session: DbSession,
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
):
    """List organization members."""
    # TODO: Query org_members table
    return wrap_response(
        [
            {
                "id": str(user.user_id),
                "email": user.email,
                "role": user.role,
                "joined_at": datetime.utcnow().isoformat(),
            }
        ],
        meta={"count": 1, "limit": limit, "offset": offset},
    )


@router.post("/current/members/invite", response_model=dict)
async def invite_member(
    data: InviteMemberRequest,
    user: AdminUser,
    session: DbSession,
):
    """
    Invite a new member to the organization.

    Sends an invitation email to the specified address.
    """
    # Validate role
    if data.role not in ["owner", "admin", "member"]:
        return wrap_response(
            None,
            meta={"error": "Invalid role. Must be owner, admin, or member"},
        )

    # Only owners can invite other owners
    if data.role == "owner" and user.role != "owner":
        return wrap_response(
            None,
            meta={"error": "Only owners can invite other owners"},
        )

    # TODO: Check seat limits based on plan
    # TODO: Create invitation and send email

    invitation_id = uuid4()

    return wrap_response({
        "invitation_id": str(invitation_id),
        "email": data.email,
        "role": data.role,
        "message": "Invitation sent",
    })


@router.get("/current/members/{member_id}", response_model=dict)
async def get_member(
    member_id: UUID,
    user: CurrentUser,
    session: DbSession,
):
    """Get a specific member's details."""
    # TODO: Look up member
    return wrap_response({
        "id": str(member_id),
        "email": None,
        "name": None,
        "role": None,
        "joined_at": None,
    })


@router.patch("/current/members/{member_id}", response_model=dict)
async def update_member(
    member_id: UUID,
    data: UpdateMemberRequest,
    user: AdminUser,
    session: DbSession,
):
    """Update a member's role."""
    # Validate role
    if data.role not in ["owner", "admin", "member"]:
        return wrap_response(
            None,
            meta={"error": "Invalid role"},
        )

    # Only owners can promote to owner or demote from owner
    if data.role == "owner" and user.role != "owner":
        return wrap_response(
            None,
            meta={"error": "Only owners can change owner roles"},
        )

    # TODO: Update member role in database
    return wrap_response({
        "id": str(member_id),
        "role": data.role,
        "message": "Member role updated",
    })


@router.delete("/current/members/{member_id}", response_model=dict)
async def remove_member(
    member_id: UUID,
    user: AdminUser,
    session: DbSession,
):
    """Remove a member from the organization."""
    # Prevent removing self
    if member_id == user.user_id:
        return wrap_response(
            None,
            meta={"error": "Cannot remove yourself. Transfer ownership first."},
        )

    # TODO: Remove from org_members table
    return wrap_response({
        "id": str(member_id),
        "message": "Member removed",
    })


# =============================================================================
# Invitations
# =============================================================================


@router.get("/current/invitations", response_model=dict)
async def list_invitations(
    user: AdminUser,
    session: DbSession,
    status: str = "pending",
    limit: int = Query(50, le=200),
):
    """List pending invitations."""
    # TODO: Query invitations table
    return wrap_response(
        [],
        meta={"count": 0, "limit": limit},
    )


@router.delete("/current/invitations/{invitation_id}", response_model=dict)
async def cancel_invitation(
    invitation_id: UUID,
    user: AdminUser,
    session: DbSession,
):
    """Cancel a pending invitation."""
    # TODO: Delete invitation
    return wrap_response({
        "invitation_id": str(invitation_id),
        "message": "Invitation cancelled",
    })


# =============================================================================
# API Keys
# =============================================================================


@router.get("/current/api-keys", response_model=dict)
async def list_api_keys(
    user: AdminUser,
    session: DbSession,
):
    """List organization API keys."""
    # TODO: Query api_keys table
    return wrap_response([])


@router.post("/current/api-keys", response_model=dict)
async def create_api_key(
    name: str,
    scopes: list[str] | None = None,
    user: AdminUser = None,
    session: DbSession = None,
):
    """
    Create a new API key.

    The full key is only returned once at creation.
    """
    import secrets

    key_id = uuid4()
    raw_key = f"{settings.api_key_prefix}{secrets.token_urlsafe(32)}"

    # TODO: Hash and store key
    # TODO: Store scopes

    return wrap_response({
        "id": str(key_id),
        "name": name,
        "key": raw_key,  # Only returned once
        "key_prefix": raw_key[:12] + "...",
        "scopes": scopes or ["*"],
        "message": "API key created. Store it securely - it won't be shown again.",
    })


@router.delete("/current/api-keys/{key_id}", response_model=dict)
async def revoke_api_key(
    key_id: UUID,
    user: AdminUser,
    session: DbSession,
):
    """Revoke an API key."""
    # TODO: Set is_active = False
    return wrap_response({
        "id": str(key_id),
        "message": "API key revoked",
    })


# =============================================================================
# Usage & Limits
# =============================================================================


@router.get("/current/usage", response_model=dict)
async def get_usage(
    user: CurrentUser,
    session: DbSession,
):
    """Get current usage for the billing period."""
    # TODO: Query usage_records table
    return wrap_response({
        "period_start": datetime.utcnow().replace(day=1).isoformat(),
        "period_end": None,
        "polecat_executions": 0,
        "beads_created": 0,
        "api_calls": 0,
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "limits": {
            "polecat_executions": 100,  # Free tier
            "rigs": 1,
            "seats": 1,
        },
    })


@router.get("/current/limits", response_model=dict)
async def get_limits(
    user: CurrentUser,
    session: DbSession,
):
    """Get organization limits based on plan tier."""
    # TODO: Get from subscription
    return wrap_response({
        "plan_tier": "free",
        "polecat_executions_per_month": 100,
        "rigs_enabled": 1,
        "seats": 1,
        "api_rate_limit": 60,
    })


# Import settings for API key prefix
from apps.api.config import settings
