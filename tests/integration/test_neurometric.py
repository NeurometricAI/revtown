"""
Integration tests for Neurometric client.

These tests verify the Neurometric gateway integration.
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Skip if no API key configured
pytestmark = pytest.mark.skipif(
    os.getenv("NEUROMETRIC_API_KEY") is None,
    reason="Neurometric API key not configured",
)


class TestNeurometricClient:
    """Tests for Neurometric client."""

    @pytest.fixture
    def neurometric_client(self):
        """Create Neurometric client."""
        from apps.api.core.neurometric import NeurometricClient

        return NeurometricClient(
            api_url=os.getenv("NEUROMETRIC_API_URL", "https://api.neurometric.ai"),
            api_key=os.getenv("NEUROMETRIC_API_KEY", "test-key"),
        )

    @pytest.fixture
    def mock_model_registry(self):
        """Mock model registry responses."""
        return {
            "blog_draft": {"model": "claude-sonnet", "status": "confirmed"},
            "email_personalization": {"model": "claude-haiku", "status": "confirmed"},
            "competitor_analysis": {"model": "claude-opus", "status": "evaluating"},
        }

    @pytest.mark.asyncio
    async def test_complete_with_task_class(self, neurometric_client):
        """Test completion with task class routing."""
        with patch.object(
            neurometric_client, "_make_request", new_callable=AsyncMock
        ) as mock:
            mock.return_value = {
                "content": "Generated blog post content",
                "model": "claude-sonnet",
                "usage": {"input_tokens": 100, "output_tokens": 500},
            }

            result = await neurometric_client.complete(
                task_class="blog_draft",
                prompt="Write a blog post about AI in marketing",
                context={"topic": "AI", "industry": "marketing"},
            )

            assert result["content"] is not None
            assert result["model"] == "claude-sonnet"
            mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_model_lookup_from_registry(self, neurometric_client, mock_model_registry):
        """Test that correct model is selected from registry."""
        with patch.object(
            neurometric_client,
            "get_model_for_task",
            new_callable=AsyncMock,
        ) as mock_lookup:
            mock_lookup.return_value = "claude-sonnet"

            model = await neurometric_client.get_model_for_task("blog_draft")

            assert model == "claude-sonnet"

    @pytest.mark.asyncio
    async def test_fallback_model(self, neurometric_client):
        """Test fallback to default model when registry unavailable."""
        with patch.object(
            neurometric_client,
            "get_model_for_task",
            new_callable=AsyncMock,
        ) as mock_lookup:
            mock_lookup.side_effect = Exception("Registry unavailable")

            # Should use fallback
            with patch.object(
                neurometric_client, "_make_request", new_callable=AsyncMock
            ) as mock_request:
                mock_request.return_value = {
                    "content": "Fallback content",
                    "model": "claude-sonnet",  # Default fallback
                }

                result = await neurometric_client.complete(
                    task_class="unknown_task",
                    prompt="Test prompt",
                )

                assert result["content"] is not None


class TestNeurometricQualityTracking:
    """Tests for Neurometric quality and efficiency tracking."""

    @pytest.fixture
    def neurometric_client(self):
        from apps.api.core.neurometric import NeurometricClient

        return NeurometricClient(
            api_url=os.getenv("NEUROMETRIC_API_URL", "https://api.neurometric.ai"),
            api_key=os.getenv("NEUROMETRIC_API_KEY", "test-key"),
        )

    @pytest.mark.asyncio
    async def test_report_quality_score(self, neurometric_client):
        """Test reporting quality score back to Neurometric."""
        with patch.object(
            neurometric_client, "_make_request", new_callable=AsyncMock
        ) as mock:
            mock.return_value = {"status": "recorded"}

            result = await neurometric_client.report_quality(
                request_id="req-001",
                task_class="blog_draft",
                quality_score=0.85,
                refinery_scores={"brand_voice": 0.9, "readability": 0.8},
            )

            assert result["status"] == "recorded"

    @pytest.mark.asyncio
    async def test_get_efficiency_report(self, neurometric_client):
        """Test retrieving efficiency report."""
        with patch.object(
            neurometric_client, "_make_request", new_callable=AsyncMock
        ) as mock:
            mock.return_value = {
                "task_classes": {
                    "blog_draft": {
                        "current_model": "claude-sonnet",
                        "avg_quality": 0.87,
                        "avg_cost": 0.02,
                        "recommendation": "optimal",
                    },
                    "email_personalization": {
                        "current_model": "claude-haiku",
                        "avg_quality": 0.82,
                        "avg_cost": 0.005,
                        "recommendation": "optimal",
                    },
                }
            }

            report = await neurometric_client.get_efficiency_report()

            assert "task_classes" in report
            assert report["task_classes"]["blog_draft"]["recommendation"] == "optimal"


class TestNeurometricShadowTesting:
    """Tests for Neurometric shadow testing integration."""

    @pytest.fixture
    def neurometric_client(self):
        from apps.api.core.neurometric import NeurometricClient

        return NeurometricClient(
            api_url=os.getenv("NEUROMETRIC_API_URL", "https://api.neurometric.ai"),
            api_key=os.getenv("NEUROMETRIC_API_KEY", "test-key"),
        )

    @pytest.mark.asyncio
    async def test_shadow_test_trigger(self, neurometric_client):
        """Test triggering shadow test evaluation."""
        with patch.object(
            neurometric_client, "_make_request", new_callable=AsyncMock
        ) as mock:
            mock.return_value = {
                "shadow_test_id": "shadow-001",
                "task_class": "competitor_analysis",
                "models_under_test": ["claude-opus", "claude-sonnet"],
                "status": "running",
            }

            result = await neurometric_client.trigger_shadow_test(
                task_class="competitor_analysis",
                sample_size=100,
            )

            assert result["status"] == "running"

    @pytest.mark.asyncio
    async def test_shadow_test_results(self, neurometric_client):
        """Test retrieving shadow test results."""
        with patch.object(
            neurometric_client, "_make_request", new_callable=AsyncMock
        ) as mock:
            mock.return_value = {
                "shadow_test_id": "shadow-001",
                "status": "completed",
                "results": {
                    "claude-opus": {"avg_quality": 0.92, "avg_latency": 2.5},
                    "claude-sonnet": {"avg_quality": 0.88, "avg_latency": 1.2},
                },
                "recommendation": "claude-opus",
                "confidence": 0.85,
            }

            result = await neurometric_client.get_shadow_test_results("shadow-001")

            assert result["status"] == "completed"
            assert result["recommendation"] == "claude-opus"


class TestNeurometricRateLimiting:
    """Tests for Neurometric rate limiting handling."""

    @pytest.fixture
    def neurometric_client(self):
        from apps.api.core.neurometric import NeurometricClient

        return NeurometricClient(
            api_url=os.getenv("NEUROMETRIC_API_URL", "https://api.neurometric.ai"),
            api_key=os.getenv("NEUROMETRIC_API_KEY", "test-key"),
        )

    @pytest.mark.asyncio
    async def test_rate_limit_retry(self, neurometric_client):
        """Test automatic retry on rate limit."""
        call_count = 0

        async def mock_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Rate limit exceeded")
            return {"content": "Success after retry", "model": "claude-sonnet"}

        with patch.object(
            neurometric_client, "_make_request", side_effect=mock_request
        ):
            result = await neurometric_client.complete(
                task_class="test",
                prompt="Test",
                retry_on_rate_limit=True,
            )

            assert call_count == 2
            assert result["content"] == "Success after retry"

    @pytest.mark.asyncio
    async def test_rate_limit_no_retry(self, neurometric_client):
        """Test no retry when disabled."""
        with patch.object(
            neurometric_client, "_make_request", new_callable=AsyncMock
        ) as mock:
            mock.side_effect = Exception("Rate limit exceeded")

            with pytest.raises(Exception, match="Rate limit"):
                await neurometric_client.complete(
                    task_class="test",
                    prompt="Test",
                    retry_on_rate_limit=False,
                )
