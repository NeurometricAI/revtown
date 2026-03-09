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
from apps.api.core.neurometric import get_neurometric_client
from apps.api.core.approval_store import (
    ApprovalItem, ApprovalType, ApprovalStatus, Urgency, get_approval_store
)

logger = structlog.get_logger()


# Import all rig polecats to populate the registry
def _load_polecat_registry():
    """Import all rig polecat modules to register them."""
    try:
        import rigs.content_factory.polecats
        import rigs.sdr_hive.polecats
        import rigs.social_command.polecats
        import rigs.press_room.polecats
        import rigs.intelligence_station.polecats
        import rigs.landing_pad.polecats
        import rigs.wire.polecats
        import rigs.repo_watch.polecats
    except ImportError as e:
        logger.warning("Failed to import some rig polecats", error=str(e))


# Load on module import
_load_polecat_registry()


# Map polecat types to approval types
POLECAT_APPROVAL_TYPES = {
    # Content
    "blog_draft": ApprovalType.CONTENT,
    "seo_optimize": ApprovalType.CONTENT,
    "content_calendar": ApprovalType.CONTENT,
    "social_snippet": ApprovalType.CONTENT,
    "image_brief": ApprovalType.CONTENT,
    "landing_page_draft": ApprovalType.CONTENT,
    # Outreach
    "email_personalize": ApprovalType.OUTREACH,
    "sequence_create": ApprovalType.OUTREACH,
    "lead_enrich": ApprovalType.OUTREACH,
    # PR
    "pr_pitch": ApprovalType.PR_PITCH,
    "journalist_research": ApprovalType.PR_PITCH,
    # Social
    "social_post": ApprovalType.CONTENT,
    "engagement_monitor": ApprovalType.OTHER,
    # SMS - always requires approval
    "sms_draft": ApprovalType.SMS,
    # Testing
    "ab_test_setup": ApprovalType.TEST_WINNER,
    # Intelligence
    "competitor_analysis": ApprovalType.OTHER,
    "competitor_monitor": ApprovalType.OTHER,
}

# Polecats that ALWAYS require approval
ALWAYS_REQUIRE_APPROVAL = {
    "pr_pitch",
    "journalist_research",
    "sms_draft",
    "ab_test_setup",
}


class ConvoyExecutor:
    """
    Executes Campaign Convoys by orchestrating Polecat execution.
    """

    def __init__(self, use_temporal: bool = False):
        self.use_temporal = use_temporal and self._temporal_available()
        self.store = get_convoy_store()
        self.approval_store = get_approval_store()
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
        """Execute a single step locally using real Polecats when available."""
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
            # Try to use a real Polecat
            result = await self._execute_polecat(convoy, step)

            # Check if requires approval
            requires_approval = result.get("requires_approval", False)

            if requires_approval:
                # Queue for approval
                await self._queue_for_approval(convoy, step, result)

                # Mark step as awaiting approval
                self.store.update_step_status(
                    convoy.id, step.id, StepStatus.COMPLETED,
                    result={
                        "output": result.get("output", "")[:500],
                        "awaiting_approval": True,
                        "approval_item_id": result.get("approval_item_id"),
                    },
                )
            else:
                # Mark as completed
                self.store.update_step_status(
                    convoy.id, step.id, StepStatus.COMPLETED,
                    result={"output": result.get("output", "")[:500]},
                )

            self.logger.info(
                "Step completed successfully",
                convoy_id=convoy.id,
                step_id=step.id,
                requires_approval=requires_approval,
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

    async def _execute_polecat(self, convoy: Convoy, step: ConvoyStep) -> dict[str, Any]:
        """Execute a Polecat and return the result."""
        from polecats.base import get_polecat_class, PolecatContext

        # Try to get a registered Polecat class
        polecat_class = get_polecat_class(step.rig, step.polecat_type)

        if polecat_class:
            # Use real Polecat
            return await self._execute_real_polecat(convoy, step, polecat_class)
        else:
            # Fall back to direct neurometric call
            return await self._execute_fallback(convoy, step)

    async def _execute_real_polecat(
        self,
        convoy: Convoy,
        step: ConvoyStep,
        polecat_class: type,
    ) -> dict[str, Any]:
        """Execute a real Polecat instance."""
        from apps.api.core.refinery import get_refinery
        from apps.api.core.witness import get_witness

        neurometric = get_neurometric_client()
        refinery = get_refinery()
        witness = get_witness(bead_store=None)

        # Create a mock bead store that provides convoy context
        mock_bead_store = MockBeadStore(convoy, step)

        # Create and run the Polecat
        polecat = polecat_class(
            bead_id=uuid4(),  # Mock bead ID
            bead_store=mock_bead_store,
            neurometric=neurometric,
            refinery=refinery,
            witness=witness,
            config={
                "convoy_id": convoy.id,
                "campaign_id": convoy.campaign_id,
                "goal": convoy.goal,
            },
        )

        # Run the Polecat
        result = await polecat.run()

        # Determine if approval is needed
        requires_approval = (
            step.polecat_type in ALWAYS_REQUIRE_APPROVAL
            or result.requires_approval
            or (result.refinery_result and result.refinery_result.should_force_approval)
        )

        return {
            "success": result.success,
            "output": result.output_bead_ids[0] if result.output_bead_ids else "",
            "requires_approval": requires_approval,
            "refinery_passed": result.refinery_result.passed if result.refinery_result else True,
            "refinery_score": result.refinery_result.overall_score if result.refinery_result else 1.0,
            "witness_passed": result.witness_result.passed if result.witness_result else True,
            "model_used": result.model_used,
            "tokens_input": result.tokens_input,
            "tokens_output": result.tokens_output,
            "error": result.error,
        }

    async def _execute_fallback(self, convoy: Convoy, step: ConvoyStep) -> dict[str, Any]:
        """Execute via direct neurometric call (fallback when no Polecat exists)."""
        neurometric = get_neurometric_client()

        # Build a prompt based on the step type
        prompt = self._build_step_prompt(convoy, step)

        # Execute via neurometric
        response = await neurometric.complete(
            task_class=step.polecat_type,
            prompt=prompt,
        )

        # Determine if approval is needed
        requires_approval = step.polecat_type in ALWAYS_REQUIRE_APPROVAL

        return {
            "success": True,
            "output": response.content if response.content else "Completed",
            "requires_approval": requires_approval,
            "refinery_passed": True,
            "refinery_score": 1.0,
            "witness_passed": True,
            "model_used": response.model_used,
            "tokens_input": response.tokens_input,
            "tokens_output": response.tokens_output,
        }

    async def _queue_for_approval(
        self,
        convoy: Convoy,
        step: ConvoyStep,
        result: dict[str, Any],
    ) -> str:
        """Queue a step's output for human approval."""
        approval_type = POLECAT_APPROVAL_TYPES.get(step.polecat_type, ApprovalType.OTHER)

        # Determine urgency based on step priority
        if step.priority >= 3:
            urgency = Urgency.LOW
        elif step.priority == 2:
            urgency = Urgency.NORMAL
        elif step.priority == 1:
            urgency = Urgency.HIGH
        else:
            urgency = Urgency.CRITICAL

        # Always make PR and SMS critical
        if approval_type in (ApprovalType.PR_PITCH, ApprovalType.SMS):
            urgency = Urgency.CRITICAL

        item = ApprovalItem(
            id=str(uuid4()),
            bead_type="asset",
            bead_id=str(uuid4()),  # Would be real bead ID in production
            rig=step.rig,
            polecat_type=step.polecat_type,
            approval_type=approval_type,
            urgency=urgency,
            organization_id=convoy.organization_id,
            campaign_id=convoy.campaign_id,
            convoy_id=convoy.id,
            step_id=step.id,
            preview_title=f"{step.polecat_type.replace('_', ' ').title()} - {convoy.campaign_name}",
            preview_content=result.get("output", "")[:200] if result.get("output") else None,
            full_content=result.get("output"),
            refinery_scores={"overall": result.get("refinery_score", 1.0)},
            refinery_warnings=[],
            refinery_passed=result.get("refinery_passed", True),
            witness_issues=[],
            witness_passed=result.get("witness_passed", True),
        )

        self.approval_store.create(item)

        self.logger.info(
            "Queued step for approval",
            convoy_id=convoy.id,
            step_id=step.id,
            approval_item_id=item.id,
            approval_type=approval_type.value,
        )

        return item.id

    def _build_step_prompt(self, convoy: Convoy, step: ConvoyStep) -> str:
        """Build a prompt for the step execution."""
        polecat_prompts = {
            "competitor_monitor": f"Analyze the competitive landscape for a {convoy.goal} campaign. Identify 3-5 key competitors and their strategies. Be concise.",
            "competitor_analysis": f"Analyze the competitive landscape for a {convoy.goal} campaign. Identify 3-5 key competitors and their strategies. Be concise.",
            "content_calendar": f"Create a 2-week content calendar for a {convoy.goal} campaign. Include blog posts, social media, and email topics.",
            "blog_draft": f"Write a compelling blog post introduction (2-3 paragraphs) for a {convoy.goal} campaign targeting B2B audiences.",
            "seo_optimize": f"Generate SEO recommendations for a {convoy.goal} campaign. Include 5 target keywords and meta description suggestions.",
            "seo_meta": f"Generate SEO metadata for a {convoy.goal} campaign. Include meta title, description, and keywords as JSON.",
            "landing_page_draft": f"Write copy for a landing page for a {convoy.goal} campaign. Include headline, subheadline, 3 benefits, and CTA.",
            "lead_enrich": f"Describe an ideal customer profile for a {convoy.goal} campaign. Include firmographics, pain points, and buying triggers.",
            "email_personalize": f"Write a personalized cold email template for a {convoy.goal} campaign. Keep it under 150 words.",
            "social_post": f"Create 3 social media posts (LinkedIn, Twitter, and one other) for a {convoy.goal} campaign.",
            "social_snippet": f"Create social media snippets for a {convoy.goal} campaign. Include Twitter, LinkedIn, and Threads variants.",
            "engagement_monitor": f"Outline an engagement monitoring strategy for a {convoy.goal} campaign. Include metrics to track and response guidelines.",
            "sequence_create": f"Design a 4-email nurture sequence for a {convoy.goal} campaign. Provide subject lines and brief descriptions.",
            "ab_test_setup": f"Propose 2 A/B test ideas for a {convoy.goal} campaign landing page. Include hypothesis and success metrics.",
            "pr_pitch": f"Draft a PR pitch for a {convoy.goal} campaign. Include angle, key messages, and suggested outlets.",
            "image_brief": f"Create image briefs for a {convoy.goal} campaign. Include hero image, inline images, and social images.",
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


class MockBeadStore:
    """
    Mock BeadStore that provides convoy context for Polecats.

    Used when we don't have a real database connection.
    """

    def __init__(self, convoy: Convoy, step: ConvoyStep):
        self.convoy = convoy
        self.step = step

    async def get_bead(self, bead_type: str, bead_id: UUID) -> dict:
        """Return mock bead data based on convoy context."""
        return {
            "id": str(bead_id),
            "type": bead_type,
            "campaign_id": self.convoy.campaign_id,
            "organization_id": self.convoy.organization_id,
            "title": f"{self.step.polecat_type} for {self.convoy.campaign_name}",
            "topic": self.convoy.goal,
            "goal": self.convoy.goal,
            "keywords": [],
            "content_draft": "",
            "content_final": "",
            "status": "draft",
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }

    async def get_bead_history(self, bead_type: str, bead_id: UUID) -> list:
        """Return empty history for mock."""
        return []


# Global singleton
_executor: ConvoyExecutor | None = None


def get_convoy_executor() -> ConvoyExecutor:
    """Get the global convoy executor."""
    global _executor
    if _executor is None:
        _executor = ConvoyExecutor(use_temporal=False)  # Use local execution for now
    return _executor
