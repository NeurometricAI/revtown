"""
Webhooks Router - Register, list, and test webhooks.

Base path: /api/v1/webhooks
"""

import hashlib
import hmac
import secrets
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import json

from fastapi import APIRouter, Header, HTTPException, Query, Request
from pydantic import BaseModel, HttpUrl
from sqlalchemy import text

from apps.api.dependencies import AdminUser, CurrentUser, DbSession, ScopedBeadStore

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
# Webhook Events
# =============================================================================

WEBHOOK_EVENTS = [
    # Bead lifecycle
    "bead.created",
    "bead.updated",
    "bead.archived",
    "bead.reverted",
    # Polecat execution
    "polecat.started",
    "polecat.completed",
    "polecat.failed",
    # Approval workflow
    "approval.pending",
    "approval.approved",
    "approval.rejected",
    "approval.sent_back",
    # Campaign lifecycle
    "campaign.created",
    "campaign.started",
    "campaign.completed",
    # Tests
    "test.started",
    "test.winner_declared",
    # Alerts
    "alert.refinery_failed",
    "alert.witness_failed",
    "alert.quota_warning",
]


# =============================================================================
# Models
# =============================================================================


class WebhookCreate(BaseModel):
    """Create a new webhook."""

    url: HttpUrl
    events: list[str]
    description: str | None = None


class WebhookUpdate(BaseModel):
    """Update a webhook."""

    url: HttpUrl | None = None
    events: list[str] | None = None
    is_active: bool | None = None
    description: str | None = None


class WebhookResponse(BaseModel):
    """Webhook response model."""

    id: UUID
    url: str
    events: list[str]
    is_active: bool
    description: str | None
    last_triggered_at: datetime | None
    failure_count: int
    created_at: datetime


# =============================================================================
# Webhook Registration
# =============================================================================


@router.post("", response_model=dict)
async def create_webhook(
    data: WebhookCreate,
    session: DbSession,
    user: AdminUser,
):
    """
    Register a new webhook.

    All webhook payloads include an X-RevTown-Signature header
    for HMAC verification.
    """
    # Validate events
    invalid_events = [e for e in data.events if e not in WEBHOOK_EVENTS]
    if invalid_events:
        return wrap_response(
            None,
            meta={"error": f"Invalid events: {invalid_events}", "valid_events": WEBHOOK_EVENTS},
        )

    # Generate secret
    secret = secrets.token_urlsafe(32)
    webhook_id = uuid4()

    # Store in webhooks table
    query = text("""
        INSERT INTO webhooks (id, organization_id, url, secret, events, is_active, created_at, updated_at)
        VALUES (:id, :org_id, :url, :secret, :events, 1, NOW(), NOW())
    """)
    await session.execute(query, {
        "id": str(webhook_id),
        "org_id": str(user.organization_id),
        "url": str(data.url),
        "secret": secret,
        "events": json.dumps(data.events),
    })
    await session.commit()

    return wrap_response({
        "webhook_id": str(webhook_id),
        "url": str(data.url),
        "events": data.events,
        "secret": secret,  # Only returned once at creation
        "message": "Webhook registered. Store the secret securely - it won't be shown again.",
    })


@router.get("", response_model=dict)
async def list_webhooks(
    session: DbSession,
    user: CurrentUser,
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
):
    """List all registered webhooks for the organization."""
    # Get total count
    count_query = text("SELECT COUNT(*) as total FROM webhooks WHERE organization_id = :org_id")
    count_result = await session.execute(count_query, {"org_id": str(user.organization_id)})
    total = count_result.fetchone()._mapping["total"]

    # Get webhooks
    query = text("""
        SELECT id, url, events, is_active, last_triggered_at, failure_count, created_at, updated_at
        FROM webhooks
        WHERE organization_id = :org_id
        ORDER BY created_at DESC
        LIMIT :limit OFFSET :offset
    """)
    result = await session.execute(query, {
        "org_id": str(user.organization_id),
        "limit": limit,
        "offset": offset,
    })

    webhooks = []
    for row in result.fetchall():
        row_dict = dict(row._mapping)
        events = row_dict.get("events")
        if events and isinstance(events, str):
            events = json.loads(events)
        webhooks.append({
            "id": row_dict["id"],
            "url": row_dict["url"],
            "events": events or [],
            "is_active": bool(row_dict["is_active"]),
            "last_triggered_at": row_dict["last_triggered_at"].isoformat() if row_dict.get("last_triggered_at") else None,
            "failure_count": row_dict["failure_count"] or 0,
            "created_at": row_dict["created_at"].isoformat() if row_dict.get("created_at") else None,
        })

    return wrap_response(
        webhooks,
        meta={"count": total, "limit": limit, "offset": offset},
    )


@router.get("/{webhook_id}", response_model=dict)
async def get_webhook(
    webhook_id: UUID,
    session: DbSession,
    user: CurrentUser,
):
    """Get details of a specific webhook."""
    query = text("""
        SELECT id, url, events, is_active, last_triggered_at, failure_count, created_at, updated_at
        FROM webhooks
        WHERE id = :webhook_id AND organization_id = :org_id
    """)
    result = await session.execute(query, {
        "webhook_id": str(webhook_id),
        "org_id": str(user.organization_id),
    })
    row = result.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Webhook not found")

    row_dict = dict(row._mapping)
    events = row_dict.get("events")
    if events and isinstance(events, str):
        events = json.loads(events)

    return wrap_response({
        "id": row_dict["id"],
        "url": row_dict["url"],
        "events": events or [],
        "is_active": bool(row_dict["is_active"]),
        "last_triggered_at": row_dict["last_triggered_at"].isoformat() if row_dict.get("last_triggered_at") else None,
        "failure_count": row_dict["failure_count"] or 0,
        "created_at": row_dict["created_at"].isoformat() if row_dict.get("created_at") else None,
        "updated_at": row_dict["updated_at"].isoformat() if row_dict.get("updated_at") else None,
    })


@router.patch("/{webhook_id}", response_model=dict)
async def update_webhook(
    webhook_id: UUID,
    data: WebhookUpdate,
    session: DbSession,
    user: AdminUser,
):
    """Update a webhook configuration."""
    if data.events:
        invalid_events = [e for e in data.events if e not in WEBHOOK_EVENTS]
        if invalid_events:
            return wrap_response(
                None,
                meta={"error": f"Invalid events: {invalid_events}"},
            )

    # Build update query
    update_fields = []
    params = {
        "webhook_id": str(webhook_id),
        "org_id": str(user.organization_id),
    }

    if data.url is not None:
        update_fields.append("url = :url")
        params["url"] = str(data.url)

    if data.events is not None:
        update_fields.append("events = :events")
        params["events"] = json.dumps(data.events)

    if data.is_active is not None:
        update_fields.append("is_active = :is_active")
        params["is_active"] = 1 if data.is_active else 0

    if not update_fields:
        return wrap_response({"webhook_id": str(webhook_id), "updated": False, "message": "No fields to update"})

    update_fields.append("updated_at = NOW()")

    query = text(f"""
        UPDATE webhooks
        SET {", ".join(update_fields)}
        WHERE id = :webhook_id AND organization_id = :org_id
    """)

    result = await session.execute(query, params)
    await session.commit()

    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Webhook not found")

    return wrap_response({
        "webhook_id": str(webhook_id),
        "updated": True,
    })


@router.delete("/{webhook_id}", response_model=dict)
async def delete_webhook(
    webhook_id: UUID,
    session: DbSession,
    user: AdminUser,
):
    """Delete a webhook."""
    query = text("""
        DELETE FROM webhooks
        WHERE id = :webhook_id AND organization_id = :org_id
    """)
    result = await session.execute(query, {
        "webhook_id": str(webhook_id),
        "org_id": str(user.organization_id),
    })
    await session.commit()

    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Webhook not found")

    return wrap_response({
        "webhook_id": str(webhook_id),
        "deleted": True,
    })


# =============================================================================
# Webhook Testing
# =============================================================================


@router.post("/{webhook_id}/test", response_model=dict)
async def test_webhook(
    webhook_id: UUID,
    session: DbSession,
    user: AdminUser,
    event_type: str = "test.ping",
):
    """
    Send a test webhook.

    Sends a test payload to the webhook URL and returns the response.
    """
    # Look up webhook
    query = text("""
        SELECT url, secret FROM webhooks
        WHERE id = :webhook_id AND organization_id = :org_id
    """)
    result = await session.execute(query, {
        "webhook_id": str(webhook_id),
        "org_id": str(user.organization_id),
    })
    row = result.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Webhook not found")

    row_dict = dict(row._mapping)
    webhook_url = row_dict["url"]
    webhook_secret = row_dict["secret"]

    # Build test payload
    test_payload = json.dumps({
        "event": event_type,
        "timestamp": datetime.utcnow().isoformat(),
        "data": {
            "message": "This is a test webhook delivery",
            "webhook_id": str(webhook_id),
        },
    })

    # Compute signature
    signature = "sha256=" + hmac.new(
        webhook_secret.encode(),
        test_payload.encode(),
        hashlib.sha256,
    ).hexdigest()

    # TODO: Actually send the webhook using httpx
    # For now, return the test payload info
    return wrap_response({
        "webhook_id": str(webhook_id),
        "event_type": event_type,
        "url": webhook_url,
        "status": "prepared",
        "payload_preview": json.loads(test_payload),
        "signature_header": "X-RevTown-Signature",
        "message": "Webhook test prepared. Actual delivery requires httpx integration.",
    })


@router.post("/{webhook_id}/rotate-secret", response_model=dict)
async def rotate_webhook_secret(
    webhook_id: UUID,
    session: DbSession,
    user: AdminUser,
):
    """Rotate the webhook secret."""
    new_secret = secrets.token_urlsafe(32)

    query = text("""
        UPDATE webhooks
        SET secret = :secret, updated_at = NOW()
        WHERE id = :webhook_id AND organization_id = :org_id
    """)
    result = await session.execute(query, {
        "webhook_id": str(webhook_id),
        "org_id": str(user.organization_id),
        "secret": new_secret,
    })
    await session.commit()

    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Webhook not found")

    return wrap_response({
        "webhook_id": str(webhook_id),
        "new_secret": new_secret,
        "message": "Secret rotated. Store the new secret securely - it won't be shown again.",
    })


# =============================================================================
# Webhook Delivery History
# =============================================================================


@router.get("/{webhook_id}/deliveries", response_model=dict)
async def get_webhook_deliveries(
    webhook_id: UUID,
    store: ScopedBeadStore,
    user: CurrentUser,
    status: str | None = None,
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
):
    """Get delivery history for a webhook."""
    # TODO: Query webhook_deliveries table
    return wrap_response(
        [],
        meta={"count": 0, "limit": limit, "offset": offset},
    )


@router.post("/{webhook_id}/deliveries/{delivery_id}/retry", response_model=dict)
async def retry_webhook_delivery(
    webhook_id: UUID,
    delivery_id: UUID,
    store: ScopedBeadStore,
    user: AdminUser,
):
    """Retry a failed webhook delivery."""
    # TODO: Re-queue delivery
    return wrap_response({
        "webhook_id": str(webhook_id),
        "delivery_id": str(delivery_id),
        "status": "retrying",
    })


# =============================================================================
# Available Events
# =============================================================================


@router.get("/events", response_model=dict)
async def list_webhook_events():
    """List all available webhook events."""
    return wrap_response({
        "events": WEBHOOK_EVENTS,
        "categories": {
            "bead": [e for e in WEBHOOK_EVENTS if e.startswith("bead.")],
            "polecat": [e for e in WEBHOOK_EVENTS if e.startswith("polecat.")],
            "approval": [e for e in WEBHOOK_EVENTS if e.startswith("approval.")],
            "campaign": [e for e in WEBHOOK_EVENTS if e.startswith("campaign.")],
            "test": [e for e in WEBHOOK_EVENTS if e.startswith("test.")],
            "alert": [e for e in WEBHOOK_EVENTS if e.startswith("alert.")],
        },
    })


# =============================================================================
# Signature Verification Helper
# =============================================================================


def verify_webhook_signature(
    payload: bytes,
    signature: str,
    secret: str,
) -> bool:
    """
    Verify webhook signature using HMAC-SHA256.

    The signature header format: sha256=<hex_digest>
    """
    if not signature.startswith("sha256="):
        return False

    expected_signature = signature[7:]
    computed_signature = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(computed_signature, expected_signature)
