"""
Integration tests for BeadStore with Dolt database.

These tests require a running Dolt instance.
"""

import os
from datetime import datetime

import pytest

# Skip all tests if no database connection
pytestmark = pytest.mark.skipif(
    os.getenv("SKIP_DB_TESTS", "true").lower() == "true",
    reason="Database tests skipped (set SKIP_DB_TESTS=false to run)",
)


class TestBeadStoreConnection:
    """Tests for BeadStore database connection."""

    @pytest.fixture
    async def bead_store(self):
        """Create BeadStore connected to test database."""
        from apps.api.core.bead_store import BeadStore

        store = BeadStore(
            host=os.getenv("DOLT_HOST", "localhost"),
            port=int(os.getenv("DOLT_PORT", "3306")),
            user=os.getenv("DOLT_USER", "root"),
            password=os.getenv("DOLT_PASSWORD", ""),
            database=os.getenv("DOLT_DATABASE", "revtown_test"),
        )
        await store.connect()
        yield store
        await store.disconnect()

    @pytest.mark.asyncio
    async def test_connection(self, bead_store):
        """Test database connection is established."""
        assert bead_store.is_connected is True

    @pytest.mark.asyncio
    async def test_health_check(self, bead_store):
        """Test database health check."""
        health = await bead_store.health_check()
        assert health["status"] == "healthy"


class TestBeadStoreCRUD:
    """Tests for BeadStore CRUD operations."""

    @pytest.fixture
    async def bead_store(self):
        """Create BeadStore connected to test database."""
        from apps.api.core.bead_store import BeadStore

        store = BeadStore(
            host=os.getenv("DOLT_HOST", "localhost"),
            port=int(os.getenv("DOLT_PORT", "3306")),
            user=os.getenv("DOLT_USER", "root"),
            password=os.getenv("DOLT_PASSWORD", ""),
            database=os.getenv("DOLT_DATABASE", "revtown_test"),
        )
        await store.connect()
        yield store
        # Cleanup after tests
        await store.cleanup_test_data()
        await store.disconnect()

    @pytest.mark.asyncio
    async def test_create_lead_bead(self, bead_store):
        """Test creating a LeadBead in Dolt."""
        lead_data = {
            "type": "LeadBead",
            "campaign_id": "test-campaign-001",
            "email": "test@example.com",
            "first_name": "Test",
            "last_name": "User",
            "company": "Test Corp",
        }

        result = await bead_store.create("LeadBead", lead_data)

        assert result["id"] is not None
        assert result["email"] == "test@example.com"
        assert result["version"] == 1

    @pytest.mark.asyncio
    async def test_get_bead(self, bead_store):
        """Test retrieving a Bead by ID."""
        # First create a bead
        lead_data = {
            "type": "LeadBead",
            "campaign_id": "test-campaign-001",
            "email": "get-test@example.com",
        }
        created = await bead_store.create("LeadBead", lead_data)

        # Then retrieve it
        result = await bead_store.get(created["id"])

        assert result is not None
        assert result["id"] == created["id"]
        assert result["email"] == "get-test@example.com"

    @pytest.mark.asyncio
    async def test_get_nonexistent_bead(self, bead_store):
        """Test retrieving non-existent Bead returns None."""
        result = await bead_store.get("nonexistent-id-12345")
        assert result is None

    @pytest.mark.asyncio
    async def test_update_bead(self, bead_store):
        """Test updating a Bead creates new version."""
        # Create bead
        lead_data = {
            "type": "LeadBead",
            "campaign_id": "test-campaign-001",
            "email": "update-test@example.com",
        }
        created = await bead_store.create("LeadBead", lead_data)

        # Update bead
        updated = await bead_store.update(
            created["id"],
            {"email": "updated@example.com", "first_name": "Updated"},
        )

        assert updated["version"] == 2
        assert updated["email"] == "updated@example.com"
        assert updated["first_name"] == "Updated"

    @pytest.mark.asyncio
    async def test_list_beads_by_type(self, bead_store):
        """Test listing Beads by type."""
        # Create multiple beads
        for i in range(3):
            await bead_store.create(
                "LeadBead",
                {
                    "type": "LeadBead",
                    "campaign_id": "test-campaign-001",
                    "email": f"list-test-{i}@example.com",
                },
            )

        results = await bead_store.list(bead_type="LeadBead", limit=10)

        assert len(results) >= 3

    @pytest.mark.asyncio
    async def test_list_beads_by_campaign(self, bead_store):
        """Test listing Beads by campaign ID."""
        campaign_id = "filter-test-campaign"

        # Create beads for specific campaign
        for i in range(2):
            await bead_store.create(
                "LeadBead",
                {
                    "type": "LeadBead",
                    "campaign_id": campaign_id,
                    "email": f"campaign-test-{i}@example.com",
                },
            )

        results = await bead_store.list(campaign_id=campaign_id)

        assert len(results) == 2
        for bead in results:
            assert bead["campaign_id"] == campaign_id

    @pytest.mark.asyncio
    async def test_soft_delete_bead(self, bead_store):
        """Test soft deleting a Bead (archive)."""
        lead_data = {
            "type": "LeadBead",
            "campaign_id": "test-campaign-001",
            "email": "delete-test@example.com",
        }
        created = await bead_store.create("LeadBead", lead_data)

        # Soft delete
        await bead_store.delete(created["id"])

        # Should still exist but be archived
        result = await bead_store.get(created["id"], include_archived=True)
        assert result is not None
        assert result["status"] == "archived"

        # Should not appear in normal list
        visible = await bead_store.get(created["id"])
        assert visible is None


class TestBeadStoreVersioning:
    """Tests for BeadStore versioning with Dolt."""

    @pytest.fixture
    async def bead_store(self):
        """Create BeadStore connected to test database."""
        from apps.api.core.bead_store import BeadStore

        store = BeadStore(
            host=os.getenv("DOLT_HOST", "localhost"),
            port=int(os.getenv("DOLT_PORT", "3306")),
            user=os.getenv("DOLT_USER", "root"),
            password=os.getenv("DOLT_PASSWORD", ""),
            database=os.getenv("DOLT_DATABASE", "revtown_test"),
        )
        await store.connect()
        yield store
        await store.cleanup_test_data()
        await store.disconnect()

    @pytest.mark.asyncio
    async def test_get_bead_history(self, bead_store):
        """Test retrieving Bead version history."""
        # Create and update bead multiple times
        lead_data = {
            "type": "LeadBead",
            "campaign_id": "test-campaign-001",
            "email": "history-test@example.com",
        }
        created = await bead_store.create("LeadBead", lead_data)

        await bead_store.update(created["id"], {"first_name": "Version2"})
        await bead_store.update(created["id"], {"first_name": "Version3"})

        history = await bead_store.get_history(created["id"])

        assert len(history) == 3
        assert history[0]["version"] == 1
        assert history[2]["version"] == 3

    @pytest.mark.asyncio
    async def test_revert_bead(self, bead_store):
        """Test reverting Bead to previous version."""
        lead_data = {
            "type": "LeadBead",
            "campaign_id": "test-campaign-001",
            "email": "revert-test@example.com",
            "first_name": "Original",
        }
        created = await bead_store.create("LeadBead", lead_data)

        # Update
        await bead_store.update(created["id"], {"first_name": "Changed"})

        # Verify change
        updated = await bead_store.get(created["id"])
        assert updated["first_name"] == "Changed"

        # Revert to version 1
        reverted = await bead_store.revert(created["id"], to_version=1)

        assert reverted["first_name"] == "Original"
        assert reverted["version"] == 3  # New version created for revert

    @pytest.mark.asyncio
    async def test_diff_versions(self, bead_store):
        """Test getting diff between Bead versions."""
        lead_data = {
            "type": "LeadBead",
            "campaign_id": "test-campaign-001",
            "email": "diff-test@example.com",
            "first_name": "Before",
        }
        created = await bead_store.create("LeadBead", lead_data)
        await bead_store.update(created["id"], {"first_name": "After"})

        diff = await bead_store.diff(created["id"], from_version=1, to_version=2)

        assert "first_name" in diff["changes"]
        assert diff["changes"]["first_name"]["from"] == "Before"
        assert diff["changes"]["first_name"]["to"] == "After"


class TestBeadStoreOrganizationScoping:
    """Tests for organization-scoped data isolation."""

    @pytest.fixture
    async def bead_store(self):
        """Create BeadStore connected to test database."""
        from apps.api.core.bead_store import BeadStore

        store = BeadStore(
            host=os.getenv("DOLT_HOST", "localhost"),
            port=int(os.getenv("DOLT_PORT", "3306")),
            user=os.getenv("DOLT_USER", "root"),
            password=os.getenv("DOLT_PASSWORD", ""),
            database=os.getenv("DOLT_DATABASE", "revtown_test"),
        )
        await store.connect()
        yield store
        await store.cleanup_test_data()
        await store.disconnect()

    @pytest.mark.asyncio
    async def test_organization_isolation(self, bead_store):
        """Test that organizations cannot access each other's data."""
        # Create beads for org1
        bead_store.set_organization("org-001")
        org1_bead = await bead_store.create(
            "LeadBead",
            {
                "type": "LeadBead",
                "campaign_id": "campaign-001",
                "email": "org1@example.com",
            },
        )

        # Create beads for org2
        bead_store.set_organization("org-002")
        org2_bead = await bead_store.create(
            "LeadBead",
            {
                "type": "LeadBead",
                "campaign_id": "campaign-002",
                "email": "org2@example.com",
            },
        )

        # Org2 should not see org1's beads
        org2_beads = await bead_store.list()
        org2_ids = [b["id"] for b in org2_beads]

        assert org1_bead["id"] not in org2_ids
        assert org2_bead["id"] in org2_ids

    @pytest.mark.asyncio
    async def test_cannot_access_other_org_bead(self, bead_store):
        """Test that direct access to other org's bead fails."""
        # Create bead for org1
        bead_store.set_organization("org-001")
        org1_bead = await bead_store.create(
            "LeadBead",
            {
                "type": "LeadBead",
                "campaign_id": "campaign-001",
                "email": "isolated@example.com",
            },
        )

        # Switch to org2 and try to access
        bead_store.set_organization("org-002")
        result = await bead_store.get(org1_bead["id"])

        # Should not be accessible
        assert result is None
