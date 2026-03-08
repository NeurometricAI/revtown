"""
Shared pytest fixtures for RevTown tests.
"""

import asyncio
import os
from collections.abc import AsyncGenerator, Generator
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

# Set test environment before importing app
os.environ["REVTOWN_MODE"] = "self-hosted"
os.environ["JWT_SECRET_KEY"] = "test-secret-key-for-testing-only"
os.environ["DOLT_HOST"] = "localhost"
os.environ["DOLT_PORT"] = "3306"
os.environ["DOLT_USER"] = "root"
os.environ["DOLT_PASSWORD"] = "testpassword"
os.environ["DOLT_DATABASE"] = "revtown_test"


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_bead_store() -> MagicMock:
    """Create a mock BeadStore for unit tests."""
    store = MagicMock()
    store.get = AsyncMock()
    store.create = AsyncMock()
    store.update = AsyncMock()
    store.delete = AsyncMock()
    store.list = AsyncMock(return_value=[])
    store.get_history = AsyncMock(return_value=[])
    store.revert = AsyncMock()
    return store


@pytest.fixture
def mock_neurometric() -> MagicMock:
    """Create a mock Neurometric client for unit tests."""
    client = MagicMock()
    client.complete = AsyncMock(
        return_value={
            "content": "Generated content from mock",
            "model": "claude-sonnet",
            "usage": {"input_tokens": 100, "output_tokens": 200},
        }
    )
    client.get_model_for_task = AsyncMock(return_value="claude-sonnet")
    return client


@pytest.fixture
def mock_refinery() -> MagicMock:
    """Create a mock Refinery for unit tests."""
    refinery = MagicMock()
    refinery.check = AsyncMock(
        return_value={
            "passed": True,
            "score": 85,
            "checks": {
                "brand_voice": {"passed": True, "score": 90},
                "spam_score": {"passed": True, "score": 80},
            },
        }
    )
    return refinery


@pytest.fixture
def mock_witness() -> MagicMock:
    """Create a mock Witness for unit tests."""
    witness = MagicMock()
    witness.verify = AsyncMock(
        return_value={
            "passed": True,
            "issues": [],
        }
    )
    return witness


@pytest.fixture
def sample_lead_bead() -> dict[str, Any]:
    """Sample LeadBead data for tests."""
    return {
        "id": "lead-001",
        "type": "LeadBead",
        "campaign_id": "campaign-001",
        "status": "active",
        "version": 1,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
        "email": "test@example.com",
        "first_name": "John",
        "last_name": "Doe",
        "company": "Acme Corp",
        "title": "CTO",
        "industry": "Technology",
        "company_size": "100-500",
        "enrichment_data": {},
        "icp_score": 75,
        "engagement_score": 50,
        "last_contacted_at": None,
        "do_not_contact": False,
    }


@pytest.fixture
def sample_asset_bead() -> dict[str, Any]:
    """Sample AssetBead data for tests."""
    return {
        "id": "asset-001",
        "type": "AssetBead",
        "campaign_id": "campaign-001",
        "status": "draft",
        "version": 1,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
        "asset_type": "blog_post",
        "title": "Test Blog Post",
        "content": "This is test content for the blog post.",
        "metadata": {"author": "AI", "keywords": ["test", "blog"]},
        "refinery_score": 85,
        "published_at": None,
        "published_url": None,
    }


@pytest.fixture
def sample_campaign_bead() -> dict[str, Any]:
    """Sample CampaignBead data for tests."""
    return {
        "id": "campaign-001",
        "type": "CampaignBead",
        "campaign_id": "campaign-001",
        "status": "active",
        "version": 1,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
        "name": "Q1 Outbound Campaign",
        "description": "Outbound campaign targeting enterprise accounts",
        "goal": "Generate 50 qualified leads",
        "budget": 10000,
        "start_date": datetime.utcnow().isoformat(),
        "end_date": None,
        "rigs_enabled": ["sdr_hive", "content_factory"],
        "convoy_plan": {},
        "metrics": {},
    }


@pytest.fixture
def auth_headers() -> dict[str, str]:
    """Generate auth headers for API tests."""
    # In self-hosted mode, auth is disabled
    return {"Authorization": "Bearer test-token"}


@pytest.fixture
def api_key_headers() -> dict[str, str]:
    """Generate API key headers for tests."""
    return {"X-API-Key": "test-api-key"}


@pytest.fixture
def organization_id() -> str:
    """Test organization ID."""
    return "org-test-001"


@pytest.fixture
def user_id() -> str:
    """Test user ID."""
    return "user-test-001"
