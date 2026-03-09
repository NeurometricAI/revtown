"""
Organizations Router - Organization management (SaaS mode only).

Base path: /api/v1/orgs
"""

import hashlib
import json
import secrets
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Query
from pydantic import BaseModel, EmailStr
from sqlalchemy import text

from apps.api.config import settings
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
    query = text("""
        SELECT id, name, slug, plan_tier, settings, created_at, updated_at
        FROM organizations
        WHERE id = :org_id
    """)
    result = await session.execute(query, {"org_id": str(user.organization_id)})
    row = result.fetchone()

    if not row:
        return wrap_response(None, meta={"error": "Organization not found"})

    row_dict = dict(row._mapping)
    org_settings = row_dict.get("settings")
    if org_settings and isinstance(org_settings, str):
        org_settings = json.loads(org_settings)

    return wrap_response({
        "id": row_dict["id"],
        "name": row_dict["name"],
        "slug": row_dict["slug"],
        "plan_tier": row_dict["plan_tier"],
        "settings": org_settings or {},
        "created_at": row_dict["created_at"].isoformat() if row_dict.get("created_at") else None,
        "updated_at": row_dict["updated_at"].isoformat() if row_dict.get("updated_at") else None,
    })


@router.patch("/current", response_model=dict)
async def update_current_organization(
    data: OrganizationUpdate,
    user: AdminUser,
    session: DbSession,
):
    """Update the current organization."""
    update_fields = []
    params = {"org_id": str(user.organization_id)}

    if data.name is not None:
        update_fields.append("name = :name")
        params["name"] = data.name

    if data.slug is not None:
        update_fields.append("slug = :slug")
        params["slug"] = data.slug

    if data.settings is not None:
        update_fields.append("settings = :settings")
        params["settings"] = json.dumps(data.settings)

    if not update_fields:
        return wrap_response({"id": str(user.organization_id), "updated": False, "message": "No fields to update"})

    update_fields.append("updated_at = NOW()")

    query = text(f"""
        UPDATE organizations
        SET {", ".join(update_fields)}
        WHERE id = :org_id
    """)

    await session.execute(query, params)
    await session.commit()

    return wrap_response({
        "id": str(user.organization_id),
        "updated": True,
        "message": "Organization updated",
    })


@router.get("/current/settings", response_model=dict)
async def get_organization_settings(
    user: CurrentUser,
    session: DbSession,
):
    """Get organization settings."""
    query = text("SELECT settings FROM organizations WHERE id = :org_id")
    result = await session.execute(query, {"org_id": str(user.organization_id)})
    row = result.fetchone()

    # Default settings structure
    default_settings = {
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
    }

    if row:
        row_dict = dict(row._mapping)
        stored_settings = row_dict.get("settings")
        if stored_settings:
            if isinstance(stored_settings, str):
                stored_settings = json.loads(stored_settings)
            # Merge stored settings with defaults (stored takes precedence)
            for key in stored_settings:
                if key in default_settings and isinstance(default_settings[key], dict):
                    default_settings[key].update(stored_settings[key])
                else:
                    default_settings[key] = stored_settings[key]

    return wrap_response(default_settings)


@router.patch("/current/settings", response_model=dict)
async def update_organization_settings(
    new_settings: dict[str, Any],
    user: AdminUser,
    session: DbSession,
):
    """Update organization settings."""
    # Get current settings first
    get_query = text("SELECT settings FROM organizations WHERE id = :org_id")
    result = await session.execute(get_query, {"org_id": str(user.organization_id)})
    row = result.fetchone()

    current_settings = {}
    if row:
        row_dict = dict(row._mapping)
        stored = row_dict.get("settings")
        if stored and isinstance(stored, str):
            current_settings = json.loads(stored)
        elif stored:
            current_settings = stored

    # Merge new settings into current
    for key, value in new_settings.items():
        if key in current_settings and isinstance(current_settings[key], dict) and isinstance(value, dict):
            current_settings[key].update(value)
        else:
            current_settings[key] = value

    # Update in database
    update_query = text("""
        UPDATE organizations
        SET settings = :settings, updated_at = NOW()
        WHERE id = :org_id
    """)
    await session.execute(update_query, {
        "org_id": str(user.organization_id),
        "settings": json.dumps(current_settings),
    })
    await session.commit()

    return wrap_response({
        "message": "Settings updated",
        "settings": current_settings,
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
    # Get total count
    count_query = text("""
        SELECT COUNT(*) as total FROM org_members WHERE organization_id = :org_id
    """)
    count_result = await session.execute(count_query, {"org_id": str(user.organization_id)})
    total = count_result.fetchone()._mapping["total"]

    # Get members with user info
    query = text("""
        SELECT om.id, om.user_id, om.role, om.joined_at,
               u.email, u.name
        FROM org_members om
        JOIN users u ON om.user_id = u.id
        WHERE om.organization_id = :org_id
        ORDER BY om.joined_at DESC
        LIMIT :limit OFFSET :offset
    """)
    result = await session.execute(query, {
        "org_id": str(user.organization_id),
        "limit": limit,
        "offset": offset,
    })

    members = []
    for row in result.fetchall():
        row_dict = dict(row._mapping)
        members.append({
            "id": row_dict["user_id"],
            "email": row_dict["email"],
            "name": row_dict["name"],
            "role": row_dict["role"],
            "joined_at": row_dict["joined_at"].isoformat() if row_dict.get("joined_at") else None,
        })

    return wrap_response(
        members,
        meta={"count": total, "limit": limit, "offset": offset},
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

    # Check if user is already a member
    check_member_query = text("""
        SELECT om.id FROM org_members om
        JOIN users u ON om.user_id = u.id
        WHERE om.organization_id = :org_id AND u.email = :email
    """)
    existing_member = await session.execute(check_member_query, {
        "org_id": str(user.organization_id),
        "email": data.email,
    })
    if existing_member.fetchone():
        return wrap_response(None, meta={"error": "User is already a member of this organization"})

    # Check for existing pending invitation
    check_invite_query = text("""
        SELECT id FROM invitations
        WHERE organization_id = :org_id AND email = :email AND status = 'pending'
    """)
    existing_invite = await session.execute(check_invite_query, {
        "org_id": str(user.organization_id),
        "email": data.email,
    })
    if existing_invite.fetchone():
        return wrap_response(None, meta={"error": "An invitation is already pending for this email"})

    # Create invitation token
    invitation_id = uuid4()
    invite_token = secrets.token_urlsafe(32)

    # Create invitation record
    insert_query = text("""
        INSERT INTO invitations (id, organization_id, email, role, token, invited_by, status, created_at, expires_at)
        VALUES (:id, :org_id, :email, :role, :token, :invited_by, 'pending', NOW(), DATE_ADD(NOW(), INTERVAL 7 DAY))
    """)
    await session.execute(insert_query, {
        "id": str(invitation_id),
        "org_id": str(user.organization_id),
        "email": data.email,
        "role": data.role,
        "token": invite_token,
        "invited_by": str(user.user_id),
    })
    await session.commit()

    # TODO: Send invitation email with token

    return wrap_response({
        "invitation_id": str(invitation_id),
        "email": data.email,
        "role": data.role,
        "message": "Invitation created",
    })


@router.get("/current/members/{member_id}", response_model=dict)
async def get_member(
    member_id: UUID,
    user: CurrentUser,
    session: DbSession,
):
    """Get a specific member's details."""
    query = text("""
        SELECT om.id, om.user_id, om.role, om.joined_at,
               u.email, u.name
        FROM org_members om
        JOIN users u ON om.user_id = u.id
        WHERE om.organization_id = :org_id AND om.user_id = :member_id
    """)
    result = await session.execute(query, {
        "org_id": str(user.organization_id),
        "member_id": str(member_id),
    })
    row = result.fetchone()

    if not row:
        return wrap_response(None, meta={"error": "Member not found"})

    row_dict = dict(row._mapping)
    return wrap_response({
        "id": row_dict["user_id"],
        "email": row_dict["email"],
        "name": row_dict["name"],
        "role": row_dict["role"],
        "joined_at": row_dict["joined_at"].isoformat() if row_dict.get("joined_at") else None,
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

    # Get current role of the member being updated
    check_query = text("""
        SELECT role FROM org_members
        WHERE organization_id = :org_id AND user_id = :member_id
    """)
    check_result = await session.execute(check_query, {
        "org_id": str(user.organization_id),
        "member_id": str(member_id),
    })
    current_row = check_result.fetchone()

    if not current_row:
        return wrap_response(None, meta={"error": "Member not found"})

    current_role = current_row._mapping["role"]

    # Only owners can promote to owner or demote from owner
    if (data.role == "owner" or current_role == "owner") and user.role != "owner":
        return wrap_response(
            None,
            meta={"error": "Only owners can change owner roles"},
        )

    # Update member role
    update_query = text("""
        UPDATE org_members
        SET role = :role
        WHERE organization_id = :org_id AND user_id = :member_id
    """)
    await session.execute(update_query, {
        "org_id": str(user.organization_id),
        "member_id": str(member_id),
        "role": data.role,
    })
    await session.commit()

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

    # Check if member exists and get their role
    check_query = text("""
        SELECT role FROM org_members
        WHERE organization_id = :org_id AND user_id = :member_id
    """)
    check_result = await session.execute(check_query, {
        "org_id": str(user.organization_id),
        "member_id": str(member_id),
    })
    member_row = check_result.fetchone()

    if not member_row:
        return wrap_response(None, meta={"error": "Member not found"})

    member_role = member_row._mapping["role"]

    # Only owners can remove other owners
    if member_role == "owner" and user.role != "owner":
        return wrap_response(
            None,
            meta={"error": "Only owners can remove other owners"},
        )

    # Remove from org_members table
    delete_query = text("""
        DELETE FROM org_members
        WHERE organization_id = :org_id AND user_id = :member_id
    """)
    await session.execute(delete_query, {
        "org_id": str(user.organization_id),
        "member_id": str(member_id),
    })
    await session.commit()

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
    query = text("""
        SELECT i.id, i.email, i.role, i.status, i.created_at, i.expires_at,
               u.email as invited_by_email, u.name as invited_by_name
        FROM invitations i
        LEFT JOIN users u ON i.invited_by = u.id
        WHERE i.organization_id = :org_id AND i.status = :status
        ORDER BY i.created_at DESC
        LIMIT :limit
    """)
    result = await session.execute(query, {
        "org_id": str(user.organization_id),
        "status": status,
        "limit": limit,
    })

    invitations = []
    for row in result.fetchall():
        row_dict = dict(row._mapping)
        invitations.append({
            "id": row_dict["id"],
            "email": row_dict["email"],
            "role": row_dict["role"],
            "status": row_dict["status"],
            "invited_by": {
                "email": row_dict["invited_by_email"],
                "name": row_dict["invited_by_name"],
            } if row_dict.get("invited_by_email") else None,
            "created_at": row_dict["created_at"].isoformat() if row_dict.get("created_at") else None,
            "expires_at": row_dict["expires_at"].isoformat() if row_dict.get("expires_at") else None,
        })

    return wrap_response(
        invitations,
        meta={"count": len(invitations), "limit": limit},
    )


@router.delete("/current/invitations/{invitation_id}", response_model=dict)
async def cancel_invitation(
    invitation_id: UUID,
    user: AdminUser,
    session: DbSession,
):
    """Cancel a pending invitation."""
    # Update status to cancelled (don't delete for audit trail)
    query = text("""
        UPDATE invitations
        SET status = 'cancelled'
        WHERE id = :invitation_id AND organization_id = :org_id AND status = 'pending'
    """)
    result = await session.execute(query, {
        "invitation_id": str(invitation_id),
        "org_id": str(user.organization_id),
    })
    await session.commit()

    if result.rowcount == 0:
        return wrap_response(None, meta={"error": "Invitation not found or already processed"})

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
    """List organization API keys (without revealing the actual keys)."""
    query = text("""
        SELECT id, key_prefix, name, scopes, last_used_at, expires_at, is_active, created_at
        FROM api_keys
        WHERE organization_id = :org_id
        ORDER BY created_at DESC
    """)

    result = await session.execute(query, {"org_id": str(user.organization_id)})
    rows = result.fetchall()

    keys = []
    for row in rows:
        row_dict = dict(row._mapping)
        # Parse scopes from JSON
        if row_dict.get("scopes") and isinstance(row_dict["scopes"], str):
            row_dict["scopes"] = json.loads(row_dict["scopes"])
        keys.append({
            "id": row_dict["id"],
            "key_prefix": row_dict["key_prefix"] + "...",
            "name": row_dict["name"],
            "scopes": row_dict.get("scopes") or ["*"],
            "last_used_at": row_dict["last_used_at"].isoformat() if row_dict.get("last_used_at") else None,
            "expires_at": row_dict["expires_at"].isoformat() if row_dict.get("expires_at") else None,
            "is_active": bool(row_dict["is_active"]),
            "created_at": row_dict["created_at"].isoformat() if row_dict.get("created_at") else None,
        })

    return wrap_response(keys)


class CreateAPIKeyRequest(BaseModel):
    name: str
    scopes: list[str] | None = None


@router.post("/current/api-keys", response_model=dict)
async def create_api_key(
    data: CreateAPIKeyRequest,
    user: AdminUser,
    session: DbSession,
):
    """
    Create a new API key.

    The full key is only returned once at creation.
    """
    key_id = uuid4()
    raw_key = f"{settings.api_key_prefix}{secrets.token_urlsafe(32)}"
    key_prefix = raw_key[:12]
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    query = text("""
        INSERT INTO api_keys (id, organization_id, key_hash, key_prefix, name, scopes, is_active, created_by, created_at)
        VALUES (:id, :org_id, :key_hash, :key_prefix, :name, :scopes, 1, :created_by, NOW())
    """)

    await session.execute(query, {
        "id": str(key_id),
        "org_id": str(user.organization_id),
        "key_hash": key_hash,
        "key_prefix": key_prefix,
        "name": data.name,
        "scopes": json.dumps(data.scopes) if data.scopes else None,
        "created_by": str(user.user_id),
    })
    await session.commit()

    return wrap_response({
        "id": str(key_id),
        "name": data.name,
        "key": raw_key,  # Only returned once
        "key_prefix": key_prefix + "...",
        "scopes": data.scopes or ["*"],
        "message": "API key created. Store it securely - it won't be shown again.",
    })


@router.delete("/current/api-keys/{key_id}", response_model=dict)
async def revoke_api_key(
    key_id: UUID,
    user: AdminUser,
    session: DbSession,
):
    """Revoke an API key."""
    query = text("""
        UPDATE api_keys
        SET is_active = 0
        WHERE id = :key_id AND organization_id = :org_id
    """)

    result = await session.execute(query, {
        "key_id": str(key_id),
        "org_id": str(user.organization_id),
    })
    await session.commit()

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
    # Get organization's plan tier
    org_query = text("SELECT plan_tier FROM organizations WHERE id = :org_id")
    org_result = await session.execute(org_query, {"org_id": str(user.organization_id)})
    org_row = org_result.fetchone()
    plan_tier = org_row._mapping["plan_tier"] if org_row else "free"

    # Calculate period start (first of current month)
    now = datetime.utcnow()
    period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # Query usage from usage_records table
    usage_query = text("""
        SELECT
            COALESCE(SUM(polecat_executions), 0) as polecat_executions,
            COALESCE(SUM(beads_created), 0) as beads_created,
            COALESCE(SUM(api_calls), 0) as api_calls,
            COALESCE(SUM(total_input_tokens), 0) as total_input_tokens,
            COALESCE(SUM(total_output_tokens), 0) as total_output_tokens
        FROM usage_records
        WHERE organization_id = :org_id AND period_start >= :period_start
    """)
    usage_result = await session.execute(usage_query, {
        "org_id": str(user.organization_id),
        "period_start": period_start,
    })
    usage_row = usage_result.fetchone()

    # Define limits based on plan tier
    tier_limits = {
        "free": {"polecat_executions": 100, "rigs": 1, "seats": 1},
        "pro": {"polecat_executions": 5000, "rigs": 4, "seats": 5},
        "scale": {"polecat_executions": 50000, "rigs": 8, "seats": 25},
        "enterprise": {"polecat_executions": None, "rigs": 8, "seats": None},
    }
    limits = tier_limits.get(plan_tier, tier_limits["free"])

    usage_data = dict(usage_row._mapping) if usage_row else {}

    return wrap_response({
        "period_start": period_start.isoformat(),
        "period_end": None,
        "polecat_executions": int(usage_data.get("polecat_executions", 0)),
        "beads_created": int(usage_data.get("beads_created", 0)),
        "api_calls": int(usage_data.get("api_calls", 0)),
        "total_input_tokens": int(usage_data.get("total_input_tokens", 0)),
        "total_output_tokens": int(usage_data.get("total_output_tokens", 0)),
        "limits": limits,
    })


@router.get("/current/limits", response_model=dict)
async def get_limits(
    user: CurrentUser,
    session: DbSession,
):
    """Get organization limits based on plan tier."""
    # Get organization's plan tier
    org_query = text("SELECT plan_tier FROM organizations WHERE id = :org_id")
    org_result = await session.execute(org_query, {"org_id": str(user.organization_id)})
    org_row = org_result.fetchone()
    plan_tier = org_row._mapping["plan_tier"] if org_row else "free"

    # Define limits based on plan tier
    tier_configs = {
        "free": {
            "plan_tier": "free",
            "polecat_executions_per_month": 100,
            "rigs_enabled": 1,
            "seats": 1,
            "api_rate_limit": 60,
            "features": ["basic_analytics"],
        },
        "pro": {
            "plan_tier": "pro",
            "polecat_executions_per_month": 5000,
            "rigs_enabled": 4,
            "seats": 5,
            "api_rate_limit": 300,
            "features": ["basic_analytics", "advanced_analytics", "custom_branding", "priority_support"],
        },
        "scale": {
            "plan_tier": "scale",
            "polecat_executions_per_month": 50000,
            "rigs_enabled": 8,
            "seats": 25,
            "api_rate_limit": 1000,
            "features": ["basic_analytics", "advanced_analytics", "custom_branding", "priority_support", "sso", "audit_logs"],
        },
        "enterprise": {
            "plan_tier": "enterprise",
            "polecat_executions_per_month": None,  # Unlimited
            "rigs_enabled": 8,
            "seats": None,  # Unlimited
            "api_rate_limit": None,  # Custom
            "features": ["basic_analytics", "advanced_analytics", "custom_branding", "priority_support", "sso", "audit_logs", "custom_integrations", "dedicated_support"],
        },
    }

    return wrap_response(tier_configs.get(plan_tier, tier_configs["free"]))


# Import settings for API key prefix
from apps.api.config import settings
