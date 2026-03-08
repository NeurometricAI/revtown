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

from fastapi import APIRouter, Header, HTTPException, Query, Request
from pydantic import BaseModel, HttpUrl

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
    store: ScopedBeadStore,
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

    # TODO: Store in webhooks table

    return wrap_response({
        "webhook_id": str(webhook_id),
        "url": str(data.url),
        "events": data.events,
        "secret": secret,  # Only returned once at creation
        "message": "Webhook registered. Store the secret securely - it won't be shown again.",
    })


@router.get("", response_model=dict)
async def list_webhooks(
    store: ScopedBeadStore,
    user: CurrentUser,
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
):
    """List all registered webhooks for the organization."""
    # TODO: Query webhooks table
    return wrap_response(
        [],
        meta={"count": 0, "limit": limit, "offset": offset},
    )


@router.get("/{webhook_id}", response_model=dict)
async def get_webhook(
    webhook_id: UUID,
    store: ScopedBeadStore,
    user: CurrentUser,
):
    """Get details of a specific webhook."""
    # TODO: Look up webhook
    return wrap_response({
        "webhook_id": str(webhook_id),
        "url": None,
        "events": [],
        "is_active": False,
        "last_triggered_at": None,
        "failure_count": 0,
    })


@router.patch("/{webhook_id}", response_model=dict)
async def update_webhook(
    webhook_id: UUID,
    data: WebhookUpdate,
    store: ScopedBeadStore,
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

    # TODO: Update webhooks table
    return wrap_response({
        "webhook_id": str(webhook_id),
        "updated": True,
    })


@router.delete("/{webhook_id}", response_model=dict)
async def delete_webhook(
    webhook_id: UUID,
    store: ScopedBeadStore,
    user: AdminUser,
):
    """Delete a webhook."""
    # TODO: Delete from webhooks table
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
    event_type: str = "test.ping",
    store: ScopedBeadStore = None,
    user: AdminUser = None,
):
    """
    Send a test webhook.

    Sends a test payload to the webhook URL and returns the response.
    """
    # TODO: Send test webhook
    return wrap_response({
        "webhook_id": str(webhook_id),
        "event_type": event_type,
        "status": "sent",
        "response_code": None,
        "response_time_ms": None,
    })


@router.post("/{webhook_id}/rotate-secret", response_model=dict)
async def rotate_webhook_secret(
    webhook_id: UUID,
    store: ScopedBeadStore,
    user: AdminUser,
):
    """Rotate the webhook secret."""
    new_secret = secrets.token_urlsafe(32)

    # TODO: Update webhooks table with new secret hash

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
