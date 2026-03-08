"""
Beads Router - CRUD operations for all Bead types.

Base path: /api/v1/beads
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Query

from apps.api.dependencies import CurrentUser, ScopedBeadStore
from apps.api.models.beads import (
    AssetBead,
    AssetBeadCreate,
    AssetBeadUpdate,
    CompetitorBead,
    CompetitorBeadCreate,
    CompetitorBeadUpdate,
    ICPBead,
    ICPBeadCreate,
    ICPBeadUpdate,
    JournalistBead,
    JournalistBeadCreate,
    JournalistBeadUpdate,
    LeadBead,
    LeadBeadCreate,
    LeadBeadUpdate,
    ModelRegistryBead,
    ModelRegistryBeadCreate,
    ModelRegistryBeadUpdate,
    PluginBead,
    PluginBeadCreate,
    PluginBeadUpdate,
    TestBead,
    TestBeadCreate,
    TestBeadUpdate,
)

router = APIRouter()


# =============================================================================
# Response Wrapper
# =============================================================================


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
# Lead Beads
# =============================================================================


@router.post("/leads", response_model=dict)
async def create_lead(
    data: LeadBeadCreate,
    store: ScopedBeadStore,
    user: CurrentUser,
):
    """Create a new Lead Bead."""
    lead = await store.create_lead(data)
    return wrap_response(lead.model_dump())


@router.get("/leads/{bead_id}", response_model=dict)
async def get_lead(
    bead_id: UUID,
    store: ScopedBeadStore,
    user: CurrentUser,
):
    """Get a Lead Bead by ID."""
    lead = await store.get_lead(bead_id)
    return wrap_response(lead.model_dump())


@router.patch("/leads/{bead_id}", response_model=dict)
async def update_lead(
    bead_id: UUID,
    data: LeadBeadUpdate,
    store: ScopedBeadStore,
    user: CurrentUser,
    expected_version: int | None = Query(None, description="Expected version for optimistic locking"),
):
    """Update a Lead Bead."""
    lead = await store.update_lead(bead_id, data, expected_version)
    return wrap_response(lead.model_dump())


@router.get("/leads", response_model=dict)
async def list_leads(
    store: ScopedBeadStore,
    user: CurrentUser,
    campaign_id: UUID | None = None,
    status: str | None = None,
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
):
    """List Lead Beads for the organization."""
    leads = await store.list_leads(campaign_id, status, limit, offset)
    return wrap_response(
        [lead.model_dump() for lead in leads],
        meta={"count": len(leads), "limit": limit, "offset": offset},
    )


# =============================================================================
# Asset Beads
# =============================================================================


@router.post("/assets", response_model=dict)
async def create_asset(
    data: AssetBeadCreate,
    store: ScopedBeadStore,
    user: CurrentUser,
):
    """Create a new Asset Bead."""
    asset = await store.create_asset(data)
    return wrap_response(asset.model_dump())


@router.get("/assets/{bead_id}", response_model=dict)
async def get_asset(
    bead_id: UUID,
    store: ScopedBeadStore,
    user: CurrentUser,
):
    """Get an Asset Bead by ID."""
    asset = await store.get_asset(bead_id)
    return wrap_response(asset.model_dump())


@router.patch("/assets/{bead_id}", response_model=dict)
async def update_asset(
    bead_id: UUID,
    data: AssetBeadUpdate,
    store: ScopedBeadStore,
    user: CurrentUser,
    expected_version: int | None = Query(None),
):
    """Update an Asset Bead."""
    asset = await store.update_asset(bead_id, data, expected_version)
    return wrap_response(asset.model_dump())


# =============================================================================
# Competitor Beads
# =============================================================================


@router.post("/competitors", response_model=dict)
async def create_competitor(
    data: CompetitorBeadCreate,
    store: ScopedBeadStore,
    user: CurrentUser,
):
    """Create a new Competitor Bead."""
    # TODO: Implement in BeadStore
    raise NotImplementedError("Competitor beads not yet implemented")


@router.get("/competitors/{bead_id}", response_model=dict)
async def get_competitor(
    bead_id: UUID,
    store: ScopedBeadStore,
    user: CurrentUser,
):
    """Get a Competitor Bead by ID."""
    bead = await store.get_bead("competitor", bead_id)
    return wrap_response(bead.model_dump() if hasattr(bead, "model_dump") else bead)


# =============================================================================
# Test Beads
# =============================================================================


@router.post("/tests", response_model=dict)
async def create_test(
    data: TestBeadCreate,
    store: ScopedBeadStore,
    user: CurrentUser,
):
    """Create a new Test Bead (A/B test)."""
    # TODO: Implement in BeadStore
    raise NotImplementedError("Test beads not yet implemented")


@router.get("/tests/{bead_id}", response_model=dict)
async def get_test(
    bead_id: UUID,
    store: ScopedBeadStore,
    user: CurrentUser,
):
    """Get a Test Bead by ID."""
    bead = await store.get_bead("test", bead_id)
    return wrap_response(bead.model_dump() if hasattr(bead, "model_dump") else bead)


# =============================================================================
# ICP Beads
# =============================================================================


@router.post("/icps", response_model=dict)
async def create_icp(
    data: ICPBeadCreate,
    store: ScopedBeadStore,
    user: CurrentUser,
):
    """Create a new ICP (Ideal Customer Profile) Bead."""
    # TODO: Implement in BeadStore
    raise NotImplementedError("ICP beads not yet implemented")


@router.get("/icps/{bead_id}", response_model=dict)
async def get_icp(
    bead_id: UUID,
    store: ScopedBeadStore,
    user: CurrentUser,
):
    """Get an ICP Bead by ID."""
    bead = await store.get_bead("icp", bead_id)
    return wrap_response(bead.model_dump() if hasattr(bead, "model_dump") else bead)


# =============================================================================
# Journalist Beads
# =============================================================================


@router.post("/journalists", response_model=dict)
async def create_journalist(
    data: JournalistBeadCreate,
    store: ScopedBeadStore,
    user: CurrentUser,
):
    """Create a new Journalist Bead."""
    # TODO: Implement in BeadStore
    raise NotImplementedError("Journalist beads not yet implemented")


@router.get("/journalists/{bead_id}", response_model=dict)
async def get_journalist(
    bead_id: UUID,
    store: ScopedBeadStore,
    user: CurrentUser,
):
    """Get a Journalist Bead by ID."""
    bead = await store.get_bead("journalist", bead_id)
    return wrap_response(bead.model_dump() if hasattr(bead, "model_dump") else bead)


# =============================================================================
# Bead History & Revert (Dolt-specific)
# =============================================================================


@router.get("/{bead_type}/{bead_id}/history", response_model=dict)
async def get_bead_history(
    bead_type: str,
    bead_id: UUID,
    store: ScopedBeadStore,
    user: CurrentUser,
    limit: int = Query(10, le=100),
):
    """Get version history of a Bead."""
    history = await store.get_bead_history(bead_type, bead_id, limit)
    return wrap_response(history)


@router.post("/{bead_type}/{bead_id}/revert", response_model=dict)
async def revert_bead(
    bead_type: str,
    bead_id: UUID,
    to_commit: str,
    store: ScopedBeadStore,
    user: CurrentUser,
):
    """Revert a Bead to a previous version."""
    result = await store.revert_bead(bead_type, bead_id, to_commit)
    return wrap_response(result)


@router.get("/{bead_type}/{bead_id}/diff", response_model=dict)
async def get_bead_diff(
    bead_type: str,
    bead_id: UUID,
    from_commit: str,
    to_commit: str,
    store: ScopedBeadStore,
    user: CurrentUser,
):
    """Get diff between two versions of a Bead."""
    diff = await store.get_bead_diff(bead_type, bead_id, from_commit, to_commit)
    return wrap_response(diff)


# =============================================================================
# Archive (Never Delete)
# =============================================================================


@router.delete("/{bead_type}/{bead_id}", response_model=dict)
async def archive_bead(
    bead_type: str,
    bead_id: UUID,
    store: ScopedBeadStore,
    user: CurrentUser,
):
    """
    Archive a Bead (does NOT delete - Dolt versioning is the audit trail).
    Sets status to 'archived'.
    """
    result = await store.archive_bead(bead_type, bead_id)
    return wrap_response({"archived": result, "bead_id": str(bead_id)})
