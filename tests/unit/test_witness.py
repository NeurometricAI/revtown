"""
Unit tests for Witness consistency checker.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from apps.api.core.witness import Witness, WitnessIssue, WitnessResult


class TestWitnessContradictions:
    """Tests for Witness contradiction detection."""

    @pytest.fixture
    def witness(self, mock_neurometric, mock_bead_store):
        """Create Witness instance with mock dependencies."""
        return Witness(neurometric=mock_neurometric, bead_store=mock_bead_store)

    @pytest.mark.asyncio
    async def test_no_contradictions(self, witness, mock_neurometric):
        """Test content with no contradictions."""
        mock_neurometric.complete.return_value = {
            "content": '{"contradictions": [], "confidence": 0.95}',
        }

        content = "Our product helps teams collaborate efficiently."
        history = [
            {"content": "Team collaboration is our focus."},
            {"content": "We prioritize efficient workflows."},
        ]

        result = await witness.check_contradictions(content, history)

        assert result.passed is True
        assert len(result.issues) == 0

    @pytest.mark.asyncio
    async def test_detects_contradictions(self, witness, mock_neurometric):
        """Test detection of contradicting statements."""
        mock_neurometric.complete.return_value = {
            "content": '{"contradictions": [{"previous": "We never store user data", "current": "Our database stores all user information", "severity": "high"}], "confidence": 0.9}',
        }

        content = "Our database stores all user information for analysis."
        history = [
            {"content": "We never store user data. Privacy is our priority."},
        ]

        result = await witness.check_contradictions(content, history)

        assert result.passed is False
        assert len(result.issues) > 0
        assert result.issues[0].issue_type == "contradiction"

    @pytest.mark.asyncio
    async def test_contradiction_severity_levels(self, witness, mock_neurometric):
        """Test that severity affects pass/fail."""
        # Low severity contradiction should pass
        mock_neurometric.complete.return_value = {
            "content": '{"contradictions": [{"previous": "Est. 2020", "current": "Founded in 2019", "severity": "low"}], "confidence": 0.7}',
        }

        content = "Founded in 2019."
        history = [{"content": "Est. 2020."}]

        result = await witness.check_contradictions(content, history)

        # Low severity might still pass with warning
        assert result.issues[0].severity == "low"


class TestWitnessDuplicateOutreach:
    """Tests for Witness duplicate outreach detection."""

    @pytest.fixture
    def witness(self, mock_neurometric, mock_bead_store):
        return Witness(neurometric=mock_neurometric, bead_store=mock_bead_store)

    @pytest.mark.asyncio
    async def test_no_duplicate_outreach(self, witness, mock_bead_store):
        """Test no duplicate when lead hasn't been contacted recently."""
        mock_bead_store.list.return_value = []

        lead_id = "lead-001"
        outreach_type = "email"

        result = await witness.check_duplicate_outreach(lead_id, outreach_type)

        assert result.passed is True

    @pytest.mark.asyncio
    async def test_detects_recent_outreach(self, witness, mock_bead_store):
        """Test detection of recent outreach to same lead."""
        recent_time = datetime.utcnow() - timedelta(hours=12)
        mock_bead_store.list.return_value = [
            {
                "id": "outreach-001",
                "lead_id": "lead-001",
                "outreach_type": "email",
                "sent_at": recent_time.isoformat(),
            }
        ]

        lead_id = "lead-001"
        outreach_type = "email"

        result = await witness.check_duplicate_outreach(lead_id, outreach_type)

        assert result.passed is False
        assert result.issues[0].issue_type == "duplicate_outreach"

    @pytest.mark.asyncio
    async def test_different_outreach_type_allowed(self, witness, mock_bead_store):
        """Test that different outreach types are allowed."""
        recent_time = datetime.utcnow() - timedelta(hours=12)
        mock_bead_store.list.return_value = [
            {
                "id": "outreach-001",
                "lead_id": "lead-001",
                "outreach_type": "email",
                "sent_at": recent_time.isoformat(),
            }
        ]

        lead_id = "lead-001"
        outreach_type = "linkedin"  # Different from email

        result = await witness.check_duplicate_outreach(lead_id, outreach_type)

        # Different channel should be allowed
        assert result.passed is True

    @pytest.mark.asyncio
    async def test_old_outreach_allowed(self, witness, mock_bead_store):
        """Test that old outreach doesn't block new outreach."""
        old_time = datetime.utcnow() - timedelta(days=30)
        mock_bead_store.list.return_value = [
            {
                "id": "outreach-001",
                "lead_id": "lead-001",
                "outreach_type": "email",
                "sent_at": old_time.isoformat(),
            }
        ]

        lead_id = "lead-001"
        outreach_type = "email"

        result = await witness.check_duplicate_outreach(lead_id, outreach_type)

        # 30 days old should be fine
        assert result.passed is True


class TestWitnessCampaignConsistency:
    """Tests for Witness campaign consistency checking."""

    @pytest.fixture
    def witness(self, mock_neurometric, mock_bead_store):
        return Witness(neurometric=mock_neurometric, bead_store=mock_bead_store)

    @pytest.mark.asyncio
    async def test_consistent_messaging(self, witness, mock_neurometric, mock_bead_store):
        """Test consistent messaging across campaign assets."""
        mock_bead_store.list.return_value = [
            {
                "id": "asset-001",
                "type": "AssetBead",
                "content": "Our AI-powered platform helps teams collaborate.",
            },
            {
                "id": "asset-002",
                "type": "AssetBead",
                "content": "Team collaboration made easy with AI.",
            },
        ]

        mock_neurometric.complete.return_value = {
            "content": '{"consistent": true, "issues": []}',
        }

        campaign_id = "campaign-001"
        new_content = "AI-driven collaboration for modern teams."

        result = await witness.check_campaign_consistency(campaign_id, new_content)

        assert result.passed is True

    @pytest.mark.asyncio
    async def test_inconsistent_messaging(self, witness, mock_neurometric, mock_bead_store):
        """Test detection of inconsistent messaging."""
        mock_bead_store.list.return_value = [
            {
                "id": "asset-001",
                "type": "AssetBead",
                "content": "Our product is designed for enterprise companies.",
            },
        ]

        mock_neurometric.complete.return_value = {
            "content": '{"consistent": false, "issues": [{"type": "target_audience_mismatch", "description": "Previous content targets enterprise, new content targets startups"}]}',
        }

        campaign_id = "campaign-001"
        new_content = "Perfect for startups and small businesses!"

        result = await witness.check_campaign_consistency(campaign_id, new_content)

        assert result.passed is False
        assert len(result.issues) > 0


class TestWitnessFullVerification:
    """Tests for full Witness verification pipeline."""

    @pytest.fixture
    def witness(self, mock_neurometric, mock_bead_store):
        return Witness(neurometric=mock_neurometric, bead_store=mock_bead_store)

    @pytest.mark.asyncio
    async def test_verify_content(self, witness, mock_neurometric, mock_bead_store):
        """Test full verification pipeline."""
        mock_bead_store.get_history.return_value = []
        mock_bead_store.list.return_value = []
        mock_neurometric.complete.return_value = {
            "content": '{"contradictions": [], "confidence": 0.95}',
        }

        content = "Test content for verification"
        bead_id = "bead-001"

        result = await witness.verify(content, bead_id=bead_id)

        assert "passed" in result
        assert "issues" in result

    @pytest.mark.asyncio
    async def test_verify_with_history(self, witness, mock_neurometric, mock_bead_store):
        """Test verification with provided history."""
        mock_neurometric.complete.return_value = {
            "content": '{"contradictions": [], "confidence": 0.95}',
        }

        content = "Test content"
        history = [
            {"version": 1, "content": "Previous version"},
            {"version": 2, "content": "Another version"},
        ]

        result = await witness.verify(content, bead_history=history)

        assert result["passed"] is True

    @pytest.mark.asyncio
    async def test_verify_aggregates_issues(self, witness, mock_neurometric, mock_bead_store):
        """Test that verification aggregates all issues."""
        # Setup multiple issues
        mock_neurometric.complete.return_value = {
            "content": '{"contradictions": [{"previous": "X", "current": "Y", "severity": "medium"}]}',
        }

        recent_time = datetime.utcnow() - timedelta(hours=1)
        mock_bead_store.list.return_value = [
            {"lead_id": "lead-001", "outreach_type": "email", "sent_at": recent_time.isoformat()}
        ]

        content = "Test content"
        result = await witness.verify(
            content,
            bead_history=[{"content": "Previous content"}],
            lead_id="lead-001",
            outreach_type="email",
        )

        # Should aggregate issues from multiple checks
        assert result["passed"] is False
        assert len(result["issues"]) > 0


class TestWitnessIssueClassification:
    """Tests for Witness issue classification."""

    def test_issue_creation(self):
        """Test WitnessIssue creation."""
        issue = WitnessIssue(
            issue_type="contradiction",
            severity="high",
            description="Content contradicts previous statement",
            details={"previous": "A", "current": "B"},
        )

        assert issue.issue_type == "contradiction"
        assert issue.severity == "high"

    def test_issue_severity_levels(self):
        """Test valid severity levels."""
        for severity in ["low", "medium", "high", "critical"]:
            issue = WitnessIssue(
                issue_type="test",
                severity=severity,
                description="Test issue",
            )
            assert issue.severity == severity

    def test_result_blocking_determination(self):
        """Test that high/critical issues block approval."""
        result = WitnessResult(
            passed=False,
            issues=[
                WitnessIssue(
                    issue_type="contradiction",
                    severity="critical",
                    description="Critical issue",
                )
            ],
        )

        assert result.requires_review is True
        assert result.blocks_auto_approval is True
