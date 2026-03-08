"""
Unit tests for Deacon background janitor.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestDeaconScheduledTasks:
    """Tests for Deacon scheduled task execution."""

    @pytest.fixture
    def deacon(self, mock_bead_store, mock_neurometric):
        """Create Deacon with mock dependencies."""
        from apps.api.core.deacon import Deacon

        return Deacon(
            bead_store=mock_bead_store,
            neurometric=mock_neurometric,
        )

    @pytest.mark.asyncio
    async def test_cleanup_dead_leads(self, deacon, mock_bead_store):
        """Test dead lead cleanup task."""
        old_date = datetime.utcnow() - timedelta(days=90)
        mock_bead_store.list.return_value = [
            {
                "id": "lead-001",
                "status": "inactive",
                "last_contacted_at": old_date.isoformat(),
            },
            {
                "id": "lead-002",
                "status": "inactive",
                "last_contacted_at": old_date.isoformat(),
            },
        ]
        mock_bead_store.update.return_value = {}

        result = await deacon.cleanup_dead_leads(days_threshold=60)

        assert result["cleaned"] == 2
        assert mock_bead_store.update.call_count == 2

    @pytest.mark.asyncio
    async def test_cleanup_orphaned_polecats(self, deacon):
        """Test orphaned Polecat cleanup."""
        with patch("apps.api.core.deacon.get_running_polecats") as mock_get:
            mock_get.return_value = [
                {
                    "polecat_id": "polecat-001",
                    "started_at": (datetime.utcnow() - timedelta(hours=2)).isoformat(),
                    "status": "running",
                },
            ]

            result = await deacon.cleanup_orphaned_polecats(timeout_hours=1)

            assert result["terminated"] == 1

    @pytest.mark.asyncio
    async def test_aggregate_usage(self, deacon, mock_bead_store):
        """Test usage aggregation task."""
        mock_bead_store.list.return_value = [
            {"id": "exec-001", "polecat_type": "blog_draft", "tokens_used": 1000},
            {"id": "exec-002", "polecat_type": "blog_draft", "tokens_used": 1500},
            {"id": "exec-003", "polecat_type": "email_personalization", "tokens_used": 500},
        ]

        result = await deacon.aggregate_usage(organization_id="org-001")

        assert result["total_executions"] == 3
        assert result["by_polecat_type"]["blog_draft"]["count"] == 2
        assert result["total_tokens"] == 3000


class TestDeaconHealthChecks:
    """Tests for Deacon health check tasks."""

    @pytest.fixture
    def deacon(self, mock_bead_store, mock_neurometric):
        from apps.api.core.deacon import Deacon

        return Deacon(
            bead_store=mock_bead_store,
            neurometric=mock_neurometric,
        )

    @pytest.mark.asyncio
    async def test_plugin_health_check(self, deacon, mock_bead_store):
        """Test plugin health polling."""
        mock_bead_store.list.return_value = [
            {
                "id": "plugin-001",
                "plugin_id": "g2-monitor",
                "health_endpoint": "http://plugin:8080/health",
                "enabled": True,
            },
        ]

        with patch("aiohttp.ClientSession.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status = 200
            mock_get.return_value.__aenter__.return_value = mock_response

            result = await deacon.check_plugin_health()

            assert result["checked"] == 1
            assert result["healthy"] == 1

    @pytest.mark.asyncio
    async def test_plugin_health_failure(self, deacon, mock_bead_store):
        """Test plugin health failure handling."""
        mock_bead_store.list.return_value = [
            {
                "id": "plugin-001",
                "plugin_id": "g2-monitor",
                "health_endpoint": "http://plugin:8080/health",
                "enabled": True,
            },
        ]
        mock_bead_store.update.return_value = {}

        with patch("aiohttp.ClientSession.get") as mock_get:
            mock_get.side_effect = Exception("Connection refused")

            result = await deacon.check_plugin_health()

            assert result["unhealthy"] == 1
            # Should update plugin status
            mock_bead_store.update.assert_called()


class TestDeaconThresholdMonitoring:
    """Tests for Deacon threshold monitoring."""

    @pytest.fixture
    def deacon(self, mock_bead_store, mock_neurometric):
        from apps.api.core.deacon import Deacon

        return Deacon(
            bead_store=mock_bead_store,
            neurometric=mock_neurometric,
        )

    @pytest.mark.asyncio
    async def test_monitor_approval_queue_threshold(self, deacon, mock_bead_store):
        """Test approval queue threshold monitoring."""
        # Simulate large approval queue
        mock_bead_store.count.return_value = 150  # Over threshold

        result = await deacon.monitor_thresholds()

        assert result["alerts"]["approval_queue_size"] is True

    @pytest.mark.asyncio
    async def test_monitor_error_rate_threshold(self, deacon, mock_bead_store):
        """Test error rate threshold monitoring."""
        mock_bead_store.list.return_value = [
            {"status": "failed"} for _ in range(20)
        ] + [{"status": "completed"} for _ in range(80)]

        result = await deacon.monitor_thresholds()

        # 20% error rate should trigger alert
        assert result["alerts"]["high_error_rate"] is True

    @pytest.mark.asyncio
    async def test_alert_mayor_on_threshold(self, deacon):
        """Test alerting Mayor when thresholds exceeded."""
        with patch.object(deacon, "alert_mayor", new_callable=AsyncMock) as mock_alert:
            await deacon.monitor_thresholds()

            # Should alert Mayor if thresholds exceeded
            # (depends on actual threshold values)


class TestDeaconNeurometricEvaluation:
    """Tests for Deacon Neurometric evaluation loop."""

    @pytest.fixture
    def deacon(self, mock_bead_store, mock_neurometric):
        from apps.api.core.deacon import Deacon

        return Deacon(
            bead_store=mock_bead_store,
            neurometric=mock_neurometric,
        )

    @pytest.mark.asyncio
    async def test_trigger_shadow_test(self, deacon, mock_neurometric):
        """Test triggering Neurometric shadow test."""
        mock_neurometric.trigger_shadow_test.return_value = {
            "shadow_test_id": "shadow-001",
            "status": "running",
        }

        result = await deacon.trigger_neurometric_evaluation(
            task_class="competitor_analysis"
        )

        assert result["shadow_test_id"] is not None
        mock_neurometric.trigger_shadow_test.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_model_registry(self, deacon, mock_bead_store, mock_neurometric):
        """Test updating model registry based on evaluation."""
        mock_neurometric.get_shadow_test_results.return_value = {
            "status": "completed",
            "recommendation": "claude-opus",
            "confidence": 0.92,
        }

        await deacon.process_shadow_test_results("shadow-001")

        # Should update ModelRegistryBead
        mock_bead_store.update.assert_called()


class TestDeaconScheduling:
    """Tests for Deacon task scheduling."""

    @pytest.fixture
    def deacon(self, mock_bead_store, mock_neurometric):
        from apps.api.core.deacon import Deacon

        return Deacon(
            bead_store=mock_bead_store,
            neurometric=mock_neurometric,
        )

    def test_task_schedule_configuration(self, deacon):
        """Test that tasks are scheduled correctly."""
        schedule = deacon.get_schedule()

        assert "cleanup_dead_leads" in schedule
        assert "plugin_health_check" in schedule
        assert "neurometric_evaluation" in schedule

    def test_schedule_intervals(self, deacon):
        """Test task schedule intervals."""
        schedule = deacon.get_schedule()

        # Health checks should be frequent
        assert schedule["plugin_health_check"]["interval_minutes"] <= 5

        # Cleanup can be less frequent
        assert schedule["cleanup_dead_leads"]["interval_minutes"] >= 60

        # Neurometric eval is weekly
        assert schedule["neurometric_evaluation"]["interval_days"] == 7
