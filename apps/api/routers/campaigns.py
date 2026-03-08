"""
Campaigns Router - Campaign CRUD and Convoy management.

Base path: /api/v1/campaigns
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Query

from apps.api.dependencies import CurrentUser, ScopedBeadStore
from apps.api.models.beads import CampaignBead, CampaignBeadCreate, CampaignBeadUpdate

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
# Campaign CRUD
# =============================================================================


@router.post("", response_model=dict)
async def create_campaign(
    data: CampaignBeadCreate,
    store: ScopedBeadStore,
    user: CurrentUser,
):
    """Create a new Campaign."""
    campaign = await store.create_campaign(data, created_by=user.user_id)
    return wrap_response(campaign.model_dump())


@router.get("/{campaign_id}", response_model=dict)
async def get_campaign(
    campaign_id: UUID,
    store: ScopedBeadStore,
    user: CurrentUser,
):
    """Get a Campaign by ID."""
    campaign = await store.get_campaign(campaign_id)
    return wrap_response(campaign.model_dump())


@router.patch("/{campaign_id}", response_model=dict)
async def update_campaign(
    campaign_id: UUID,
    data: CampaignBeadUpdate,
    store: ScopedBeadStore,
    user: CurrentUser,
    expected_version: int | None = Query(None),
):
    """Update a Campaign."""
    campaign = await store.update_campaign(campaign_id, data, expected_version)
    return wrap_response(campaign.model_dump())


@router.get("", response_model=dict)
async def list_campaigns(
    store: ScopedBeadStore,
    user: CurrentUser,
    status: str | None = None,
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
):
    """List Campaigns for the organization."""
    campaigns = await store.list_campaigns(status, limit, offset)
    return wrap_response(
        [c.model_dump() for c in campaigns],
        meta={"count": len(campaigns), "limit": limit, "offset": offset},
    )


@router.delete("/{campaign_id}", response_model=dict)
async def archive_campaign(
    campaign_id: UUID,
    store: ScopedBeadStore,
    user: CurrentUser,
):
    """Archive a Campaign (does not delete)."""
    result = await store.archive_bead("campaign", campaign_id)
    return wrap_response({"archived": result, "campaign_id": str(campaign_id)})


# =============================================================================
# Convoy Management (Campaign execution)
# =============================================================================


@router.post("/{campaign_id}/convoy", response_model=dict)
async def create_convoy(
    campaign_id: UUID,
    store: ScopedBeadStore,
    user: CurrentUser,
):
    """
    Create a Convoy for a Campaign.

    This triggers the GTM Mayor to:
    1. Analyze the campaign goal and budget
    2. Create a sequenced set of Beads
    3. Distribute work across appropriate Rigs
    """
    # TODO: Implement via Mayor
    return wrap_response({
        "campaign_id": str(campaign_id),
        "convoy_id": "todo",
        "status": "creating",
        "message": "Convoy creation initiated - Mayor will plan execution",
    })


@router.get("/{campaign_id}/convoy", response_model=dict)
async def get_convoy_status(
    campaign_id: UUID,
    store: ScopedBeadStore,
    user: CurrentUser,
):
    """Get the current Convoy status for a Campaign."""
    # TODO: Implement convoy tracking
    return wrap_response({
        "campaign_id": str(campaign_id),
        "convoy": None,
        "message": "No active convoy for this campaign",
    })


@router.post("/{campaign_id}/convoy/pause", response_model=dict)
async def pause_convoy(
    campaign_id: UUID,
    store: ScopedBeadStore,
    user: CurrentUser,
):
    """Pause the active Convoy for a Campaign."""
    # TODO: Implement
    return wrap_response({
        "campaign_id": str(campaign_id),
        "status": "paused",
    })


@router.post("/{campaign_id}/convoy/resume", response_model=dict)
async def resume_convoy(
    campaign_id: UUID,
    store: ScopedBeadStore,
    user: CurrentUser,
):
    """Resume a paused Convoy."""
    # TODO: Implement
    return wrap_response({
        "campaign_id": str(campaign_id),
        "status": "resumed",
    })


# =============================================================================
# Campaign Analytics
# =============================================================================


@router.get("/{campaign_id}/analytics", response_model=dict)
async def get_campaign_analytics(
    campaign_id: UUID,
    store: ScopedBeadStore,
    user: CurrentUser,
):
    """Get analytics for a Campaign."""
    # TODO: Aggregate from various sources
    return wrap_response({
        "campaign_id": str(campaign_id),
        "beads": {
            "leads": 0,
            "assets": 0,
            "tests": 0,
        },
        "polecats": {
            "total": 0,
            "completed": 0,
            "failed": 0,
        },
        "approvals": {
            "pending": 0,
            "approved": 0,
            "rejected": 0,
        },
    })


@router.get("/{campaign_id}/beads", response_model=dict)
async def list_campaign_beads(
    campaign_id: UUID,
    store: ScopedBeadStore,
    user: CurrentUser,
    bead_type: str | None = None,
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
):
    """List all Beads associated with a Campaign."""
    # Get leads for this campaign
    leads = await store.list_leads(campaign_id=campaign_id, limit=limit, offset=offset)

    # TODO: Add other bead types

    return wrap_response({
        "leads": [lead.model_dump() for lead in leads],
        "assets": [],
        "tests": [],
    })
