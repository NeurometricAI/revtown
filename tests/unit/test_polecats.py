"""
Unit tests for Polecat base class and implementations.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from polecats.base import BasePolecat, polecat_registry


class TestBasePolecat:
    """Tests for BasePolecat abstract class."""

    @pytest.fixture
    def mock_dependencies(
        self, mock_bead_store, mock_neurometric, mock_refinery, mock_witness
    ):
        """Create mock dependencies for Polecat."""
        return {
            "bead_store": mock_bead_store,
            "neurometric": mock_neurometric,
            "refinery": mock_refinery,
            "witness": mock_witness,
        }

    def test_polecat_requires_task_class(self, mock_dependencies):
        """Test that Polecat requires task_class to be defined."""

        class InvalidPolecat(BasePolecat):
            async def execute(self):
                pass

        with pytest.raises(ValueError, match="task_class"):
            InvalidPolecat(
                bead_id="test-001",
                organization_id="org-001",
                **mock_dependencies,
            )

    def test_polecat_initialization(self, mock_dependencies):
        """Test valid Polecat initialization."""

        class TestPolecat(BasePolecat):
            task_class = "test_task"

            async def execute(self):
                return {"result": "success"}

        polecat = TestPolecat(
            bead_id="test-001",
            organization_id="org-001",
            **mock_dependencies,
        )
        assert polecat.bead_id == "test-001"
        assert polecat.organization_id == "org-001"
        assert polecat.task_class == "test_task"

    @pytest.mark.asyncio
    async def test_polecat_run_calls_execute(self, mock_dependencies):
        """Test that run() calls execute() and passes through gates."""

        class TestPolecat(BasePolecat):
            task_class = "test_task"

            async def execute(self):
                return {"content": "Generated content"}

        polecat = TestPolecat(
            bead_id="test-001",
            organization_id="org-001",
            **mock_dependencies,
        )

        # Mock the bead fetch
        mock_dependencies["bead_store"].get.return_value = {
            "id": "test-001",
            "type": "AssetBead",
            "status": "pending",
        }

        result = await polecat.run()

        # Verify execute was called via run
        assert result is not None
        mock_dependencies["refinery"].check.assert_called_once()
        mock_dependencies["witness"].verify.assert_called_once()

    @pytest.mark.asyncio
    async def test_polecat_fails_refinery(self, mock_dependencies):
        """Test Polecat handling when Refinery fails."""

        class TestPolecat(BasePolecat):
            task_class = "test_task"
            refinery_rules = ["brand_voice", "spam_score"]

            async def execute(self):
                return {"content": "Bad content"}

        mock_dependencies["refinery"].check.return_value = {
            "passed": False,
            "score": 40,
            "checks": {"brand_voice": {"passed": False, "score": 30}},
        }

        polecat = TestPolecat(
            bead_id="test-001",
            organization_id="org-001",
            **mock_dependencies,
        )

        mock_dependencies["bead_store"].get.return_value = {
            "id": "test-001",
            "type": "AssetBead",
            "status": "pending",
        }

        result = await polecat.run()

        # Should still complete but mark for approval
        assert result["requires_approval"] is True

    @pytest.mark.asyncio
    async def test_polecat_fails_witness(self, mock_dependencies):
        """Test Polecat handling when Witness finds issues."""

        class TestPolecat(BasePolecat):
            task_class = "test_task"

            async def execute(self):
                return {"content": "Contradictory content"}

        mock_dependencies["witness"].verify.return_value = {
            "passed": False,
            "issues": [{"type": "contradiction", "description": "Conflicts with previous"}],
        }

        polecat = TestPolecat(
            bead_id="test-001",
            organization_id="org-001",
            **mock_dependencies,
        )

        mock_dependencies["bead_store"].get.return_value = {
            "id": "test-001",
            "type": "AssetBead",
            "status": "pending",
        }

        result = await polecat.run()

        # Should flag for review
        assert result["requires_approval"] is True
        assert len(result["witness_issues"]) > 0

    @pytest.mark.asyncio
    async def test_polecat_neurometric_call(self, mock_dependencies):
        """Test that Polecat uses Neurometric for LLM calls."""

        class TestPolecat(BasePolecat):
            task_class = "blog_draft"

            async def execute(self):
                result = await self.neurometric.complete(
                    task_class=self.task_class,
                    prompt="Write a blog post about AI",
                    context={"topic": "AI"},
                )
                return {"content": result["content"]}

        polecat = TestPolecat(
            bead_id="test-001",
            organization_id="org-001",
            **mock_dependencies,
        )

        mock_dependencies["bead_store"].get.return_value = {
            "id": "test-001",
            "type": "AssetBead",
            "status": "pending",
        }

        await polecat.run()

        # Verify Neurometric was called
        mock_dependencies["neurometric"].complete.assert_called_once()
        call_args = mock_dependencies["neurometric"].complete.call_args
        assert call_args.kwargs["task_class"] == "blog_draft"


class TestPolecatRegistry:
    """Tests for Polecat registration system."""

    def test_polecat_registration(self):
        """Test that Polecats can be registered."""
        from polecats.base import register_polecat

        @register_polecat("test_rig", "test_polecat")
        class TestRegisteredPolecat(BasePolecat):
            task_class = "test_task"

            async def execute(self):
                pass

        # Check registration
        assert "test_rig" in polecat_registry
        assert "test_polecat" in polecat_registry["test_rig"]

    def test_get_polecat_class(self):
        """Test retrieving registered Polecat class."""
        from polecats.base import get_polecat_class, register_polecat

        @register_polecat("lookup_rig", "lookup_polecat")
        class LookupPolecat(BasePolecat):
            task_class = "lookup_task"

            async def execute(self):
                pass

        cls = get_polecat_class("lookup_rig", "lookup_polecat")
        assert cls == LookupPolecat

    def test_get_nonexistent_polecat(self):
        """Test retrieving non-existent Polecat returns None."""
        from polecats.base import get_polecat_class

        cls = get_polecat_class("nonexistent_rig", "nonexistent_polecat")
        assert cls is None


class TestPolecatApprovalRequirements:
    """Tests for Polecat approval requirements."""

    @pytest.fixture
    def mock_dependencies(
        self, mock_bead_store, mock_neurometric, mock_refinery, mock_witness
    ):
        return {
            "bead_store": mock_bead_store,
            "neurometric": mock_neurometric,
            "refinery": mock_refinery,
            "witness": mock_witness,
        }

    @pytest.mark.asyncio
    async def test_always_requires_approval_flag(self, mock_dependencies):
        """Test Polecat with always_requires_approval=True."""

        class PRPitchPolecat(BasePolecat):
            task_class = "pr_pitch"
            always_requires_approval = True

            async def execute(self):
                return {"content": "PR pitch content"}

        polecat = PRPitchPolecat(
            bead_id="test-001",
            organization_id="org-001",
            **mock_dependencies,
        )

        mock_dependencies["bead_store"].get.return_value = {
            "id": "test-001",
            "type": "AssetBead",
            "status": "pending",
        }

        result = await polecat.run()

        # Should always require approval regardless of Refinery score
        assert result["requires_approval"] is True

    @pytest.mark.asyncio
    async def test_configurable_approval_threshold(self, mock_dependencies):
        """Test Polecat with configurable approval threshold."""

        class BlogPolecat(BasePolecat):
            task_class = "blog_draft"
            approval_threshold = 90  # High threshold

            async def execute(self):
                return {"content": "Blog content"}

        mock_dependencies["refinery"].check.return_value = {
            "passed": True,
            "score": 85,  # Below threshold
            "checks": {},
        }

        polecat = BlogPolecat(
            bead_id="test-001",
            organization_id="org-001",
            **mock_dependencies,
        )

        mock_dependencies["bead_store"].get.return_value = {
            "id": "test-001",
            "type": "AssetBead",
            "status": "pending",
        }

        result = await polecat.run()

        # Score below threshold should require approval
        assert result["requires_approval"] is True
