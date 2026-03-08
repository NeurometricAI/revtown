"""
Temporal Workflow Definitions for RevTown.

These workflows define the durable execution patterns for:
- Polecat execution
- Campaign convoys
- Scheduled tasks
"""

from datetime import timedelta
from typing import Any

from temporalio import activity, workflow
from temporalio.common import RetryPolicy

import structlog

logger = structlog.get_logger()


@activity.defn
async def execute_convoy_step(
    step: dict[str, Any],
    convoy_id: str,
    organization_id: str,
) -> dict[str, Any]:
    """
    Execute a single convoy step by spawning its Polecat.

    This activity:
    1. Updates step status to 'running'
    2. Spawns the Polecat via PolecatSpawner
    3. Waits for completion
    4. Updates step status with result
    """
    from uuid import uuid4

    from apps.api.core.convoy_store import get_convoy_store, StepStatus
    from polecats.runner import get_polecat_spawner

    store = get_convoy_store()
    spawner = get_polecat_spawner()

    step_id = step["id"]
    rig = step["rig"]
    polecat_type = step["polecat_type"]

    logger.info(
        "Executing convoy step",
        convoy_id=convoy_id,
        step_id=step_id,
        rig=rig,
        polecat_type=polecat_type,
    )

    # Update step to running
    store.update_step_status(convoy_id, step_id, StepStatus.RUNNING)

    try:
        # Create a temporary bead ID for this execution
        # In production, this would create/use actual beads
        bead_id = uuid4()

        # Spawn the Polecat
        execution_id = await spawner.spawn(
            rig=rig,
            polecat_type=polecat_type,
            bead_id=bead_id,
            organization_id=organization_id,
            config=step.get("config", {}),
        )

        # Wait for result
        result = await spawner.get_result(execution_id)

        # Update step status
        if result.get("success"):
            store.update_step_status(
                convoy_id, step_id, StepStatus.COMPLETED,
                execution_id=execution_id,
                result=result,
            )
        else:
            store.update_step_status(
                convoy_id, step_id, StepStatus.FAILED,
                execution_id=execution_id,
                error=result.get("error", "Unknown error"),
            )

        return result

    except Exception as e:
        logger.error("Step execution failed", step_id=step_id, error=str(e))
        store.update_step_status(
            convoy_id, step_id, StepStatus.FAILED,
            error=str(e),
        )
        return {"success": False, "error": str(e)}


@workflow.defn
class CampaignConvoyWorkflow:
    """
    Workflow for executing a Campaign Convoy.

    Manages the sequenced execution of Polecats across Rigs
    according to the Mayor's plan.
    """

    @workflow.run
    async def run(
        self,
        campaign_id: str,
        convoy_plan: dict[str, Any],
        organization_id: str,
    ) -> dict[str, Any]:
        """Execute the campaign convoy."""

        convoy_id = convoy_plan.get("convoy_id")
        results = {
            "campaign_id": campaign_id,
            "convoy_id": convoy_id,
            "steps_completed": 0,
            "steps_failed": 0,
            "outputs": [],
        }

        steps = convoy_plan.get("steps", [])

        for step in steps:
            try:
                # Execute step - pass convoy_id along with step and org_id
                step_result = await workflow.execute_activity(
                    execute_convoy_step,
                    args=[step, convoy_id, organization_id],
                    start_to_close_timeout=timedelta(minutes=30),
                    retry_policy=RetryPolicy(
                        initial_interval=timedelta(seconds=5),
                        maximum_interval=timedelta(minutes=5),
                        backoff_coefficient=2.0,
                        maximum_attempts=3,
                    ),
                )

                results["steps_completed"] += 1
                results["outputs"].append(step_result)

                # Check if step requires waiting for approval
                if step_result.get("requires_approval"):
                    # Wait for approval signal
                    approved = await workflow.wait_condition(
                        lambda: self._step_approved(step["id"]),
                        timeout=timedelta(hours=24),
                    )
                    if not approved:
                        results["steps_failed"] += 1

            except Exception as e:
                results["steps_failed"] += 1
                workflow.logger.error(f"Step failed: {step['id']}", exc_info=e)

        return results

    def _step_approved(self, step_id: str) -> bool:
        # Check if step has been approved
        # This would be signaled from the Approval Dashboard
        return False

    @workflow.signal
    async def approve_step(self, step_id: str):
        """Signal to approve a pending step."""
        pass

    @workflow.signal
    async def reject_step(self, step_id: str, reason: str):
        """Signal to reject a pending step."""
        pass

    @workflow.signal
    async def pause_convoy(self):
        """Signal to pause the convoy."""
        pass

    @workflow.signal
    async def resume_convoy(self):
        """Signal to resume the convoy."""
        pass


@workflow.defn
class ScheduledMaintenanceWorkflow:
    """
    Workflow for scheduled maintenance tasks.

    Runs on a schedule and performs:
    - Dead lead cleanup
    - Orphaned Polecat retirement
    - Usage aggregation
    - Health checks
    """

    @workflow.run
    async def run(self, task_type: str) -> dict[str, Any]:
        """Run scheduled maintenance."""

        if task_type == "dead_lead_cleanup":
            return await workflow.execute_activity(
                "cleanup_dead_leads",
                start_to_close_timeout=timedelta(minutes=30),
            )

        elif task_type == "orphan_polecat_cleanup":
            return await workflow.execute_activity(
                "cleanup_orphaned_polecats",
                start_to_close_timeout=timedelta(minutes=15),
            )

        elif task_type == "usage_aggregation":
            return await workflow.execute_activity(
                "aggregate_usage",
                start_to_close_timeout=timedelta(minutes=15),
            )

        elif task_type == "plugin_health_check":
            return await workflow.execute_activity(
                "check_plugin_health",
                start_to_close_timeout=timedelta(minutes=5),
            )

        else:
            return {"error": f"Unknown task type: {task_type}"}


@workflow.defn
class ABTestMonitorWorkflow:
    """
    Workflow for monitoring A/B tests.

    Continuously monitors test metrics and triggers
    winner declaration when statistical significance is reached.
    """

    @workflow.run
    async def run(
        self,
        test_id: str,
        min_sample_size: int,
        max_duration_days: int,
    ) -> dict[str, Any]:
        """Monitor A/B test until completion."""

        from datetime import datetime

        start_time = datetime.utcnow()
        max_duration = timedelta(days=max_duration_days)

        while True:
            # Check metrics
            metrics = await workflow.execute_activity(
                "get_test_metrics",
                args=[test_id],
                start_to_close_timeout=timedelta(minutes=5),
            )

            # Check if we have enough samples
            if metrics.get("total_samples", 0) >= min_sample_size:
                # Check statistical significance
                significance = await workflow.execute_activity(
                    "check_statistical_significance",
                    args=[test_id, metrics],
                    start_to_close_timeout=timedelta(minutes=5),
                )

                if significance.get("is_significant"):
                    # Declare winner
                    return await workflow.execute_activity(
                        "declare_test_winner",
                        args=[test_id, significance],
                        start_to_close_timeout=timedelta(minutes=5),
                    )

            # Check timeout
            if datetime.utcnow() - start_time > max_duration:
                return {
                    "test_id": test_id,
                    "status": "timeout",
                    "message": "Test reached maximum duration without significance",
                    "final_metrics": metrics,
                }

            # Wait before next check
            await workflow.sleep(timedelta(hours=1))
