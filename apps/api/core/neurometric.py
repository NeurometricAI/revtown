"""
Neurometric Client - Gateway for all LLM calls.

IMPORTANT: Every AI API call must be routed through the Neurometric gateway.
No direct calls to Claude, OpenAI, or any model provider.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

import httpx
import structlog

from apps.api.config import settings

logger = structlog.get_logger()


@dataclass
class NeurometricResponse:
    """Response from Neurometric API."""

    content: str
    model_used: str
    tokens_input: int
    tokens_output: int
    latency_ms: int
    task_class: str
    metadata: dict[str, Any] | None = None


class NeurometricError(Exception):
    """Error from Neurometric gateway."""

    def __init__(self, message: str, code: str | None = None, details: dict | None = None):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(message)


class NeurometricClient:
    """
    Client for the Neurometric AI gateway.

    All LLM calls route through here for:
    - Model selection based on task class
    - Usage tracking and metering
    - Shadow testing for model optimization
    - Rate limiting and quota enforcement
    """

    def __init__(
        self,
        api_url: str | None = None,
        api_key: str | None = None,
        organization_id: UUID | None = None,
    ):
        self.api_url = api_url or settings.neurometric_api_url
        self.api_key = api_key or settings.neurometric_api_key
        self.organization_id = organization_id
        self.logger = logger.bind(
            service="neurometric",
            organization_id=str(organization_id) if organization_id else None,
        )
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.api_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "X-Organization-ID": str(self.organization_id) if self.organization_id else "",
                },
                timeout=60.0,
            )
        return self._client

    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def complete(
        self,
        task_class: str,
        prompt: str,
        context: dict[str, Any] | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        model_override: str | None = None,
    ) -> NeurometricResponse:
        """
        Make an LLM completion request through Neurometric.

        Args:
            task_class: The type of task (e.g., "blog_draft", "email_personalization")
            prompt: The prompt to send to the model
            context: Additional context for the request
            max_tokens: Override max tokens (uses registry default if not specified)
            temperature: Override temperature (uses registry default if not specified)
            model_override: Force a specific model (for testing)

        Returns:
            NeurometricResponse with the completion and metadata
        """
        start_time = datetime.utcnow()

        request_body = {
            "task_class": task_class,
            "prompt": prompt,
            "context": context or {},
        }

        if max_tokens:
            request_body["max_tokens"] = max_tokens
        if temperature is not None:
            request_body["temperature"] = temperature
        if model_override:
            request_body["model_override"] = model_override

        self.logger.info(
            "Making Neurometric completion request",
            task_class=task_class,
            prompt_length=len(prompt),
        )

        try:
            client = await self._get_client()
            response = await client.post("/v1/complete", json=request_body)

            if response.status_code != 200:
                error_data = response.json() if response.content else {}
                raise NeurometricError(
                    message=error_data.get("message", f"Request failed with status {response.status_code}"),
                    code=error_data.get("code"),
                    details=error_data,
                )

            data = response.json()
            latency_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

            self.logger.info(
                "Neurometric completion successful",
                task_class=task_class,
                model_used=data.get("model"),
                tokens_input=data.get("tokens_input"),
                tokens_output=data.get("tokens_output"),
                latency_ms=latency_ms,
            )

            return NeurometricResponse(
                content=data["content"],
                model_used=data.get("model", "unknown"),
                tokens_input=data.get("tokens_input", 0),
                tokens_output=data.get("tokens_output", 0),
                latency_ms=latency_ms,
                task_class=task_class,
                metadata=data.get("metadata"),
            )

        except httpx.RequestError as e:
            self.logger.error("Neurometric request failed", error=str(e))
            raise NeurometricError(
                message=f"Request failed: {e}",
                code="REQUEST_ERROR",
            )

    async def get_model_for_task(self, task_class: str) -> dict[str, Any]:
        """
        Get the recommended model for a task class.

        Returns the model configuration from the registry.
        """
        try:
            client = await self._get_client()
            response = await client.get(f"/v1/registry/{task_class}")

            if response.status_code == 404:
                return {
                    "task_class": task_class,
                    "default_model": "claude-sonnet-4-5-20250929",  # Fallback
                    "status": "not_found",
                }

            if response.status_code != 200:
                raise NeurometricError(
                    message=f"Failed to get model for task: {response.status_code}",
                )

            return response.json()

        except httpx.RequestError as e:
            self.logger.error("Failed to get model registry", error=str(e))
            # Return fallback
            return {
                "task_class": task_class,
                "default_model": "claude-sonnet-4-5-20250929",
                "status": "fallback",
            }

    async def report_quality(
        self,
        task_class: str,
        model_used: str,
        quality_score: float,
        execution_id: str | None = None,
    ):
        """
        Report quality metrics back to Neurometric for model optimization.

        This feeds into the shadow testing evaluation loop.
        """
        try:
            client = await self._get_client()
            await client.post(
                "/v1/quality/report",
                json={
                    "task_class": task_class,
                    "model": model_used,
                    "quality_score": quality_score,
                    "execution_id": execution_id,
                },
            )
            self.logger.info(
                "Quality report submitted",
                task_class=task_class,
                model=model_used,
                score=quality_score,
            )
        except Exception as e:
            # Don't fail on quality reporting errors
            self.logger.warning("Failed to submit quality report", error=str(e))

    async def get_efficiency_report(self, days: int = 30) -> dict[str, Any]:
        """
        Get efficiency report for the organization.

        Shows cost, quality, and speed metrics across task classes.
        """
        try:
            client = await self._get_client()
            response = await client.get(f"/v1/efficiency?days={days}")

            if response.status_code != 200:
                return {"error": "Failed to get efficiency report"}

            return response.json()

        except Exception as e:
            self.logger.error("Failed to get efficiency report", error=str(e))
            return {"error": str(e)}


# =============================================================================
# Singleton Instance
# =============================================================================

_client: NeurometricClient | None = None


def get_neurometric_client(organization_id: UUID | None = None) -> NeurometricClient:
    """Get a Neurometric client instance."""
    global _client
    if _client is None:
        _client = NeurometricClient(organization_id=organization_id)
    return _client


async def close_neurometric_client():
    """Close the global Neurometric client."""
    global _client
    if _client:
        await _client.close()
        _client = None
