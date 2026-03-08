"""
Approval Router - Queue management, decisions, and audit log.

Base path: /api/v1/approval

Human-in-the-loop checkpoint for all high-stakes outputs.
"""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import BaseModel

from apps.api.dependencies import CurrentUser, DbSession, ScopedBeadStore

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
# Enums & Models
# =============================================================================


class ApprovalType(str, Enum):
    CONTENT = "content"
    OUTREACH = "outreach"
    PR_PITCH = "pr_pitch"
    SMS = "sms"
    TEST_WINNER = "test_winner"
    OTHER = "other"


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    SENT_BACK = "sent_back"
    EXPIRED = "expired"


class Urgency(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class ApprovalDecision(BaseModel):
    """Decision on an approval item."""

    decision: ApprovalStatus
    notes: str | None = None
    edited_content: str | None = None  # If approving with modifications


class ApprovalItem(BaseModel):
    """An item in the approval queue."""

    id: UUID
    bead_type: str
    bead_id: UUID
    rig: str
    approval_type: ApprovalType
    urgency: Urgency
    preview_title: str | None
    preview_content: str | None
    refinery_scores: dict[str, Any] | None
    refinery_warnings: list[str] | None
    status: ApprovalStatus
    created_at: datetime
    expires_at: datetime | None


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
    # TODO: Query approval_queue table
    return wrap_response(
        [],
        meta={
            "count": 0,
            "limit": limit,
            "offset": offset,
            "filters": {
                "status": status,
                "approval_type": approval_type,
                "rig": rig,
                "urgency": urgency,
            },
        },
    )


@router.get("/queue/counts", response_model=dict)
async def get_queue_counts(
    store: ScopedBeadStore,
    user: CurrentUser,
):
    """Get counts of items in each queue category."""
    # TODO: Aggregate from approval_queue table
    return wrap_response({
        "total_pending": 0,
        "by_type": {
            "content": 0,
            "outreach": 0,
            "pr_pitch": 0,
            "sms": 0,
            "test_winner": 0,
            "other": 0,
        },
        "by_urgency": {
            "critical": 0,
            "high": 0,
            "normal": 0,
            "low": 0,
        },
        "by_rig": {},
    })


# =============================================================================
# Item Details
# =============================================================================


@router.get("/queue/{item_id}", response_model=dict)
async def get_approval_item(
    item_id: UUID,
    store: ScopedBeadStore,
    user: CurrentUser,
):
    """Get details of an approval queue item."""
    # TODO: Look up in approval_queue table
    return wrap_response({
        "id": str(item_id),
        "status": "pending",
        "bead": None,
        "bead_history": [],
        "refinery_details": None,
        "witness_details": None,
        "polecat_execution": None,
    })


@router.get("/queue/{item_id}/context", response_model=dict)
async def get_approval_context(
    item_id: UUID,
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
    return wrap_response({
        "item_id": str(item_id),
        "bead": None,
        "related_beads": [],
        "refinery": {
            "scores": {},
            "warnings": [],
            "passed": True,
        },
        "witness": {
            "contradictions": [],
            "duplicates": [],
            "passed": True,
        },
        "history": [],
    })


# =============================================================================
# Decisions
# =============================================================================


@router.post("/queue/{item_id}/decide", response_model=dict)
async def make_decision(
    item_id: UUID,
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
    # TODO: Update approval_queue, log to audit_log
    return wrap_response({
        "item_id": str(item_id),
        "decision": decision.decision,
        "decided_by": str(user.user_id),
        "decided_at": datetime.utcnow().isoformat(),
        "notes": decision.notes,
    })


@router.post("/queue/{item_id}/approve", response_model=dict)
async def quick_approve(
    item_id: UUID,
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
    item_id: UUID,
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


class BulkDecision(BaseModel):
    """Bulk decision on multiple items."""

    item_ids: list[UUID]
    decision: ApprovalStatus
    notes: str | None = None


@router.post("/queue/bulk-decide", response_model=dict)
async def bulk_decide(
    bulk: BulkDecision,
    store: ScopedBeadStore,
    user: CurrentUser,
):
    """Make the same decision on multiple items."""
    # TODO: Implement bulk update
    return wrap_response({
        "processed": len(bulk.item_ids),
        "decision": bulk.decision,
        "results": [
            {"item_id": str(item_id), "status": "processed"}
            for item_id in bulk.item_ids
        ],
    })


# =============================================================================
# Audit Log
# =============================================================================


@router.get("/audit-log", response_model=dict)
async def get_audit_log(
    store: ScopedBeadStore,
    user: CurrentUser,
    action: str | None = None,
    user_id: UUID | None = None,
    entity_type: str | None = None,
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
):
    """Get the approval audit log."""
    # TODO: Query audit_log table
    return wrap_response(
        [],
        meta={"count": 0, "limit": limit, "offset": offset},
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
    # TODO: Query with journalist history join
    return wrap_response(
        [],
        meta={"count": 0, "limit": limit},
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
    return wrap_response(
        [],
        meta={"count": 0, "limit": limit},
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
    return wrap_response(
        [],
        meta={"count": 0, "limit": limit},
    )
