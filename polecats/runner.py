"""
Polecat Runner - Temporal.io workflow wrapper for Polecat execution.

Handles:
- Durable execution with retries
- Status reporting to API
- Kubernetes Job spawning interface
"""

from datetime import timedelta
from typing import Any
from uuid import UUID

import structlog
from temporalio import activity, workflow
from temporalio.client import Client
from temporalio.common import RetryPolicy
from temporalio.worker import Worker

from apps.api.config import settings
from apps.api.core.bead_store import BeadStore, get_session_factory
from apps.api.core.neurometric import get_neurometric_client
from apps.api.core.refinery import get_refinery
from apps.api.core.witness import get_witness
from polecats.base import BasePolecat, PolecatResult, get_polecat_class

logger = structlog.get_logger()


# =============================================================================
# Temporal Activities
# =============================================================================


@activity.defn
async def execute_polecat_activity(
    rig: str,
    polecat_type: str,
    bead_id: str,
    organization_id: str | None,
    config: dict[str, Any] | None,
) -> dict[str, Any]:
    """
    Execute a Polecat as a Temporal activity.

    This is the actual execution logic that runs within Temporal's
    durable execution framework.
    """
    logger.info(
        "Executing Polecat activity",
        rig=rig,
        polecat_type=polecat_type,
        bead_id=bead_id,
    )

    # Get the Polecat class
    polecat_class = get_polecat_class(rig, polecat_type)
    if not polecat_class:
        return {
            "success": False,
            "error": f"Unknown Polecat type: {rig}:{polecat_type}",
            "output_bead_ids": [],
        }

    # Create dependencies
    session_factory = get_session_factory()
    async with session_factory() as session:
        org_id = UUID(organization_id) if organization_id else None

        bead_store = BeadStore(session, org_id)
        neurometric = get_neurometric_client(org_id)
        refinery = get_refinery(org_id)
        witness = get_witness(bead_store, org_id)

        # Instantiate and run the Polecat
        polecat = polecat_class(
            bead_id=UUID(bead_id),
            bead_store=bead_store,
            neurometric=neurometric,
            refinery=refinery,
            witness=witness,
            config=config or {},
        )

        result = await polecat.run()

        return {
            "success": result.success,
            "output_bead_ids": result.output_bead_ids,
            "model_used": result.model_used,
            "tokens_input": result.tokens_input,
            "tokens_output": result.tokens_output,
            "duration_ms": result.duration_ms,
            "requires_approval": result.requires_approval,
            "error": result.error,
            "refinery_passed": result.refinery_result.passed if result.refinery_result else None,
            "refinery_score": result.refinery_result.overall_score if result.refinery_result else None,
            "witness_passed": result.witness_result.passed if result.witness_result else None,
        }


@activity.defn
async def update_execution_status_activity(
    execution_id: str,
    status: str,
    result: dict[str, Any] | None,
) -> bool:
    """Update the Polecat execution status in the database."""
    # TODO: Update polecat_executions table
    logger.info(
        "Updating execution status",
        execution_id=execution_id,
        status=status,
    )
    return True


@activity.defn
async def queue_for_approval_activity(
    bead_id: str,
    bead_type: str,
    rig: str,
    refinery_scores: dict[str, Any],
    execution_id: str,
) -> str:
    """Queue output for human approval."""
    # TODO: Create approval_queue entry
    logger.info(
        "Queueing for approval",
        bead_id=bead_id,
        execution_id=execution_id,
    )
    return "approval_queued"


# =============================================================================
# Temporal Workflow
# =============================================================================


@workflow.defn
class PolecatWorkflow:
    """
    Temporal workflow for Polecat execution.

    Provides:
    - Durable execution with automatic retries
    - Timeout management
    - Status tracking
    - Error handling
    """

    @workflow.run
    async def run(
        self,
        rig: str,
        polecat_type: str,
        bead_id: str,
        organization_id: str | None = None,
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute the Polecat workflow."""

        execution_id = workflow.info().workflow_id

        # Update status to running
        await workflow.execute_activity(
            update_execution_status_activity,
            args=[execution_id, "running", None],
            start_to_close_timeout=timedelta(seconds=30),
        )

        try:
            # Execute the Polecat
            result = await workflow.execute_activity(
                execute_polecat_activity,
                args=[rig, polecat_type, bead_id, organization_id, config],
                start_to_close_timeout=timedelta(minutes=10),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=1),
                    maximum_interval=timedelta(minutes=1),
                    backoff_coefficient=2.0,
                    maximum_attempts=3,
                    non_retryable_error_types=["ValueError", "PermissionError"],
                ),
            )

            # Queue for approval if needed
            if result.get("requires_approval"):
                await workflow.execute_activity(
                    queue_for_approval_activity,
                    args=[
                        bead_id,
                        "asset",  # TODO: Get actual bead type
                        rig,
                        {"overall_score": result.get("refinery_score")},
                        execution_id,
                    ],
                    start_to_close_timeout=timedelta(seconds=30),
                )

            # Update final status
            status = "completed" if result.get("success") else "failed"
            await workflow.execute_activity(
                update_execution_status_activity,
                args=[execution_id, status, result],
                start_to_close_timeout=timedelta(seconds=30),
            )

            return result

        except Exception as e:
            # Update status to failed
            await workflow.execute_activity(
                update_execution_status_activity,
                args=[execution_id, "failed", {"error": str(e)}],
                start_to_close_timeout=timedelta(seconds=30),
            )
            raise


# =============================================================================
# Polecat Spawner
# =============================================================================


class PolecatSpawner:
    """
    Interface for spawning Polecats.

    Abstracts the Temporal client interaction for spawning Polecat workflows.
    """

    def __init__(self, client: Client | None = None):
        self._client = client
        self.logger = logger.bind(service="polecat_spawner")

    async def _get_client(self) -> Client:
        """Get or create the Temporal client."""
        if self._client is None:
            self._client = await Client.connect(settings.temporal_host)
        return self._client

    async def spawn(
        self,
        rig: str,
        polecat_type: str,
        bead_id: UUID,
        organization_id: UUID | None = None,
        config: dict[str, Any] | None = None,
    ) -> str:
        """
        Spawn a new Polecat.

        Returns the workflow/execution ID for tracking.
        """
        from uuid import uuid4

        execution_id = f"polecat-{uuid4()}"

        self.logger.info(
            "Spawning Polecat",
            execution_id=execution_id,
            rig=rig,
            polecat_type=polecat_type,
            bead_id=str(bead_id),
        )

        client = await self._get_client()

        # Start the workflow
        await client.start_workflow(
            PolecatWorkflow.run,
            args=[rig, polecat_type, str(bead_id), str(organization_id) if organization_id else None, config],
            id=execution_id,
            task_queue=settings.temporal_task_queue,
        )

        return execution_id

    async def get_status(self, execution_id: str) -> dict[str, Any]:
        """Get the status of a Polecat execution."""
        client = await self._get_client()

        handle = client.get_workflow_handle(execution_id)
        desc = await handle.describe()

        return {
            "execution_id": execution_id,
            "status": desc.status.name,
            "start_time": desc.start_time.isoformat() if desc.start_time else None,
            "close_time": desc.close_time.isoformat() if desc.close_time else None,
        }

    async def cancel(self, execution_id: str) -> bool:
        """Cancel a running Polecat execution."""
        client = await self._get_client()

        handle = client.get_workflow_handle(execution_id)
        await handle.cancel()

        self.logger.info("Polecat cancelled", execution_id=execution_id)
        return True

    async def get_result(self, execution_id: str) -> dict[str, Any]:
        """Get the result of a completed Polecat execution."""
        client = await self._get_client()

        handle = client.get_workflow_handle(execution_id)
        return await handle.result()


# =============================================================================
# Worker Setup
# =============================================================================


async def create_worker() -> Worker:
    """Create a Temporal worker for Polecat execution."""
    client = await Client.connect(settings.temporal_host)

    worker = Worker(
        client,
        task_queue=settings.temporal_task_queue,
        workflows=[PolecatWorkflow],
        activities=[
            execute_polecat_activity,
            update_execution_status_activity,
            queue_for_approval_activity,
        ],
    )

    return worker


async def run_worker():
    """Run the Polecat worker."""
    logger.info("Starting Polecat worker")

    worker = await create_worker()
    await worker.run()


# =============================================================================
# Singleton Spawner
# =============================================================================

_spawner: PolecatSpawner | None = None


def get_polecat_spawner() -> PolecatSpawner:
    """Get the global Polecat spawner."""
    global _spawner
    if _spawner is None:
        _spawner = PolecatSpawner()
    return _spawner
