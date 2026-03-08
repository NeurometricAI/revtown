"""
Unit tests for Bead models and validation.
"""

from datetime import datetime

import pytest
from pydantic import ValidationError

from apps.api.models.beads import (
    AssetBead,
    AssetBeadCreate,
    CampaignBead,
    CampaignBeadCreate,
    CompetitorBead,
    ICPBead,
    JournalistBead,
    LeadBead,
    LeadBeadCreate,
    ModelRegistryBead,
    PluginBead,
    TestBead,
)


class TestLeadBead:
    """Tests for LeadBead model."""

    def test_create_valid_lead_bead(self):
        """Test creating a valid LeadBead."""
        lead = LeadBeadCreate(
            campaign_id="campaign-001",
            email="test@example.com",
            first_name="John",
            last_name="Doe",
            company="Acme Corp",
        )
        assert lead.email == "test@example.com"
        assert lead.first_name == "John"
        assert lead.company == "Acme Corp"

    def test_lead_bead_email_validation(self):
        """Test email validation on LeadBead."""
        with pytest.raises(ValidationError):
            LeadBeadCreate(
                campaign_id="campaign-001",
                email="invalid-email",
                first_name="John",
            )

    def test_lead_bead_optional_fields(self):
        """Test LeadBead with optional fields."""
        lead = LeadBeadCreate(
            campaign_id="campaign-001",
            email="test@example.com",
        )
        assert lead.first_name is None
        assert lead.company is None
        assert lead.icp_score is None

    def test_lead_bead_icp_score_bounds(self):
        """Test ICP score must be 0-100."""
        with pytest.raises(ValidationError):
            LeadBeadCreate(
                campaign_id="campaign-001",
                email="test@example.com",
                icp_score=150,
            )

    def test_lead_bead_do_not_contact_flag(self):
        """Test do_not_contact flag defaults to False."""
        lead = LeadBeadCreate(
            campaign_id="campaign-001",
            email="test@example.com",
        )
        assert lead.do_not_contact is False


class TestAssetBead:
    """Tests for AssetBead model."""

    def test_create_valid_asset_bead(self):
        """Test creating a valid AssetBead."""
        asset = AssetBeadCreate(
            campaign_id="campaign-001",
            asset_type="blog_post",
            title="Test Blog Post",
            content="This is the content.",
        )
        assert asset.asset_type == "blog_post"
        assert asset.title == "Test Blog Post"

    def test_asset_bead_valid_types(self):
        """Test valid asset types."""
        valid_types = [
            "blog_post",
            "landing_page",
            "email_template",
            "social_post",
            "pr_pitch",
            "image_brief",
        ]
        for asset_type in valid_types:
            asset = AssetBeadCreate(
                campaign_id="campaign-001",
                asset_type=asset_type,
                title="Test",
            )
            assert asset.asset_type == asset_type

    def test_asset_bead_refinery_score_bounds(self):
        """Test refinery_score must be 0-100."""
        with pytest.raises(ValidationError):
            AssetBeadCreate(
                campaign_id="campaign-001",
                asset_type="blog_post",
                title="Test",
                refinery_score=-5,
            )


class TestCampaignBead:
    """Tests for CampaignBead model."""

    def test_create_valid_campaign_bead(self):
        """Test creating a valid CampaignBead."""
        campaign = CampaignBeadCreate(
            name="Q1 Outbound",
            description="Outbound campaign",
            goal="Generate 50 leads",
        )
        assert campaign.name == "Q1 Outbound"

    def test_campaign_bead_budget_positive(self):
        """Test budget must be positive."""
        with pytest.raises(ValidationError):
            CampaignBeadCreate(
                name="Test",
                budget=-1000,
            )

    def test_campaign_bead_rigs_enabled(self):
        """Test rigs_enabled field."""
        campaign = CampaignBeadCreate(
            name="Test",
            rigs_enabled=["sdr_hive", "content_factory"],
        )
        assert "sdr_hive" in campaign.rigs_enabled
        assert len(campaign.rigs_enabled) == 2


class TestCompetitorBead:
    """Tests for CompetitorBead model."""

    def test_create_competitor_bead(self, sample_campaign_bead):
        """Test creating a CompetitorBead."""
        competitor = CompetitorBead(
            id="comp-001",
            campaign_id="campaign-001",
            status="active",
            version=1,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            company_name="Competitor Inc",
            website="https://competitor.com",
            monitoring_enabled=True,
        )
        assert competitor.company_name == "Competitor Inc"
        assert competitor.monitoring_enabled is True


class TestTestBead:
    """Tests for TestBead model (A/B tests)."""

    def test_create_test_bead(self):
        """Test creating a TestBead."""
        test = TestBead(
            id="test-001",
            campaign_id="campaign-001",
            status="running",
            version=1,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            test_name="Subject Line Test",
            test_type="email_subject",
            variants=["Variant A", "Variant B"],
            min_sample_size=1000,
        )
        assert test.test_name == "Subject Line Test"
        assert len(test.variants) == 2


class TestModelRegistryBead:
    """Tests for ModelRegistryBead."""

    def test_create_model_registry_bead(self):
        """Test creating a ModelRegistryBead."""
        registry = ModelRegistryBead(
            id="reg-001",
            campaign_id="system",
            status="active",
            version=1,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            task_class="blog_draft",
            default_model="claude-sonnet",
            evaluation_status="confirmed",
        )
        assert registry.task_class == "blog_draft"
        assert registry.default_model == "claude-sonnet"


class TestICPBead:
    """Tests for ICPBead."""

    def test_create_icp_bead(self):
        """Test creating an ICPBead."""
        icp = ICPBead(
            id="icp-001",
            campaign_id="campaign-001",
            status="active",
            version=1,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            name="Enterprise Tech",
            criteria={
                "company_size": ["100-500", "500+"],
                "industry": ["Technology", "SaaS"],
                "revenue": ">10M",
            },
            weight_config={
                "company_size": 0.3,
                "industry": 0.4,
                "revenue": 0.3,
            },
        )
        assert icp.name == "Enterprise Tech"
        assert "industry" in icp.criteria


class TestJournalistBead:
    """Tests for JournalistBead."""

    def test_create_journalist_bead(self):
        """Test creating a JournalistBead."""
        journalist = JournalistBead(
            id="jour-001",
            campaign_id="campaign-001",
            status="active",
            version=1,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            name="Jane Smith",
            outlet="TechCrunch",
            beat="Startups",
            email="jane@techcrunch.com",
            relationship_score=75,
            last_pitched_at=None,
        )
        assert journalist.name == "Jane Smith"
        assert journalist.outlet == "TechCrunch"


class TestPluginBead:
    """Tests for PluginBead."""

    def test_create_plugin_bead(self):
        """Test creating a PluginBead."""
        plugin = PluginBead(
            id="plugin-001",
            campaign_id="system",
            status="active",
            version=1,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            plugin_id="g2-monitor",
            name="G2 Monitor",
            manifest_version="1.0.0",
            enabled=True,
            health_status="healthy",
        )
        assert plugin.plugin_id == "g2-monitor"
        assert plugin.enabled is True
