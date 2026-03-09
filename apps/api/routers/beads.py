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
    competitor = await store.create_competitor(data)
    return wrap_response(competitor.model_dump())


@router.get("/competitors/{bead_id}", response_model=dict)
async def get_competitor(
    bead_id: UUID,
    store: ScopedBeadStore,
    user: CurrentUser,
):
    """Get a Competitor Bead by ID."""
    competitor = await store.get_competitor(bead_id)
    return wrap_response(competitor.model_dump())


@router.patch("/competitors/{bead_id}", response_model=dict)
async def update_competitor(
    bead_id: UUID,
    data: CompetitorBeadUpdate,
    store: ScopedBeadStore,
    user: CurrentUser,
    expected_version: int | None = Query(None),
):
    """Update a Competitor Bead."""
    competitor = await store.update_competitor(bead_id, data, expected_version)
    return wrap_response(competitor.model_dump())


@router.get("/competitors", response_model=dict)
async def list_competitors(
    store: ScopedBeadStore,
    user: CurrentUser,
    campaign_id: UUID | None = None,
    status: str | None = None,
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
):
    """List Competitor Beads for the organization."""
    competitors = await store.list_competitors(campaign_id, status, limit, offset)
    return wrap_response(
        [c.model_dump() for c in competitors],
        meta={"count": len(competitors), "limit": limit, "offset": offset},
    )


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
    test = await store.create_test(data)
    return wrap_response(test.model_dump())


@router.get("/tests/{bead_id}", response_model=dict)
async def get_test(
    bead_id: UUID,
    store: ScopedBeadStore,
    user: CurrentUser,
):
    """Get a Test Bead by ID."""
    test = await store.get_test(bead_id)
    return wrap_response(test.model_dump())


@router.patch("/tests/{bead_id}", response_model=dict)
async def update_test(
    bead_id: UUID,
    data: TestBeadUpdate,
    store: ScopedBeadStore,
    user: CurrentUser,
    expected_version: int | None = Query(None),
):
    """Update a Test Bead."""
    test = await store.update_test(bead_id, data, expected_version)
    return wrap_response(test.model_dump())


@router.get("/tests", response_model=dict)
async def list_tests(
    store: ScopedBeadStore,
    user: CurrentUser,
    campaign_id: UUID | None = None,
    status: str | None = None,
    test_type: str | None = None,
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
):
    """List Test Beads for the organization."""
    tests = await store.list_tests(campaign_id, status, test_type, limit, offset)
    return wrap_response(
        [t.model_dump() for t in tests],
        meta={"count": len(tests), "limit": limit, "offset": offset},
    )


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
    icp = await store.create_icp(data)
    return wrap_response(icp.model_dump())


@router.get("/icps/{bead_id}", response_model=dict)
async def get_icp(
    bead_id: UUID,
    store: ScopedBeadStore,
    user: CurrentUser,
):
    """Get an ICP Bead by ID."""
    icp = await store.get_icp(bead_id)
    return wrap_response(icp.model_dump())


@router.patch("/icps/{bead_id}", response_model=dict)
async def update_icp(
    bead_id: UUID,
    data: ICPBeadUpdate,
    store: ScopedBeadStore,
    user: CurrentUser,
    expected_version: int | None = Query(None),
):
    """Update an ICP Bead."""
    icp = await store.update_icp(bead_id, data, expected_version)
    return wrap_response(icp.model_dump())


@router.get("/icps", response_model=dict)
async def list_icps(
    store: ScopedBeadStore,
    user: CurrentUser,
    campaign_id: UUID | None = None,
    is_default: bool | None = None,
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
):
    """List ICP Beads for the organization."""
    icps = await store.list_icps(campaign_id, is_default, limit, offset)
    return wrap_response(
        [i.model_dump() for i in icps],
        meta={"count": len(icps), "limit": limit, "offset": offset},
    )


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
    journalist = await store.create_journalist(data)
    return wrap_response(journalist.model_dump())


@router.get("/journalists/{bead_id}", response_model=dict)
async def get_journalist(
    bead_id: UUID,
    store: ScopedBeadStore,
    user: CurrentUser,
):
    """Get a Journalist Bead by ID."""
    journalist = await store.get_journalist(bead_id)
    return wrap_response(journalist.model_dump())


@router.patch("/journalists/{bead_id}", response_model=dict)
async def update_journalist(
    bead_id: UUID,
    data: JournalistBeadUpdate,
    store: ScopedBeadStore,
    user: CurrentUser,
    expected_version: int | None = Query(None),
):
    """Update a Journalist Bead."""
    journalist = await store.update_journalist(bead_id, data, expected_version)
    return wrap_response(journalist.model_dump())


@router.get("/journalists", response_model=dict)
async def list_journalists(
    store: ScopedBeadStore,
    user: CurrentUser,
    publication: str | None = None,
    publication_tier: str | None = None,
    status: str | None = None,
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
):
    """List Journalist Beads for the organization."""
    journalists = await store.list_journalists(publication, publication_tier, status, limit, offset)
    return wrap_response(
        [j.model_dump() for j in journalists],
        meta={"count": len(journalists), "limit": limit, "offset": offset},
    )


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
