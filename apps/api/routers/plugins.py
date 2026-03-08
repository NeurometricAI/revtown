"""
Plugins Router - Register, list, health, and configure plugins.

Base path: /api/v1/plugins
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import BaseModel

from apps.api.dependencies import AdminUser, CurrentUser, ScopedBeadStore
from apps.api.models.beads import PluginBeadCreate, PluginSourceType, PluginStatus

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
# Plugin Registration
# =============================================================================


class PluginManifest(BaseModel):
    """Plugin manifest (revtown-plugin.json)."""

    name: str
    version: str
    description: str | None = None
    author: str | None = None

    # Registrations
    polecats: list[dict[str, Any]] | None = None  # Polecat templates
    refinery_checks: list[dict[str, Any]] | None = None  # Refinery check functions
    bead_types: list[dict[str, Any]] | None = None  # Custom Bead types

    # Health
    health_endpoint: str | None = None

    # Credentials
    required_credentials: list[str] | None = None


class RegisterPluginRequest(BaseModel):
    """Request to register a plugin."""

    source_type: PluginSourceType
    source_url: str | None = None
    manifest: PluginManifest


@router.post("", response_model=dict)
async def register_plugin(
    request: RegisterPluginRequest,
    store: ScopedBeadStore,
    user: AdminUser,  # Admin only
):
    """
    Register a new plugin.

    Validates the manifest and creates a PluginBead.
    The Deacon will begin health monitoring once registered.
    """
    # Validate manifest
    manifest = request.manifest

    # Check for required fields
    if not manifest.name or not manifest.version:
        return wrap_response(
            None,
            meta={"error": "Plugin manifest must include name and version"},
        )

    # TODO: Create PluginBead
    from uuid import uuid4

    plugin_id = uuid4()

    return wrap_response({
        "plugin_id": str(plugin_id),
        "name": manifest.name,
        "version": manifest.version,
        "status": "active",
        "message": "Plugin registered successfully",
        "registrations": {
            "polecats": len(manifest.polecats or []),
            "refinery_checks": len(manifest.refinery_checks or []),
            "bead_types": len(manifest.bead_types or []),
        },
    })


@router.get("", response_model=dict)
async def list_plugins(
    store: ScopedBeadStore,
    user: CurrentUser,
    status: PluginStatus | None = None,
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
):
    """List all registered plugins for the organization."""
    # TODO: Query plugin_beads table
    return wrap_response(
        [],
        meta={"count": 0, "limit": limit, "offset": offset},
    )


@router.get("/{plugin_id}", response_model=dict)
async def get_plugin(
    plugin_id: UUID,
    store: ScopedBeadStore,
    user: CurrentUser,
):
    """Get details of a specific plugin."""
    # TODO: Look up PluginBead
    return wrap_response({
        "plugin_id": str(plugin_id),
        "name": None,
        "version": None,
        "manifest": None,
        "status": None,
        "health_status": None,
        "last_health_check_at": None,
    })


# =============================================================================
# Plugin Health
# =============================================================================


@router.get("/{plugin_id}/health", response_model=dict)
async def get_plugin_health(
    plugin_id: UUID,
    store: ScopedBeadStore,
    user: CurrentUser,
):
    """Get the health status of a plugin."""
    return wrap_response({
        "plugin_id": str(plugin_id),
        "health_status": "unknown",
        "last_check_at": None,
        "health_history": [],
    })


@router.post("/{plugin_id}/health/check", response_model=dict)
async def trigger_health_check(
    plugin_id: UUID,
    store: ScopedBeadStore,
    user: AdminUser,
):
    """Manually trigger a health check for a plugin."""
    # TODO: Trigger via Deacon
    return wrap_response({
        "plugin_id": str(plugin_id),
        "status": "check_requested",
        "message": "Health check will be performed by Deacon",
    })


# =============================================================================
# Plugin Configuration
# =============================================================================


class PluginConfig(BaseModel):
    """Plugin configuration update."""

    config: dict[str, Any]


@router.patch("/{plugin_id}/config", response_model=dict)
async def update_plugin_config(
    plugin_id: UUID,
    config: PluginConfig,
    store: ScopedBeadStore,
    user: AdminUser,
):
    """Update plugin configuration."""
    # TODO: Update PluginBead config field
    return wrap_response({
        "plugin_id": str(plugin_id),
        "config_updated": True,
    })


@router.get("/{plugin_id}/credentials", response_model=dict)
async def get_required_credentials(
    plugin_id: UUID,
    store: ScopedBeadStore,
    user: AdminUser,
):
    """
    Get the credentials required by a plugin.

    Credentials are stored in Vault and injected at runtime.
    """
    return wrap_response({
        "plugin_id": str(plugin_id),
        "required_credentials": [],
        "configured": [],
        "missing": [],
    })


# =============================================================================
# Plugin Management
# =============================================================================


@router.post("/{plugin_id}/enable", response_model=dict)
async def enable_plugin(
    plugin_id: UUID,
    store: ScopedBeadStore,
    user: AdminUser,
):
    """Enable a disabled plugin."""
    # TODO: Update status to active
    return wrap_response({
        "plugin_id": str(plugin_id),
        "status": "active",
    })


@router.post("/{plugin_id}/disable", response_model=dict)
async def disable_plugin(
    plugin_id: UUID,
    store: ScopedBeadStore,
    user: AdminUser,
):
    """Disable a plugin."""
    # TODO: Update status to disabled
    return wrap_response({
        "plugin_id": str(plugin_id),
        "status": "disabled",
    })


@router.delete("/{plugin_id}", response_model=dict)
async def unregister_plugin(
    plugin_id: UUID,
    store: ScopedBeadStore,
    user: AdminUser,
):
    """
    Unregister a plugin.

    Archives the PluginBead (does not delete for audit trail).
    """
    # TODO: Archive PluginBead
    return wrap_response({
        "plugin_id": str(plugin_id),
        "status": "archived",
        "message": "Plugin unregistered",
    })


# =============================================================================
# Plugin Discovery
# =============================================================================


@router.get("/registry/search", response_model=dict)
async def search_plugin_registry(
    query: str | None = None,
    category: str | None = None,
    user: CurrentUser = None,
):
    """
    Search the public plugin registry.

    Returns plugins available for installation.
    """
    # TODO: Query external plugin registry
    return wrap_response({
        "results": [],
        "query": query,
        "category": category,
    })


@router.get("/registry/featured", response_model=dict)
async def get_featured_plugins(
    user: CurrentUser,
):
    """Get featured plugins from the registry."""
    return wrap_response({
        "featured": [
            {
                "name": "revtown-g2-monitor",
                "description": "G2 review sentiment analysis",
                "category": "intelligence",
                "installs": 0,
            },
        ],
    })
