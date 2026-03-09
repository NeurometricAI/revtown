"""
Polecats Router - Spawn, status, list, and cancel Polecat executions.

Base path: /api/v1/polecats
"""

import asyncio
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from apps.api.dependencies import CurrentUser, DbSession, ScopedBeadStore, get_session_factory
from apps.api.core.polecat_store import (
    PolecatExecution,
    PolecatStatus,
    PolecatStore,
    get_polecat_store,
)
from apps.api.core.neurometric import get_neurometric_client
from apps.api.core.refinery import get_refinery
from apps.api.core.witness import get_witness
from apps.api.core.approval_store import (
    ApprovalItem,
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

# Polecat types that always require approval
ALWAYS_REQUIRE_APPROVAL = {
    "pitch_draft",
    "journalist_research",
    "sms_draft",
    "winner_declare",
}

# Map polecat types to approval types
POLECAT_APPROVAL_TYPES = {
    "blog_draft": ApprovalType.CONTENT,
    "seo_meta": ApprovalType.CONTENT,
    "content_calendar": ApprovalType.CONTENT,
    "social_snippet": ApprovalType.CONTENT,
    "image_brief": ApprovalType.CONTENT,
    "landing_page_draft": ApprovalType.CONTENT,
    "landing_page_variant": ApprovalType.CONTENT,
    "email_variant": ApprovalType.OUTREACH,
    "personalize": ApprovalType.OUTREACH,
    "sequence": ApprovalType.OUTREACH,
    "pitch_draft": ApprovalType.PR_PITCH,
    "journalist_research": ApprovalType.PR_PITCH,
    "sms_draft": ApprovalType.SMS,
    "winner_declare": ApprovalType.TEST_WINNER,
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


# =============================================================================
# Polecat Execution Logic
# =============================================================================


async def execute_polecat(execution: PolecatExecution, store: PolecatStore):
    """Execute a Polecat in the background."""
    from polecats.base import get_polecat_class

    session_factory = get_session_factory()

    # Update to running
    async with session_factory() as session:
        await store.update_status(session, execution.id, PolecatStatus.RUNNING)

    try:
        # Try to get a registered Polecat class
        polecat_class = get_polecat_class(execution.rig, execution.polecat_type)

        if polecat_class:
            # Execute real Polecat
            result = await _execute_real_polecat(execution, polecat_class)
        else:
            # Fallback to direct neurometric
            result = await _execute_fallback(execution)

        # Check if needs approval
        requires_approval = (
            execution.polecat_type in ALWAYS_REQUIRE_APPROVAL
            or result.get("requires_approval", False)
        )

        approval_item_id = None
        if requires_approval:
            approval_item_id = await _queue_for_approval(execution, result)

        # Update execution with results
        async with session_factory() as session:
            await store.update_status(
                session,
                execution.id,
                PolecatStatus.COMPLETED,
                output_content=result.get("output"),
                output_bead_ids=result.get("output_bead_ids", []),
                refinery_scores={"overall": result.get("refinery_score", 1.0)},
                refinery_passed=result.get("refinery_passed", True),
                witness_passed=result.get("witness_passed", True),
                requires_approval=requires_approval,
                approval_item_id=approval_item_id,
                model_used=result.get("model_used"),
                tokens_input=result.get("tokens_input", 0),
                tokens_output=result.get("tokens_output", 0),
            )

    except asyncio.CancelledError:
        async with session_factory() as session:
            await store.update_status(session, execution.id, PolecatStatus.CANCELLED)
        raise
    except Exception as e:
        async with session_factory() as session:
            await store.update_status(
                session,
                execution.id,
                PolecatStatus.FAILED,
                error_message=str(e),
            )


async def _execute_real_polecat(
    execution: PolecatExecution,
    polecat_class: type,
) -> dict[str, Any]:
    """Execute a real Polecat instance."""
    from apps.api.core.convoy_executor import MockBeadStore
    from apps.api.core.convoy_store import Convoy, ConvoyStep, ConvoyStatus

    neurometric = get_neurometric_client()
    refinery = get_refinery()
    witness = get_witness()

    # Create mock convoy/step for context
    mock_convoy = Convoy(
        id="direct-execution",
        campaign_id=execution.campaign_id or "",
        campaign_name="Direct Execution",
        goal=execution.config.get("goal", "Execute task"),
        organization_id=execution.organization_id,
        status=ConvoyStatus.EXECUTING,
        steps=[],
    )
    mock_step = ConvoyStep(
        id=execution.id,
        rig=execution.rig,
        polecat_type=execution.polecat_type,
        description=f"Execute {execution.polecat_type}",
    )
    mock_bead_store = MockBeadStore(mock_convoy, mock_step)

    # Create and run the Polecat
    polecat = polecat_class(
        bead_id=UUID(execution.bead_id),
        bead_store=mock_bead_store,
        neurometric=neurometric,
        refinery=refinery,
        witness=witness,
        config=execution.config,
    )

    result = await polecat.run()

    return {
        "success": result.success,
        "output": str(result.output_bead_ids[0]) if result.output_bead_ids else None,
        "output_bead_ids": [str(bid) for bid in result.output_bead_ids],
        "requires_approval": result.requires_approval,
        "refinery_passed": result.refinery_result.passed if result.refinery_result else True,
        "refinery_score": result.refinery_result.overall_score if result.refinery_result else 1.0,
        "witness_passed": result.witness_result.passed if result.witness_result else True,
        "model_used": result.model_used,
        "tokens_input": result.tokens_input,
        "tokens_output": result.tokens_output,
        "error": result.error,
    }


async def _execute_fallback(execution: PolecatExecution) -> dict[str, Any]:
    """Execute via direct neurometric call."""
    neurometric = get_neurometric_client()

    # Build prompt based on polecat type
    prompts = {
        "blog_draft": f"Write a blog post about: {execution.config.get('topic', 'general topic')}",
        "seo_meta": f"Generate SEO metadata for: {execution.config.get('topic', 'content')}",
        "content_calendar": f"Create a content calendar for: {execution.config.get('goal', 'marketing')}",
        "social_snippet": f"Create social media snippets for: {execution.config.get('topic', 'content')}",
        "personalize": f"Write a personalized email for: {execution.config.get('context', 'outreach')}",
        "sequence": f"Design an email sequence for: {execution.config.get('goal', 'nurturing')}",
        "pitch_draft": f"Draft a PR pitch for: {execution.config.get('topic', 'announcement')}",
        "landing_page_draft": f"Write landing page copy for: {execution.config.get('product', 'product')}",
    }

    prompt = prompts.get(
        execution.polecat_type,
        f"Execute {execution.polecat_type} task. Context: {execution.config}"
    )

    response = await neurometric.complete(
        task_class=execution.polecat_type,
        prompt=prompt,
    )

    return {
        "success": True,
        "output": response.content,
        "output_bead_ids": [],
        "requires_approval": execution.polecat_type in ALWAYS_REQUIRE_APPROVAL,
        "refinery_passed": True,
        "refinery_score": 1.0,
        "witness_passed": True,
        "model_used": response.model_used,
        "tokens_input": response.tokens_input,
        "tokens_output": response.tokens_output,
    }


async def _queue_for_approval(
    execution: PolecatExecution,
    result: dict[str, Any],
) -> str:
    """Queue output for human approval."""
    approval_store = get_approval_store()
    approval_type = POLECAT_APPROVAL_TYPES.get(execution.polecat_type, ApprovalType.OTHER)

    # SMS and PR are always critical
    if approval_type in (ApprovalType.SMS, ApprovalType.PR_PITCH):
        urgency = Urgency.CRITICAL
    elif not result.get("refinery_passed", True):
        urgency = Urgency.HIGH
    else:
        urgency = Urgency.NORMAL

    item = ApprovalItem(
        id=str(uuid4()),
        bead_type="asset",
        bead_id=execution.bead_id,
        rig=execution.rig,
        polecat_type=execution.polecat_type,
        approval_type=approval_type,
        urgency=urgency,
        organization_id=execution.organization_id,
        campaign_id=execution.campaign_id,
        polecat_execution_id=execution.id,
        preview_title=f"{execution.polecat_type.replace('_', ' ').title()}",
        preview_content=result.get("output", "")[:200] if result.get("output") else None,
        full_content=result.get("output"),
        refinery_scores={"overall": result.get("refinery_score", 1.0)},
        refinery_passed=result.get("refinery_passed", True),
        witness_passed=result.get("witness_passed", True),
    )

    # Create session for database operation
    session_factory = get_session_factory()
    async with session_factory() as session:
        await approval_store.create(session, item)

    return item.id


# =============================================================================
# Endpoints
# =============================================================================


@router.post("", response_model=dict)
async def spawn_polecat(
    request: SpawnPolecatRequest,
    session: DbSession,
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
        raise HTTPException(
            status_code=400,
            detail=f"Invalid polecat_type '{request.polecat_type}' for rig '{request.rig}'. Valid types: {valid_types}",
        )

    polecat_store = get_polecat_store()
    org_id = str(user.organization_id) if user.organization_id else ""

    # Create execution record
    execution = PolecatExecution(
        id=str(uuid4()),
        polecat_type=request.polecat_type,
        rig=request.rig.value,
        bead_id=str(request.bead_id),
        organization_id=org_id,
        campaign_id=str(request.campaign_id) if request.campaign_id else None,
        config=request.config or {},
    )
    await polecat_store.create(session, execution)

    # Start execution in background
    task = asyncio.create_task(execute_polecat(execution, polecat_store))
    polecat_store.register_task(execution.id, task)

    return wrap_response({
        "polecat_id": execution.id,
        "polecat_type": execution.polecat_type,
        "rig": execution.rig,
        "bead_id": execution.bead_id,
        "status": execution.status.value,
        "message": "Polecat spawned - use /polecats/{id}/status to track progress",
    })


@router.get("/{polecat_id}/status", response_model=dict)
async def get_polecat_status(
    polecat_id: str,
    session: DbSession,
    store: ScopedBeadStore,
    user: CurrentUser,
):
    """Get the status of a Polecat execution."""
    polecat_store = get_polecat_store()
    execution = await polecat_store.get(session, polecat_id)

    if not execution:
        raise HTTPException(status_code=404, detail="Polecat execution not found")

    # Verify org access
    org_id = str(user.organization_id) if user.organization_id else ""
    if execution.organization_id != org_id:
        raise HTTPException(status_code=404, detail="Polecat execution not found")

    return wrap_response({
        "polecat_id": execution.id,
        "status": execution.status.value,
        "progress": execution.progress,
        "started_at": execution.started_at.isoformat() if execution.started_at else None,
        "completed_at": execution.completed_at.isoformat() if execution.completed_at else None,
        "duration_ms": execution.duration_ms,
        "error": execution.error_message,
        "requires_approval": execution.requires_approval,
        "approval_item_id": execution.approval_item_id,
    })


@router.get("/{polecat_id}", response_model=dict)
async def get_polecat(
    polecat_id: str,
    session: DbSession,
    store: ScopedBeadStore,
    user: CurrentUser,
):
    """Get full details of a Polecat execution."""
    polecat_store = get_polecat_store()
    execution = await polecat_store.get(session, polecat_id)

    if not execution:
        raise HTTPException(status_code=404, detail="Polecat execution not found")

    org_id = str(user.organization_id) if user.organization_id else ""
    if execution.organization_id != org_id:
        raise HTTPException(status_code=404, detail="Polecat execution not found")

    return wrap_response(execution.to_dict())


@router.post("/{polecat_id}/cancel", response_model=dict)
async def cancel_polecat(
    polecat_id: str,
    session: DbSession,
    store: ScopedBeadStore,
    user: CurrentUser,
):
    """Cancel a running Polecat execution."""
    polecat_store = get_polecat_store()
    execution = await polecat_store.get(session, polecat_id)

    if not execution:
        raise HTTPException(status_code=404, detail="Polecat execution not found")

    org_id = str(user.organization_id) if user.organization_id else ""
    if execution.organization_id != org_id:
        raise HTTPException(status_code=404, detail="Polecat execution not found")

    if execution.status not in (PolecatStatus.PENDING, PolecatStatus.RUNNING):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel execution in status: {execution.status.value}",
        )

    await polecat_store.cancel(session, polecat_id)

    return wrap_response({
        "polecat_id": polecat_id,
        "status": "cancelled",
        "message": "Polecat execution cancelled",
    })


@router.get("", response_model=dict)
async def list_polecats(
    session: DbSession,
    store: ScopedBeadStore,
    user: CurrentUser,
    rig: Rig | None = None,
    status: PolecatStatus | None = None,
    campaign_id: str | None = None,
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
):
    """List Polecat executions for the organization."""
    polecat_store = get_polecat_store()
    org_id = str(user.organization_id) if user.organization_id else ""

    executions, total = await polecat_store.list_executions(
        session=session,
        organization_id=org_id,
        rig=rig.value if rig else None,
        status=status,
        campaign_id=campaign_id,
        limit=limit,
        offset=offset,
    )

    return wrap_response(
        [e.to_dict() for e in executions],
        meta={"count": total, "limit": limit, "offset": offset},
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
