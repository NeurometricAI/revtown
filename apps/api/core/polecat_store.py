"""
Polecat Store - Persistence layer for Polecat executions.

Database-backed store using the polecat_executions table.
"""

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()


class PolecatStatus(str, Enum):
    """Status of a Polecat execution."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class PolecatExecution:
    """A Polecat execution record."""
    id: str
    polecat_type: str
    rig: str
    bead_id: str
    organization_id: str
    campaign_id: str | None = None
    config: dict[str, Any] = field(default_factory=dict)
    task_class: str | None = None

    # Status
    status: PolecatStatus = PolecatStatus.PENDING
    progress: float | None = None  # 0.0 to 1.0

    # Timing
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None

    # Results
    output_bead_ids: list[str] = field(default_factory=list)
    output_content: str | None = None
    refinery_scores: dict[str, Any] = field(default_factory=dict)
    refinery_passed: bool | None = None
    witness_passed: bool | None = None
    witness_notes: str | None = None
    requires_approval: bool = False
    approval_item_id: str | None = None

    # LLM usage
    model_used: str | None = None
    tokens_input: int = 0
    tokens_output: int = 0

    # Temporal
    temporal_workflow_id: str | None = None
    temporal_run_id: str | None = None

    # Error
    error_message: str | None = None

    # Internal (not persisted)
    _task: asyncio.Task | None = field(default=None, repr=False)

    @property
    def duration_ms(self) -> int | None:
        if self.started_at and self.completed_at:
            return int((self.completed_at - self.started_at).total_seconds() * 1000)
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "polecat_type": self.polecat_type,
            "rig": self.rig,
            "bead_id": self.bead_id,
            "organization_id": self.organization_id,
            "campaign_id": self.campaign_id,
            "task_class": self.task_class,
            "status": self.status.value,
            "progress": self.progress,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_ms": self.duration_ms,
            "output_bead_ids": self.output_bead_ids,
            "refinery_scores": self.refinery_scores,
            "refinery_passed": self.refinery_passed,
            "witness_passed": self.witness_passed,
            "requires_approval": self.requires_approval,
            "approval_item_id": self.approval_item_id,
            "model_used": self.model_used,
            "tokens_input": self.tokens_input,
            "tokens_output": self.tokens_output,
            "error_message": self.error_message,
        }

    @classmethod
    def from_row(cls, row_dict: dict[str, Any]) -> "PolecatExecution":
        """Create a PolecatExecution from a database row."""
        # Parse JSON fields
        output_bead_ids = row_dict.get("output_bead_ids")
        if output_bead_ids and isinstance(output_bead_ids, str):
            output_bead_ids = json.loads(output_bead_ids)

        refinery_scores = row_dict.get("refinery_scores")
        if refinery_scores and isinstance(refinery_scores, str):
            refinery_scores = json.loads(refinery_scores)

        return cls(
            id=row_dict["id"],
            polecat_type=row_dict["polecat_type"],
            rig=row_dict["rig"],
            bead_id=row_dict.get("input_bead_id", ""),
            organization_id=row_dict["organization_id"],
            campaign_id=row_dict.get("campaign_id"),
            task_class=row_dict.get("task_class"),
            status=PolecatStatus(row_dict["status"]),
            created_at=row_dict.get("started_at") or datetime.utcnow(),  # Use started_at as proxy
            started_at=row_dict.get("started_at"),
            completed_at=row_dict.get("completed_at"),
            output_bead_ids=output_bead_ids or [],
            refinery_scores=refinery_scores or {},
            refinery_passed=bool(row_dict.get("refinery_passed")) if row_dict.get("refinery_passed") is not None else None,
            witness_passed=bool(row_dict.get("witness_passed")) if row_dict.get("witness_passed") is not None else None,
            witness_notes=row_dict.get("witness_notes"),
            model_used=row_dict.get("model_used"),
            tokens_input=row_dict.get("tokens_input") or 0,
            tokens_output=row_dict.get("tokens_output") or 0,
            temporal_workflow_id=row_dict.get("temporal_workflow_id"),
            temporal_run_id=row_dict.get("temporal_run_id"),
            error_message=row_dict.get("error_message"),
        )


class PolecatStore:
    """
    Database-backed store for Polecat executions.

    Uses the polecat_executions table.
    """

    def __init__(self):
        self.logger = logger.bind(service="polecat_store")
        # Keep in-memory task references for cancellation
        self._tasks: dict[str, asyncio.Task] = {}

    async def create(self, session: AsyncSession, execution: PolecatExecution) -> PolecatExecution:
        """Store a new execution."""
        query = text("""
            INSERT INTO polecat_executions
            (id, organization_id, campaign_id, polecat_type, rig, task_class,
             input_bead_id, status, started_at)
            VALUES (:id, :org_id, :campaign_id, :polecat_type, :rig, :task_class,
                    :input_bead_id, :status, :started_at)
        """)

        await session.execute(query, {
            "id": execution.id,
            "org_id": execution.organization_id,
            "campaign_id": execution.campaign_id,
            "polecat_type": execution.polecat_type,
            "rig": execution.rig,
            "task_class": execution.task_class or execution.polecat_type,
            "input_bead_id": execution.bead_id,
            "status": execution.status.value,
            "started_at": execution.created_at,
        })
        await session.commit()

        self.logger.info(
            "Polecat execution created",
            execution_id=execution.id,
            rig=execution.rig,
            polecat_type=execution.polecat_type,
        )
        return execution

    async def get(self, session: AsyncSession, execution_id: str) -> PolecatExecution | None:
        """Get an execution by ID."""
        query = text("SELECT * FROM polecat_executions WHERE id = :id")
        result = await session.execute(query, {"id": execution_id})
        row = result.fetchone()

        if not row:
            return None

        execution = PolecatExecution.from_row(dict(row._mapping))
        # Restore task reference if exists
        if execution.id in self._tasks:
            execution._task = self._tasks[execution.id]
        return execution

    async def update(self, session: AsyncSession, execution: PolecatExecution) -> PolecatExecution:
        """Update an execution."""
        query = text("""
            UPDATE polecat_executions
            SET status = :status,
                started_at = :started_at,
                completed_at = :completed_at,
                duration_ms = :duration_ms,
                output_bead_ids = :output_bead_ids,
                refinery_scores = :refinery_scores,
                refinery_passed = :refinery_passed,
                witness_passed = :witness_passed,
                witness_notes = :witness_notes,
                model_used = :model_used,
                tokens_input = :tokens_input,
                tokens_output = :tokens_output,
                temporal_workflow_id = :temporal_workflow_id,
                temporal_run_id = :temporal_run_id,
                error_message = :error_message
            WHERE id = :id
        """)

        await session.execute(query, {
            "id": execution.id,
            "status": execution.status.value,
            "started_at": execution.started_at,
            "completed_at": execution.completed_at,
            "duration_ms": execution.duration_ms,
            "output_bead_ids": json.dumps(execution.output_bead_ids) if execution.output_bead_ids else None,
            "refinery_scores": json.dumps(execution.refinery_scores) if execution.refinery_scores else None,
            "refinery_passed": execution.refinery_passed,
            "witness_passed": execution.witness_passed,
            "witness_notes": execution.witness_notes,
            "model_used": execution.model_used,
            "tokens_input": execution.tokens_input,
            "tokens_output": execution.tokens_output,
            "temporal_workflow_id": execution.temporal_workflow_id,
            "temporal_run_id": execution.temporal_run_id,
            "error_message": execution.error_message,
        })
        await session.commit()

        return execution

    async def update_status(
        self,
        session: AsyncSession,
        execution_id: str,
        status: PolecatStatus,
        error_message: str | None = None,
        output_content: str | None = None,
        output_bead_ids: list[str] | None = None,
        refinery_scores: dict[str, Any] | None = None,
        refinery_passed: bool | None = None,
        witness_passed: bool | None = None,
        requires_approval: bool = False,
        approval_item_id: str | None = None,
        model_used: str | None = None,
        tokens_input: int | None = None,
        tokens_output: int | None = None,
    ) -> PolecatExecution | None:
        """Update execution status and results."""
        execution = await self.get(session, execution_id)
        if not execution:
            return None

        execution.status = status

        if status == PolecatStatus.RUNNING and not execution.started_at:
            execution.started_at = datetime.utcnow()
        elif status in (PolecatStatus.COMPLETED, PolecatStatus.FAILED, PolecatStatus.CANCELLED):
            execution.completed_at = datetime.utcnow()

        if error_message is not None:
            execution.error_message = error_message
        if output_content is not None:
            execution.output_content = output_content
        if output_bead_ids is not None:
            execution.output_bead_ids = output_bead_ids
        if refinery_scores is not None:
            execution.refinery_scores = refinery_scores
        if refinery_passed is not None:
            execution.refinery_passed = refinery_passed
        if witness_passed is not None:
            execution.witness_passed = witness_passed
        if requires_approval:
            execution.requires_approval = requires_approval
        if approval_item_id is not None:
            execution.approval_item_id = approval_item_id
        if model_used is not None:
            execution.model_used = model_used
        if tokens_input is not None:
            execution.tokens_input = tokens_input
        if tokens_output is not None:
            execution.tokens_output = tokens_output

        await self.update(session, execution)

        self.logger.info(
            "Polecat execution updated",
            execution_id=execution_id,
            status=status.value,
        )
        return execution

    async def list_executions(
        self,
        session: AsyncSession,
        organization_id: str,
        rig: str | None = None,
        status: PolecatStatus | None = None,
        campaign_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[PolecatExecution], int]:
        """List executions with filters."""
        conditions = ["organization_id = :org_id"]
        params: dict[str, Any] = {"org_id": organization_id, "limit": limit, "offset": offset}

        if rig:
            conditions.append("rig = :rig")
            params["rig"] = rig
        if status:
            conditions.append("status = :status")
            params["status"] = status.value
        if campaign_id:
            conditions.append("campaign_id = :campaign_id")
            params["campaign_id"] = campaign_id

        where_clause = " AND ".join(conditions)

        # Get total count
        count_query = text(f"SELECT COUNT(*) as total FROM polecat_executions WHERE {where_clause}")
        count_result = await session.execute(count_query, params)
        total = count_result.fetchone()._mapping["total"]

        # Get executions
        query = text(f"""
            SELECT * FROM polecat_executions
            WHERE {where_clause}
            ORDER BY started_at DESC
            LIMIT :limit OFFSET :offset
        """)
        result = await session.execute(query, params)

        executions = []
        for row in result.fetchall():
            executions.append(PolecatExecution.from_row(dict(row._mapping)))

        return executions, total

    async def get_running(
        self,
        session: AsyncSession,
        organization_id: str | None = None,
    ) -> list[PolecatExecution]:
        """Get all running executions."""
        if organization_id:
            query = text("""
                SELECT * FROM polecat_executions
                WHERE organization_id = :org_id AND status = 'running'
            """)
            result = await session.execute(query, {"org_id": organization_id})
        else:
            query = text("SELECT * FROM polecat_executions WHERE status = 'running'")
            result = await session.execute(query)

        executions = []
        for row in result.fetchall():
            executions.append(PolecatExecution.from_row(dict(row._mapping)))

        return executions

    async def get_orphaned(
        self,
        session: AsyncSession,
        max_age_minutes: int = 30,
    ) -> list[PolecatExecution]:
        """Get executions that have been running too long (potential orphans)."""
        query = text("""
            SELECT * FROM polecat_executions
            WHERE status = 'running'
            AND started_at < DATE_SUB(NOW(), INTERVAL :max_age MINUTE)
        """)
        result = await session.execute(query, {"max_age": max_age_minutes})

        orphans = []
        for row in result.fetchall():
            orphans.append(PolecatExecution.from_row(dict(row._mapping)))

        return orphans

    async def cancel(self, session: AsyncSession, execution_id: str) -> PolecatExecution | None:
        """Cancel an execution."""
        execution = await self.get(session, execution_id)
        if not execution:
            return None

        if execution.status not in (PolecatStatus.PENDING, PolecatStatus.RUNNING):
            self.logger.warning(
                "Cannot cancel non-running execution",
                execution_id=execution_id,
                status=execution.status.value,
            )
            return execution

        # Cancel the task if it exists
        if execution_id in self._tasks:
            task = self._tasks[execution_id]
            if not task.done():
                task.cancel()
            del self._tasks[execution_id]

        execution.status = PolecatStatus.CANCELLED
        execution.completed_at = datetime.utcnow()
        await self.update(session, execution)

        self.logger.info("Polecat execution cancelled", execution_id=execution_id)
        return execution

    def register_task(self, execution_id: str, task: asyncio.Task):
        """Register an asyncio task for an execution (for cancellation)."""
        self._tasks[execution_id] = task

    def unregister_task(self, execution_id: str):
        """Unregister an asyncio task."""
        if execution_id in self._tasks:
            del self._tasks[execution_id]


# Global singleton instance
_store: PolecatStore | None = None


def get_polecat_store() -> PolecatStore:
    """Get the global polecat store instance."""
    global _store
    if _store is None:
        _store = PolecatStore()
    return _store
