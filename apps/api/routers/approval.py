"""
Approval Router - Queue management, decisions, and audit log.

Base path: /api/v1/approval

Human-in-the-loop checkpoint for all high-stakes outputs.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from apps.api.dependencies import CurrentUser, ScopedBeadStore
from apps.api.core.approval_store import (
    ApprovalItem,
    ApprovalStatus,
    ApprovalType,
    Urgency,
    get_approval_store,
)

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
# Request/Response Models
# =============================================================================


class ApprovalDecision(BaseModel):
    """Decision on an approval item."""

    decision: ApprovalStatus
    notes: str | None = None
    edited_content: str | None = None  # If approving with modifications


class BulkDecision(BaseModel):
    """Bulk decision on multiple items."""

    item_ids: list[str]
    decision: ApprovalStatus
    notes: str | None = None


# =============================================================================
# Queue Endpoints
# =============================================================================


@router.get("/queue", response_model=dict)
async def get_approval_queue(
    store: ScopedBeadStore,
    user: CurrentUser,
    status: ApprovalStatus = ApprovalStatus.PENDING,
    approval_type: ApprovalType | None = None,
    rig: str | None = None,
    urgency: Urgency | None = None,
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
):
    """
    Get items in the approval queue.

    By default returns pending items sorted by urgency and creation time.
    """
    approval_store = get_approval_store()
    org_id = str(user.organization_id) if user.organization_id else ""

    items, total = approval_store.get_queue(
        organization_id=org_id,
        status=status,
        approval_type=approval_type,
        rig=rig,
        urgency=urgency,
        limit=limit,
        offset=offset,
    )

    return wrap_response(
        [item.to_dict() for item in items],
        meta={
            "count": total,
            "limit": limit,
            "offset": offset,
            "filters": {
                "status": status.value if status else None,
                "approval_type": approval_type.value if approval_type else None,
                "rig": rig,
                "urgency": urgency.value if urgency else None,
            },
        },
    )


@router.get("/queue/counts", response_model=dict)
async def get_queue_counts(
    store: ScopedBeadStore,
    user: CurrentUser,
):
    """Get counts of items in each queue category."""
    approval_store = get_approval_store()
    org_id = str(user.organization_id) if user.organization_id else ""

    counts = approval_store.get_counts(org_id)
    return wrap_response(counts)


# =============================================================================
# Item Details
# =============================================================================


@router.get("/queue/{item_id}", response_model=dict)
async def get_approval_item(
    item_id: str,
    store: ScopedBeadStore,
    user: CurrentUser,
):
    """Get details of an approval queue item."""
    approval_store = get_approval_store()
    item = approval_store.get(item_id)

    if not item:
        raise HTTPException(status_code=404, detail="Approval item not found")

    # Verify organization access
    org_id = str(user.organization_id) if user.organization_id else ""
    if item.organization_id != org_id:
        raise HTTPException(status_code=404, detail="Approval item not found")

    return wrap_response({
        "item": item.to_dict(),
        "full_content": item.full_content,
        "bead": None,  # TODO: Load from BeadStore
        "bead_history": [],  # TODO: Load from BeadStore
    })


@router.get("/queue/{item_id}/context", response_model=dict)
async def get_approval_context(
    item_id: str,
    store: ScopedBeadStore,
    user: CurrentUser,
):
    """
    Get full context for reviewing an approval item.

    Includes:
    - The Bead being approved
    - Related Beads (e.g., lead info for outreach)
    - Refinery scores and warnings
    - Witness check results
    - For PR pitches: journalist history
    """
    approval_store = get_approval_store()
    item = approval_store.get(item_id)

    if not item:
        raise HTTPException(status_code=404, detail="Approval item not found")

    org_id = str(user.organization_id) if user.organization_id else ""
    if item.organization_id != org_id:
        raise HTTPException(status_code=404, detail="Approval item not found")

    return wrap_response({
        "item_id": item_id,
        "item": item.to_dict(),
        "full_content": item.full_content,
        "bead": None,  # TODO: Load from BeadStore
        "related_beads": [],
        "refinery": {
            "scores": item.refinery_scores,
            "warnings": item.refinery_warnings,
            "passed": item.refinery_passed,
        },
        "witness": {
            "issues": item.witness_issues,
            "passed": item.witness_passed,
        },
        "history": [],  # TODO: Load from BeadStore
    })


# =============================================================================
# Decisions
# =============================================================================


@router.post("/queue/{item_id}/decide", response_model=dict)
async def make_decision(
    item_id: str,
    decision: ApprovalDecision,
    store: ScopedBeadStore,
    user: CurrentUser,
):
    """
    Make a decision on an approval item.

    Decisions:
    - approved: Item is approved and will be processed
    - rejected: Item is rejected and archived
    - sent_back: Item needs rework by the Polecat

    The decision is signed with the authenticated user's identity
    and logged to the Bead ledger (audit trail).
    """
    approval_store = get_approval_store()
    item = approval_store.get(item_id)

    if not item:
        raise HTTPException(status_code=404, detail="Approval item not found")

    org_id = str(user.organization_id) if user.organization_id else ""
    if item.organization_id != org_id:
        raise HTTPException(status_code=404, detail="Approval item not found")

    if item.status != ApprovalStatus.PENDING:
        raise HTTPException(status_code=400, detail=f"Item already {item.status.value}")

    # Make the decision
    updated_item = approval_store.decide(
        item_id=item_id,
        decision=decision.decision,
        user_id=str(user.user_id),
        notes=decision.notes,
        edited_content=decision.edited_content,
    )

    if not updated_item:
        raise HTTPException(status_code=500, detail="Failed to update item")

    return wrap_response({
        "item_id": item_id,
        "decision": decision.decision.value,
        "decided_by": str(user.user_id),
        "decided_at": updated_item.decided_at.isoformat() if updated_item.decided_at else None,
        "notes": decision.notes,
    })


@router.post("/queue/{item_id}/approve", response_model=dict)
async def quick_approve(
    item_id: str,
    store: ScopedBeadStore,
    user: CurrentUser,
):
    """Quick approve an item (one-click)."""
    return await make_decision(
        item_id,
        ApprovalDecision(decision=ApprovalStatus.APPROVED),
        store,
        user,
    )


@router.post("/queue/{item_id}/reject", response_model=dict)
async def quick_reject(
    item_id: str,
    reason: str | None = None,
    store: ScopedBeadStore = None,
    user: CurrentUser = None,
):
    """Quick reject an item."""
    return await make_decision(
        item_id,
        ApprovalDecision(decision=ApprovalStatus.REJECTED, notes=reason),
        store,
        user,
    )


# =============================================================================
# Bulk Operations
# =============================================================================


@router.post("/queue/bulk-decide", response_model=dict)
async def bulk_decide(
    bulk: BulkDecision,
    store: ScopedBeadStore,
    user: CurrentUser,
):
    """Make the same decision on multiple items."""
    approval_store = get_approval_store()
    org_id = str(user.organization_id) if user.organization_id else ""

    results = []
    for item_id in bulk.item_ids:
        item = approval_store.get(item_id)
        if not item or item.organization_id != org_id:
            results.append({"item_id": item_id, "status": "not_found"})
            continue

        if item.status != ApprovalStatus.PENDING:
            results.append({"item_id": item_id, "status": f"already_{item.status.value}"})
            continue

        updated = approval_store.decide(
            item_id=item_id,
            decision=bulk.decision,
            user_id=str(user.user_id),
            notes=bulk.notes,
        )

        if updated:
            results.append({"item_id": item_id, "status": "processed"})
        else:
            results.append({"item_id": item_id, "status": "failed"})

    processed = len([r for r in results if r["status"] == "processed"])

    return wrap_response({
        "processed": processed,
        "total": len(bulk.item_ids),
        "decision": bulk.decision.value,
        "results": results,
    })


# =============================================================================
# Audit Log
# =============================================================================


@router.get("/audit-log", response_model=dict)
async def get_audit_log(
    store: ScopedBeadStore,
    user: CurrentUser,
    action: str | None = None,
    user_id: str | None = None,
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
):
    """Get the approval audit log."""
    approval_store = get_approval_store()
    org_id = str(user.organization_id) if user.organization_id else ""

    entries, total = approval_store.get_audit_log(
        organization_id=org_id,
        action=action,
        user_id=user_id,
        limit=limit,
        offset=offset,
    )

    return wrap_response(
        [entry.to_dict() for entry in entries],
        meta={"count": total, "limit": limit, "offset": offset},
    )


# =============================================================================
# PR-Specific (Press Room queue)
# =============================================================================


@router.get("/queue/pr-pitches", response_model=dict)
async def get_pr_pitch_queue(
    store: ScopedBeadStore,
    user: CurrentUser,
    limit: int = Query(50, le=200),
):
    """
    Get PR pitches awaiting approval.

    PR pitches ALWAYS require human approval - no exceptions.
    Includes journalist relationship history for context.
    """
    approval_store = get_approval_store()
    org_id = str(user.organization_id) if user.organization_id else ""

    items, total = approval_store.get_queue(
        organization_id=org_id,
        status=ApprovalStatus.PENDING,
        approval_type=ApprovalType.PR_PITCH,
        limit=limit,
    )

    return wrap_response(
        [item.to_dict() for item in items],
        meta={"count": total, "limit": limit},
    )


# =============================================================================
# SMS-Specific (The Wire queue)
# =============================================================================


@router.get("/queue/sms", response_model=dict)
async def get_sms_queue(
    store: ScopedBeadStore,
    user: CurrentUser,
    limit: int = Query(50, le=200),
):
    """
    Get SMS messages awaiting approval.

    SMS messages ALWAYS require human approval - no exceptions.
    The Wire is human-assisted only.
    """
    approval_store = get_approval_store()
    org_id = str(user.organization_id) if user.organization_id else ""

    items, total = approval_store.get_queue(
        organization_id=org_id,
        status=ApprovalStatus.PENDING,
        approval_type=ApprovalType.SMS,
        limit=limit,
    )

    return wrap_response(
        [item.to_dict() for item in items],
        meta={"count": total, "limit": limit},
    )


# =============================================================================
# A/B Test Winners
# =============================================================================


@router.get("/queue/test-winners", response_model=dict)
async def get_test_winner_queue(
    store: ScopedBeadStore,
    user: CurrentUser,
    limit: int = Query(50, le=200),
):
    """
    Get A/B test winners awaiting approval.

    Test winner declarations require human approval before promotion.
    """
    approval_store = get_approval_store()
    org_id = str(user.organization_id) if user.organization_id else ""

    items, total = approval_store.get_queue(
        organization_id=org_id,
        status=ApprovalStatus.PENDING,
        approval_type=ApprovalType.TEST_WINNER,
        limit=limit,
    )

    return wrap_response(
        [item.to_dict() for item in items],
        meta={"count": total, "limit": limit},
    )
