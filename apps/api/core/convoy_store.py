"""
Convoy Store - Persistence layer for Campaign Convoys.

Stores convoy state so it persists across API requests.
In production, this would be backed by Redis or the database.
For now, using in-memory storage with a module-level singleton.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

import structlog

logger = structlog.get_logger()


class ConvoyStatus(str, Enum):
    """Status of a Campaign Convoy."""
    DRAFT = "draft"
    PLANNING = "planning"
    READY = "ready"
    EXECUTING = "executing"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class StepStatus(str, Enum):
    """Status of a Convoy Step."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    AWAITING_APPROVAL = "awaiting_approval"


@dataclass
class ConvoyStep:
    """A step in the Campaign Convoy."""
    id: str
    rig: str
    polecat_type: str
    description: str
    depends_on: list[str] = field(default_factory=list)
    priority: int = 0
    status: StepStatus = StepStatus.PENDING
    execution_id: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result: dict[str, Any] | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "rig": self.rig,
            "polecat_type": self.polecat_type,
            "description": self.description,
            "depends_on": self.depends_on,
            "priority": self.priority,
            "status": self.status.value,
            "execution_id": self.execution_id,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error": self.error,
        }


@dataclass
class Convoy:
    """A Campaign Convoy - sequenced set of steps across Rigs."""
    id: str
    campaign_id: str
    campaign_name: str
    goal: str
    organization_id: str
    status: ConvoyStatus
    steps: list[ConvoyStep]
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None

    @property
    def pending_steps(self) -> list[ConvoyStep]:
        return [s for s in self.steps if s.status == StepStatus.PENDING]

    @property
    def running_steps(self) -> list[ConvoyStep]:
        return [s for s in self.steps if s.status == StepStatus.RUNNING]

    @property
    def completed_steps(self) -> list[ConvoyStep]:
        return [s for s in self.steps if s.status == StepStatus.COMPLETED]

    @property
    def ready_steps(self) -> list[ConvoyStep]:
        """Steps that are ready to execute (dependencies satisfied)."""
        # Build set of completed step IDs and polecat types for dependency matching
        completed_ids = {s.id for s in self.steps if s.status == StepStatus.COMPLETED}
        completed_types = {s.polecat_type for s in self.steps if s.status == StepStatus.COMPLETED}
        completed_all = completed_ids | completed_types
        return [
            s for s in self.steps
            if s.status == StepStatus.PENDING and all(d in completed_all for d in s.depends_on)
        ]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "campaign_id": self.campaign_id,
            "campaign_name": self.campaign_name,
            "goal": self.goal,
            "status": self.status.value,
            "steps": [s.to_dict() for s in self.steps],
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "stats": {
                "total": len(self.steps),
                "pending": len(self.pending_steps),
                "running": len(self.running_steps),
                "completed": len(self.completed_steps),
            },
        }


class ConvoyStore:
    """
    In-memory store for Convoys.

    In production, this would be backed by Redis or database.
    """

    def __init__(self):
        self._convoys: dict[str, Convoy] = {}
        self._by_campaign: dict[str, list[str]] = {}  # campaign_id -> convoy_ids
        self.logger = logger.bind(service="convoy_store")

    def create(self, convoy: Convoy) -> Convoy:
        """Store a new convoy."""
        self._convoys[convoy.id] = convoy

        if convoy.campaign_id not in self._by_campaign:
            self._by_campaign[convoy.campaign_id] = []
        self._by_campaign[convoy.campaign_id].append(convoy.id)

        self.logger.info(
            "Convoy created",
            convoy_id=convoy.id,
            campaign_id=convoy.campaign_id,
            step_count=len(convoy.steps),
        )
        return convoy

    def get(self, convoy_id: str) -> Convoy | None:
        """Get a convoy by ID."""
        return self._convoys.get(convoy_id)

    def get_by_campaign(self, campaign_id: str) -> list[Convoy]:
        """Get all convoys for a campaign."""
        convoy_ids = self._by_campaign.get(campaign_id, [])
        return [self._convoys[cid] for cid in convoy_ids if cid in self._convoys]

    def update(self, convoy: Convoy) -> Convoy:
        """Update a convoy."""
        self._convoys[convoy.id] = convoy
        self.logger.debug("Convoy updated", convoy_id=convoy.id, status=convoy.status.value)
        return convoy

    def update_step_status(
        self,
        convoy_id: str,
        step_id: str,
        status: StepStatus,
        execution_id: str | None = None,
        result: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> ConvoyStep | None:
        """Update a step's status."""
        convoy = self._convoys.get(convoy_id)
        if not convoy:
            return None

        for step in convoy.steps:
            if step.id == step_id:
                step.status = status
                if execution_id:
                    step.execution_id = execution_id
                if status == StepStatus.RUNNING:
                    step.started_at = datetime.utcnow()
                elif status in (StepStatus.COMPLETED, StepStatus.FAILED):
                    step.completed_at = datetime.utcnow()
                if result:
                    step.result = result
                if error:
                    step.error = error

                self.logger.info(
                    "Step status updated",
                    convoy_id=convoy_id,
                    step_id=step_id,
                    status=status.value,
                )

                # Check if convoy is complete
                self._check_convoy_completion(convoy)

                return step

        return None

    def _check_convoy_completion(self, convoy: Convoy):
        """Check if convoy is complete and update status."""
        all_done = all(
            s.status in (StepStatus.COMPLETED, StepStatus.FAILED)
            for s in convoy.steps
        )

        if all_done and convoy.status == ConvoyStatus.EXECUTING:
            has_failures = any(s.status == StepStatus.FAILED for s in convoy.steps)
            convoy.status = ConvoyStatus.FAILED if has_failures else ConvoyStatus.COMPLETED
            convoy.completed_at = datetime.utcnow()
            self.logger.info(
                "Convoy completed",
                convoy_id=convoy.id,
                status=convoy.status.value,
            )


# Global singleton instance
_store: ConvoyStore | None = None


def get_convoy_store() -> ConvoyStore:
    """Get the global convoy store instance."""
    global _store
    if _store is None:
        _store = ConvoyStore()
    return _store
