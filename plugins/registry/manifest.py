"""
Plugin Manifest Parser and Validator.

Parses and validates revtown-plugin.json manifests.
"""

from dataclasses import dataclass, field
from typing import Any

import structlog
from pydantic import BaseModel, Field, validator

logger = structlog.get_logger()


class PolecatTemplate(BaseModel):
    """Polecat template definition in a plugin."""

    name: str = Field(..., description="Polecat name")
    task_class: str = Field(..., description="Neurometric task class")
    rig: str = Field(..., description="Target rig")
    content_type: str = Field(..., description="Content type for Refinery")
    description: str | None = None
    always_requires_approval: bool = False


class RefineryCheck(BaseModel):
    """Refinery check definition in a plugin."""

    name: str = Field(..., description="Check name")
    content_types: list[str] = Field(..., description="Content types this applies to")
    description: str | None = None
    severity: str = Field("warn", description="Default severity: pass, warn, fail")


class BeadType(BaseModel):
    """Custom Bead type definition in a plugin."""

    name: str = Field(..., description="Bead type name")
    table_name: str = Field(..., description="Database table name")
    fields: list[dict[str, Any]] = Field(..., description="Field definitions")
    description: str | None = None


class PluginManifest(BaseModel):
    """
    Plugin manifest schema (revtown-plugin.json).

    This defines the structure of plugin configuration files.
    """

    # Required fields
    name: str = Field(..., description="Plugin name (unique identifier)")
    version: str = Field(..., description="Semantic version (e.g., 1.0.0)")

    # Optional metadata
    description: str | None = None
    author: str | None = None
    license: str | None = None
    homepage: str | None = None
    repository: str | None = None

    # Plugin capabilities
    polecats: list[PolecatTemplate] = Field(default_factory=list)
    refinery_checks: list[RefineryCheck] = Field(default_factory=list)
    bead_types: list[BeadType] = Field(default_factory=list)

    # Health monitoring
    health_endpoint: str | None = None

    # Required credentials (stored in Vault)
    required_credentials: list[str] = Field(default_factory=list)

    # Plugin configuration schema
    config_schema: dict[str, Any] | None = None

    # Compatibility
    min_revtown_version: str | None = None
    max_revtown_version: str | None = None

    @validator("name")
    def validate_name(cls, v):
        """Validate plugin name format."""
        if not v or len(v) < 3:
            raise ValueError("Plugin name must be at least 3 characters")
        if not v.replace("-", "").replace("_", "").isalnum():
            raise ValueError("Plugin name must be alphanumeric with - or _")
        return v.lower()

    @validator("version")
    def validate_version(cls, v):
        """Validate semantic version format."""
        parts = v.split(".")
        if len(parts) != 3:
            raise ValueError("Version must be semantic (e.g., 1.0.0)")
        for part in parts:
            if not part.isdigit():
                raise ValueError("Version parts must be numeric")
        return v


class ManifestValidationError(Exception):
    """Error during manifest validation."""

    def __init__(self, message: str, errors: list[str] | None = None):
        self.message = message
        self.errors = errors or []
        super().__init__(message)


def parse_manifest(manifest_data: dict[str, Any]) -> PluginManifest:
    """
    Parse and validate a plugin manifest.

    Args:
        manifest_data: Raw manifest dictionary

    Returns:
        Validated PluginManifest

    Raises:
        ManifestValidationError: If validation fails
    """
    try:
        return PluginManifest(**manifest_data)
    except Exception as e:
        raise ManifestValidationError(f"Invalid manifest: {e}")


def validate_manifest_strict(manifest: PluginManifest) -> list[str]:
    """
    Perform strict validation on a manifest.

    Returns a list of warnings (empty if all OK).
    """
    warnings = []

    # Check for description
    if not manifest.description:
        warnings.append("Plugin should have a description")

    # Check for author
    if not manifest.author:
        warnings.append("Plugin should have an author")

    # Check Polecat task classes
    for polecat in manifest.polecats:
        if not polecat.description:
            warnings.append(f"Polecat '{polecat.name}' should have a description")

    # Check credentials are specified
    if manifest.polecats and not manifest.required_credentials:
        warnings.append("Plugin has Polecats but no required_credentials - verify this is intentional")

    return warnings


# =============================================================================
# Example Manifest
# =============================================================================

EXAMPLE_MANIFEST = {
    "name": "revtown-g2-monitor",
    "version": "1.0.0",
    "description": "G2 review sentiment analysis plugin",
    "author": "RevTown Team",
    "license": "MIT",

    "polecats": [
        {
            "name": "G2ReviewAnalyzer",
            "task_class": "g2_review_analysis",
            "rig": "intelligence_station",
            "content_type": "blog",
            "description": "Analyze G2 reviews for sentiment and insights"
        }
    ],

    "refinery_checks": [
        {
            "name": "g2_claim_verification",
            "content_types": ["blog", "landing_page"],
            "description": "Verify G2-related claims in content",
            "severity": "warn"
        }
    ],

    "health_endpoint": "/health",

    "required_credentials": [
        "g2_api_key"
    ],

    "config_schema": {
        "type": "object",
        "properties": {
            "review_limit": {"type": "integer", "default": 100},
            "sentiment_threshold": {"type": "number", "default": 0.7}
        }
    }
}
