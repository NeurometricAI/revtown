"""
Plugin Loader - Load and register plugins at runtime.
"""

import importlib.util
import json
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import structlog

from apps.api.core.bead_store import BeadStore
from plugins.registry.manifest import (
    ManifestValidationError,
    PluginManifest,
    parse_manifest,
    validate_manifest_strict,
)
from polecats.base import BasePolecat, _polecat_registry

logger = structlog.get_logger()


class PluginLoadError(Exception):
    """Error loading a plugin."""

    pass


class PluginLoader:
    """
    Load and register plugins at runtime.

    Handles:
    - Manifest parsing and validation
    - Polecat template registration
    - Refinery check registration
    - Credential requirement tracking
    """

    def __init__(self, bead_store: BeadStore | None = None):
        self.bead_store = bead_store
        self.logger = logger.bind(service="plugin_loader")
        self._loaded_plugins: dict[str, PluginManifest] = {}

    async def load_from_path(
        self,
        plugin_path: Path,
        organization_id: UUID | None = None,
    ) -> PluginManifest:
        """
        Load a plugin from a local path.

        Args:
            plugin_path: Path to plugin directory containing revtown-plugin.json
            organization_id: Organization loading the plugin

        Returns:
            Loaded and validated PluginManifest
        """
        manifest_path = plugin_path / "revtown-plugin.json"

        if not manifest_path.exists():
            raise PluginLoadError(f"No manifest found at {manifest_path}")

        try:
            with open(manifest_path) as f:
                manifest_data = json.load(f)
        except json.JSONDecodeError as e:
            raise PluginLoadError(f"Invalid JSON in manifest: {e}")

        # Parse and validate manifest
        try:
            manifest = parse_manifest(manifest_data)
        except ManifestValidationError as e:
            raise PluginLoadError(f"Manifest validation failed: {e}")

        # Strict validation warnings
        warnings = validate_manifest_strict(manifest)
        if warnings:
            for warning in warnings:
                self.logger.warning("Plugin manifest warning", warning=warning)

        # Register plugin components
        await self._register_plugin(manifest, plugin_path)

        # Store in loaded plugins
        self._loaded_plugins[manifest.name] = manifest

        self.logger.info(
            "Plugin loaded",
            name=manifest.name,
            version=manifest.version,
            polecats=len(manifest.polecats),
            refinery_checks=len(manifest.refinery_checks),
        )

        return manifest

    async def load_from_manifest(
        self,
        manifest_data: dict[str, Any],
        organization_id: UUID | None = None,
    ) -> PluginManifest:
        """
        Load a plugin from a manifest dictionary.

        Used for registry-based or remote plugins.
        """
        try:
            manifest = parse_manifest(manifest_data)
        except ManifestValidationError as e:
            raise PluginLoadError(f"Manifest validation failed: {e}")

        # For manifest-only loading, we can't load Python code
        # Just register the metadata

        self._loaded_plugins[manifest.name] = manifest

        self.logger.info(
            "Plugin registered (manifest only)",
            name=manifest.name,
            version=manifest.version,
        )

        return manifest

    async def _register_plugin(
        self,
        manifest: PluginManifest,
        plugin_path: Path | None = None,
    ):
        """Register plugin components."""

        # Register Polecat templates
        for polecat_def in manifest.polecats:
            self._register_polecat_template(manifest.name, polecat_def, plugin_path)

        # Register Refinery checks
        for check_def in manifest.refinery_checks:
            self._register_refinery_check(manifest.name, check_def, plugin_path)

    def _register_polecat_template(
        self,
        plugin_name: str,
        polecat_def: Any,
        plugin_path: Path | None,
    ):
        """Register a Polecat template from a plugin."""
        # If we have a path, try to load the actual Python implementation
        if plugin_path:
            polecat_file = plugin_path / "polecats" / f"{polecat_def.name.lower()}.py"
            if polecat_file.exists():
                try:
                    spec = importlib.util.spec_from_file_location(
                        f"plugin_{plugin_name}_{polecat_def.name}",
                        polecat_file,
                    )
                    if spec and spec.loader:
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        self.logger.info(
                            "Loaded Polecat implementation",
                            plugin=plugin_name,
                            polecat=polecat_def.name,
                        )
                except Exception as e:
                    self.logger.error(
                        "Failed to load Polecat implementation",
                        plugin=plugin_name,
                        polecat=polecat_def.name,
                        error=str(e),
                    )

        # Register the template metadata
        key = f"{polecat_def.rig}:{polecat_def.task_class}"
        self.logger.debug(
            "Registered Polecat template",
            key=key,
            plugin=plugin_name,
        )

    def _register_refinery_check(
        self,
        plugin_name: str,
        check_def: Any,
        plugin_path: Path | None,
    ):
        """Register a Refinery check from a plugin."""
        # Similar to Polecat registration
        self.logger.debug(
            "Registered Refinery check",
            check=check_def.name,
            plugin=plugin_name,
        )

    def get_loaded_plugins(self) -> dict[str, PluginManifest]:
        """Get all loaded plugins."""
        return self._loaded_plugins.copy()

    def get_plugin(self, name: str) -> PluginManifest | None:
        """Get a loaded plugin by name."""
        return self._loaded_plugins.get(name)

    def unload_plugin(self, name: str) -> bool:
        """Unload a plugin."""
        if name in self._loaded_plugins:
            del self._loaded_plugins[name]
            self.logger.info("Plugin unloaded", name=name)
            return True
        return False


# =============================================================================
# Global Plugin Loader
# =============================================================================

_loader: PluginLoader | None = None


def get_plugin_loader() -> PluginLoader:
    """Get the global plugin loader."""
    global _loader
    if _loader is None:
        _loader = PluginLoader()
    return _loader
