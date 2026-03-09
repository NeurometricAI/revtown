"""
Plugins Router - Register, list, health, and configure plugins.

Base path: /api/v1/plugins
"""

import json
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text

from apps.api.dependencies import AdminUser, CurrentUser, DbSession, ScopedBeadStore
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
    session: DbSession,
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

    # Check if plugin already exists
    check_query = text("""
        SELECT id FROM plugin_beads
        WHERE organization_id = :org_id AND plugin_name = :name AND status != 'archived'
    """)
    existing = await session.execute(check_query, {
        "org_id": str(user.organization_id),
        "name": manifest.name,
    })
    if existing.fetchone():
        return wrap_response(None, meta={"error": f"Plugin '{manifest.name}' is already registered"})

    plugin_id = uuid4()

    # Create PluginBead
    query = text("""
        INSERT INTO plugin_beads
        (id, type, organization_id, plugin_name, plugin_version, manifest, source_type, source_url,
         health_endpoint, required_credentials, status, version, created_at, updated_at)
        VALUES (:id, 'plugin', :org_id, :name, :version, :manifest, :source_type, :source_url,
                :health_endpoint, :required_credentials, 'active', 1, NOW(), NOW())
    """)
    await session.execute(query, {
        "id": str(plugin_id),
        "org_id": str(user.organization_id),
        "name": manifest.name,
        "version": manifest.version,
        "manifest": json.dumps(manifest.model_dump()),
        "source_type": request.source_type.value if hasattr(request.source_type, 'value') else request.source_type,
        "source_url": request.source_url,
        "health_endpoint": manifest.health_endpoint,
        "required_credentials": json.dumps(manifest.required_credentials) if manifest.required_credentials else None,
    })
    await session.commit()

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
    session: DbSession,
    user: CurrentUser,
    status: PluginStatus | None = None,
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
):
    """List all registered plugins for the organization."""
    # Build query with optional status filter
    params = {"org_id": str(user.organization_id), "limit": limit, "offset": offset}
    status_filter = ""
    if status:
        status_filter = "AND status = :status"
        params["status"] = status.value if hasattr(status, 'value') else status

    # Get total count
    count_query = text(f"""
        SELECT COUNT(*) as total FROM plugin_beads
        WHERE organization_id = :org_id {status_filter}
    """)
    count_result = await session.execute(count_query, params)
    total = count_result.fetchone()._mapping["total"]

    # Get plugins
    query = text(f"""
        SELECT id, plugin_name, plugin_version, health_status, health_endpoint,
               last_health_check_at, status, created_at, updated_at
        FROM plugin_beads
        WHERE organization_id = :org_id {status_filter}
        ORDER BY created_at DESC
        LIMIT :limit OFFSET :offset
    """)
    result = await session.execute(query, params)

    plugins = []
    for row in result.fetchall():
        row_dict = dict(row._mapping)
        plugins.append({
            "id": row_dict["id"],
            "name": row_dict["plugin_name"],
            "version": row_dict["plugin_version"],
            "health_status": row_dict["health_status"],
            "health_endpoint": row_dict["health_endpoint"],
            "last_health_check_at": row_dict["last_health_check_at"].isoformat() if row_dict.get("last_health_check_at") else None,
            "status": row_dict["status"],
            "created_at": row_dict["created_at"].isoformat() if row_dict.get("created_at") else None,
        })

    return wrap_response(
        plugins,
        meta={"count": total, "limit": limit, "offset": offset},
    )


@router.get("/{plugin_id}", response_model=dict)
async def get_plugin(
    plugin_id: UUID,
    session: DbSession,
    user: CurrentUser,
):
    """Get details of a specific plugin."""
    query = text("""
        SELECT id, plugin_name, plugin_version, manifest, source_type, source_url,
               health_endpoint, health_status, last_health_check_at, config,
               required_credentials, status, version, created_at, updated_at
        FROM plugin_beads
        WHERE id = :plugin_id AND organization_id = :org_id
    """)
    result = await session.execute(query, {
        "plugin_id": str(plugin_id),
        "org_id": str(user.organization_id),
    })
    row = result.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Plugin not found")

    row_dict = dict(row._mapping)

    # Parse JSON fields
    manifest = row_dict.get("manifest")
    if manifest and isinstance(manifest, str):
        manifest = json.loads(manifest)

    config = row_dict.get("config")
    if config and isinstance(config, str):
        config = json.loads(config)

    required_credentials = row_dict.get("required_credentials")
    if required_credentials and isinstance(required_credentials, str):
        required_credentials = json.loads(required_credentials)

    return wrap_response({
        "id": row_dict["id"],
        "name": row_dict["plugin_name"],
        "version": row_dict["plugin_version"],
        "manifest": manifest,
        "source_type": row_dict["source_type"],
        "source_url": row_dict["source_url"],
        "health_endpoint": row_dict["health_endpoint"],
        "health_status": row_dict["health_status"],
        "last_health_check_at": row_dict["last_health_check_at"].isoformat() if row_dict.get("last_health_check_at") else None,
        "config": config,
        "required_credentials": required_credentials,
        "status": row_dict["status"],
        "created_at": row_dict["created_at"].isoformat() if row_dict.get("created_at") else None,
        "updated_at": row_dict["updated_at"].isoformat() if row_dict.get("updated_at") else None,
    })


# =============================================================================
# Plugin Health
# =============================================================================


@router.get("/{plugin_id}/health", response_model=dict)
async def get_plugin_health(
    plugin_id: UUID,
    session: DbSession,
    user: CurrentUser,
):
    """Get the health status of a plugin."""
    query = text("""
        SELECT health_status, health_endpoint, last_health_check_at
        FROM plugin_beads
        WHERE id = :plugin_id AND organization_id = :org_id
    """)
    result = await session.execute(query, {
        "plugin_id": str(plugin_id),
        "org_id": str(user.organization_id),
    })
    row = result.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Plugin not found")

    row_dict = dict(row._mapping)

    return wrap_response({
        "plugin_id": str(plugin_id),
        "health_status": row_dict["health_status"] or "unknown",
        "health_endpoint": row_dict["health_endpoint"],
        "last_check_at": row_dict["last_health_check_at"].isoformat() if row_dict.get("last_health_check_at") else None,
    })


@router.post("/{plugin_id}/health/check", response_model=dict)
async def trigger_health_check(
    plugin_id: UUID,
    session: DbSession,
    user: AdminUser,
):
    """Manually trigger a health check for a plugin."""
    # Verify plugin exists
    query = text("""
        SELECT health_endpoint FROM plugin_beads
        WHERE id = :plugin_id AND organization_id = :org_id
    """)
    result = await session.execute(query, {
        "plugin_id": str(plugin_id),
        "org_id": str(user.organization_id),
    })
    row = result.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Plugin not found")

    # TODO: Queue health check via Deacon/message queue
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
    session: DbSession,
    user: AdminUser,
):
    """Update plugin configuration."""
    query = text("""
        UPDATE plugin_beads
        SET config = :config, updated_at = NOW(), version = version + 1
        WHERE id = :plugin_id AND organization_id = :org_id
    """)
    result = await session.execute(query, {
        "plugin_id": str(plugin_id),
        "org_id": str(user.organization_id),
        "config": json.dumps(config.config),
    })
    await session.commit()

    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Plugin not found")

    return wrap_response({
        "plugin_id": str(plugin_id),
        "config_updated": True,
    })


@router.get("/{plugin_id}/credentials", response_model=dict)
async def get_required_credentials(
    plugin_id: UUID,
    session: DbSession,
    user: AdminUser,
):
    """
    Get the credentials required by a plugin.

    Credentials are stored in Vault and injected at runtime.
    """
    query = text("""
        SELECT required_credentials, config FROM plugin_beads
        WHERE id = :plugin_id AND organization_id = :org_id
    """)
    result = await session.execute(query, {
        "plugin_id": str(plugin_id),
        "org_id": str(user.organization_id),
    })
    row = result.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Plugin not found")

    row_dict = dict(row._mapping)

    required = row_dict.get("required_credentials")
    if required and isinstance(required, str):
        required = json.loads(required)
    required = required or []

    config = row_dict.get("config")
    if config and isinstance(config, str):
        config = json.loads(config)
    config = config or {}

    # Check which credentials are configured (keys present in config)
    configured = [cred for cred in required if cred in config]
    missing = [cred for cred in required if cred not in config]

    return wrap_response({
        "plugin_id": str(plugin_id),
        "required_credentials": required,
        "configured": configured,
        "missing": missing,
    })


# =============================================================================
# Plugin Management
# =============================================================================


@router.post("/{plugin_id}/enable", response_model=dict)
async def enable_plugin(
    plugin_id: UUID,
    session: DbSession,
    user: AdminUser,
):
    """Enable a disabled plugin."""
    query = text("""
        UPDATE plugin_beads
        SET status = 'active', updated_at = NOW()
        WHERE id = :plugin_id AND organization_id = :org_id AND status = 'disabled'
    """)
    result = await session.execute(query, {
        "plugin_id": str(plugin_id),
        "org_id": str(user.organization_id),
    })
    await session.commit()

    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Plugin not found or not disabled")

    return wrap_response({
        "plugin_id": str(plugin_id),
        "status": "active",
    })


@router.post("/{plugin_id}/disable", response_model=dict)
async def disable_plugin(
    plugin_id: UUID,
    session: DbSession,
    user: AdminUser,
):
    """Disable a plugin."""
    query = text("""
        UPDATE plugin_beads
        SET status = 'disabled', updated_at = NOW()
        WHERE id = :plugin_id AND organization_id = :org_id AND status = 'active'
    """)
    result = await session.execute(query, {
        "plugin_id": str(plugin_id),
        "org_id": str(user.organization_id),
    })
    await session.commit()

    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Plugin not found or not active")

    return wrap_response({
        "plugin_id": str(plugin_id),
        "status": "disabled",
    })


@router.delete("/{plugin_id}", response_model=dict)
async def unregister_plugin(
    plugin_id: UUID,
    session: DbSession,
    user: AdminUser,
):
    """
    Unregister a plugin.

    Archives the PluginBead (does not delete for audit trail).
    """
    query = text("""
        UPDATE plugin_beads
        SET status = 'archived', updated_at = NOW()
        WHERE id = :plugin_id AND organization_id = :org_id AND status != 'archived'
    """)
    result = await session.execute(query, {
        "plugin_id": str(plugin_id),
        "org_id": str(user.organization_id),
    })
    await session.commit()

    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Plugin not found or already archived")

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
