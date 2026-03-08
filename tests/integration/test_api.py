"""
Integration tests for RevTown API endpoints.
"""

import os
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

# Set test environment
os.environ["REVTOWN_MODE"] = "self-hosted"
os.environ["JWT_SECRET_KEY"] = "test-secret-key"


class TestHealthEndpoints:
    """Tests for health check endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from apps.api.main import app

        return TestClient(app)

    def test_health_check(self, client):
        """Test basic health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_readiness_check(self, client):
        """Test readiness probe."""
        response = client.get("/ready")
        assert response.status_code == 200


class TestBeadEndpoints:
    """Tests for Bead CRUD endpoints."""

    @pytest.fixture
    def client(self):
        from apps.api.main import app

        return TestClient(app)

    @pytest.fixture
    def mock_bead_store(self):
        """Mock BeadStore for API tests."""
        with patch("apps.api.dependencies.get_bead_store") as mock:
            store = MagicMock()
            store.create = AsyncMock()
            store.get = AsyncMock()
            store.update = AsyncMock()
            store.delete = AsyncMock()
            store.list = AsyncMock(return_value=[])
            mock.return_value = store
            yield store

    def test_create_lead_bead(self, client, mock_bead_store, auth_headers):
        """Test creating a LeadBead."""
        mock_bead_store.create.return_value = {
            "id": "lead-001",
            "type": "LeadBead",
            "campaign_id": "campaign-001",
            "email": "test@example.com",
            "status": "active",
            "version": 1,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }

        response = client.post(
            "/api/v1/beads/leads",
            json={
                "campaign_id": "campaign-001",
                "email": "test@example.com",
                "first_name": "John",
                "last_name": "Doe",
            },
            headers=auth_headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["data"]["email"] == "test@example.com"

    def test_get_bead(self, client, mock_bead_store, auth_headers):
        """Test retrieving a Bead by ID."""
        mock_bead_store.get.return_value = {
            "id": "lead-001",
            "type": "LeadBead",
            "email": "test@example.com",
        }

        response = client.get(
            "/api/v1/beads/lead-001",
            headers=auth_headers,
        )

        assert response.status_code == 200
        assert response.json()["data"]["id"] == "lead-001"

    def test_get_bead_not_found(self, client, mock_bead_store, auth_headers):
        """Test 404 when Bead not found."""
        mock_bead_store.get.return_value = None

        response = client.get(
            "/api/v1/beads/nonexistent",
            headers=auth_headers,
        )

        assert response.status_code == 404

    def test_list_beads(self, client, mock_bead_store, auth_headers):
        """Test listing Beads with filters."""
        mock_bead_store.list.return_value = [
            {"id": "lead-001", "type": "LeadBead"},
            {"id": "lead-002", "type": "LeadBead"},
        ]

        response = client.get(
            "/api/v1/beads?type=LeadBead&limit=10",
            headers=auth_headers,
        )

        assert response.status_code == 200
        assert len(response.json()["data"]) == 2

    def test_update_bead(self, client, mock_bead_store, auth_headers):
        """Test updating a Bead."""
        mock_bead_store.get.return_value = {
            "id": "lead-001",
            "type": "LeadBead",
            "email": "test@example.com",
            "version": 1,
        }
        mock_bead_store.update.return_value = {
            "id": "lead-001",
            "type": "LeadBead",
            "email": "updated@example.com",
            "version": 2,
        }

        response = client.patch(
            "/api/v1/beads/lead-001",
            json={"email": "updated@example.com"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        assert response.json()["data"]["version"] == 2

    def test_get_bead_history(self, client, mock_bead_store, auth_headers):
        """Test retrieving Bead history."""
        mock_bead_store.get_history.return_value = [
            {"version": 1, "updated_at": "2024-01-01T00:00:00"},
            {"version": 2, "updated_at": "2024-01-02T00:00:00"},
        ]

        response = client.get(
            "/api/v1/beads/lead-001/history",
            headers=auth_headers,
        )

        assert response.status_code == 200
        assert len(response.json()["data"]) == 2

    def test_revert_bead(self, client, mock_bead_store, auth_headers):
        """Test reverting a Bead to previous version."""
        mock_bead_store.revert.return_value = {
            "id": "lead-001",
            "version": 1,
            "reverted_from": 2,
        }

        response = client.post(
            "/api/v1/beads/lead-001/revert",
            json={"to_version": 1},
            headers=auth_headers,
        )

        assert response.status_code == 200


class TestPolecatEndpoints:
    """Tests for Polecat spawning and management endpoints."""

    @pytest.fixture
    def client(self):
        from apps.api.main import app

        return TestClient(app)

    @pytest.fixture
    def mock_polecat_spawner(self):
        """Mock Polecat spawner."""
        with patch("apps.api.routers.polecats.spawn_polecat") as mock:
            mock.return_value = {
                "polecat_id": "polecat-001",
                "status": "spawned",
                "rig": "content_factory",
                "type": "blog_draft",
            }
            yield mock

    def test_spawn_polecat(self, client, mock_polecat_spawner, auth_headers):
        """Test spawning a Polecat."""
        response = client.post(
            "/api/v1/polecats/spawn",
            json={
                "rig": "content_factory",
                "polecat_type": "blog_draft",
                "bead_id": "asset-001",
            },
            headers=auth_headers,
        )

        assert response.status_code == 202
        data = response.json()
        assert data["data"]["polecat_id"] == "polecat-001"
        assert data["data"]["status"] == "spawned"

    def test_spawn_polecat_invalid_rig(self, client, auth_headers):
        """Test spawning Polecat with invalid rig."""
        response = client.post(
            "/api/v1/polecats/spawn",
            json={
                "rig": "invalid_rig",
                "polecat_type": "blog_draft",
                "bead_id": "asset-001",
            },
            headers=auth_headers,
        )

        assert response.status_code == 400

    def test_get_polecat_status(self, client, auth_headers):
        """Test getting Polecat status."""
        with patch("apps.api.routers.polecats.get_polecat_status") as mock:
            mock.return_value = {
                "polecat_id": "polecat-001",
                "status": "completed",
                "result": {"content": "Generated blog post"},
            }

            response = client.get(
                "/api/v1/polecats/polecat-001/status",
                headers=auth_headers,
            )

            assert response.status_code == 200
            assert response.json()["data"]["status"] == "completed"

    def test_list_polecats(self, client, auth_headers):
        """Test listing active Polecats."""
        with patch("apps.api.routers.polecats.list_polecats") as mock:
            mock.return_value = [
                {"polecat_id": "polecat-001", "status": "running"},
                {"polecat_id": "polecat-002", "status": "completed"},
            ]

            response = client.get(
                "/api/v1/polecats?status=running",
                headers=auth_headers,
            )

            assert response.status_code == 200

    def test_cancel_polecat(self, client, auth_headers):
        """Test cancelling a running Polecat."""
        with patch("apps.api.routers.polecats.cancel_polecat") as mock:
            mock.return_value = {"polecat_id": "polecat-001", "status": "cancelled"}

            response = client.post(
                "/api/v1/polecats/polecat-001/cancel",
                headers=auth_headers,
            )

            assert response.status_code == 200


class TestApprovalEndpoints:
    """Tests for Approval Dashboard endpoints."""

    @pytest.fixture
    def client(self):
        from apps.api.main import app

        return TestClient(app)

    def test_get_approval_queue(self, client, auth_headers):
        """Test getting approval queue."""
        with patch("apps.api.routers.approval.get_approval_queue") as mock:
            mock.return_value = [
                {
                    "id": "approval-001",
                    "bead_id": "asset-001",
                    "status": "pending",
                    "refinery_score": 85,
                },
            ]

            response = client.get(
                "/api/v1/approvals?status=pending",
                headers=auth_headers,
            )

            assert response.status_code == 200

    def test_approve_item(self, client, auth_headers):
        """Test approving an item."""
        with patch("apps.api.routers.approval.process_approval") as mock:
            mock.return_value = {
                "id": "approval-001",
                "status": "approved",
                "approved_by": "user-001",
            }

            response = client.post(
                "/api/v1/approvals/approval-001/approve",
                headers=auth_headers,
            )

            assert response.status_code == 200

    def test_reject_item(self, client, auth_headers):
        """Test rejecting an item."""
        with patch("apps.api.routers.approval.process_approval") as mock:
            mock.return_value = {
                "id": "approval-001",
                "status": "rejected",
                "rejected_by": "user-001",
            }

            response = client.post(
                "/api/v1/approvals/approval-001/reject",
                json={"reason": "Content not aligned with brand voice"},
                headers=auth_headers,
            )

            assert response.status_code == 200

    def test_edit_and_approve(self, client, auth_headers):
        """Test editing content and approving."""
        with patch("apps.api.routers.approval.edit_and_approve") as mock:
            mock.return_value = {
                "id": "approval-001",
                "status": "approved",
                "edited": True,
            }

            response = client.post(
                "/api/v1/approvals/approval-001/edit-approve",
                json={"edited_content": "Updated content here"},
                headers=auth_headers,
            )

            assert response.status_code == 200


class TestCampaignEndpoints:
    """Tests for Campaign management endpoints."""

    @pytest.fixture
    def client(self):
        from apps.api.main import app

        return TestClient(app)

    def test_create_campaign(self, client, auth_headers):
        """Test creating a new campaign."""
        with patch("apps.api.routers.campaigns.create_campaign") as mock:
            mock.return_value = {
                "id": "campaign-001",
                "name": "Q1 Outbound",
                "status": "draft",
            }

            response = client.post(
                "/api/v1/campaigns",
                json={
                    "name": "Q1 Outbound",
                    "goal": "Generate 50 leads",
                    "rigs_enabled": ["sdr_hive", "content_factory"],
                },
                headers=auth_headers,
            )

            assert response.status_code == 201

    def test_get_campaign_convoy(self, client, auth_headers):
        """Test getting campaign convoy status."""
        with patch("apps.api.routers.campaigns.get_convoy") as mock:
            mock.return_value = {
                "campaign_id": "campaign-001",
                "convoy_plan": {"steps": []},
                "status": "active",
            }

            response = client.get(
                "/api/v1/campaigns/campaign-001/convoy",
                headers=auth_headers,
            )

            assert response.status_code == 200


class TestWebhookEndpoints:
    """Tests for Webhook management endpoints."""

    @pytest.fixture
    def client(self):
        from apps.api.main import app

        return TestClient(app)

    def test_register_webhook(self, client, auth_headers):
        """Test registering a new webhook."""
        with patch("apps.api.routers.webhooks.register_webhook") as mock:
            mock.return_value = {
                "id": "webhook-001",
                "url": "https://example.com/webhook",
                "events": ["bead.created", "bead.updated"],
            }

            response = client.post(
                "/api/v1/webhooks",
                json={
                    "url": "https://example.com/webhook",
                    "events": ["bead.created", "bead.updated"],
                },
                headers=auth_headers,
            )

            assert response.status_code == 201

    def test_webhook_signature_validation(self, client):
        """Test webhook signature validation."""
        # This would test incoming webhook signature verification
        pass
