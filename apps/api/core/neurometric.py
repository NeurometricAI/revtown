"""
Neurometric Client - Gateway for all LLM calls.

Currently using direct Anthropic API. Will be replaced with Neurometric gateway
once it's fully deployed.
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
    """Response from LLM API."""

    content: str
    model_used: str
    tokens_input: int
    tokens_output: int
    latency_ms: int
    task_class: str
    metadata: dict[str, Any] | None = None


class NeurometricError(Exception):
    """Error from LLM gateway."""

    def __init__(self, message: str, code: str | None = None, details: dict | None = None):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(message)


class NeurometricClient:
    """
    Client for LLM completions.

    Currently using direct Anthropic API. Will migrate to Neurometric gateway.
    """

    # Anthropic API configuration
    ANTHROPIC_API_URL = "https://api.anthropic.com"
    ANTHROPIC_VERSION = "2023-06-01"

    # Model mapping for task classes
    TASK_CLASS_MODELS: dict[str, str] = {
        "mayor_intent_analysis": "claude-sonnet-4-5-20250929",
        "mayor_convoy_planning": "claude-sonnet-4-5-20250929",
        "mayor_conversation": "claude-sonnet-4-5-20250929",
        "mayor_general_qa": "claude-sonnet-4-5-20250929",
        "mayor_re_slate": "claude-sonnet-4-5-20250929",
        "blog_draft": "claude-sonnet-4-5-20250929",
        "email_personalization": "claude-haiku-3-5-20241022",
        "subject_line": "claude-haiku-3-5-20241022",
        "pr_pitch": "claude-sonnet-4-5-20250929",
    }

    def __init__(
        self,
        api_key: str | None = None,
        organization_id: UUID | None = None,
    ):
        # Use Anthropic API key (stored in same env var for now)
        self.api_key = api_key or settings.anthropic_api_key
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
                base_url=self.ANTHROPIC_API_URL,
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": self.ANTHROPIC_VERSION,
                    "content-type": "application/json",
                },
                timeout=120.0,
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
        Make an LLM completion request.

        Args:
            task_class: The type of task (e.g., "blog_draft", "email_personalization")
            prompt: The prompt to send to the model
            context: Additional context for the request
            max_tokens: Override max tokens (default 4096)
            temperature: Override temperature
            model_override: Force a specific model (for testing)

        Returns:
            NeurometricResponse with the completion and metadata
        """
        start_time = datetime.utcnow()

        # Select model based on task class or override
        model = model_override or self.TASK_CLASS_MODELS.get(
            task_class, "claude-sonnet-4-5-20250929"
        )

        # Build Anthropic Messages API request body
        request_body: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens or 4096,
            "messages": [{"role": "user", "content": prompt}],
        }

        if temperature is not None:
            request_body["temperature"] = temperature

        self.logger.info(
            "Making Anthropic completion request",
            task_class=task_class,
            model=model,
            prompt_length=len(prompt),
        )

        try:
            client = await self._get_client()
            response = await client.post("/v1/messages", json=request_body)

            if response.status_code != 200:
                error_data = response.json() if response.content else {}
                error_msg = error_data.get("error", {}).get("message", f"Request failed with status {response.status_code}")
                raise NeurometricError(
                    message=error_msg,
                    code=error_data.get("error", {}).get("type"),
                    details=error_data,
                )

            data = response.json()
            latency_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

            # Extract content from Anthropic response
            content = ""
            for block in data.get("content", []):
                if block.get("type") == "text":
                    content += block.get("text", "")

            usage = data.get("usage", {})

            self.logger.info(
                "Anthropic completion successful",
                task_class=task_class,
                model_used=data.get("model", model),
                tokens_input=usage.get("input_tokens", 0),
                tokens_output=usage.get("output_tokens", 0),
                latency_ms=latency_ms,
            )

            return NeurometricResponse(
                content=content,
                model_used=data.get("model", model),
                tokens_input=usage.get("input_tokens", 0),
                tokens_output=usage.get("output_tokens", 0),
                latency_ms=latency_ms,
                task_class=task_class,
                metadata={"id": data.get("id")},
            )

        except httpx.RequestError as e:
            self.logger.error("Anthropic request failed", error=str(e))
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
            response = await client.get(f"/registry/{task_class}")

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
                "/quality/report",
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
            response = await client.get(f"/efficiency?days={days}")

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
