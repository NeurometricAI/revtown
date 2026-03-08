"""
BasePolecat - Base class that all Polecats inherit from.

Polecats are ephemeral single-task agents that:
- Accept a bead_id at instantiation (their sole state input)
- Read context from the Bead ledger via BeadStore
- Call LLMs through the Neurometric client only
- Write output back as a new or updated Bead
- Pass output through Refinery → Witness before writing
- Self-terminate cleanly on success or failure
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, ClassVar
from uuid import UUID, uuid4

import structlog

from apps.api.core.bead_store import BeadStore
from apps.api.core.neurometric import NeurometricClient, NeurometricResponse
from apps.api.core.refinery import Refinery, RefineryResult
from apps.api.core.witness import Witness, WitnessResult

logger = structlog.get_logger()


@dataclass
class PolecatResult:
    """Result from a Polecat execution."""

    success: bool
    output_bead_ids: list[str]
    refinery_result: RefineryResult | None = None
    witness_result: WitnessResult | None = None
    model_used: str | None = None
    tokens_input: int = 0
    tokens_output: int = 0
    duration_ms: int = 0
    error: str | None = None
    requires_approval: bool = False


@dataclass
class PolecatContext:
    """Context for Polecat execution."""

    bead_id: UUID
    bead_type: str
    bead_data: dict[str, Any]
    campaign_id: UUID | None = None
    organization_id: UUID | None = None
    related_beads: list[dict[str, Any]] = field(default_factory=list)
    config: dict[str, Any] = field(default_factory=dict)


class BasePolecat(ABC):
    """
    Base class for all Polecats.

    Polecats are ephemeral, single-task agents. They:
    1. Read context from Beads (never hold state)
    2. Execute a specific task via Neurometric
    3. Pass output through Refinery + Witness
    4. Write results back to the Bead ledger
    5. Self-terminate cleanly

    All subclasses must define:
    - task_class: The Neurometric task class for model selection
    - content_type: The content type for Refinery checks
    - execute(): The core execution logic
    """

    # Class variables - must be set by subclasses
    task_class: ClassVar[str] = ""
    content_type: ClassVar[str] = ""  # email, blog, pr_pitch, social, landing_page
    rig: ClassVar[str] = ""  # The Rig this Polecat belongs to

    # Configurable refinery rules (subclasses can override)
    refinery_rules: ClassVar[list[str]] = []

    # Whether this Polecat's output always requires approval
    always_requires_approval: ClassVar[bool] = False

    def __init__(
        self,
        bead_id: UUID,
        bead_store: BeadStore,
        neurometric: NeurometricClient,
        refinery: Refinery,
        witness: Witness,
        config: dict[str, Any] | None = None,
    ):
        self.bead_id = bead_id
        self.bead_store = bead_store
        self.neurometric = neurometric
        self.refinery = refinery
        self.witness = witness
        self.config = config or {}

        self.execution_id = str(uuid4())
        self.start_time: datetime | None = None
        self.context: PolecatContext | None = None

        self.logger = logger.bind(
            polecat_type=self.__class__.__name__,
            task_class=self.task_class,
            bead_id=str(bead_id),
            execution_id=self.execution_id,
        )

    # =========================================================================
    # Core Execution Flow
    # =========================================================================

    async def run(self) -> PolecatResult:
        """
        Execute the Polecat with full pipeline.

        This is the main entry point that:
        1. Loads context from the Bead
        2. Executes the task
        3. Runs Refinery checks
        4. Runs Witness verification
        5. Writes output to the ledger
        6. Returns result

        Subclasses should NOT override this method.
        Override execute() instead.
        """
        self.start_time = datetime.utcnow()
        self.logger.info("Starting Polecat execution")

        try:
            # Load context
            self.context = await self._load_context()

            # Execute the task
            output = await self.execute()

            # Run through Refinery
            refinery_result = await self._run_refinery(output)

            # Run through Witness
            witness_result = await self._run_witness(output, refinery_result)

            # Determine if approval is needed
            requires_approval = self._requires_approval(refinery_result, witness_result)

            # Write output to ledger
            output_bead_ids = await self._write_output(output, requires_approval)

            # Calculate duration
            duration_ms = int((datetime.utcnow() - self.start_time).total_seconds() * 1000)

            result = PolecatResult(
                success=True,
                output_bead_ids=output_bead_ids,
                refinery_result=refinery_result,
                witness_result=witness_result,
                model_used=getattr(self, "_last_model_used", None),
                tokens_input=getattr(self, "_total_tokens_input", 0),
                tokens_output=getattr(self, "_total_tokens_output", 0),
                duration_ms=duration_ms,
                requires_approval=requires_approval,
            )

            self.logger.info(
                "Polecat execution completed",
                success=True,
                duration_ms=duration_ms,
                requires_approval=requires_approval,
            )

            return result

        except Exception as e:
            self.logger.error("Polecat execution failed", error=str(e))

            # Log failure to Bead
            await self._log_failure(str(e))

            duration_ms = int((datetime.utcnow() - self.start_time).total_seconds() * 1000) if self.start_time else 0

            return PolecatResult(
                success=False,
                output_bead_ids=[],
                error=str(e),
                duration_ms=duration_ms,
            )

    @abstractmethod
    async def execute(self) -> str:
        """
        Execute the core task logic.

        Subclasses must implement this method.

        Returns:
            The generated content/output as a string.

        The context is available via self.context.
        Use self.call_neurometric() for LLM calls.
        """
        raise NotImplementedError

    # =========================================================================
    # Context Loading
    # =========================================================================

    async def _load_context(self) -> PolecatContext:
        """Load context from the Bead ledger."""
        # Get the input Bead
        bead = await self.bead_store.get_bead(
            self._get_bead_type(),
            self.bead_id,
        )

        bead_data = bead.model_dump() if hasattr(bead, "model_dump") else dict(bead)

        # Get related Beads if needed
        related_beads = await self._load_related_beads(bead_data)

        return PolecatContext(
            bead_id=self.bead_id,
            bead_type=bead_data.get("type", "unknown"),
            bead_data=bead_data,
            campaign_id=bead_data.get("campaign_id"),
            organization_id=bead_data.get("organization_id"),
            related_beads=related_beads,
            config=self.config,
        )

    def _get_bead_type(self) -> str:
        """Get the expected Bead type for this Polecat."""
        # Default implementation - subclasses can override
        return "asset"

    async def _load_related_beads(self, bead_data: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Load any related Beads needed for context.

        Subclasses can override to load specific related Beads.
        """
        return []

    # =========================================================================
    # Neurometric Integration
    # =========================================================================

    async def call_neurometric(
        self,
        prompt: str,
        context: dict[str, Any] | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        """
        Make an LLM call through Neurometric.

        This is the ONLY way Polecats should make LLM calls.
        """
        response = await self.neurometric.complete(
            task_class=self.task_class,
            prompt=prompt,
            context=context,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        # Track usage
        self._last_model_used = response.model_used
        self._total_tokens_input = getattr(self, "_total_tokens_input", 0) + response.tokens_input
        self._total_tokens_output = getattr(self, "_total_tokens_output", 0) + response.tokens_output

        return response.content

    # =========================================================================
    # Quality Gates
    # =========================================================================

    async def _run_refinery(self, content: str) -> RefineryResult:
        """Run content through Refinery checks."""
        context = {
            "bead_id": str(self.bead_id),
            "bead_type": self.context.bead_type if self.context else None,
            "campaign_id": str(self.context.campaign_id) if self.context and self.context.campaign_id else None,
            **self.context.bead_data if self.context else {},
        }

        return await self.refinery.check(
            content=content,
            content_type=self.content_type,
            context=context,
        )

    async def _run_witness(
        self,
        content: str,
        refinery_result: RefineryResult,
    ) -> WitnessResult:
        """Run content through Witness verification."""
        # Get Bead history for contradiction checking
        bead_history = []
        try:
            bead_history = await self.bead_store.get_bead_history(
                self.context.bead_type if self.context else "asset",
                self.bead_id,
            )
        except Exception:
            pass  # History not available

        context = {
            "bead_type": self.context.bead_type if self.context else None,
            "campaign_id": str(self.context.campaign_id) if self.context and self.context.campaign_id else None,
            "refinery_passed": refinery_result.passed,
            **self.context.bead_data if self.context else {},
        }

        return await self.witness.verify(
            content=content,
            bead_id=self.bead_id,
            bead_type=self.context.bead_type if self.context else "asset",
            bead_history=bead_history,
            context=context,
        )

    def _requires_approval(
        self,
        refinery_result: RefineryResult,
        witness_result: WitnessResult,
    ) -> bool:
        """Determine if output requires human approval."""
        # Always require approval for certain Polecats
        if self.always_requires_approval:
            return True

        # Require approval if Refinery score is below threshold
        if refinery_result.should_force_approval:
            return True

        # Require approval if Witness found blocking issues
        if witness_result.has_blocking_issues:
            return True

        return False

    # =========================================================================
    # Output Writing
    # =========================================================================

    async def _write_output(
        self,
        content: str,
        requires_approval: bool,
    ) -> list[str]:
        """
        Write output back to the Bead ledger.

        Subclasses can override to customize output writing.
        """
        # Default: update the input Bead with the content
        status = "ready_for_approval" if requires_approval else "approved"

        # TODO: Use appropriate update method based on Bead type
        # For now, return the input Bead ID
        return [str(self.bead_id)]

    async def _log_failure(self, error: str):
        """Log failure to the Bead ledger."""
        self.logger.error("Logging failure to Bead", error=error)
        # TODO: Update Bead with failure status and error message

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def build_prompt(self, template: str, **kwargs) -> str:
        """
        Build a prompt from a template.

        Convenience method for subclasses.
        """
        context_data = self.context.bead_data if self.context else {}
        return template.format(**context_data, **kwargs)


# =============================================================================
# Polecat Registry
# =============================================================================

_polecat_registry: dict[str, type[BasePolecat]] = {}


def register_polecat(polecat_class: type[BasePolecat]) -> type[BasePolecat]:
    """
    Decorator to register a Polecat class.

    Usage:
        @register_polecat
        class MyPolecat(BasePolecat):
            task_class = "my_task"
            ...
    """
    key = f"{polecat_class.rig}:{polecat_class.task_class}"
    _polecat_registry[key] = polecat_class
    return polecat_class


def get_polecat_class(rig: str, task_class: str) -> type[BasePolecat] | None:
    """Get a registered Polecat class."""
    return _polecat_registry.get(f"{rig}:{task_class}")


def list_registered_polecats() -> dict[str, list[str]]:
    """List all registered Polecats by Rig."""
    by_rig: dict[str, list[str]] = {}
    for key in _polecat_registry:
        rig, task_class = key.split(":", 1)
        if rig not in by_rig:
            by_rig[rig] = []
        by_rig[rig].append(task_class)
    return by_rig
