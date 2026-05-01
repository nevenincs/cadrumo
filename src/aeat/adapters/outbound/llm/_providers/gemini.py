"""Google Gemini provider adapter."""

from __future__ import annotations

import httpx
from pydantic import BaseModel, ConfigDict, Field

from .._errors import LLMConfigError, LLMProviderError
from .._models import LLMProvider
from .base import ProviderCompletion, ProviderRequest, _ProviderAdapter, raise_rate_limit


class _GeminiPart(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True)

    text: str | None = None


class _GeminiContent(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True)

    parts: tuple[_GeminiPart, ...]


class _GeminiCandidate(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True)

    content: _GeminiContent


class _GeminiUsage(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, populate_by_name=True)

    prompt_token_count: int = Field(default=0, ge=0, alias="promptTokenCount")
    candidates_token_count: int = Field(default=0, ge=0, alias="candidatesTokenCount")


class _GeminiResponse(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, populate_by_name=True)

    candidates: tuple[_GeminiCandidate, ...]
    usage_metadata: _GeminiUsage = Field(default_factory=_GeminiUsage, alias="usageMetadata")


class GeminiAdapter(_ProviderAdapter):
    """Execute requests against the Gemini ``generateContent`` API."""

    provider = LLMProvider.GEMINI

    def __init__(self, api_key: str, timeout_s: int) -> None:
        if not api_key:
            msg = "AEAT_LLM_GEMINI_API_KEY must be set for the Gemini provider."
            raise LLMConfigError(msg)
        self._api_key = api_key
        self._timeout_s = timeout_s

    async def complete(self, request: ProviderRequest) -> ProviderCompletion:
        """Execute a completion request."""

        parts: list[dict[str, str]] = []
        if request.system is not None:
            parts.append({"text": f"System instruction:\n{request.system}"})
        parts.append({"text": request.prompt})
        async with httpx.AsyncClient(timeout=self._timeout_s) as client:
            response = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{request.model}:generateContent",
                params={"key": self._api_key},
                json={
                    "contents": [{"role": "user", "parts": parts}],
                    "generationConfig": {
                        "temperature": request.temperature,
                        "maxOutputTokens": request.max_tokens,
                    },
                },
            )
        if response.status_code == 429:
            raise_rate_limit("Gemini rate limit exceeded.", response.headers.get("retry-after"))
        if response.status_code >= 400:
            raise LLMProviderError(f"Gemini API failure ({response.status_code}).")
        parsed = _GeminiResponse.model_validate_json(response.text)
        text = "".join(part.text or "" for part in parsed.candidates[0].content.parts).strip()
        return ProviderCompletion(
            text=text,
            model=request.model,
            input_tokens=parsed.usage_metadata.prompt_token_count,
            output_tokens=parsed.usage_metadata.candidates_token_count,
            provider_request_id=None,
        )
