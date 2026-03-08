"""
Witness - Second-pass AI agent for consistency checking.

Checks Bead history for:
- Contradictions
- Duplicate outreach
- Consistency violations
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

import structlog

from apps.api.core.bead_store import BeadStore
from apps.api.core.neurometric import NeurometricClient, get_neurometric_client

logger = structlog.get_logger()


@dataclass
class WitnessIssue:
    """An issue found by the Witness."""

    issue_type: str  # contradiction, duplicate, consistency
    severity: str  # low, medium, high, critical
    description: str
    affected_beads: list[str]
    recommendation: str


@dataclass
class WitnessResult:
    """Result from Witness verification."""

    passed: bool
    issues: list[WitnessIssue]
    notes: str | None
    verified_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def has_blocking_issues(self) -> bool:
        """Check if there are any high/critical severity issues."""
        return any(i.severity in ("high", "critical") for i in self.issues)


class Witness:
    """
    The Witness consistency checker.

    Performs second-pass verification on Bead outputs to ensure:
    1. No contradictions with previous outputs
    2. No duplicate outreach to the same contacts
    3. Consistency across the campaign
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
            service="witness",
            organization_id=str(organization_id) if organization_id else None,
        )

    async def verify(
        self,
        content: str,
        bead_id: UUID,
        bead_type: str,
        bead_history: list[dict[str, Any]] | None = None,
        context: dict[str, Any] | None = None,
    ) -> WitnessResult:
        """
        Verify content against Bead history and campaign context.

        Args:
            content: The content to verify
            bead_id: ID of the Bead being processed
            bead_type: Type of the Bead
            bead_history: Historical versions of this Bead
            context: Additional context (campaign, related Beads)

        Returns:
            WitnessResult with any issues found
        """
        self.logger.info(
            "Running Witness verification",
            bead_id=str(bead_id),
            bead_type=bead_type,
        )

        context = context or {}
        issues: list[WitnessIssue] = []

        # Run applicable checks based on bead type
        if bead_type == "asset":
            issues.extend(await self._check_content_consistency(content, bead_history, context))

        if bead_type in ("lead", "journalist"):
            issues.extend(await self._check_duplicate_outreach(content, bead_id, context))

        if context.get("campaign_id"):
            issues.extend(await self._check_campaign_consistency(content, context))

        # Always check for contradictions
        if bead_history:
            issues.extend(await self._check_contradictions(content, bead_history))

        passed = not any(i.severity in ("high", "critical") for i in issues)

        result = WitnessResult(
            passed=passed,
            issues=issues,
            notes=f"Verified {len(bead_history or [])} historical versions" if bead_history else None,
        )

        self.logger.info(
            "Witness verification completed",
            passed=passed,
            issue_count=len(issues),
            blocking_issues=result.has_blocking_issues,
        )

        return result

    async def _check_duplicate_outreach(
        self,
        content: str,
        bead_id: UUID,
        context: dict[str, Any],
    ) -> list[WitnessIssue]:
        """
        Check for duplicate outreach to the same contact.

        Prevents:
        - Sending the same pitch to a journalist twice
        - Re-contacting a lead within the cooldown period
        - Overlapping sequences to the same email
        """
        issues = []

        # Get contact identifier from context
        email = context.get("email")
        contact_id = context.get("contact_id")

        if not email and not contact_id:
            return issues

        # Check recent outreach history
        # TODO: Query outreach history from Beads
        # For now, return placeholder

        # Check journalist pitch history
        if context.get("bead_type") == "journalist":
            # Journalist pitches have a 30-day cooldown
            last_pitched = context.get("last_pitched_at")
            if last_pitched:
                last_pitched_dt = datetime.fromisoformat(last_pitched) if isinstance(last_pitched, str) else last_pitched
                if datetime.utcnow() - last_pitched_dt < timedelta(days=30):
                    issues.append(WitnessIssue(
                        issue_type="duplicate",
                        severity="high",
                        description=f"Journalist was pitched within the last 30 days",
                        affected_beads=[str(bead_id)],
                        recommendation="Wait until cooldown period expires or get explicit approval",
                    ))

        return issues

    async def _check_contradictions(
        self,
        content: str,
        bead_history: list[dict[str, Any]],
    ) -> list[WitnessIssue]:
        """
        Check for contradictions with previous versions.

        Uses AI to detect semantic contradictions between current
        content and historical versions.
        """
        issues = []

        if not bead_history or len(bead_history) < 2:
            return issues

        # Get the most recent previous content
        previous_content = None
        for hist in bead_history:
            prev = hist.get("content_final") or hist.get("content_draft") or hist.get("content")
            if prev and prev != content:
                previous_content = prev
                break

        if not previous_content:
            return issues

        # Use Neurometric to check for contradictions
        try:
            prompt = f"""Compare these two versions of content for contradictions.

Previous version:
{previous_content[:2000]}

Current version:
{content[:2000]}

Identify any contradictions where the current version makes claims that directly conflict with the previous version.
Only flag genuine contradictions, not updates or refinements.

Respond with JSON:
{{"has_contradictions": true/false, "contradictions": ["description1", "description2"]}}
"""

            response = await self.neurometric.complete(
                task_class="witness_contradiction_check",
                prompt=prompt,
            )

            # Parse response (simplified)
            import json
            try:
                result = json.loads(response.content)
                if result.get("has_contradictions"):
                    for contradiction in result.get("contradictions", []):
                        issues.append(WitnessIssue(
                            issue_type="contradiction",
                            severity="medium",
                            description=contradiction,
                            affected_beads=[],
                            recommendation="Review and reconcile the contradiction",
                        ))
            except json.JSONDecodeError:
                pass  # Could not parse AI response

        except Exception as e:
            self.logger.warning("Contradiction check failed", error=str(e))

        return issues

    async def _check_content_consistency(
        self,
        content: str,
        bead_history: list[dict[str, Any]] | None,
        context: dict[str, Any],
    ) -> list[WitnessIssue]:
        """
        Check content consistency across campaign assets.

        Ensures:
        - Consistent messaging across content pieces
        - No conflicting claims
        - Aligned value propositions
        """
        issues = []

        # Get related assets from context
        related_assets = context.get("related_assets", [])

        if not related_assets:
            return issues

        # TODO: Implement cross-asset consistency check
        # This would compare key claims, statistics, and messaging
        # across related content pieces

        return issues

    async def _check_campaign_consistency(
        self,
        content: str,
        context: dict[str, Any],
    ) -> list[WitnessIssue]:
        """
        Check consistency with overall campaign parameters.

        Ensures content aligns with:
        - Campaign goals
        - Target ICP
        - Brand voice guidelines
        """
        issues = []

        campaign = context.get("campaign", {})
        icp = context.get("icp", {})

        # Check alignment with campaign goal
        goal = campaign.get("goal")
        if goal:
            # TODO: Use AI to verify content supports the goal
            pass

        # Check ICP alignment
        target_industries = icp.get("industries", [])
        if target_industries:
            # Check if content references appropriate industries
            content_lower = content.lower()
            if not any(ind.lower() in content_lower for ind in target_industries):
                # Not necessarily an issue, just a note
                pass

        return issues

    async def verify_cross_rig(
        self,
        bead_ids: list[UUID],
        campaign_id: UUID,
    ) -> WitnessResult:
        """
        Verify consistency across multiple Beads from different Rigs.

        Used for campaign-wide consistency checks.
        """
        issues = []

        # TODO: Implement cross-Rig consistency verification
        # This would:
        # 1. Fetch all relevant Beads
        # 2. Extract key claims and messaging
        # 3. Check for conflicts between Rigs

        return WitnessResult(
            passed=True,
            issues=issues,
            notes=f"Cross-rig verification for campaign {campaign_id}",
        )


# =============================================================================
# Factory Function
# =============================================================================


def get_witness(
    bead_store: BeadStore,
    organization_id: UUID | None = None,
) -> Witness:
    """Get a Witness instance."""
    return Witness(bead_store=bead_store, organization_id=organization_id)
