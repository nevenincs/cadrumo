"""Google Gemini provider adapter for the LLM outbound subpackage.

Speaks the Gemini ``v1beta/models/{model}:generateContent`` HTTP API and
adapts its response shape to the
:class:`~adapters.outbound.llm._providers.base.ProviderCompletion`
contract. Internal pydantic models mirror the upstream JSON schema and are kept
private.
"""

from __future__ import annotations

from typing import override

import httpx
from pydantic import BaseModel, ConfigDict, Field

from .....core.config import load_settings
from .....core.logging import get_logger
from .._errors import LLMConfigError
from .._models import LLMProvider
from .base import (
    ProviderCompletion,
    ProviderRequest,
    _ProviderAdapter,
    check_http_error,
    parse_provider_response,
    post_provider_request,
    require_provider_response_item,
)

_logger = get_logger(__name__)


class _GeminiPart(BaseModel):
    """Single text part of a Gemini ``content`` block."""

    model_config = ConfigDict(strict=True, frozen=True)

    text: str | None = None


class _GeminiContent(BaseModel):
    """Multi-part content payload returned for a single Gemini candidate."""

    model_config = ConfigDict(strict=True, frozen=True)

    parts: tuple[_GeminiPart, ...]


class _GeminiCandidate(BaseModel):
    """One candidate completion within a Gemini response."""

    model_config = ConfigDict(strict=True, frozen=True)

    content: _GeminiContent


class _GeminiUsage(BaseModel):
    """Token accounting reported by the Gemini API.

    Attributes:
        prompt_token_count: Tokens charged for the prompt.
        candidates_token_count: Tokens charged for the generated candidates.
    """

    model_config = ConfigDict(strict=True, frozen=True, populate_by_name=True)

    prompt_token_count: int = Field(default=0, ge=0, alias="promptTokenCount")
    candidates_token_count: int = Field(default=0, ge=0, alias="candidatesTokenCount")


class _GeminiResponse(BaseModel):
    """Top-level Gemini ``generateContent`` response envelope.

    Attributes:
        candidates: Candidate completions returned by the model.
        usage_metadata: Token accounting metadata.
    """

    model_config = ConfigDict(strict=True, frozen=True, populate_by_name=True)

    candidates: tuple[_GeminiCandidate, ...]
    usage_metadata: _GeminiUsage = Field(default_factory=_GeminiUsage, alias="usageMetadata")


class GeminiAdapter(_ProviderAdapter):
    """Provider adapter that invokes the Gemini ``generateContent`` HTTP API.

    A non-empty ``api_key`` is mandatory; the adapter refuses to construct
    without one because the underlying API rejects unauthenticated calls.
    """

    provider = LLMProvider.GEMINI

    def __init__(self, api_key: str, timeout_s: int) -> None:
        """Initialize the adapter.

        Args:
            api_key: Google AI Studio API key.
            timeout_s: Per-request HTTP timeout in seconds.

        Raises:
            LLMConfigError: When ``api_key`` is empty.
        """
        if not api_key:
            msg = "CADRUMO_LLM_GEMINI_API_KEY must be set for the Gemini provider."
            raise LLMConfigError(msg)
        self._api_key = api_key
        self._timeout_s = timeout_s

    @override
    async def complete(self, request: ProviderRequest) -> ProviderCompletion:
        """Execute a Gemini completion request.

        Args:
            request: Normalized provider request.

        Returns:
            A :class:`ProviderCompletion` containing the concatenated text of the
            first candidate and reported token counts.

        Raises:
            LLMProviderError: When the API returns a 4xx or 5xx HTTP error status.
        """
        parts: list[dict[str, str]] = []
        if request.system is not None:
            parts.append({"text": f"System instruction:\n{request.system}"})
        parts.append({"text": request.prompt})
        endpoint = load_settings().cadrumo_llm_gemini_generate_content_template.format(model=request.model)
        async with httpx.AsyncClient(timeout=self._timeout_s) as client:
            response = await post_provider_request(
                client,
                endpoint,
                provider_name="Gemini",
                model=request.model,
                logger=_logger,
                headers={"x-goog-api-key": self._api_key},
                json={
                    "contents": [{"role": "user", "parts": parts}],
                    "generationConfig": {
                        "temperature": request.temperature,
                        "maxOutputTokens": request.max_tokens,
                    },
                },
            )
        check_http_error(response, provider_name="Gemini", model=request.model, logger=_logger)
        parsed = parse_provider_response(response, provider_name="Gemini", response_model=_GeminiResponse)
        candidate = require_provider_response_item(parsed.candidates, provider_name="Gemini", item_name="candidates")
        text = "".join(part.text or "" for part in candidate.content.parts).strip()
        return ProviderCompletion(
            text=text,
            model=request.model,
            input_tokens=parsed.usage_metadata.prompt_token_count,
            output_tokens=parsed.usage_metadata.candidates_token_count,
            provider_request_id=None,
        )
