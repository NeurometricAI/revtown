"""
Convoy Executor - Handles the execution of Campaign Convoys.

Supports two modes:
- Local: Executes Polecats directly in the API process (for development)
- Temporal: Spawns durable workflows via Temporal (for production)
"""

import asyncio
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import structlog

from apps.api.config import settings
from apps.api.core.convoy_store import (
    Convoy, ConvoyStatus, ConvoyStep, StepStatus, get_convoy_store
)
from apps.api.core.bead_store import BeadStore
from apps.api.core.neurometric import get_neurometric_client

logger = structlog.get_logger()


class ConvoyExecutor:
    """
    Executes Campaign Convoys by orchestrating Polecat execution.
    """

    def __init__(self, use_temporal: bool = False):
        self.use_temporal = use_temporal and self._temporal_available()
        self.store = get_convoy_store()
        self.logger = logger.bind(service="convoy_executor")
        self._running_tasks: dict[str, asyncio.Task] = {}

    def _temporal_available(self) -> bool:
        """Check if Temporal is available."""
        # For now, always use local execution
        # TODO: Check Temporal connection
        return False

    async def start_convoy(self, convoy_id: str) -> Convoy:
        """
        Start executing a convoy.

        Marks the convoy as executing and starts running ready steps.
        """
        convoy = self.store.get(convoy_id)
        if not convoy:
            raise ValueError(f"Convoy not found: {convoy_id}")

        if convoy.status not in (ConvoyStatus.DRAFT, ConvoyStatus.READY, ConvoyStatus.PAUSED):
            raise ValueError(f"Convoy cannot be started in status: {convoy.status}")

        convoy.status = ConvoyStatus.EXECUTING
        convoy.started_at = datetime.utcnow()
        self.store.update(convoy)

        self.logger.info(
            "Starting convoy execution",
            convoy_id=convoy_id,
            ready_steps=len(convoy.ready_steps),
        )

        # Start executing ready steps
        await self._execute_ready_steps(convoy)

        return convoy

    async def _execute_ready_steps(self, convoy: Convoy):
        """Execute all steps that are ready (dependencies satisfied)."""
        ready_steps = convoy.ready_steps

        if not ready_steps:
            self.logger.info("No ready steps to execute", convoy_id=convoy.id)
            return

        self.logger.info(
            "Executing ready steps",
            convoy_id=convoy.id,
            step_count=len(ready_steps),
        )

        if self.use_temporal:
            await self._execute_via_temporal(convoy, ready_steps)
        else:
            await self._execute_locally(convoy, ready_steps)

    async def _execute_locally(self, convoy: Convoy, steps: list[ConvoyStep]):
        """Execute steps locally in the API process (development mode)."""
        for step in steps:
            # Start each step as a background task
            task = asyncio.create_task(
                self._execute_step_locally(convoy, step)
            )
            self._running_tasks[step.id] = task

    async def _execute_step_locally(self, convoy: Convoy, step: ConvoyStep):
        """Execute a single step locally."""
        self.logger.info(
            "Executing step locally",
            convoy_id=convoy.id,
            step_id=step.id,
            rig=step.rig,
            polecat_type=step.polecat_type,
        )

        # Update step to running
        self.store.update_step_status(convoy.id, step.id, StepStatus.RUNNING)

        try:
            # Get dependencies
            neurometric = get_neurometric_client()

            # Build a prompt based on the step type
            prompt = self._build_step_prompt(convoy, step)

            # Execute via neurometric
            response = await neurometric.complete(
                task_class=step.polecat_type,
                prompt=prompt,
            )

            # Mark as completed
            self.store.update_step_status(
                convoy.id, step.id, StepStatus.COMPLETED,
                result={"output": response.content[:500] if response.content else "Completed"},
            )

            self.logger.info(
                "Step completed successfully",
                convoy_id=convoy.id,
                step_id=step.id,
            )

            # After step completes, check for more ready steps
            convoy = self.store.get(convoy.id)
            if convoy and convoy.status == ConvoyStatus.EXECUTING:
                await self._execute_ready_steps(convoy)

        except Exception as e:
            self.logger.error(
                "Step execution failed",
                convoy_id=convoy.id,
                step_id=step.id,
                error=str(e),
            )
            self.store.update_step_status(
                convoy.id, step.id, StepStatus.FAILED,
                error=str(e),
            )

    def _build_step_prompt(self, convoy: Convoy, step: ConvoyStep) -> str:
        """Build a prompt for the step execution."""
        polecat_prompts = {
            "competitor_monitor": f"Analyze the competitive landscape for a {convoy.goal} campaign. Identify 3-5 key competitors and their strategies. Be concise.",
            "content_calendar": f"Create a 2-week content calendar for a {convoy.goal} campaign. Include blog posts, social media, and email topics.",
            "blog_draft": f"Write a compelling blog post introduction (2-3 paragraphs) for a {convoy.goal} campaign targeting B2B audiences.",
            "seo_optimize": f"Generate SEO recommendations for a {convoy.goal} campaign. Include 5 target keywords and meta description suggestions.",
            "landing_page_draft": f"Write copy for a landing page for a {convoy.goal} campaign. Include headline, subheadline, 3 benefits, and CTA.",
            "lead_enrich": f"Describe an ideal customer profile for a {convoy.goal} campaign. Include firmographics, pain points, and buying triggers.",
            "email_personalize": f"Write a personalized cold email template for a {convoy.goal} campaign. Keep it under 150 words.",
            "social_post": f"Create 3 social media posts (LinkedIn, Twitter, and one other) for a {convoy.goal} campaign.",
            "engagement_monitor": f"Outline an engagement monitoring strategy for a {convoy.goal} campaign. Include metrics to track and response guidelines.",
            "sequence_create": f"Design a 4-email nurture sequence for a {convoy.goal} campaign. Provide subject lines and brief descriptions.",
            "ab_test_setup": f"Propose 2 A/B test ideas for a {convoy.goal} campaign landing page. Include hypothesis and success metrics.",
        }

        default_prompt = f"Execute the {step.polecat_type} task for a {convoy.goal} campaign. {step.description}"

        return polecat_prompts.get(step.polecat_type, default_prompt)

    async def _execute_via_temporal(self, convoy: Convoy, steps: list[ConvoyStep]):
        """Execute steps via Temporal workflows (production mode)."""
        from temporalio.client import Client
        from infra.temporal.workflows import CampaignConvoyWorkflow

        client = await Client.connect(settings.temporal_host)

        # Build convoy plan from steps
        convoy_plan = {
            "convoy_id": convoy.id,
            "steps": [step.to_dict() for step in steps],
        }

        # Start the CampaignConvoyWorkflow for the entire convoy
        await client.start_workflow(
            CampaignConvoyWorkflow.run,
            args=[convoy.campaign_id, convoy_plan, convoy.organization_id],
            id=f"convoy-{convoy.id}",
            task_queue=settings.temporal_task_queue,
        )

    async def pause_convoy(self, convoy_id: str) -> Convoy:
        """Pause a running convoy."""
        convoy = self.store.get(convoy_id)
        if not convoy:
            raise ValueError(f"Convoy not found: {convoy_id}")

        convoy.status = ConvoyStatus.PAUSED
        self.store.update(convoy)

        # Cancel running tasks
        for step in convoy.running_steps:
            task = self._running_tasks.get(step.id)
            if task and not task.done():
                task.cancel()

        self.logger.info("Convoy paused", convoy_id=convoy_id)
        return convoy

    async def resume_convoy(self, convoy_id: str) -> Convoy:
        """Resume a paused convoy."""
        convoy = self.store.get(convoy_id)
        if not convoy:
            raise ValueError(f"Convoy not found: {convoy_id}")

        if convoy.status != ConvoyStatus.PAUSED:
            raise ValueError(f"Convoy is not paused: {convoy_id}")

        convoy.status = ConvoyStatus.EXECUTING
        self.store.update(convoy)

        await self._execute_ready_steps(convoy)

        self.logger.info("Convoy resumed", convoy_id=convoy_id)
        return convoy

    def get_convoy_status(self, convoy_id: str) -> dict[str, Any] | None:
        """Get the current status of a convoy."""
        convoy = self.store.get(convoy_id)
        if not convoy:
            return None
        return convoy.to_dict()


# Global singleton
_executor: ConvoyExecutor | None = None


def get_convoy_executor() -> ConvoyExecutor:
    """Get the global convoy executor."""
    global _executor
    if _executor is None:
        _executor = ConvoyExecutor(use_temporal=False)  # Use local execution for now
    return _executor
