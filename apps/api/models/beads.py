"""
Bead Models - Pydantic schemas for all Bead types.

All Beads must have: id, type, campaign_id, created_at, updated_at, status, version
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# =============================================================================
# Common Enums
# =============================================================================


class BeadStatus(str, Enum):
    """Generic status for most Beads."""

    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class CampaignStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class LeadStatus(str, Enum):
    NEW = "new"
    ENRICHING = "enriching"
    ENRICHED = "enriched"
    QUALIFIED = "qualified"
    CONTACTED = "contacted"
    ENGAGED = "engaged"
    CONVERTED = "converted"
    DEAD = "dead"


class AssetType(str, Enum):
    BLOG_POST = "blog_post"
    LANDING_PAGE = "landing_page"
    EMAIL = "email"
    SOCIAL_POST = "social_post"
    PRESS_RELEASE = "press_release"
    CASE_STUDY = "case_study"
    WHITEPAPER = "whitepaper"
    OTHER = "other"


class AssetStatus(str, Enum):
    DRAFT = "draft"
    REFINERY_PENDING = "refinery_pending"
    REFINERY_FAILED = "refinery_failed"
    READY_FOR_APPROVAL = "ready_for_approval"
    APPROVED = "approved"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class TestType(str, Enum):
    EMAIL_SUBJECT = "email_subject"
    EMAIL_BODY = "email_body"
    LANDING_PAGE = "landing_page"
    CTA = "cta"
    SOCIAL_POST = "social_post"
    OTHER = "other"


class TestStatus(str, Enum):
    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    WINNER_PENDING_APPROVAL = "winner_pending_approval"
    WINNER_PROMOTED = "winner_promoted"


class PublicationTier(str, Enum):
    TIER1 = "tier1"
    TIER2 = "tier2"
    TIER3 = "tier3"
    TRADE = "trade"
    BLOG = "blog"


class JournalistStatus(str, Enum):
    ACTIVE = "active"
    COLD = "cold"
    DO_NOT_CONTACT = "do_not_contact"
    ARCHIVED = "archived"


class EvaluationStatus(str, Enum):
    CONFIRMED_OPTIMAL = "confirmed_optimal"
    UNDER_EVALUATION = "under_evaluation"
    DEPRECATED = "deprecated"


class PluginSourceType(str, Enum):
    REGISTRY = "registry"
    GIT = "git"
    LOCAL = "local"


class PluginHealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class PluginStatus(str, Enum):
    ACTIVE = "active"
    DISABLED = "disabled"
    FAILED = "failed"
    ARCHIVED = "archived"


class AlertThreshold(str, Enum):
    ALL = "all"
    HIGH = "high"
    CRITICAL = "critical"


class ContactMethod(str, Enum):
    EMAIL = "email"
    TWITTER_DM = "twitter_dm"
    PHONE = "phone"
    LINKEDIN = "linkedin"


# =============================================================================
# Base Bead Model
# =============================================================================


class BeadBase(BaseModel):
    """Base fields required for all Beads."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    type: str
    campaign_id: UUID | None = None
    created_at: datetime
    updated_at: datetime
    version: int = 1


# =============================================================================
# Campaign Bead
# =============================================================================


class CampaignBeadCreate(BaseModel):
    """Create a new Campaign Bead."""

    name: str = Field(..., max_length=255)
    description: str | None = None
    goal: str | None = None
    budget_cents: int | None = None
    horizon_days: int | None = None
    settings: dict[str, Any] | None = None


class CampaignBeadUpdate(BaseModel):
    """Update a Campaign Bead."""

    name: str | None = Field(None, max_length=255)
    description: str | None = None
    goal: str | None = None
    budget_cents: int | None = None
    horizon_days: int | None = None
    status: CampaignStatus | None = None
    settings: dict[str, Any] | None = None


class CampaignBead(BeadBase):
    """Campaign Bead response model."""

    type: str = "campaign"
    organization_id: UUID
    name: str
    description: str | None = None
    goal: str | None = None
    budget_cents: int | None = None
    horizon_days: int | None = None
    status: CampaignStatus = CampaignStatus.DRAFT
    settings: dict[str, Any] | None = None
    created_by: UUID | None = None


# =============================================================================
# Lead Bead
# =============================================================================


class LeadBeadCreate(BaseModel):
    """Create a new Lead Bead."""

    email: EmailStr | None = None
    phone: str | None = Field(None, max_length=50)
    first_name: str | None = Field(None, max_length=100)
    last_name: str | None = Field(None, max_length=100)
    title: str | None = Field(None, max_length=255)
    company_name: str | None = Field(None, max_length=255)
    company_domain: str | None = Field(None, max_length=255)
    company_size: str | None = Field(None, max_length=50)
    industry: str | None = Field(None, max_length=100)
    linkedin_url: str | None = Field(None, max_length=500)
    twitter_handle: str | None = Field(None, max_length=100)
    source: str | None = Field(None, max_length=100)
    source_id: str | None = Field(None, max_length=255)
    tags: list[str] | None = None
    notes: str | None = None
    campaign_id: UUID | None = None


class LeadBeadUpdate(BaseModel):
    """Update a Lead Bead."""

    email: EmailStr | None = None
    phone: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    title: str | None = None
    company_name: str | None = None
    company_domain: str | None = None
    company_size: str | None = None
    industry: str | None = None
    linkedin_url: str | None = None
    twitter_handle: str | None = None
    enrichment_data: dict[str, Any] | None = None
    lead_score: int | None = None
    icp_match_score: Decimal | None = None
    status: LeadStatus | None = None
    tags: list[str] | None = None
    notes: str | None = None


class LeadBead(BeadBase):
    """Lead Bead response model."""

    type: str = "lead"
    organization_id: UUID
    email: str | None = None
    phone: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    title: str | None = None
    company_name: str | None = None
    company_domain: str | None = None
    company_size: str | None = None
    industry: str | None = None
    linkedin_url: str | None = None
    twitter_handle: str | None = None
    enrichment_data: dict[str, Any] | None = None
    lead_score: int = 0
    icp_match_score: Decimal | None = None
    status: LeadStatus = LeadStatus.NEW
    last_contacted_at: datetime | None = None
    contact_count: int = 0
    source: str | None = None
    source_id: str | None = None
    tags: list[str] | None = None
    notes: str | None = None


# =============================================================================
# Asset Bead
# =============================================================================


class AssetBeadCreate(BaseModel):
    """Create a new Asset Bead."""

    asset_type: AssetType
    title: str | None = Field(None, max_length=500)
    slug: str | None = Field(None, max_length=255)
    content_draft: str | None = None
    meta_title: str | None = Field(None, max_length=255)
    meta_description: str | None = Field(None, max_length=500)
    keywords: list[str] | None = None
    campaign_id: UUID | None = None


class AssetBeadUpdate(BaseModel):
    """Update an Asset Bead."""

    title: str | None = None
    slug: str | None = None
    content_draft: str | None = None
    content_final: str | None = None
    content_html: str | None = None
    meta_title: str | None = None
    meta_description: str | None = None
    keywords: list[str] | None = None
    brand_voice_score: Decimal | None = None
    seo_score: Decimal | None = None
    readability_score: Decimal | None = None
    spam_score: Decimal | None = None
    published_url: str | None = None
    published_at: datetime | None = None
    status: AssetStatus | None = None


class AssetBead(BeadBase):
    """Asset Bead response model."""

    type: str = "asset"
    organization_id: UUID
    asset_type: AssetType
    title: str | None = None
    slug: str | None = None
    content_draft: str | None = None
    content_final: str | None = None
    content_html: str | None = None
    meta_title: str | None = None
    meta_description: str | None = None
    keywords: list[str] | None = None
    brand_voice_score: Decimal | None = None
    seo_score: Decimal | None = None
    readability_score: Decimal | None = None
    spam_score: Decimal | None = None
    published_url: str | None = None
    published_at: datetime | None = None
    status: AssetStatus = AssetStatus.DRAFT


# =============================================================================
# Competitor Bead
# =============================================================================


class CompetitorBeadCreate(BaseModel):
    """Create a new Competitor Bead."""

    name: str = Field(..., max_length=255)
    domain: str | None = Field(None, max_length=255)
    description: str | None = None
    monitor_website: bool = True
    monitor_social: bool = True
    monitor_jobs: bool = True
    monitor_reviews: bool = True
    monitor_pr: bool = True
    alert_threshold: AlertThreshold = AlertThreshold.HIGH
    campaign_id: UUID | None = None


class CompetitorBeadUpdate(BaseModel):
    """Update a Competitor Bead."""

    name: str | None = None
    domain: str | None = None
    description: str | None = None
    monitor_website: bool | None = None
    monitor_social: bool | None = None
    monitor_jobs: bool | None = None
    monitor_reviews: bool | None = None
    monitor_pr: bool | None = None
    latest_changes: dict[str, Any] | None = None
    job_postings: dict[str, Any] | None = None
    social_activity: dict[str, Any] | None = None
    review_summary: dict[str, Any] | None = None
    pr_mentions: dict[str, Any] | None = None
    alert_threshold: AlertThreshold | None = None
    status: BeadStatus | None = None


class CompetitorBead(BeadBase):
    """Competitor Bead response model."""

    type: str = "competitor"
    organization_id: UUID
    name: str
    domain: str | None = None
    description: str | None = None
    monitor_website: bool = True
    monitor_social: bool = True
    monitor_jobs: bool = True
    monitor_reviews: bool = True
    monitor_pr: bool = True
    latest_changes: dict[str, Any] | None = None
    job_postings: dict[str, Any] | None = None
    social_activity: dict[str, Any] | None = None
    review_summary: dict[str, Any] | None = None
    pr_mentions: dict[str, Any] | None = None
    alert_threshold: AlertThreshold = AlertThreshold.HIGH
    last_alert_at: datetime | None = None
    status: BeadStatus = BeadStatus.ACTIVE


# =============================================================================
# Test Bead
# =============================================================================


class TestBeadCreate(BaseModel):
    """Create a new Test Bead."""

    name: str = Field(..., max_length=255)
    test_type: TestType
    hypothesis: str | None = None
    control_asset_id: UUID | None = None
    variant_asset_ids: list[UUID] | None = None
    traffic_split: dict[str, int] | None = None
    min_sample_size: int = 100
    max_duration_days: int = 14
    campaign_id: UUID | None = None


class TestBeadUpdate(BaseModel):
    """Update a Test Bead."""

    name: str | None = None
    hypothesis: str | None = None
    control_asset_id: UUID | None = None
    variant_asset_ids: list[UUID] | None = None
    traffic_split: dict[str, int] | None = None
    metrics: dict[str, Any] | None = None
    winner_variant: str | None = None
    confidence_level: Decimal | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    min_sample_size: int | None = None
    max_duration_days: int | None = None
    status: TestStatus | None = None


class TestBead(BeadBase):
    """Test Bead response model."""

    type: str = "test"
    organization_id: UUID
    name: str
    test_type: TestType
    hypothesis: str | None = None
    control_asset_id: UUID | None = None
    variant_asset_ids: list[UUID] | None = None
    traffic_split: dict[str, int] | None = None
    metrics: dict[str, Any] | None = None
    winner_variant: str | None = None
    confidence_level: Decimal | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    min_sample_size: int = 100
    max_duration_days: int = 14
    status: TestStatus = TestStatus.DRAFT


# =============================================================================
# ICP Bead
# =============================================================================


class ICPBeadCreate(BaseModel):
    """Create a new ICP Bead."""

    name: str = Field(..., max_length=255)
    description: str | None = None
    company_sizes: list[str] | None = None
    industries: list[str] | None = None
    revenue_ranges: list[str] | None = None
    geographies: list[str] | None = None
    job_titles: list[str] | None = None
    departments: list[str] | None = None
    seniority_levels: list[str] | None = None
    technologies: list[str] | None = None
    buying_signals: list[str] | None = None
    pain_points: list[str] | None = None
    scoring_weights: dict[str, float] | None = None
    is_default: bool = False
    campaign_id: UUID | None = None


class ICPBeadUpdate(BaseModel):
    """Update an ICP Bead."""

    name: str | None = None
    description: str | None = None
    company_sizes: list[str] | None = None
    industries: list[str] | None = None
    revenue_ranges: list[str] | None = None
    geographies: list[str] | None = None
    job_titles: list[str] | None = None
    departments: list[str] | None = None
    seniority_levels: list[str] | None = None
    technologies: list[str] | None = None
    buying_signals: list[str] | None = None
    pain_points: list[str] | None = None
    scoring_weights: dict[str, float] | None = None
    is_default: bool | None = None
    status: BeadStatus | None = None


class ICPBead(BeadBase):
    """ICP Bead response model."""

    type: str = "icp"
    organization_id: UUID
    name: str
    description: str | None = None
    company_sizes: list[str] | None = None
    industries: list[str] | None = None
    revenue_ranges: list[str] | None = None
    geographies: list[str] | None = None
    job_titles: list[str] | None = None
    departments: list[str] | None = None
    seniority_levels: list[str] | None = None
    technologies: list[str] | None = None
    buying_signals: list[str] | None = None
    pain_points: list[str] | None = None
    scoring_weights: dict[str, float] | None = None
    is_default: bool = False
    status: BeadStatus = BeadStatus.ACTIVE


# =============================================================================
# Journalist Bead
# =============================================================================


class JournalistBeadCreate(BaseModel):
    """Create a new Journalist Bead."""

    name: str = Field(..., max_length=255)
    email: EmailStr | None = None
    phone: str | None = Field(None, max_length=50)
    publication: str | None = Field(None, max_length=255)
    publication_tier: PublicationTier = PublicationTier.TIER2
    beats: list[str] | None = None
    twitter_handle: str | None = Field(None, max_length=100)
    linkedin_url: str | None = Field(None, max_length=500)
    preferred_contact_method: ContactMethod = ContactMethod.EMAIL
    notes: str | None = None
    campaign_id: UUID | None = None


class JournalistBeadUpdate(BaseModel):
    """Update a Journalist Bead."""

    name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    publication: str | None = None
    publication_tier: PublicationTier | None = None
    beats: list[str] | None = None
    twitter_handle: str | None = None
    linkedin_url: str | None = None
    relationship_score: int | None = None
    last_pitched_at: datetime | None = None
    last_coverage_at: datetime | None = None
    pitch_history: list[dict[str, Any]] | None = None
    coverage_history: list[dict[str, Any]] | None = None
    notes: str | None = None
    preferred_contact_method: ContactMethod | None = None
    do_not_contact: bool | None = None
    embargo_history: list[dict[str, Any]] | None = None
    status: JournalistStatus | None = None


class JournalistBead(BeadBase):
    """Journalist Bead response model."""

    type: str = "journalist"
    organization_id: UUID
    name: str
    email: str | None = None
    phone: str | None = None
    publication: str | None = None
    publication_tier: PublicationTier = PublicationTier.TIER2
    beats: list[str] | None = None
    twitter_handle: str | None = None
    linkedin_url: str | None = None
    relationship_score: int = 0
    last_pitched_at: datetime | None = None
    last_coverage_at: datetime | None = None
    pitch_count: int = 0
    coverage_count: int = 0
    pitch_history: list[dict[str, Any]] | None = None
    coverage_history: list[dict[str, Any]] | None = None
    notes: str | None = None
    preferred_contact_method: ContactMethod = ContactMethod.EMAIL
    do_not_contact: bool = False
    embargo_history: list[dict[str, Any]] | None = None
    status: JournalistStatus = JournalistStatus.ACTIVE


# =============================================================================
# Model Registry Bead
# =============================================================================


class ModelRegistryBeadCreate(BaseModel):
    """Create a new Model Registry Bead."""

    task_class: str = Field(..., max_length=100)
    default_model: str = Field(..., max_length=100)
    fallback_model: str | None = Field(None, max_length=100)
    max_tokens: int | None = None
    temperature: Decimal = Decimal("0.7")


class ModelRegistryBeadUpdate(BaseModel):
    """Update a Model Registry Bead."""

    default_model: str | None = None
    fallback_model: str | None = None
    evaluation_status: EvaluationStatus | None = None
    evaluation_metrics: dict[str, Any] | None = None
    max_tokens: int | None = None
    temperature: Decimal | None = None
    status: BeadStatus | None = None


class ModelRegistryBead(BeadBase):
    """Model Registry Bead response model."""

    type: str = "model_registry"
    organization_id: UUID | None = None
    task_class: str
    default_model: str
    fallback_model: str | None = None
    evaluation_status: EvaluationStatus = EvaluationStatus.UNDER_EVALUATION
    last_evaluated_at: datetime | None = None
    evaluation_metrics: dict[str, Any] | None = None
    max_tokens: int | None = None
    temperature: Decimal = Decimal("0.7")
    status: BeadStatus = BeadStatus.ACTIVE


# =============================================================================
# Plugin Bead
# =============================================================================


class PluginBeadCreate(BaseModel):
    """Create a new Plugin Bead."""

    plugin_name: str = Field(..., max_length=255)
    plugin_version: str = Field(..., max_length=50)
    manifest: dict[str, Any]
    source_type: PluginSourceType
    source_url: str | None = Field(None, max_length=500)
    health_endpoint: str | None = Field(None, max_length=255)
    config: dict[str, Any] | None = None
    required_credentials: list[str] | None = None


class PluginBeadUpdate(BaseModel):
    """Update a Plugin Bead."""

    plugin_version: str | None = None
    manifest: dict[str, Any] | None = None
    health_status: PluginHealthStatus | None = None
    config: dict[str, Any] | None = None
    status: PluginStatus | None = None


class PluginBead(BeadBase):
    """Plugin Bead response model."""

    type: str = "plugin"
    organization_id: UUID
    plugin_name: str
    plugin_version: str
    manifest: dict[str, Any]
    source_type: PluginSourceType
    source_url: str | None = None
    health_endpoint: str | None = None
    last_health_check_at: datetime | None = None
    health_status: PluginHealthStatus = PluginHealthStatus.UNKNOWN
    config: dict[str, Any] | None = None
    required_credentials: list[str] | None = None
    status: PluginStatus = PluginStatus.ACTIVE


# =============================================================================
# Union Types for Generic Bead Handling
# =============================================================================

AnyBead = (
    CampaignBead
    | LeadBead
    | AssetBead
    | CompetitorBead
    | TestBead
    | ICPBead
    | JournalistBead
    | ModelRegistryBead
    | PluginBead
)

BEAD_TYPE_MAP: dict[str, type[BeadBase]] = {
    "campaign": CampaignBead,
    "lead": LeadBead,
    "asset": AssetBead,
    "competitor": CompetitorBead,
    "test": TestBead,
    "icp": ICPBead,
    "journalist": JournalistBead,
    "model_registry": ModelRegistryBead,
    "plugin": PluginBead,
}
