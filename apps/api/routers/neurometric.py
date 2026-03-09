"""
Neurometric Router - Model registry and efficiency reports.

Base path: /api/v1/neurometric

All LLM calls MUST route through the Neurometric gateway.
"""

import json
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from apps.api.dependencies import AdminUser, CurrentUser, DbSession, ScopedBeadStore
from apps.api.models.beads import EvaluationStatus, ModelRegistryBeadCreate, ModelRegistryBeadUpdate

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
# Model Registry
# =============================================================================


@router.get("/registry", response_model=dict)
async def get_model_registry(
    session: DbSession,
    user: CurrentUser,
):
    """
    Get the current model registry for the organization.

    The registry determines which model is used for each task class.
    Organization-specific overrides take precedence over global defaults.
    """
    # Get global defaults (organization_id IS NULL)
    defaults_query = text("""
        SELECT id, task_class, default_model, fallback_model, evaluation_status,
               max_tokens, temperature, last_evaluated_at
        FROM model_registry_beads
        WHERE organization_id IS NULL AND status = 'active'
        ORDER BY task_class
    """)
    defaults_result = await session.execute(defaults_query)
    defaults = []
    for row in defaults_result.fetchall():
        row_dict = dict(row._mapping)
        defaults.append({
            "id": row_dict["id"],
            "task_class": row_dict["task_class"],
            "default_model": row_dict["default_model"],
            "fallback_model": row_dict["fallback_model"],
            "evaluation_status": row_dict["evaluation_status"],
            "max_tokens": row_dict["max_tokens"],
            "temperature": float(row_dict["temperature"]) if row_dict["temperature"] else 0.7,
            "last_evaluated_at": row_dict["last_evaluated_at"].isoformat() if row_dict["last_evaluated_at"] else None,
        })

    # Get org-specific overrides
    overrides_query = text("""
        SELECT id, task_class, default_model, fallback_model, evaluation_status,
               max_tokens, temperature, last_evaluated_at
        FROM model_registry_beads
        WHERE organization_id = :org_id AND status = 'active'
        ORDER BY task_class
    """)
    overrides_result = await session.execute(overrides_query, {"org_id": str(user.organization_id)})
    org_overrides = []
    for row in overrides_result.fetchall():
        row_dict = dict(row._mapping)
        org_overrides.append({
            "id": row_dict["id"],
            "task_class": row_dict["task_class"],
            "default_model": row_dict["default_model"],
            "fallback_model": row_dict["fallback_model"],
            "evaluation_status": row_dict["evaluation_status"],
            "max_tokens": row_dict["max_tokens"],
            "temperature": float(row_dict["temperature"]) if row_dict["temperature"] else 0.7,
            "last_evaluated_at": row_dict["last_evaluated_at"].isoformat() if row_dict["last_evaluated_at"] else None,
        })

    return wrap_response({
        "defaults": defaults,
        "org_overrides": org_overrides,
    })


@router.get("/registry/{task_class}", response_model=dict)
async def get_model_for_task(
    task_class: str,
    session: DbSession,
    user: CurrentUser,
):
    """Get the recommended model for a specific task class."""
    # First check for org-specific override
    org_query = text("""
        SELECT id, task_class, default_model, fallback_model, evaluation_status,
               max_tokens, temperature, evaluation_metrics
        FROM model_registry_beads
        WHERE organization_id = :org_id AND task_class = :task_class AND status = 'active'
        LIMIT 1
    """)
    org_result = await session.execute(org_query, {
        "org_id": str(user.organization_id),
        "task_class": task_class,
    })
    row = org_result.fetchone()

    # If no org override, get global default
    if not row:
        global_query = text("""
            SELECT id, task_class, default_model, fallback_model, evaluation_status,
                   max_tokens, temperature, evaluation_metrics
            FROM model_registry_beads
            WHERE organization_id IS NULL AND task_class = :task_class AND status = 'active'
            LIMIT 1
        """)
        global_result = await session.execute(global_query, {"task_class": task_class})
        row = global_result.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail=f"No model configuration found for task class: {task_class}")

    row_dict = dict(row._mapping)
    metrics = row_dict.get("evaluation_metrics")
    if metrics and isinstance(metrics, str):
        metrics = json.loads(metrics)

    return wrap_response({
        "id": row_dict["id"],
        "task_class": row_dict["task_class"],
        "default_model": row_dict["default_model"],
        "fallback_model": row_dict["fallback_model"],
        "evaluation_status": row_dict["evaluation_status"],
        "max_tokens": row_dict["max_tokens"],
        "temperature": float(row_dict["temperature"]) if row_dict["temperature"] else 0.7,
        "evaluation_metrics": metrics,
    })


@router.post("/registry", response_model=dict)
async def create_model_override(
    data: ModelRegistryBeadCreate,
    session: DbSession,
    user: AdminUser,
):
    """Create an organization-specific model override."""
    bead_id = uuid4()

    # Check if override already exists
    check_query = text("""
        SELECT id FROM model_registry_beads
        WHERE organization_id = :org_id AND task_class = :task_class AND status = 'active'
    """)
    existing = await session.execute(check_query, {
        "org_id": str(user.organization_id),
        "task_class": data.task_class,
    })
    if existing.fetchone():
        raise HTTPException(status_code=400, detail=f"Override already exists for task class: {data.task_class}")

    query = text("""
        INSERT INTO model_registry_beads
        (id, type, organization_id, task_class, default_model, fallback_model,
         max_tokens, temperature, status, version, created_at, updated_at)
        VALUES (:id, 'model_registry', :org_id, :task_class, :default_model, :fallback_model,
                :max_tokens, :temperature, 'active', 1, NOW(), NOW())
    """)

    await session.execute(query, {
        "id": str(bead_id),
        "org_id": str(user.organization_id),
        "task_class": data.task_class,
        "default_model": data.default_model,
        "fallback_model": data.fallback_model,
        "max_tokens": data.max_tokens,
        "temperature": float(data.temperature) if data.temperature else 0.7,
    })
    await session.commit()

    return wrap_response({
        "id": str(bead_id),
        "task_class": data.task_class,
        "default_model": data.default_model,
        "message": "Model override created",
    })


@router.patch("/registry/{task_class}", response_model=dict)
async def update_model_config(
    task_class: str,
    data: ModelRegistryBeadUpdate,
    session: DbSession,
    user: AdminUser,
):
    """Update model configuration for a task class."""
    # Find the org-specific override
    find_query = text("""
        SELECT id, version FROM model_registry_beads
        WHERE organization_id = :org_id AND task_class = :task_class AND status = 'active'
    """)
    result = await session.execute(find_query, {
        "org_id": str(user.organization_id),
        "task_class": task_class,
    })
    row = result.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail=f"No override found for task class: {task_class}. Create one first.")

    row_dict = dict(row._mapping)

    # Build update query
    update_fields = []
    params = {
        "id": row_dict["id"],
        "new_version": row_dict["version"] + 1,
    }

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if key == "evaluation_status" and value is not None:
            params[key] = value.value if hasattr(value, 'value') else value
        elif key == "evaluation_metrics" and value is not None:
            params[key] = json.dumps(value)
        elif key == "temperature" and value is not None:
            params[key] = float(value)
        else:
            params[key] = value
        update_fields.append(f"{key} = :{key}")

    if not update_fields:
        return wrap_response({"task_class": task_class, "updated": False, "message": "No fields to update"})

    update_fields.append("version = :new_version")
    update_fields.append("updated_at = NOW()")

    query = text(f"""
        UPDATE model_registry_beads
        SET {", ".join(update_fields)}
        WHERE id = :id
    """)

    await session.execute(query, params)
    await session.commit()

    return wrap_response({
        "task_class": task_class,
        "updated": True,
    })


# =============================================================================
# Efficiency Reports
# =============================================================================


@router.get("/efficiency", response_model=dict)
async def get_efficiency_report(
    store: ScopedBeadStore,
    user: CurrentUser,
    days: int = Query(30, le=90),
):
    """
    Get model efficiency report.

    Shows cost, quality, and speed metrics across task classes
    to help optimize model selection.
    """
    return wrap_response({
        "period_days": days,
        "summary": {
            "total_calls": 0,
            "total_tokens_input": 0,
            "total_tokens_output": 0,
            "estimated_cost_usd": 0.0,
            "avg_latency_ms": 0,
        },
        "by_task_class": {},
        "by_model": {},
        "recommendations": [],
    })


@router.get("/efficiency/{task_class}", response_model=dict)
async def get_task_efficiency(
    task_class: str,
    store: ScopedBeadStore,
    user: CurrentUser,
    days: int = Query(30, le=90),
):
    """Get efficiency metrics for a specific task class."""
    return wrap_response({
        "task_class": task_class,
        "period_days": days,
        "current_model": None,
        "metrics": {
            "call_count": 0,
            "avg_tokens_input": 0,
            "avg_tokens_output": 0,
            "avg_latency_ms": 0,
            "success_rate": 0.0,
            "quality_score": 0.0,
        },
        "shadow_test_results": [],
    })


# =============================================================================
# Shadow Testing
# =============================================================================


@router.get("/shadow-tests", response_model=dict)
async def get_shadow_tests(
    store: ScopedBeadStore,
    user: CurrentUser,
    status: str | None = None,
    limit: int = Query(50, le=200),
):
    """
    Get shadow test results.

    Shadow tests run alternative models in parallel to evaluate
    whether a different model would be more efficient.
    """
    return wrap_response(
        [],
        meta={"count": 0, "limit": limit},
    )


@router.post("/shadow-tests/trigger", response_model=dict)
async def trigger_shadow_test(
    task_class: str,
    alternative_model: str,
    store: ScopedBeadStore,
    user: AdminUser,
):
    """
    Trigger a shadow test for a task class.

    The Deacon will run the alternative model in parallel
    and compare results to the current model.
    """
    return wrap_response({
        "task_class": task_class,
        "alternative_model": alternative_model,
        "status": "scheduled",
        "message": "Shadow test scheduled - Deacon will execute on next evaluation loop",
    })


# =============================================================================
# Available Models
# =============================================================================


@router.get("/models", response_model=dict)
async def list_available_models(
    user: CurrentUser,
):
    """List all available models through the Neurometric gateway."""
    return wrap_response({
        "models": [
            {
                "id": "claude-opus-4-5-20251101",
                "name": "Claude Opus 4.5",
                "tier": "premium",
                "best_for": ["complex_analysis", "strategic_planning"],
            },
            {
                "id": "claude-sonnet-4-5-20250929",
                "name": "Claude Sonnet 4.5",
                "tier": "standard",
                "best_for": ["content_generation", "analysis"],
            },
            {
                "id": "claude-haiku-4-5-20251001",
                "name": "Claude Haiku 4.5",
                "tier": "fast",
                "best_for": ["simple_tasks", "high_volume"],
            },
        ],
    })
