"""
Billing Router - Stripe integration (SaaS mode only).

Base path: /api/v1/billing
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel

from apps.api.config import settings
from apps.api.dependencies import AdminUser, CurrentUser, DbSession, OwnerUser

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
# Plan Tiers
# =============================================================================

PLAN_TIERS = {
    "free": {
        "name": "Free",
        "price_monthly": 0,
        "limits": {
            "rigs": 1,
            "polecats_per_month": 100,
            "seats": 1,
        },
    },
    "pro": {
        "name": "Pro",
        "price_monthly": 99,
        "stripe_price_id": settings.stripe_price_id_pro,
        "limits": {
            "rigs": 4,
            "polecats_per_month": 5000,
            "seats": 5,
        },
    },
    "scale": {
        "name": "Scale",
        "price_monthly": 499,
        "stripe_price_id": settings.stripe_price_id_scale,
        "limits": {
            "rigs": 8,
            "polecats_per_month": 50000,
            "seats": 25,
        },
    },
    "enterprise": {
        "name": "Enterprise",
        "price_monthly": None,  # Custom
        "limits": {
            "rigs": "unlimited",
            "polecats_per_month": "unlimited",
            "seats": "unlimited",
        },
    },
}


# =============================================================================
# Subscription Management
# =============================================================================


@router.get("/subscription", response_model=dict)
async def get_subscription(
    user: CurrentUser,
    session: DbSession,
):
    """Get current subscription details."""
    # TODO: Query from organizations table
    return wrap_response({
        "plan_tier": "free",
        "status": "active",
        "current_period_start": datetime.utcnow().isoformat(),
        "current_period_end": None,
        "cancel_at_period_end": False,
        "stripe_subscription_id": None,
    })


@router.get("/plans", response_model=dict)
async def list_plans(
    user: CurrentUser,
):
    """List available subscription plans."""
    return wrap_response(PLAN_TIERS)


@router.post("/checkout", response_model=dict)
async def create_checkout_session(
    plan_tier: str,
    user: OwnerUser,
    session: DbSession,
):
    """
    Create a Stripe Checkout session for subscription.

    Returns a URL to redirect the user to Stripe Checkout.
    """
    if plan_tier not in ["pro", "scale"]:
        return wrap_response(
            None,
            meta={"error": "Invalid plan tier. Use 'pro' or 'scale'."},
        )

    if not settings.stripe_secret_key:
        return wrap_response(
            None,
            meta={"error": "Stripe not configured"},
        )

    # TODO: Create Stripe Checkout session
    # stripe.checkout.Session.create(...)

    return wrap_response({
        "checkout_url": "https://checkout.stripe.com/...",
        "plan_tier": plan_tier,
    })


@router.post("/portal", response_model=dict)
async def create_customer_portal_session(
    user: OwnerUser,
    session: DbSession,
):
    """
    Create a Stripe Customer Portal session.

    Returns a URL to redirect the user to manage their subscription.
    """
    if not settings.stripe_secret_key:
        return wrap_response(
            None,
            meta={"error": "Stripe not configured"},
        )

    # TODO: Create Stripe Customer Portal session
    # stripe.billing_portal.Session.create(...)

    return wrap_response({
        "portal_url": "https://billing.stripe.com/...",
    })


@router.post("/subscription/cancel", response_model=dict)
async def cancel_subscription(
    user: OwnerUser,
    session: DbSession,
):
    """
    Cancel the current subscription.

    Cancellation takes effect at the end of the current billing period.
    """
    # TODO: Update Stripe subscription to cancel at period end

    return wrap_response({
        "message": "Subscription will be cancelled at the end of the current period",
        "cancel_at_period_end": True,
    })


@router.post("/subscription/resume", response_model=dict)
async def resume_subscription(
    user: OwnerUser,
    session: DbSession,
):
    """
    Resume a cancelled subscription.

    Only works if the cancellation hasn't taken effect yet.
    """
    # TODO: Update Stripe subscription to not cancel

    return wrap_response({
        "message": "Subscription resumed",
        "cancel_at_period_end": False,
    })


# =============================================================================
# Invoices
# =============================================================================


@router.get("/invoices", response_model=dict)
async def list_invoices(
    user: AdminUser,
    session: DbSession,
    limit: int = 10,
):
    """List past invoices."""
    # TODO: Query Stripe for invoices

    return wrap_response([])


@router.get("/invoices/{invoice_id}", response_model=dict)
async def get_invoice(
    invoice_id: str,
    user: AdminUser,
    session: DbSession,
):
    """Get a specific invoice."""
    # TODO: Query Stripe for invoice

    return wrap_response({
        "id": invoice_id,
        "amount_due": 0,
        "status": "paid",
        "pdf_url": None,
    })


# =============================================================================
# Payment Methods
# =============================================================================


@router.get("/payment-methods", response_model=dict)
async def list_payment_methods(
    user: OwnerUser,
    session: DbSession,
):
    """List saved payment methods."""
    # TODO: Query Stripe for payment methods

    return wrap_response([])


@router.post("/payment-methods/setup", response_model=dict)
async def setup_payment_method(
    user: OwnerUser,
    session: DbSession,
):
    """
    Create a setup session for adding a new payment method.

    Returns a URL to redirect the user to Stripe.
    """
    if not settings.stripe_secret_key:
        return wrap_response(
            None,
            meta={"error": "Stripe not configured"},
        )

    # TODO: Create Stripe Setup Intent

    return wrap_response({
        "setup_url": "https://checkout.stripe.com/...",
    })


@router.delete("/payment-methods/{payment_method_id}", response_model=dict)
async def delete_payment_method(
    payment_method_id: str,
    user: OwnerUser,
    session: DbSession,
):
    """Delete a saved payment method."""
    # TODO: Delete from Stripe

    return wrap_response({
        "id": payment_method_id,
        "message": "Payment method deleted",
    })


# =============================================================================
# Usage-Based Billing
# =============================================================================


@router.get("/usage/current", response_model=dict)
async def get_current_usage(
    user: CurrentUser,
    session: DbSession,
):
    """Get current period usage for billing."""
    # TODO: Query usage_records table

    return wrap_response({
        "period_start": datetime.utcnow().replace(day=1).isoformat(),
        "polecat_executions": 0,
        "included_in_plan": 100,
        "overage": 0,
        "overage_rate_cents": 5,  # $0.05 per overage execution
    })


@router.get("/usage/history", response_model=dict)
async def get_usage_history(
    user: AdminUser,
    session: DbSession,
    months: int = 6,
):
    """Get historical usage."""
    # TODO: Query usage_records table

    return wrap_response([])


# =============================================================================
# Stripe Webhooks
# =============================================================================


@router.post("/webhooks/stripe", include_in_schema=False)
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="Stripe-Signature"),
    session: DbSession = None,
):
    """
    Handle Stripe webhook events.

    Events handled:
    - checkout.session.completed
    - customer.subscription.created
    - customer.subscription.updated
    - customer.subscription.deleted
    - invoice.paid
    - invoice.payment_failed
    """
    if not settings.stripe_webhook_secret:
        raise HTTPException(status_code=400, detail="Webhook not configured")

    # Get raw body
    body = await request.body()

    # TODO: Verify webhook signature
    # try:
    #     event = stripe.Webhook.construct_event(
    #         body, stripe_signature, settings.stripe_webhook_secret
    #     )
    # except ValueError:
    #     raise HTTPException(status_code=400, detail="Invalid payload")
    # except stripe.error.SignatureVerificationError:
    #     raise HTTPException(status_code=400, detail="Invalid signature")

    # TODO: Handle events
    # event_type = event["type"]
    # if event_type == "checkout.session.completed":
    #     ...

    return {"received": True}
