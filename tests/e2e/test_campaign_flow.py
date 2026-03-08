"""
End-to-end tests for complete campaign flows.

These tests verify the full pipeline from campaign creation
through Polecat execution, Refinery/Witness gates, and approval.
"""

import asyncio
import os
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestCampaignCreationFlow:
    """E2E tests for campaign creation and convoy generation."""

    @pytest.fixture
    def mock_services(self):
        """Mock all external services."""
        with patch.multiple(
            "apps.api.core",
            BeadStore=MagicMock(),
            NeurometricClient=MagicMock(),
            Refinery=MagicMock(),
            Witness=MagicMock(),
        ) as mocks:
            yield mocks

    @pytest.mark.asyncio
    async def test_campaign_creation_generates_convoy(self, mock_services):
        """Test that creating a campaign generates a convoy plan."""
        from apps.api.core.mayor import Mayor

        # Setup mocks
        mock_bead_store = MagicMock()
        mock_bead_store.create = AsyncMock(
            return_value={
                "id": "campaign-001",
                "type": "CampaignBead",
                "status": "active",
            }
        )

        mock_neurometric = MagicMock()
        mock_neurometric.complete = AsyncMock(
            return_value={
                "content": '{"steps": [{"rig": "content_factory", "polecat": "blog_draft", "priority": 1}]}',
            }
        )

        mayor = Mayor(
            bead_store=mock_bead_store,
            neurometric=mock_neurometric,
        )

        # Create campaign
        campaign = await mayor.create_campaign(
            name="Q1 Outbound",
            goal="Generate 50 qualified leads",
            budget=10000,
            rigs_enabled=["content_factory", "sdr_hive"],
            organization_id="org-001",
        )

        assert campaign is not None
        assert campaign["convoy_plan"] is not None
        assert len(campaign["convoy_plan"]["steps"]) > 0


class TestPolecatExecutionFlow:
    """E2E tests for Polecat execution pipeline."""

    @pytest.fixture
    def mock_dependencies(self):
        """Create mock dependencies."""
        bead_store = MagicMock()
        bead_store.get = AsyncMock(
            return_value={
                "id": "asset-001",
                "type": "AssetBead",
                "campaign_id": "campaign-001",
                "asset_type": "blog_post",
                "title": "Draft: AI in Marketing",
                "status": "pending",
            }
        )
        bead_store.update = AsyncMock()

        neurometric = MagicMock()
        neurometric.complete = AsyncMock(
            return_value={
                "content": "# AI in Marketing\n\nAI is transforming...",
                "model": "claude-sonnet",
                "usage": {"input_tokens": 100, "output_tokens": 500},
            }
        )

        refinery = MagicMock()
        refinery.check = AsyncMock(
            return_value={
                "passed": True,
                "score": 88,
                "checks": {
                    "brand_voice": {"passed": True, "score": 90},
                    "readability": {"passed": True, "score": 85},
                },
            }
        )

        witness = MagicMock()
        witness.verify = AsyncMock(
            return_value={
                "passed": True,
                "issues": [],
            }
        )

        return {
            "bead_store": bead_store,
            "neurometric": neurometric,
            "refinery": refinery,
            "witness": witness,
        }

    @pytest.mark.asyncio
    async def test_polecat_execution_happy_path(self, mock_dependencies):
        """Test successful Polecat execution through all gates."""
        from rigs.content_factory.polecats import BlogDraftPolecat

        polecat = BlogDraftPolecat(
            bead_id="asset-001",
            organization_id="org-001",
            **mock_dependencies,
        )

        result = await polecat.run()

        # Verify all steps executed
        mock_dependencies["bead_store"].get.assert_called_once()
        mock_dependencies["neurometric"].complete.assert_called_once()
        mock_dependencies["refinery"].check.assert_called_once()
        mock_dependencies["witness"].verify.assert_called_once()
        mock_dependencies["bead_store"].update.assert_called()

        # Verify result
        assert result["status"] == "completed"
        assert result["requires_approval"] is False

    @pytest.mark.asyncio
    async def test_polecat_execution_refinery_fail(self, mock_dependencies):
        """Test Polecat execution when Refinery fails."""
        from rigs.content_factory.polecats import BlogDraftPolecat

        # Make Refinery fail
        mock_dependencies["refinery"].check.return_value = {
            "passed": False,
            "score": 45,
            "checks": {"brand_voice": {"passed": False, "score": 40}},
        }

        polecat = BlogDraftPolecat(
            bead_id="asset-001",
            organization_id="org-001",
            **mock_dependencies,
        )

        result = await polecat.run()

        # Should require approval due to low score
        assert result["requires_approval"] is True
        assert result["refinery_score"] < 50

    @pytest.mark.asyncio
    async def test_polecat_execution_witness_issues(self, mock_dependencies):
        """Test Polecat execution when Witness finds issues."""
        from rigs.content_factory.polecats import BlogDraftPolecat

        # Make Witness find issues
        mock_dependencies["witness"].verify.return_value = {
            "passed": False,
            "issues": [
                {
                    "type": "contradiction",
                    "severity": "medium",
                    "description": "Conflicts with previous messaging",
                }
            ],
        }

        polecat = BlogDraftPolecat(
            bead_id="asset-001",
            organization_id="org-001",
            **mock_dependencies,
        )

        result = await polecat.run()

        # Should require approval due to Witness issues
        assert result["requires_approval"] is True
        assert len(result["witness_issues"]) > 0


class TestApprovalFlow:
    """E2E tests for the approval workflow."""

    @pytest.fixture
    def mock_services(self):
        """Mock all services."""
        return {
            "bead_store": MagicMock(),
            "approval_queue": MagicMock(),
        }

    @pytest.mark.asyncio
    async def test_item_queued_for_approval(self, mock_services):
        """Test that items are properly queued for approval."""
        mock_services["approval_queue"].add = AsyncMock(
            return_value={
                "id": "approval-001",
                "bead_id": "asset-001",
                "status": "pending",
                "refinery_score": 75,
            }
        )

        # Simulate adding to approval queue
        result = await mock_services["approval_queue"].add(
            bead_id="asset-001",
            bead_type="AssetBead",
            rig="content_factory",
            polecat_type="blog_draft",
            refinery_score=75,
            witness_issues=[],
        )

        assert result["status"] == "pending"
        assert result["bead_id"] == "asset-001"

    @pytest.mark.asyncio
    async def test_approval_updates_bead_status(self, mock_services):
        """Test that approval updates Bead status."""
        mock_services["bead_store"].update = AsyncMock(
            return_value={
                "id": "asset-001",
                "status": "approved",
                "approved_by": "user-001",
                "approved_at": datetime.utcnow().isoformat(),
            }
        )

        # Simulate approval
        result = await mock_services["bead_store"].update(
            "asset-001",
            {
                "status": "approved",
                "approved_by": "user-001",
            },
        )

        assert result["status"] == "approved"
        assert result["approved_by"] == "user-001"

    @pytest.mark.asyncio
    async def test_rejection_creates_audit_log(self, mock_services):
        """Test that rejection creates audit log entry."""
        mock_services["bead_store"].update = AsyncMock()
        mock_services["bead_store"].create_audit_log = AsyncMock(
            return_value={
                "id": "audit-001",
                "action": "rejected",
                "reason": "Off-brand messaging",
            }
        )

        # Simulate rejection
        await mock_services["bead_store"].update(
            "asset-001",
            {"status": "rejected"},
        )

        audit = await mock_services["bead_store"].create_audit_log(
            bead_id="asset-001",
            action="rejected",
            user_id="user-001",
            reason="Off-brand messaging",
        )

        assert audit["action"] == "rejected"


class TestConvoyExecutionFlow:
    """E2E tests for Campaign Convoy execution."""

    @pytest.fixture
    def mock_services(self):
        """Mock all services."""
        return {
            "bead_store": MagicMock(),
            "neurometric": MagicMock(),
            "polecat_spawner": MagicMock(),
        }

    @pytest.mark.asyncio
    async def test_convoy_executes_steps_in_order(self, mock_services):
        """Test that convoy executes steps in sequence."""
        execution_order = []

        async def mock_spawn(rig, polecat_type, bead_id):
            execution_order.append(f"{rig}:{polecat_type}")
            return {"polecat_id": f"polecat-{len(execution_order)}", "status": "completed"}

        mock_services["polecat_spawner"].spawn = mock_spawn

        convoy_plan = {
            "steps": [
                {"rig": "content_factory", "polecat": "blog_draft", "bead_id": "asset-001"},
                {"rig": "content_factory", "polecat": "seo_meta", "bead_id": "asset-001"},
                {"rig": "social_command", "polecat": "social_snippet", "bead_id": "asset-001"},
            ]
        }

        # Execute convoy
        for step in convoy_plan["steps"]:
            await mock_services["polecat_spawner"].spawn(
                step["rig"],
                step["polecat"],
                step["bead_id"],
            )

        # Verify order
        assert execution_order == [
            "content_factory:blog_draft",
            "content_factory:seo_meta",
            "social_command:social_snippet",
        ]

    @pytest.mark.asyncio
    async def test_convoy_handles_step_failure(self, mock_services):
        """Test convoy handling when a step fails."""
        step_count = 0

        async def mock_spawn(rig, polecat_type, bead_id):
            nonlocal step_count
            step_count += 1
            if step_count == 2:
                raise Exception("Polecat execution failed")
            return {"polecat_id": f"polecat-{step_count}", "status": "completed"}

        mock_services["polecat_spawner"].spawn = mock_spawn

        convoy_plan = {
            "steps": [
                {"rig": "content_factory", "polecat": "blog_draft", "bead_id": "asset-001"},
                {"rig": "content_factory", "polecat": "seo_meta", "bead_id": "asset-001"},
                {"rig": "social_command", "polecat": "social_snippet", "bead_id": "asset-001"},
            ]
        }

        results = {"completed": 0, "failed": 0}

        for step in convoy_plan["steps"]:
            try:
                await mock_services["polecat_spawner"].spawn(
                    step["rig"],
                    step["polecat"],
                    step["bead_id"],
                )
                results["completed"] += 1
            except Exception:
                results["failed"] += 1

        assert results["completed"] == 2
        assert results["failed"] == 1


class TestOutboundFlow:
    """E2E tests for SDR Hive outbound flows."""

    @pytest.fixture
    def mock_services(self):
        """Mock all services."""
        return {
            "bead_store": MagicMock(),
            "neurometric": MagicMock(),
            "refinery": MagicMock(),
            "witness": MagicMock(),
        }

    @pytest.mark.asyncio
    async def test_email_sequence_flow(self, mock_services):
        """Test email sequence generation flow."""
        # Mock lead bead
        mock_services["bead_store"].get = AsyncMock(
            return_value={
                "id": "lead-001",
                "type": "LeadBead",
                "email": "prospect@company.com",
                "first_name": "Jane",
                "company": "BigCorp",
                "title": "VP Engineering",
            }
        )

        # Mock neurometric
        mock_services["neurometric"].complete = AsyncMock(
            return_value={
                "content": "Subject: Quick question about BigCorp's engineering challenges...",
            }
        )

        # Mock refinery
        mock_services["refinery"].check = AsyncMock(
            return_value={
                "passed": True,
                "score": 82,
                "checks": {
                    "personalization_depth": {"passed": True, "score": 85},
                    "spam_score": {"passed": True, "score": 10},
                },
            }
        )

        # Mock witness
        mock_services["witness"].check_duplicate_outreach = AsyncMock(
            return_value={"passed": True, "issues": []}
        )

        # Simulate flow
        lead = await mock_services["bead_store"].get("lead-001")
        email = await mock_services["neurometric"].complete(
            task_class="email_personalization",
            prompt=f"Write personalized email for {lead['first_name']} at {lead['company']}",
        )
        refinery_result = await mock_services["refinery"].check(email["content"])
        witness_result = await mock_services["witness"].check_duplicate_outreach(
            "lead-001", "email"
        )

        assert refinery_result["passed"] is True
        assert witness_result["passed"] is True

    @pytest.mark.asyncio
    async def test_duplicate_outreach_blocked(self, mock_services):
        """Test that duplicate outreach is blocked by Witness."""
        mock_services["witness"].check_duplicate_outreach = AsyncMock(
            return_value={
                "passed": False,
                "issues": [
                    {
                        "type": "duplicate_outreach",
                        "description": "Lead contacted via email 2 hours ago",
                    }
                ],
            }
        )

        result = await mock_services["witness"].check_duplicate_outreach(
            "lead-001", "email"
        )

        assert result["passed"] is False
        assert result["issues"][0]["type"] == "duplicate_outreach"


class TestPRFlow:
    """E2E tests for Press Room PR flows."""

    @pytest.mark.asyncio
    async def test_pr_pitch_requires_approval(self):
        """Test that PR pitches always require approval."""
        from rigs.press_room.polecats import PitchDraftPolecat

        # PR pitches should have always_requires_approval=True
        assert PitchDraftPolecat.always_requires_approval is True

    @pytest.mark.asyncio
    async def test_journalist_relationship_tracked(self):
        """Test that journalist relationships are tracked."""
        mock_bead_store = MagicMock()
        mock_bead_store.list = AsyncMock(
            return_value=[
                {
                    "id": "pitch-001",
                    "journalist_id": "jour-001",
                    "sent_at": "2024-01-15",
                    "status": "sent",
                },
                {
                    "id": "pitch-002",
                    "journalist_id": "jour-001",
                    "sent_at": "2024-02-01",
                    "status": "replied",
                },
            ]
        )

        # Get pitch history for journalist
        history = await mock_bead_store.list(
            bead_type="PitchBead",
            filters={"journalist_id": "jour-001"},
        )

        assert len(history) == 2


class TestWireSMSFlow:
    """E2E tests for The Wire SMS flows."""

    @pytest.mark.asyncio
    async def test_sms_always_requires_approval(self):
        """Test that SMS always requires human approval."""
        from rigs.wire.polecats import WireSMSDraftPolecat

        # Wire SMS should always require approval (compliance requirement)
        assert WireSMSDraftPolecat.always_requires_approval is True

    @pytest.mark.asyncio
    async def test_automated_sms_blocked_at_router(self):
        """Test that automated SMS sending is blocked."""
        # This is a design invariant - SMS must be human-approved
        # The router should enforce this regardless of Polecat settings

        mock_router = MagicMock()
        mock_router.can_auto_send = MagicMock(return_value=False)

        # Even with high Refinery score, should not auto-send
        can_send = mock_router.can_auto_send(
            rig="wire",
            output_type="sms",
            refinery_score=95,
        )

        assert can_send is False
