-- RevTown Database Schema
-- All Bead types are defined here for Dolt (git-versioned MySQL-compatible DB)

-- Create and use the revtown database
CREATE DATABASE IF NOT EXISTS revtown;
USE revtown;

-- =============================================================================
-- Core Tables (SaaS Platform)
-- =============================================================================

-- Organizations
CREATE TABLE IF NOT EXISTS organizations (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) NOT NULL UNIQUE,
    plan_tier ENUM('free', 'pro', 'scale', 'enterprise') NOT NULL DEFAULT 'free',
    stripe_customer_id VARCHAR(255),
    stripe_subscription_id VARCHAR(255),
    settings JSON,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_org_slug (slug),
    INDEX idx_org_stripe (stripe_customer_id)
);

-- Users
CREATE TABLE IF NOT EXISTS users (
    id VARCHAR(36) PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    name VARCHAR(255),
    email_verified BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_user_email (email)
);

-- Organization Members (User-to-Org mapping)
CREATE TABLE IF NOT EXISTS org_members (
    id VARCHAR(36) PRIMARY KEY,
    organization_id VARCHAR(36) NOT NULL,
    user_id VARCHAR(36) NOT NULL,
    role ENUM('owner', 'admin', 'member') NOT NULL DEFAULT 'member',
    invited_by VARCHAR(36),
    joined_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE KEY unique_org_user (organization_id, user_id),
    INDEX idx_member_org (organization_id),
    INDEX idx_member_user (user_id)
);

-- API Keys
CREATE TABLE IF NOT EXISTS api_keys (
    id VARCHAR(36) PRIMARY KEY,
    organization_id VARCHAR(36) NOT NULL,
    key_hash VARCHAR(255) NOT NULL,
    key_prefix VARCHAR(20) NOT NULL,
    name VARCHAR(255) NOT NULL,
    scopes JSON,
    last_used_at TIMESTAMP,
    expires_at TIMESTAMP,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_by VARCHAR(36) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
    FOREIGN KEY (created_by) REFERENCES users(id),
    INDEX idx_apikey_org (organization_id),
    INDEX idx_apikey_prefix (key_prefix)
);

-- =============================================================================
-- Bead Base Table (Common fields for all Beads)
-- =============================================================================

-- Note: In Dolt, we create separate tables per Bead type for better schema control
-- Each table includes the required base fields: id, type, campaign_id, created_at, updated_at, status, version

-- =============================================================================
-- CampaignBead - Campaign configuration and state
-- =============================================================================
CREATE TABLE IF NOT EXISTS campaign_beads (
    id VARCHAR(36) PRIMARY KEY,
    type VARCHAR(50) NOT NULL DEFAULT 'campaign',
    organization_id VARCHAR(36) NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    goal TEXT,
    budget_cents INT,
    horizon_days INT,
    status ENUM('draft', 'active', 'paused', 'completed', 'archived') NOT NULL DEFAULT 'draft',
    settings JSON,
    version INT NOT NULL DEFAULT 1,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    created_by VARCHAR(36),
    FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
    INDEX idx_campaign_org (organization_id),
    INDEX idx_campaign_status (status)
);

-- =============================================================================
-- LeadBead - Lead/prospect data with enrichment
-- =============================================================================
CREATE TABLE IF NOT EXISTS lead_beads (
    id VARCHAR(36) PRIMARY KEY,
    type VARCHAR(50) NOT NULL DEFAULT 'lead',
    organization_id VARCHAR(36) NOT NULL,
    campaign_id VARCHAR(36),

    -- Contact info
    email VARCHAR(255),
    phone VARCHAR(50),
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    title VARCHAR(255),

    -- Company info
    company_name VARCHAR(255),
    company_domain VARCHAR(255),
    company_size VARCHAR(50),
    industry VARCHAR(100),

    -- Enrichment data
    linkedin_url VARCHAR(500),
    twitter_handle VARCHAR(100),
    enrichment_data JSON,

    -- Lead scoring
    lead_score INT DEFAULT 0,
    icp_match_score DECIMAL(5,2),

    -- Status tracking
    status ENUM('new', 'enriching', 'enriched', 'qualified', 'contacted', 'engaged', 'converted', 'dead') NOT NULL DEFAULT 'new',
    last_contacted_at TIMESTAMP,
    contact_count INT DEFAULT 0,

    -- Metadata
    source VARCHAR(100),
    source_id VARCHAR(255),
    tags JSON,
    notes TEXT,

    version INT NOT NULL DEFAULT 1,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
    FOREIGN KEY (campaign_id) REFERENCES campaign_beads(id) ON DELETE SET NULL,
    INDEX idx_lead_org (organization_id),
    INDEX idx_lead_campaign (campaign_id),
    INDEX idx_lead_status (status),
    INDEX idx_lead_email (email),
    INDEX idx_lead_company (company_domain)
);

-- =============================================================================
-- AssetBead - Content assets (blog posts, landing pages, emails, etc.)
-- =============================================================================
CREATE TABLE IF NOT EXISTS asset_beads (
    id VARCHAR(36) PRIMARY KEY,
    type VARCHAR(50) NOT NULL DEFAULT 'asset',
    organization_id VARCHAR(36) NOT NULL,
    campaign_id VARCHAR(36),

    -- Asset identification
    asset_type ENUM('blog_post', 'landing_page', 'email', 'social_post', 'press_release', 'case_study', 'whitepaper', 'other') NOT NULL,
    title VARCHAR(500),
    slug VARCHAR(255),

    -- Content
    content_draft TEXT,
    content_final TEXT,
    content_html TEXT,

    -- SEO metadata
    meta_title VARCHAR(255),
    meta_description VARCHAR(500),
    keywords JSON,

    -- Quality scores (from Refinery)
    brand_voice_score DECIMAL(5,2),
    seo_score DECIMAL(5,2),
    readability_score DECIMAL(5,2),
    spam_score DECIMAL(5,2),

    -- Publishing
    published_url VARCHAR(500),
    published_at TIMESTAMP,

    -- Status
    status ENUM('draft', 'refinery_pending', 'refinery_failed', 'ready_for_approval', 'approved', 'published', 'archived') NOT NULL DEFAULT 'draft',

    version INT NOT NULL DEFAULT 1,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
    FOREIGN KEY (campaign_id) REFERENCES campaign_beads(id) ON DELETE SET NULL,
    INDEX idx_asset_org (organization_id),
    INDEX idx_asset_campaign (campaign_id),
    INDEX idx_asset_type (asset_type),
    INDEX idx_asset_status (status)
);

-- =============================================================================
-- CompetitorBead - Competitor intelligence data
-- =============================================================================
CREATE TABLE IF NOT EXISTS competitor_beads (
    id VARCHAR(36) PRIMARY KEY,
    type VARCHAR(50) NOT NULL DEFAULT 'competitor',
    organization_id VARCHAR(36) NOT NULL,
    campaign_id VARCHAR(36),

    -- Competitor info
    name VARCHAR(255) NOT NULL,
    domain VARCHAR(255),
    description TEXT,

    -- Monitoring config
    monitor_website BOOLEAN DEFAULT TRUE,
    monitor_social BOOLEAN DEFAULT TRUE,
    monitor_jobs BOOLEAN DEFAULT TRUE,
    monitor_reviews BOOLEAN DEFAULT TRUE,
    monitor_pr BOOLEAN DEFAULT TRUE,

    -- Latest intelligence
    latest_changes JSON,
    job_postings JSON,
    social_activity JSON,
    review_summary JSON,
    pr_mentions JSON,

    -- Alerts
    alert_threshold ENUM('all', 'high', 'critical') DEFAULT 'high',
    last_alert_at TIMESTAMP,

    status ENUM('active', 'paused', 'archived') NOT NULL DEFAULT 'active',
    version INT NOT NULL DEFAULT 1,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
    FOREIGN KEY (campaign_id) REFERENCES campaign_beads(id) ON DELETE SET NULL,
    INDEX idx_competitor_org (organization_id),
    INDEX idx_competitor_domain (domain)
);

-- =============================================================================
-- TestBead - A/B test configuration and results
-- =============================================================================
CREATE TABLE IF NOT EXISTS test_beads (
    id VARCHAR(36) PRIMARY KEY,
    type VARCHAR(50) NOT NULL DEFAULT 'test',
    organization_id VARCHAR(36) NOT NULL,
    campaign_id VARCHAR(36),

    -- Test config
    name VARCHAR(255) NOT NULL,
    test_type ENUM('email_subject', 'email_body', 'landing_page', 'cta', 'social_post', 'other') NOT NULL,
    hypothesis TEXT,

    -- Variants
    control_asset_id VARCHAR(36),
    variant_asset_ids JSON,  -- Array of asset bead IDs

    -- Traffic allocation
    traffic_split JSON,  -- {"control": 50, "variant_a": 25, "variant_b": 25}

    -- Results
    metrics JSON,  -- {"control": {"views": 100, "conversions": 10}, ...}
    winner_variant VARCHAR(50),
    confidence_level DECIMAL(5,4),

    -- Timing
    started_at TIMESTAMP,
    ended_at TIMESTAMP,
    min_sample_size INT DEFAULT 100,
    max_duration_days INT DEFAULT 14,

    status ENUM('draft', 'running', 'paused', 'completed', 'winner_pending_approval', 'winner_promoted') NOT NULL DEFAULT 'draft',
    version INT NOT NULL DEFAULT 1,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
    FOREIGN KEY (campaign_id) REFERENCES campaign_beads(id) ON DELETE SET NULL,
    FOREIGN KEY (control_asset_id) REFERENCES asset_beads(id) ON DELETE SET NULL,
    INDEX idx_test_org (organization_id),
    INDEX idx_test_status (status)
);

-- =============================================================================
-- ICPBead - Ideal Customer Profile parameters
-- =============================================================================
CREATE TABLE IF NOT EXISTS icp_beads (
    id VARCHAR(36) PRIMARY KEY,
    type VARCHAR(50) NOT NULL DEFAULT 'icp',
    organization_id VARCHAR(36) NOT NULL,
    campaign_id VARCHAR(36),

    -- ICP definition
    name VARCHAR(255) NOT NULL,
    description TEXT,

    -- Firmographic criteria
    company_sizes JSON,  -- ["1-10", "11-50", "51-200"]
    industries JSON,
    revenue_ranges JSON,
    geographies JSON,

    -- Role criteria
    job_titles JSON,
    departments JSON,
    seniority_levels JSON,

    -- Technographic criteria
    technologies JSON,

    -- Behavioral criteria
    buying_signals JSON,
    pain_points JSON,

    -- Scoring weights
    scoring_weights JSON,

    is_default BOOLEAN DEFAULT FALSE,
    status ENUM('active', 'draft', 'archived') NOT NULL DEFAULT 'active',
    version INT NOT NULL DEFAULT 1,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
    FOREIGN KEY (campaign_id) REFERENCES campaign_beads(id) ON DELETE SET NULL,
    INDEX idx_icp_org (organization_id)
);

-- =============================================================================
-- JournalistBead - Journalist relationship history
-- =============================================================================
CREATE TABLE IF NOT EXISTS journalist_beads (
    id VARCHAR(36) PRIMARY KEY,
    type VARCHAR(50) NOT NULL DEFAULT 'journalist',
    organization_id VARCHAR(36) NOT NULL,
    campaign_id VARCHAR(36),

    -- Journalist info
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    phone VARCHAR(50),

    -- Publication info
    publication VARCHAR(255),
    publication_tier ENUM('tier1', 'tier2', 'tier3', 'trade', 'blog') DEFAULT 'tier2',
    beats JSON,  -- ["AI", "Enterprise Software", "Startups"]

    -- Social profiles
    twitter_handle VARCHAR(100),
    linkedin_url VARCHAR(500),

    -- Relationship tracking
    relationship_score INT DEFAULT 0,  -- -100 to 100
    last_pitched_at TIMESTAMP,
    last_coverage_at TIMESTAMP,
    pitch_count INT DEFAULT 0,
    coverage_count INT DEFAULT 0,

    -- History
    pitch_history JSON,
    coverage_history JSON,
    notes TEXT,

    -- Preferences
    preferred_contact_method ENUM('email', 'twitter_dm', 'phone', 'linkedin') DEFAULT 'email',
    do_not_contact BOOLEAN DEFAULT FALSE,
    embargo_history JSON,

    status ENUM('active', 'cold', 'do_not_contact', 'archived') NOT NULL DEFAULT 'active',
    version INT NOT NULL DEFAULT 1,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
    FOREIGN KEY (campaign_id) REFERENCES campaign_beads(id) ON DELETE SET NULL,
    INDEX idx_journalist_org (organization_id),
    INDEX idx_journalist_email (email),
    INDEX idx_journalist_publication (publication)
);

-- =============================================================================
-- ModelRegistryBead - Neurometric model preferences per task class
-- =============================================================================
CREATE TABLE IF NOT EXISTS model_registry_beads (
    id VARCHAR(36) PRIMARY KEY,
    type VARCHAR(50) NOT NULL DEFAULT 'model_registry',
    organization_id VARCHAR(36),  -- NULL = global default

    -- Task class configuration
    task_class VARCHAR(100) NOT NULL,  -- e.g., "blog_draft", "email_personalization"

    -- Model selection
    default_model VARCHAR(100) NOT NULL,  -- e.g., "claude-sonnet-4-5-20250929"
    fallback_model VARCHAR(100),

    -- Performance tracking
    evaluation_status ENUM('confirmed_optimal', 'under_evaluation', 'deprecated') DEFAULT 'under_evaluation',
    last_evaluated_at TIMESTAMP,
    evaluation_metrics JSON,

    -- Cost/performance tradeoffs
    max_tokens INT,
    temperature DECIMAL(3,2) DEFAULT 0.7,

    status ENUM('active', 'archived') NOT NULL DEFAULT 'active',
    version INT NOT NULL DEFAULT 1,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY unique_task_org (task_class, organization_id),
    INDEX idx_model_task (task_class)
);

-- =============================================================================
-- PluginBead - Plugin registration and state
-- =============================================================================
CREATE TABLE IF NOT EXISTS plugin_beads (
    id VARCHAR(36) PRIMARY KEY,
    type VARCHAR(50) NOT NULL DEFAULT 'plugin',
    organization_id VARCHAR(36) NOT NULL,

    -- Plugin identification
    plugin_name VARCHAR(255) NOT NULL,
    plugin_version VARCHAR(50) NOT NULL,
    manifest JSON NOT NULL,  -- Full revtown-plugin.json contents

    -- Installation info
    source_type ENUM('registry', 'git', 'local') NOT NULL,
    source_url VARCHAR(500),

    -- Health monitoring
    health_endpoint VARCHAR(255),
    last_health_check_at TIMESTAMP,
    health_status ENUM('healthy', 'degraded', 'unhealthy', 'unknown') DEFAULT 'unknown',

    -- Configuration
    config JSON,
    required_credentials JSON,  -- List of credential keys needed

    status ENUM('active', 'disabled', 'failed', 'archived') NOT NULL DEFAULT 'active',
    version INT NOT NULL DEFAULT 1,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
    UNIQUE KEY unique_plugin_org (plugin_name, organization_id),
    INDEX idx_plugin_org (organization_id),
    INDEX idx_plugin_status (status)
);

-- =============================================================================
-- Polecat Executions (Not a Bead - execution tracking)
-- =============================================================================
CREATE TABLE IF NOT EXISTS polecat_executions (
    id VARCHAR(36) PRIMARY KEY,
    organization_id VARCHAR(36) NOT NULL,
    campaign_id VARCHAR(36),

    -- Polecat info
    polecat_type VARCHAR(100) NOT NULL,
    rig VARCHAR(50) NOT NULL,
    task_class VARCHAR(100) NOT NULL,

    -- Input/Output
    input_bead_id VARCHAR(36),
    output_bead_ids JSON,  -- Array of created/updated bead IDs

    -- Temporal tracking
    temporal_workflow_id VARCHAR(255),
    temporal_run_id VARCHAR(255),

    -- Execution details
    started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    duration_ms INT,

    -- Model usage
    model_used VARCHAR(100),
    tokens_input INT,
    tokens_output INT,

    -- Quality gates
    refinery_passed BOOLEAN,
    refinery_scores JSON,
    witness_passed BOOLEAN,
    witness_notes TEXT,

    -- Status
    status ENUM('pending', 'running', 'completed', 'failed', 'cancelled') NOT NULL DEFAULT 'pending',
    error_message TEXT,

    FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
    FOREIGN KEY (campaign_id) REFERENCES campaign_beads(id) ON DELETE SET NULL,
    INDEX idx_polecat_org (organization_id),
    INDEX idx_polecat_status (status),
    INDEX idx_polecat_type (polecat_type),
    INDEX idx_polecat_temporal (temporal_workflow_id)
);

-- =============================================================================
-- Approval Queue
-- =============================================================================
CREATE TABLE IF NOT EXISTS approval_queue (
    id VARCHAR(36) PRIMARY KEY,
    organization_id VARCHAR(36) NOT NULL,

    -- What needs approval
    bead_type VARCHAR(50) NOT NULL,
    bead_id VARCHAR(36) NOT NULL,
    polecat_execution_id VARCHAR(36),

    -- Context
    rig VARCHAR(50) NOT NULL,
    approval_type ENUM('content', 'outreach', 'pr_pitch', 'sms', 'test_winner', 'other') NOT NULL,
    urgency ENUM('low', 'normal', 'high', 'critical') DEFAULT 'normal',

    -- Preview
    preview_title VARCHAR(500),
    preview_content TEXT,

    -- Refinery results
    refinery_scores JSON,
    refinery_warnings JSON,

    -- Decision
    status ENUM('pending', 'approved', 'rejected', 'sent_back', 'expired') NOT NULL DEFAULT 'pending',
    decided_by VARCHAR(36),
    decided_at TIMESTAMP,
    decision_notes TEXT,

    -- Edits (if approved with modifications)
    edited_content TEXT,

    -- Timing
    expires_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
    FOREIGN KEY (decided_by) REFERENCES users(id),
    FOREIGN KEY (polecat_execution_id) REFERENCES polecat_executions(id),
    INDEX idx_approval_org (organization_id),
    INDEX idx_approval_status (status),
    INDEX idx_approval_urgency (urgency),
    INDEX idx_approval_type (approval_type)
);

-- =============================================================================
-- Webhooks
-- =============================================================================
CREATE TABLE IF NOT EXISTS webhooks (
    id VARCHAR(36) PRIMARY KEY,
    organization_id VARCHAR(36) NOT NULL,

    url VARCHAR(500) NOT NULL,
    secret VARCHAR(255) NOT NULL,

    events JSON NOT NULL,  -- ["bead.created", "bead.updated", "approval.decided"]

    is_active BOOLEAN DEFAULT TRUE,
    last_triggered_at TIMESTAMP,
    failure_count INT DEFAULT 0,

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
    INDEX idx_webhook_org (organization_id)
);

-- =============================================================================
-- Usage Tracking (for billing)
-- =============================================================================
CREATE TABLE IF NOT EXISTS usage_records (
    id VARCHAR(36) PRIMARY KEY,
    organization_id VARCHAR(36) NOT NULL,

    period_start DATE NOT NULL,
    period_end DATE NOT NULL,

    -- Counts
    polecat_executions INT DEFAULT 0,
    beads_created INT DEFAULT 0,
    api_calls INT DEFAULT 0,

    -- Tokens
    total_input_tokens BIGINT DEFAULT 0,
    total_output_tokens BIGINT DEFAULT 0,

    -- By rig breakdown
    usage_by_rig JSON,

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
    UNIQUE KEY unique_org_period (organization_id, period_start, period_end),
    INDEX idx_usage_org (organization_id)
);

-- =============================================================================
-- Invitations
-- =============================================================================
CREATE TABLE IF NOT EXISTS invitations (
    id VARCHAR(36) PRIMARY KEY,
    organization_id VARCHAR(36) NOT NULL,
    email VARCHAR(255) NOT NULL,
    role ENUM('owner', 'admin', 'member') NOT NULL DEFAULT 'member',
    token VARCHAR(255) NOT NULL,
    invited_by VARCHAR(36),
    status ENUM('pending', 'accepted', 'cancelled', 'expired') NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,

    FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
    FOREIGN KEY (invited_by) REFERENCES users(id),
    UNIQUE KEY unique_invite_token (token),
    INDEX idx_invite_org (organization_id),
    INDEX idx_invite_email (email),
    INDEX idx_invite_status (status)
);

-- =============================================================================
-- Audit Log
-- =============================================================================
CREATE TABLE IF NOT EXISTS audit_log (
    id VARCHAR(36) PRIMARY KEY,
    organization_id VARCHAR(36) NOT NULL,
    user_id VARCHAR(36),

    action VARCHAR(100) NOT NULL,
    entity_type VARCHAR(50) NOT NULL,
    entity_id VARCHAR(36),

    details JSON,
    ip_address VARCHAR(45),
    user_agent VARCHAR(500),

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_audit_org (organization_id),
    INDEX idx_audit_user (user_id),
    INDEX idx_audit_action (action),
    INDEX idx_audit_time (created_at)
);

-- =============================================================================
-- Insert Default Model Registry (Global Defaults per CLAUDE.md)
-- =============================================================================
INSERT INTO model_registry_beads (id, task_class, default_model, evaluation_status) VALUES
('00000000-0000-0000-0000-000000000001', 'blog_draft', 'claude-sonnet-4-5-20250929', 'confirmed_optimal'),
('00000000-0000-0000-0000-000000000002', 'email_personalization', 'claude-haiku-4-5-20251001', 'confirmed_optimal'),
('00000000-0000-0000-0000-000000000003', 'competitor_analysis', 'claude-opus-4-5-20251101', 'under_evaluation'),
('00000000-0000-0000-0000-000000000004', 'subject_line_ab', 'claude-haiku-4-5-20251001', 'confirmed_optimal'),
('00000000-0000-0000-0000-000000000005', 'pr_pitch_draft', 'claude-sonnet-4-5-20250929', 'confirmed_optimal'),
('00000000-0000-0000-0000-000000000006', 'statistical_significance', 'claude-sonnet-4-5-20250929', 'confirmed_optimal');

-- =============================================================================
-- Default Organization for Self-Hosted Mode
-- =============================================================================
INSERT INTO organizations (id, name, slug, plan_tier, created_at, updated_at) VALUES
('00000000-0000-0000-0000-000000000001', 'Default Organization', 'default', 'scale', NOW(), NOW())
ON DUPLICATE KEY UPDATE name = name;

-- =============================================================================
-- Create Remote Access User
-- =============================================================================
-- Note: This allows connections from any host (for Docker networking)
CREATE USER IF NOT EXISTS 'revtown'@'%' IDENTIFIED BY 'revtown';
GRANT ALL PRIVILEGES ON revtown.* TO 'revtown'@'%';
FLUSH PRIVILEGES;
