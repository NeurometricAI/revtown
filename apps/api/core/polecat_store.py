"""
Polecat Store - Persistence layer for Polecat executions.

Tracks Polecat execution state across API requests.
In production, this would be backed by Redis or the database.
For now, using in-memory storage with a module-level singleton.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

import structlog

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
    requires_approval: bool = False
    approval_item_id: str | None = None

    # LLM usage
    model_used: str | None = None
    tokens_input: int = 0
    tokens_output: int = 0

    # Error
    error_message: str | None = None

    # Internal
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


class PolecatStore:
    """
    In-memory store for Polecat executions.

    In production, this would be backed by Redis or database.
    """

    def __init__(self):
        self._executions: dict[str, PolecatExecution] = {}
        self._by_org: dict[str, list[str]] = {}  # org_id -> execution_ids
        self._by_campaign: dict[str, list[str]] = {}  # campaign_id -> execution_ids
        self._by_rig: dict[str, list[str]] = {}  # rig -> execution_ids
        self.logger = logger.bind(service="polecat_store")

    def create(self, execution: PolecatExecution) -> PolecatExecution:
        """Store a new execution."""
        self._executions[execution.id] = execution

        # Index by organization
        if execution.organization_id not in self._by_org:
            self._by_org[execution.organization_id] = []
        self._by_org[execution.organization_id].append(execution.id)

        # Index by campaign
        if execution.campaign_id:
            if execution.campaign_id not in self._by_campaign:
                self._by_campaign[execution.campaign_id] = []
            self._by_campaign[execution.campaign_id].append(execution.id)

        # Index by rig
        if execution.rig not in self._by_rig:
            self._by_rig[execution.rig] = []
        self._by_rig[execution.rig].append(execution.id)

        self.logger.info(
            "Polecat execution created",
            execution_id=execution.id,
            rig=execution.rig,
            polecat_type=execution.polecat_type,
        )
        return execution

    def get(self, execution_id: str) -> PolecatExecution | None:
        """Get an execution by ID."""
        return self._executions.get(execution_id)

    def update(self, execution: PolecatExecution) -> PolecatExecution:
        """Update an execution."""
        self._executions[execution.id] = execution
        return execution

    def update_status(
        self,
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
        execution = self._executions.get(execution_id)
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

        self.logger.info(
            "Polecat execution updated",
            execution_id=execution_id,
            status=status.value,
        )
        return execution

    def list_executions(
        self,
        organization_id: str,
        rig: str | None = None,
        status: PolecatStatus | None = None,
        campaign_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[PolecatExecution], int]:
        """List executions with filters."""
        # Start with org filter
        execution_ids = self._by_org.get(organization_id, [])
        executions = [self._executions[eid] for eid in execution_ids if eid in self._executions]

        # Apply filters
        if rig:
            executions = [e for e in executions if e.rig == rig]
        if status:
            executions = [e for e in executions if e.status == status]
        if campaign_id:
            executions = [e for e in executions if e.campaign_id == campaign_id]

        # Sort by created_at descending (newest first)
        executions.sort(key=lambda x: x.created_at, reverse=True)

        total = len(executions)
        executions = executions[offset:offset + limit]

        return executions, total

    def get_running(self, organization_id: str | None = None) -> list[PolecatExecution]:
        """Get all running executions."""
        if organization_id:
            execution_ids = self._by_org.get(organization_id, [])
            executions = [self._executions[eid] for eid in execution_ids if eid in self._executions]
        else:
            executions = list(self._executions.values())

        return [e for e in executions if e.status == PolecatStatus.RUNNING]

    def get_orphaned(self, max_age_minutes: int = 30) -> list[PolecatExecution]:
        """Get executions that have been running too long (potential orphans)."""
        now = datetime.utcnow()
        orphans = []

        for execution in self._executions.values():
            if execution.status == PolecatStatus.RUNNING and execution.started_at:
                age_minutes = (now - execution.started_at).total_seconds() / 60
                if age_minutes > max_age_minutes:
                    orphans.append(execution)

        return orphans

    def cancel(self, execution_id: str) -> PolecatExecution | None:
        """Cancel an execution."""
        execution = self._executions.get(execution_id)
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
        if execution._task and not execution._task.done():
            execution._task.cancel()

        execution.status = PolecatStatus.CANCELLED
        execution.completed_at = datetime.utcnow()

        self.logger.info("Polecat execution cancelled", execution_id=execution_id)
        return execution


# Global singleton instance
_store: PolecatStore | None = None


def get_polecat_store() -> PolecatStore:
    """Get the global polecat store instance."""
    global _store
    if _store is None:
        _store = PolecatStore()
    return _store
