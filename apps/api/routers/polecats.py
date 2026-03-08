"""
Polecats Router - Spawn, status, list, and cancel Polecat executions.

Base path: /api/v1/polecats
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
# Polecat Types (organized by Rig)
# =============================================================================


class Rig(str, Enum):
    CONTENT_FACTORY = "content_factory"
    SDR_HIVE = "sdr_hive"
    SOCIAL_COMMAND = "social_command"
    PRESS_ROOM = "press_room"
    INTELLIGENCE_STATION = "intelligence_station"
    LANDING_PAD = "landing_pad"
    WIRE = "wire"
    REPO_WATCH = "repo_watch"


class PolecatStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# Available Polecat types per Rig
POLECAT_TYPES: dict[Rig, list[str]] = {
    Rig.CONTENT_FACTORY: [
        "blog_draft",
        "seo_meta",
        "social_snippet",
        "content_calendar",
        "image_brief",
    ],
    Rig.SDR_HIVE: [
        "scout",
        "enrich",
        "personalize",
        "sequence",
        "sms_draft",
    ],
    Rig.SOCIAL_COMMAND: [
        "draft_tweet",
        "draft_linkedin",
        "draft_threads",
        "engagement",
        "hashtag_research",
        "cross_post_adapt",
    ],
    Rig.PRESS_ROOM: [
        "journalist_research",
        "pitch_draft",
        "pr_wire_draft",
        "haro_watcher",
        "embargo",
    ],
    Rig.INTELLIGENCE_STATION: [
        "competitor_web_change",
        "competitor_jobs",
        "competitor_social",
        "competitor_review",
        "competitor_pr",
    ],
    Rig.LANDING_PAD: [
        "landing_page_draft",
        "landing_page_variant",
        "email_variant",
        "winner_declare",
    ],
    Rig.WIRE: [
        "sms_draft",  # Note: All SMS output requires human approval
    ],
    Rig.REPO_WATCH: [
        "repo_stargazer",
        "issue_trend",
        "pr_mention",
        "readme_optimize",
        "devrel_content",
        "changelog",
    ],
}


# =============================================================================
# Request/Response Models
# =============================================================================


class SpawnPolecatRequest(BaseModel):
    """Request to spawn a new Polecat."""

    polecat_type: str
    rig: Rig
    bead_id: UUID
    campaign_id: UUID | None = None
    config: dict[str, Any] | None = None


class PolecatResponse(BaseModel):
    """Polecat execution info."""

    id: UUID
    polecat_type: str
    rig: str
    status: PolecatStatus
    bead_id: UUID
    campaign_id: UUID | None
    started_at: datetime
    completed_at: datetime | None
    error_message: str | None


# =============================================================================
# Endpoints
# =============================================================================


@router.post("", response_model=dict)
async def spawn_polecat(
    request: SpawnPolecatRequest,
    store: ScopedBeadStore,
    user: CurrentUser,
):
    """
    Spawn a new Polecat to execute a task.

    The Polecat will:
    1. Read context from the specified Bead
    2. Execute its task via Neurometric
    3. Run output through Refinery + Witness
    4. Write results back to the Bead ledger

    Returns immediately with a polecat_id for status polling.
    """
    # Validate polecat type exists for the rig
    valid_types = POLECAT_TYPES.get(request.rig, [])
    if request.polecat_type not in valid_types:
        return wrap_response(
            None,
            meta={
                "error": f"Invalid polecat_type '{request.polecat_type}' for rig '{request.rig}'",
                "valid_types": valid_types,
            },
        )

    # TODO: Actually spawn the Polecat via Temporal
    # For now, return a placeholder
    from uuid import uuid4

    polecat_id = uuid4()

    return wrap_response({
        "polecat_id": str(polecat_id),
        "polecat_type": request.polecat_type,
        "rig": request.rig,
        "bead_id": str(request.bead_id),
        "status": "pending",
        "message": "Polecat spawned - use /polecats/{id}/status to track progress",
    })


@router.get("/{polecat_id}/status", response_model=dict)
async def get_polecat_status(
    polecat_id: UUID,
    store: ScopedBeadStore,
    user: CurrentUser,
):
    """Get the status of a Polecat execution."""
    # TODO: Look up in polecat_executions table
    return wrap_response({
        "polecat_id": str(polecat_id),
        "status": "pending",
        "progress": None,
        "error": None,
    })


@router.get("/{polecat_id}", response_model=dict)
async def get_polecat(
    polecat_id: UUID,
    store: ScopedBeadStore,
    user: CurrentUser,
):
    """Get full details of a Polecat execution."""
    # TODO: Look up in polecat_executions table
    return wrap_response({
        "polecat_id": str(polecat_id),
        "polecat_type": None,
        "rig": None,
        "status": "pending",
        "input_bead_id": None,
        "output_bead_ids": [],
        "refinery_scores": None,
        "witness_passed": None,
        "model_used": None,
        "tokens_input": None,
        "tokens_output": None,
        "started_at": None,
        "completed_at": None,
        "duration_ms": None,
        "error_message": None,
    })


@router.post("/{polecat_id}/cancel", response_model=dict)
async def cancel_polecat(
    polecat_id: UUID,
    store: ScopedBeadStore,
    user: CurrentUser,
):
    """Cancel a running Polecat execution."""
    # TODO: Cancel via Temporal
    return wrap_response({
        "polecat_id": str(polecat_id),
        "status": "cancelled",
        "message": "Polecat cancellation requested",
    })


@router.get("", response_model=dict)
async def list_polecats(
    store: ScopedBeadStore,
    user: CurrentUser,
    rig: Rig | None = None,
    status: PolecatStatus | None = None,
    campaign_id: UUID | None = None,
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
):
    """List Polecat executions for the organization."""
    # TODO: Query polecat_executions table
    return wrap_response(
        [],
        meta={"count": 0, "limit": limit, "offset": offset},
    )


# =============================================================================
# Rig & Polecat Type Discovery
# =============================================================================


@router.get("/types", response_model=dict)
async def list_polecat_types():
    """List all available Polecat types organized by Rig."""
    return wrap_response({
        rig.value: types for rig, types in POLECAT_TYPES.items()
    })


@router.get("/types/{rig}", response_model=dict)
async def list_polecat_types_for_rig(rig: Rig):
    """List available Polecat types for a specific Rig."""
    return wrap_response({
        "rig": rig.value,
        "polecat_types": POLECAT_TYPES.get(rig, []),
    })
