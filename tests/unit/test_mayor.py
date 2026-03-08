"""
Unit tests for GTM Mayor orchestration.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from apps.api.core.mayor import Mayor


class TestMayorCampaignCreation:
    """Tests for Mayor campaign creation."""

    @pytest.fixture
    def mayor(self, mock_bead_store, mock_neurometric):
        """Create Mayor with mock dependencies."""
        return Mayor(
            bead_store=mock_bead_store,
            neurometric=mock_neurometric,
        )

    @pytest.mark.asyncio
    async def test_create_campaign_generates_convoy(self, mayor, mock_neurometric):
        """Test campaign creation generates convoy plan."""
        mock_neurometric.complete.return_value = {
            "content": """{
                "steps": [
                    {"rig": "content_factory", "polecat": "blog_draft", "priority": 1},
                    {"rig": "sdr_hive", "polecat": "scout", "priority": 2}
                ]
            }""",
        }

        campaign = await mayor.create_campaign(
            name="Q1 Outbound",
            goal="Generate 50 leads",
            budget=10000,
            rigs_enabled=["content_factory", "sdr_hive"],
            organization_id="org-001",
        )

        assert "convoy_plan" in campaign
        assert len(campaign["convoy_plan"]["steps"]) == 2

    @pytest.mark.asyncio
    async def test_create_campaign_respects_rig_selection(self, mayor, mock_neurometric):
        """Test convoy only includes enabled rigs."""
        mock_neurometric.complete.return_value = {
            "content": """{
                "steps": [
                    {"rig": "content_factory", "polecat": "blog_draft", "priority": 1}
                ]
            }""",
        }

        campaign = await mayor.create_campaign(
            name="Content Only",
            goal="Create content",
            rigs_enabled=["content_factory"],  # Only content factory
            organization_id="org-001",
        )

        for step in campaign["convoy_plan"]["steps"]:
            assert step["rig"] == "content_factory"


class TestMayorConvoyExecution:
    """Tests for Mayor convoy execution."""

    @pytest.fixture
    def mayor(self, mock_bead_store, mock_neurometric):
        return Mayor(
            bead_store=mock_bead_store,
            neurometric=mock_neurometric,
        )

    @pytest.mark.asyncio
    async def test_execute_convoy_step(self, mayor, mock_bead_store):
        """Test executing a single convoy step."""
        mock_bead_store.create.return_value = {
            "id": "asset-001",
            "type": "AssetBead",
            "status": "pending",
        }

        step = {
            "rig": "content_factory",
            "polecat": "blog_draft",
            "bead_type": "AssetBead",
            "params": {"topic": "AI in Marketing"},
        }

        result = await mayor.execute_convoy_step(step, "org-001")

        assert result is not None
        mock_bead_store.create.assert_called()

    @pytest.mark.asyncio
    async def test_convoy_step_failure_handling(self, mayor, mock_bead_store):
        """Test handling of convoy step failure."""
        mock_bead_store.create.side_effect = Exception("Database error")

        step = {
            "rig": "content_factory",
            "polecat": "blog_draft",
        }

        result = await mayor.execute_convoy_step(step, "org-001")

        assert result["status"] == "failed"
        assert "error" in result


class TestMayorReslating:
    """Tests for Mayor dynamic re-slating."""

    @pytest.fixture
    def mayor(self, mock_bead_store, mock_neurometric):
        return Mayor(
            bead_store=mock_bead_store,
            neurometric=mock_neurometric,
        )

    @pytest.mark.asyncio
    async def test_reslate_based_on_feedback(self, mayor, mock_neurometric):
        """Test re-slating convoy based on feedback."""
        mock_neurometric.complete.return_value = {
            "content": """{
                "action": "adjust",
                "new_steps": [
                    {"rig": "content_factory", "polecat": "seo_meta", "priority": 1}
                ],
                "reason": "Blog posts performing well, add SEO optimization"
            }""",
        }

        feedback = {
            "campaign_id": "campaign-001",
            "metrics": {"blog_engagement": 0.85, "lead_conversion": 0.02},
            "issues": [],
        }

        result = await mayor.reslate_convoy("campaign-001", feedback)

        assert result["action"] == "adjust"
        assert len(result["new_steps"]) > 0

    @pytest.mark.asyncio
    async def test_reslate_pauses_on_budget_exceeded(self, mayor, mock_bead_store):
        """Test convoy pauses when budget exceeded."""
        mock_bead_store.get.return_value = {
            "id": "campaign-001",
            "budget": 1000,
            "spent": 1200,  # Over budget
        }

        feedback = {"campaign_id": "campaign-001", "metrics": {}}

        result = await mayor.reslate_convoy("campaign-001", feedback)

        assert result["action"] == "pause"
        assert "budget" in result["reason"].lower()


class TestMayorResourceAllocation:
    """Tests for Mayor Rig resource allocation."""

    @pytest.fixture
    def mayor(self, mock_bead_store, mock_neurometric):
        return Mayor(
            bead_store=mock_bead_store,
            neurometric=mock_neurometric,
        )

    @pytest.mark.asyncio
    async def test_allocate_rig_resources(self, mayor):
        """Test Rig resource allocation."""
        allocation = await mayor.allocate_resources(
            campaign_id="campaign-001",
            rigs=["content_factory", "sdr_hive"],
            total_budget=10000,
        )

        assert "content_factory" in allocation
        assert "sdr_hive" in allocation
        assert sum(allocation.values()) <= 10000

    @pytest.mark.asyncio
    async def test_allocation_respects_priorities(self, mayor, mock_neurometric):
        """Test allocation respects Rig priorities."""
        mock_neurometric.complete.return_value = {
            "content": """{
                "priorities": {
                    "sdr_hive": 0.6,
                    "content_factory": 0.4
                }
            }""",
        }

        allocation = await mayor.allocate_resources(
            campaign_id="campaign-001",
            rigs=["content_factory", "sdr_hive"],
            total_budget=10000,
            optimize_for="leads",
        )

        # SDR Hive should get more budget when optimizing for leads
        assert allocation["sdr_hive"] >= allocation["content_factory"]
