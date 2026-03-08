"""
GTM Mayor - The single orchestration agent.

Takes a goal + budget + horizon, produces a Campaign Convoy,
monitors feedback, and re-slates Beads dynamically.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

import structlog

from apps.api.core.bead_store import BeadStore
from apps.api.core.neurometric import NeurometricClient, get_neurometric_client

logger = structlog.get_logger()


class ConvoyStatus(str, Enum):
    """Status of a Campaign Convoy."""

    PLANNING = "planning"
    EXECUTING = "executing"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class RigType(str, Enum):
    """Available Rig types."""

    CONTENT_FACTORY = "content_factory"
    SDR_HIVE = "sdr_hive"
    SOCIAL_COMMAND = "social_command"
    PRESS_ROOM = "press_room"
    INTELLIGENCE_STATION = "intelligence_station"
    LANDING_PAD = "landing_pad"
    WIRE = "wire"
    REPO_WATCH = "repo_watch"


@dataclass
class ConvoyStep:
    """A step in the Campaign Convoy."""

    id: str
    rig: RigType
    polecat_type: str
    bead_ids: list[str]  # Input Beads
    depends_on: list[str]  # Step IDs this depends on
    priority: int  # Lower = higher priority
    status: str = "pending"
    started_at: datetime | None = None
    completed_at: datetime | None = None


@dataclass
class Convoy:
    """A Campaign Convoy - sequenced set of Beads distributed across Rigs."""

    id: str
    campaign_id: str
    status: ConvoyStatus
    steps: list[ConvoyStep]
    created_at: datetime = field(default_factory=datetime.utcnow)
    goal: str | None = None
    budget_cents: int | None = None
    horizon_days: int | None = None

    @property
    def pending_steps(self) -> list[ConvoyStep]:
        return [s for s in self.steps if s.status == "pending"]

    @property
    def ready_steps(self) -> list[ConvoyStep]:
        """Steps that are ready to execute (dependencies satisfied)."""
        completed_ids = {s.id for s in self.steps if s.status == "completed"}
        return [
            s for s in self.steps
            if s.status == "pending" and all(d in completed_ids for d in s.depends_on)
        ]


class Mayor:
    """
    The GTM Mayor - Campaign orchestration agent.

    Responsibilities:
    1. Analyze campaign goals and create execution plans
    2. Create Convoys (sequenced Bead work across Rigs)
    3. Monitor execution and re-slate based on feedback
    4. Optimize resource allocation across Rigs
    5. Respond to Intelligence Rig feedback
    """

    def __init__(
        self,
        bead_store: BeadStore,
        neurometric: NeurometricClient | None = None,
        organization_id: UUID | None = None,
    ):
        self.bead_store = bead_store
        self.neurometric = neurometric or get_neurometric_client(organization_id)
        self.organization_id = organization_id
        self.logger = logger.bind(
            service="mayor",
            organization_id=str(organization_id) if organization_id else None,
        )
        self._active_convoys: dict[str, Convoy] = {}

    async def create_convoy(
        self,
        campaign_id: UUID,
        goal: str,
        budget_cents: int | None = None,
        horizon_days: int | None = None,
    ) -> Convoy:
        """
        Create a Campaign Convoy from a goal.

        Uses AI to:
        1. Analyze the goal
        2. Determine which Rigs are needed
        3. Plan the sequence of work
        4. Create the initial Bead slate
        """
        self.logger.info(
            "Creating campaign convoy",
            campaign_id=str(campaign_id),
            goal=goal[:100],
        )

        # Use AI to plan the convoy
        plan = await self._plan_convoy(goal, budget_cents, horizon_days)

        # Create convoy steps from the plan
        steps = await self._create_convoy_steps(campaign_id, plan)

        convoy = Convoy(
            id=str(uuid4()),
            campaign_id=str(campaign_id),
            status=ConvoyStatus.PLANNING,
            steps=steps,
            goal=goal,
            budget_cents=budget_cents,
            horizon_days=horizon_days,
        )

        self._active_convoys[convoy.id] = convoy

        self.logger.info(
            "Convoy created",
            convoy_id=convoy.id,
            step_count=len(steps),
        )

        return convoy

    async def _plan_convoy(
        self,
        goal: str,
        budget_cents: int | None,
        horizon_days: int | None,
    ) -> dict[str, Any]:
        """
        Use AI to plan the convoy execution.

        Returns a structured plan with:
        - Rigs to activate
        - Polecat sequences
        - Dependencies between steps
        - Resource allocation
        """
        context = {
            "budget_cents": budget_cents,
            "horizon_days": horizon_days,
            "available_rigs": [r.value for r in RigType],
        }

        prompt = f"""You are the GTM Mayor planning a go-to-market campaign.

Goal: {goal}

Budget: ${(budget_cents or 0) / 100:.2f}
Timeline: {horizon_days or 30} days

Available Rigs and their capabilities:
- content_factory: Blog posts, social content, case studies, SEO optimization
- sdr_hive: Lead enrichment, email sequences, personalized outreach
- social_command: Social media posting, engagement, hashtag research
- press_room: PR pitches, journalist outreach
- intelligence_station: Competitor monitoring
- landing_pad: Landing pages, A/B testing
- wire: SMS outreach (human-assisted)
- repo_watch: GitHub/developer content

Create a comprehensive campaign execution plan with 5-8 steps. Respond with ONLY valid JSON (no markdown, no explanation):
{{
    "phases": [
        {{
            "name": "Phase name",
            "rigs": ["content_factory", "sdr_hive"],
            "steps": [
                {{
                    "rig": "content_factory",
                    "polecat_type": "blog_draft",
                    "description": "What this step does",
                    "depends_on": [],
                    "priority": 1
                }}
            ]
        }}
    ],
    "estimated_duration_days": 14,
    "success_metrics": ["metric1", "metric2"]
}}

Use these polecat_type values:
- content_factory: blog_draft, seo_optimize, social_snippet, content_calendar
- sdr_hive: lead_enrich, email_personalize, sequence_create
- social_command: social_post, engagement_monitor
- landing_pad: landing_page_draft, ab_test_setup

Respond with ONLY the JSON object, nothing else."""

        try:
            response = await self.neurometric.complete(
                task_class="mayor_convoy_planning",
                prompt=prompt,
                context=context,
            )

            import json
            import re

            # Clean up the response - remove markdown code blocks if present
            content = response.content.strip()
            if content.startswith("```"):
                content = re.sub(r'^```(?:json)?\s*', '', content)
                content = re.sub(r'\s*```$', '', content)

            return json.loads(content)

        except Exception as e:
            self.logger.error("Convoy planning failed", error=str(e))
            # Return a comprehensive fallback plan
            return {
                "phases": [
                    {
                        "name": "Content Creation",
                        "rigs": ["content_factory"],
                        "steps": [
                            {
                                "rig": "content_factory",
                                "polecat_type": "blog_draft",
                                "description": "Create initial blog content targeting key topics",
                                "depends_on": [],
                                "priority": 1,
                            },
                            {
                                "rig": "content_factory",
                                "polecat_type": "seo_optimize",
                                "description": "Optimize content for search engines",
                                "depends_on": [],
                                "priority": 2,
                            },
                        ],
                    },
                    {
                        "name": "Landing & Conversion",
                        "rigs": ["landing_pad"],
                        "steps": [
                            {
                                "rig": "landing_pad",
                                "polecat_type": "landing_page_draft",
                                "description": "Create conversion-optimized landing page",
                                "depends_on": [],
                                "priority": 3,
                            },
                        ],
                    },
                    {
                        "name": "Outreach",
                        "rigs": ["sdr_hive", "social_command"],
                        "steps": [
                            {
                                "rig": "sdr_hive",
                                "polecat_type": "lead_enrich",
                                "description": "Enrich lead data with firmographics",
                                "depends_on": [],
                                "priority": 4,
                            },
                            {
                                "rig": "sdr_hive",
                                "polecat_type": "email_personalize",
                                "description": "Create personalized email sequences",
                                "depends_on": [],
                                "priority": 5,
                            },
                            {
                                "rig": "social_command",
                                "polecat_type": "social_post",
                                "description": "Schedule social media content",
                                "depends_on": [],
                                "priority": 6,
                            },
                        ],
                    },
                ],
                "estimated_duration_days": horizon_days or 30,
                "success_metrics": ["leads_generated", "content_published", "email_sent"],
            }

    async def _create_convoy_steps(
        self,
        campaign_id: UUID,
        plan: dict[str, Any],
    ) -> list[ConvoyStep]:
        """Create ConvoySteps from the AI-generated plan."""
        steps = []
        step_counter = 0

        for phase in plan.get("phases", []):
            for step_data in phase.get("steps", []):
                step_counter += 1
                step = ConvoyStep(
                    id=f"step_{step_counter}",
                    rig=RigType(step_data["rig"]),
                    polecat_type=step_data["polecat_type"],
                    bead_ids=[],  # Will be populated when Beads are created
                    depends_on=step_data.get("depends_on", []),
                    priority=step_data.get("priority", step_counter),
                )
                steps.append(step)

        return steps

    async def start_convoy(self, convoy_id: str) -> Convoy:
        """
        Start executing a Convoy.

        Begins processing ready steps (those with no unmet dependencies).
        """
        convoy = self._active_convoys.get(convoy_id)
        if not convoy:
            raise ValueError(f"Convoy not found: {convoy_id}")

        convoy.status = ConvoyStatus.EXECUTING

        self.logger.info(
            "Starting convoy execution",
            convoy_id=convoy_id,
            ready_steps=len(convoy.ready_steps),
        )

        # Spawn Polecats for ready steps
        for step in convoy.ready_steps:
            await self._execute_step(convoy, step)

        return convoy

    async def _execute_step(self, convoy: Convoy, step: ConvoyStep):
        """Execute a single convoy step by spawning appropriate Polecats."""
        self.logger.info(
            "Executing convoy step",
            convoy_id=convoy.id,
            step_id=step.id,
            rig=step.rig.value,
            polecat_type=step.polecat_type,
        )

        step.status = "running"
        step.started_at = datetime.utcnow()

        # TODO: Actually spawn the Polecat via Temporal
        # This would:
        # 1. Create input Beads if needed
        # 2. Submit to the appropriate Rig's task queue
        # 3. Track execution status

    async def handle_step_completion(
        self,
        convoy_id: str,
        step_id: str,
        output_bead_ids: list[str],
        success: bool,
    ):
        """
        Handle completion of a convoy step.

        Updates convoy state and triggers next steps if ready.
        """
        convoy = self._active_convoys.get(convoy_id)
        if not convoy:
            return

        step = next((s for s in convoy.steps if s.id == step_id), None)
        if not step:
            return

        step.status = "completed" if success else "failed"
        step.completed_at = datetime.utcnow()
        step.bead_ids.extend(output_bead_ids)

        self.logger.info(
            "Convoy step completed",
            convoy_id=convoy_id,
            step_id=step_id,
            success=success,
        )

        # Check if convoy is complete
        if all(s.status in ("completed", "failed") for s in convoy.steps):
            convoy.status = ConvoyStatus.COMPLETED
            self.logger.info("Convoy completed", convoy_id=convoy_id)
            return

        # Execute any newly-ready steps
        for next_step in convoy.ready_steps:
            await self._execute_step(convoy, next_step)

    async def pause_convoy(self, convoy_id: str) -> Convoy:
        """Pause a running Convoy."""
        convoy = self._active_convoys.get(convoy_id)
        if not convoy:
            raise ValueError(f"Convoy not found: {convoy_id}")

        convoy.status = ConvoyStatus.PAUSED

        # TODO: Pause any running Polecats

        self.logger.info("Convoy paused", convoy_id=convoy_id)
        return convoy

    async def resume_convoy(self, convoy_id: str) -> Convoy:
        """Resume a paused Convoy."""
        convoy = self._active_convoys.get(convoy_id)
        if not convoy:
            raise ValueError(f"Convoy not found: {convoy_id}")

        if convoy.status != ConvoyStatus.PAUSED:
            raise ValueError(f"Convoy is not paused: {convoy_id}")

        convoy.status = ConvoyStatus.EXECUTING

        # Resume ready steps
        for step in convoy.ready_steps:
            await self._execute_step(convoy, step)

        self.logger.info("Convoy resumed", convoy_id=convoy_id)
        return convoy

    async def re_slate(
        self,
        convoy_id: str,
        feedback: dict[str, Any],
    ) -> Convoy:
        """
        Re-slate a Convoy based on feedback.

        The Mayor analyzes feedback and adjusts the execution plan:
        - Add new steps
        - Remove unnecessary steps
        - Re-prioritize steps
        - Adjust Rig allocation
        """
        convoy = self._active_convoys.get(convoy_id)
        if not convoy:
            raise ValueError(f"Convoy not found: {convoy_id}")

        self.logger.info(
            "Re-slating convoy",
            convoy_id=convoy_id,
            feedback_type=feedback.get("type"),
        )

        # Use AI to analyze feedback and suggest changes
        prompt = f"""You are the GTM Mayor re-evaluating a campaign based on new feedback.

Current convoy status:
- Steps: {len(convoy.steps)}
- Completed: {len([s for s in convoy.steps if s.status == 'completed'])}
- Pending: {len(convoy.pending_steps)}

Feedback received:
{feedback}

Based on this feedback, suggest adjustments to the campaign plan.
Output as JSON:
{{
    "add_steps": [...],
    "remove_steps": [...],
    "reprioritize": {{...}},
    "reasoning": "..."
}}
"""

        try:
            response = await self.neurometric.complete(
                task_class="mayor_re_slate",
                prompt=prompt,
            )

            import json
            adjustments = json.loads(response.content)

            # Apply adjustments
            # TODO: Implement adjustment application

            self.logger.info(
                "Convoy re-slated",
                convoy_id=convoy_id,
                adjustments=adjustments.get("reasoning"),
            )

        except Exception as e:
            self.logger.error("Re-slating failed", error=str(e))

        return convoy

    async def handle_intelligence_feedback(
        self,
        campaign_id: UUID,
        intelligence: dict[str, Any],
    ):
        """
        Handle feedback from the Intelligence Station Rig.

        Competitor intelligence may trigger re-slating:
        - Competitor launched similar feature → accelerate messaging
        - Competitor pricing change → adjust value props
        - Competitor PR mention → consider response
        """
        self.logger.info(
            "Processing intelligence feedback",
            campaign_id=str(campaign_id),
            intel_type=intelligence.get("type"),
        )

        # Find active convoy for this campaign
        convoy = next(
            (c for c in self._active_convoys.values() if c.campaign_id == str(campaign_id)),
            None,
        )

        if convoy:
            await self.re_slate(convoy.id, {"type": "intelligence", "data": intelligence})

    def get_convoy_status(self, convoy_id: str) -> Convoy | None:
        """Get the current status of a Convoy."""
        return self._active_convoys.get(convoy_id)

    def get_active_convoys(self, campaign_id: UUID | None = None) -> list[Convoy]:
        """Get all active Convoys, optionally filtered by campaign."""
        convoys = list(self._active_convoys.values())
        if campaign_id:
            convoys = [c for c in convoys if c.campaign_id == str(campaign_id)]
        return convoys


# =============================================================================
# Factory Function
# =============================================================================


def get_mayor(
    bead_store: BeadStore,
    organization_id: UUID | None = None,
) -> Mayor:
    """Get a Mayor instance."""
    return Mayor(bead_store=bead_store, organization_id=organization_id)
