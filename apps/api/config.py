"""
RevTown Configuration - Settings management using Pydantic Settings.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # =========================================================================
    # Core Settings
    # =========================================================================
    revtown_mode: Literal["saas", "self-hosted"] = "saas"
    revtown_env: Literal["development", "staging", "production"] = "development"
    debug: bool = True
    log_level: str = "INFO"

    # =========================================================================
    # Database (Dolt)
    # =========================================================================
    dolt_host: str = "localhost"
    dolt_port: int = 3306
    dolt_database: str = "revtown"
    dolt_user: str = "root"
    dolt_password: str = ""

    # =========================================================================
    # Message Queue (Kafka)
    # =========================================================================
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_consumer_group: str = "revtown-api"
    kafka_security_protocol: str = "PLAINTEXT"

    # =========================================================================
    # Temporal.io
    # =========================================================================
    temporal_host: str = "localhost:7233"
    temporal_namespace: str = "revtown"
    temporal_task_queue: str = "revtown-polecats"

    # =========================================================================
    # API Settings
    # =========================================================================
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_base_url: str = "http://localhost:8000"
    cors_origins: list[str] = Field(default=["http://localhost:5173", "http://localhost:3000"])

    # JWT Authentication
    jwt_secret_key: str = "your-super-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7

    # API Key Settings
    api_key_prefix: str = "rtk_"

    # =========================================================================
    # Neurometric Gateway
    # =========================================================================
    neurometric_api_url: str = "https://api.neurometric.ai"
    neurometric_api_key: str = ""

    # =========================================================================
    # Secrets Management (Vault)
    # =========================================================================
    vault_addr: str = "http://localhost:8200"
    vault_token: str = ""
    vault_mount_path: str = "secret"
    vault_path_prefix: str = "revtown"

    # =========================================================================
    # Stripe Billing (SaaS mode only)
    # =========================================================================
    stripe_secret_key: str = ""
    stripe_publishable_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_id_pro: str = ""
    stripe_price_id_scale: str = ""

    # =========================================================================
    # External Integrations
    # =========================================================================
    # Twilio (The Wire)
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""

    # Vercel (Landing Pad)
    vercel_api_token: str = ""
    vercel_team_id: str = ""

    # GitHub (Repo Watch)
    github_app_id: str = ""
    github_app_private_key: str = ""
    github_webhook_secret: str = ""

    # LinkedIn API (Social Command)
    linkedin_client_id: str = ""
    linkedin_client_secret: str = ""

    # Twitter/X API (Social Command)
    twitter_api_key: str = ""
    twitter_api_secret: str = ""
    twitter_access_token: str = ""
    twitter_access_secret: str = ""

    # =========================================================================
    # Rate Limiting
    # =========================================================================
    rate_limit_requests_per_minute: int = 60
    rate_limit_burst: int = 100

    # =========================================================================
    # Self-Hosted License
    # =========================================================================
    revtown_license_key: str = ""

    # =========================================================================
    # Properties
    # =========================================================================

    @property
    def is_saas(self) -> bool:
        """Check if running in SaaS mode."""
        return self.revtown_mode == "saas"

    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.revtown_env == "production"

    @property
    def database_url(self) -> str:
        """Get the full database URL."""
        return (
            f"mysql+aiomysql://{self.dolt_user}:{self.dolt_password}"
            f"@{self.dolt_host}:{self.dolt_port}/{self.dolt_database}"
        )


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()
