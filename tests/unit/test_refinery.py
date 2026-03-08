"""
Unit tests for Refinery quality gate.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from apps.api.core.refinery import Refinery, RefineryCheck, RefineryResult


class TestRefineryChecks:
    """Tests for individual Refinery checks."""

    @pytest.fixture
    def refinery(self, mock_neurometric):
        """Create Refinery instance with mock dependencies."""
        return Refinery(neurometric=mock_neurometric)

    @pytest.mark.asyncio
    async def test_brand_voice_check_passes(self, refinery, mock_neurometric):
        """Test brand voice check with matching content."""
        mock_neurometric.complete.return_value = {
            "content": '{"score": 85, "issues": []}',
        }

        content = "This is on-brand content that matches our voice guidelines."
        brand_guidelines = "Professional, friendly, and technical."

        result = await refinery.check_brand_voice(content, brand_guidelines)

        assert result.passed is True
        assert result.score >= 70

    @pytest.mark.asyncio
    async def test_brand_voice_check_fails(self, refinery, mock_neurometric):
        """Test brand voice check with off-brand content."""
        mock_neurometric.complete.return_value = {
            "content": '{"score": 45, "issues": ["Too casual", "Missing technical depth"]}',
        }

        content = "Hey bro, check out this cool stuff!"
        brand_guidelines = "Professional, formal, and technical."

        result = await refinery.check_brand_voice(content, brand_guidelines)

        assert result.passed is False
        assert result.score < 70

    @pytest.mark.asyncio
    async def test_spam_score_check(self, refinery):
        """Test spam score detection."""
        # Content with spam indicators
        spammy_content = """
        BUY NOW!!! LIMITED TIME OFFER!!!
        Click here for FREE money!!!
        Act NOW before it's too late!!!
        """

        result = await refinery.check_spam_score(spammy_content)

        assert result.passed is False
        assert "spam" in result.details.get("reason", "").lower()

    @pytest.mark.asyncio
    async def test_spam_score_clean_content(self, refinery):
        """Test spam score with clean content."""
        clean_content = """
        We're excited to announce our new product feature.
        This enhancement will help teams collaborate more effectively.
        Learn more about how it works in our documentation.
        """

        result = await refinery.check_spam_score(clean_content)

        assert result.passed is True

    @pytest.mark.asyncio
    async def test_hallucination_check(self, refinery, mock_neurometric):
        """Test hallucination detection."""
        mock_neurometric.complete.return_value = {
            "content": '{"hallucination_likelihood": 0.2, "flagged_claims": []}',
        }

        content = "Our product has been used by over 1000 companies."
        context = {"verified_facts": ["Product launched in 2023"]}

        result = await refinery.check_hallucination(content, context)

        assert result.passed is True

    @pytest.mark.asyncio
    async def test_hallucination_check_fails(self, refinery, mock_neurometric):
        """Test hallucination detection with unverifiable claims."""
        mock_neurometric.complete.return_value = {
            "content": '{"hallucination_likelihood": 0.8, "flagged_claims": ["Revenue figure not verifiable"]}',
        }

        content = "Our revenue grew 500% last quarter."
        context = {"verified_facts": []}

        result = await refinery.check_hallucination(content, context)

        assert result.passed is False
        assert len(result.details.get("flagged_claims", [])) > 0

    @pytest.mark.asyncio
    async def test_legal_flags_check(self, refinery):
        """Test legal compliance check."""
        # Content with potential legal issues
        problematic_content = """
        This product will definitely cure your illness.
        Guaranteed results or your money back!
        Our competitor's product is dangerous.
        """

        result = await refinery.check_legal_flags(problematic_content)

        assert result.passed is False
        assert len(result.details.get("flags", [])) > 0

    @pytest.mark.asyncio
    async def test_personalization_depth_check(self, refinery):
        """Test email personalization depth."""
        # Well-personalized content
        personalized = """
        Hi John,

        I noticed Acme Corp recently expanded into the European market -
        congratulations on the growth! Given your role as CTO and the
        challenges of scaling infrastructure internationally, I thought
        you might find our solution helpful.

        Based on your recent post about microservices architecture...
        """

        lead_data = {
            "first_name": "John",
            "company": "Acme Corp",
            "title": "CTO",
        }

        result = await refinery.check_personalization_depth(personalized, lead_data)

        assert result.passed is True
        assert result.score >= 70

    @pytest.mark.asyncio
    async def test_personalization_depth_generic(self, refinery):
        """Test personalization check with generic content."""
        generic = """
        Hi there,

        I wanted to reach out about our product. It helps companies
        be more productive. Would you like to learn more?

        Best regards
        """

        lead_data = {
            "first_name": "John",
            "company": "Acme Corp",
            "title": "CTO",
        }

        result = await refinery.check_personalization_depth(generic, lead_data)

        assert result.passed is False
        assert result.score < 70


class TestRefineryAggregation:
    """Tests for Refinery result aggregation."""

    @pytest.fixture
    def refinery(self, mock_neurometric):
        return Refinery(neurometric=mock_neurometric)

    @pytest.mark.asyncio
    async def test_aggregate_all_pass(self, refinery):
        """Test aggregation when all checks pass."""
        checks = [
            RefineryCheck(name="brand_voice", passed=True, score=90, details={}),
            RefineryCheck(name="spam_score", passed=True, score=85, details={}),
            RefineryCheck(name="legal_flags", passed=True, score=100, details={}),
        ]

        result = refinery.aggregate_results(checks)

        assert result.passed is True
        assert result.overall_score > 80

    @pytest.mark.asyncio
    async def test_aggregate_one_fails(self, refinery):
        """Test aggregation when one check fails."""
        checks = [
            RefineryCheck(name="brand_voice", passed=True, score=90, details={}),
            RefineryCheck(name="spam_score", passed=False, score=40, details={}),
            RefineryCheck(name="legal_flags", passed=True, score=100, details={}),
        ]

        result = refinery.aggregate_results(checks)

        assert result.passed is False
        assert "spam_score" in [c.name for c in result.failed_checks]

    @pytest.mark.asyncio
    async def test_aggregate_weighted_scoring(self, refinery):
        """Test that some checks are weighted more heavily."""
        # Legal flags should be weighted highest
        checks = [
            RefineryCheck(name="brand_voice", passed=True, score=100, details={}),
            RefineryCheck(name="legal_flags", passed=False, score=30, details={}),
        ]

        result = refinery.aggregate_results(checks)

        # Legal flag failure should cause overall failure
        assert result.passed is False


class TestRefineryRigSpecific:
    """Tests for rig-specific Refinery checks."""

    @pytest.fixture
    def refinery(self, mock_neurometric):
        return Refinery(neurometric=mock_neurometric)

    @pytest.mark.asyncio
    async def test_seo_grade_check(self, refinery):
        """Test SEO grade for content factory."""
        content = """
        # How to Improve Your Marketing Strategy

        Marketing is essential for business growth. In this guide,
        we'll explore effective marketing strategies that work.

        ## Key Takeaways
        - Focus on your target audience
        - Use data-driven decisions
        - Measure and iterate

        ## Conclusion
        Implementing these strategies will help you succeed.
        """

        keywords = ["marketing", "strategy", "growth"]

        result = await refinery.check_seo_grade(content, keywords)

        assert result.score >= 0
        assert "keyword_density" in result.details

    @pytest.mark.asyncio
    async def test_readability_check(self, refinery):
        """Test Flesch reading ease score."""
        # Simple, readable content
        readable = """
        We make software that helps teams work together.
        It is easy to use. You can start in minutes.
        No training needed. Just sign up and go.
        """

        result = await refinery.check_readability(readable)

        assert result.passed is True
        assert result.details.get("flesch_score", 0) > 60

    @pytest.mark.asyncio
    async def test_ap_style_check(self, refinery):
        """Test AP Style compliance for press room."""
        # AP Style compliant content
        compliant = """
        NEW YORK — The company announced Monday that its
        revenue increased 15 percent in the third quarter.

        CEO Jane Smith said the growth reflects strong demand.
        """

        result = await refinery.check_ap_style(compliant)

        assert result.passed is True

    @pytest.mark.asyncio
    async def test_ap_style_violations(self, refinery):
        """Test AP Style check with violations."""
        # Content with AP Style violations
        non_compliant = """
        On January 1st, 2024, the CEO announced that revenue
        grew by fifteen percent. The company is headquartered
        in the United States of America.
        """

        result = await refinery.check_ap_style(non_compliant)

        # Should flag potential issues
        assert len(result.details.get("suggestions", [])) > 0


class TestRefineryFullPipeline:
    """Tests for full Refinery check pipeline."""

    @pytest.fixture
    def refinery(self, mock_neurometric):
        return Refinery(neurometric=mock_neurometric)

    @pytest.mark.asyncio
    async def test_check_with_rules(self, refinery):
        """Test running specific rules."""
        content = "Test content for checking"
        context = {"brand_guidelines": "Professional tone"}

        result = await refinery.check(
            content=content,
            rules=["brand_voice", "spam_score"],
            context=context,
        )

        assert "passed" in result
        assert "score" in result
        assert "checks" in result

    @pytest.mark.asyncio
    async def test_check_default_rules(self, refinery):
        """Test running with default rules."""
        content = "Default test content"

        result = await refinery.check(content=content)

        # Should run universal checks
        assert "passed" in result
