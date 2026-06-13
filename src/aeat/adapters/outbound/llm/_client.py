"""Async-first public LLM client."""

from __future__ import annotations

import hashlib
import json

from pydantic import SecretStr

from ....core.config import Settings
from ....core.logging import get_logger
from ....core.time import now
from ._cache import LLMCache
from ._errors import LLMConfigError
from ._models import LLMProvider, LLMRequest, LLMResponse, PromptRegistry
from ._pricing import estimate_cost_usd
from ._providers import (
    AnthropicAdapter,
    GeminiAdapter,
    LocalAdapter,
    OpenAIAdapter,
    ProviderRequest,
    _ProviderAdapter,
)
from ._usage import UsageRecorder

_LOGGER = get_logger(__name__)


class LLMClient:
    """Public async-first LLM completion entry point.

    Args:
        settings: Optional settings override used for provider selection and
            defaults.
        cache: Optional cache implementation override.
        usage_recorder: Optional usage recorder override.
        prompt_registry: Optional prompt registry override.
        caller: Stable caller identifier recorded in usage logs.
        prompt_id: Stable prompt identifier recorded in usage logs.
        adapter_override: Optional adapter override for tests and controlled flows.
    """

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        cache: LLMCache | None = None,
        usage_recorder: UsageRecorder | None = None,
        prompt_registry: PromptRegistry | None = None,
        caller: str = "aeat.adapters.outbound.llm.client",
        prompt_id: str = "adhoc",
        adapter_override: _ProviderAdapter | None = None,
    ) -> None:
        self.settings = settings or Settings()
        self.cache = cache or LLMCache(root_dir=self.settings.aeat_llm_cache_dir)
        self.usage_recorder = usage_recorder or UsageRecorder(root_dir=self.settings.aeat_llm_usage_dir)
        self.prompt_registry = prompt_registry or PromptRegistry.seeded()
        self.caller = caller
        self.prompt_id = prompt_id
        self._adapter_override = adapter_override

    async def complete(self, request: LLMRequest) -> LLMResponse:
        """Complete a prompt request.

        Args:
            request: Structured completion request.

        Returns:
            A :class:`LLMResponse` enriched with cache and cost metadata.

        Raises:
            Exception: Re-raised after logging when the LLM provider adapter fails.
        """
        provider = request.provider_override or self._default_provider()
        model = request.model_override or self._default_model(provider)
        request_id = self._request_id(request)
        cached = self.cache.read(request, provider, model)
        if cached is not None:
            response = cached.model_copy(update={"request_id": request_id, "cache_hit": True})
            self.usage_recorder.record(self.usage_recorder.build_record(response, self.prompt_id, self.caller))
            return response

        adapter = self._adapter_override or self._build_adapter(provider)
        provider_request = ProviderRequest(
            request_id=request_id,
            model=model,
            prompt=request.prompt,
            system=request.system,
            max_tokens=request.max_tokens or self.settings.aeat_llm_default_max_tokens,
            temperature=(
                request.temperature if request.temperature is not None else self.settings.aeat_llm_default_temperature
            ),
            timeout_s=self.settings.aeat_llm_default_timeout_s,
            images=tuple(image.base64_data for image in request.images),
        )
        try:
            completion = await adapter.complete(provider_request)
        except Exception:  # LLM provider adapters surface heterogeneous exceptions; log+re-raise at this boundary
            _LOGGER.error(
                "llm request failed provider=%s model=%s request_id=%s",
                provider.value,
                model,
                request_id,
                exc_info=True,
            )
            raise
        response = LLMResponse(
            text=completion.text,
            provider=provider,
            model=completion.model,
            input_tokens=completion.input_tokens,
            output_tokens=completion.output_tokens,
            cost_estimate_usd=estimate_cost_usd(
                provider=provider,
                model=completion.model,
                input_tokens=completion.input_tokens,
                output_tokens=completion.output_tokens,
            ),
            cache_hit=False,
            created_at=now(),
            request_id=request_id,
        )
        self.cache.write(request, response)
        self.usage_recorder.record(self.usage_recorder.build_record(response, self.prompt_id, self.caller))
        _LOGGER.info(
            "llm request completed provider=%s model=%s input_tokens=%d output_tokens=%d",
            provider.value,
            completion.model,
            completion.input_tokens,
            completion.output_tokens,
        )
        return response

    def _default_provider(self) -> LLMProvider:
        raw_provider = self.settings.aeat_llm_provider
        try:
            return LLMProvider(raw_provider)
        except ValueError as exc:
            msg = f"Unsupported AEAT_LLM_PROVIDER value: {raw_provider!r}"
            raise LLMConfigError(msg) from exc

    def _default_model(self, provider: LLMProvider) -> str:
        if provider is self._default_provider():
            return self.settings.aeat_llm_model
        defaults = {
            LLMProvider.ANTHROPIC: "claude-sonnet-4-6",
            LLMProvider.OPENAI: "gpt-4.1",
            LLMProvider.GEMINI: "gemini-2.5-pro",
            LLMProvider.LOCAL: "gpt-oss",
        }
        return defaults[provider]

    def _build_adapter(self, provider: LLMProvider) -> _ProviderAdapter:
        timeout_s = self.settings.aeat_llm_default_timeout_s
        if provider is LLMProvider.ANTHROPIC:
            return AnthropicAdapter(
                api_key=self._unwrap_secret(self.settings.aeat_llm_anthropic_api_key),
                timeout_s=timeout_s,
            )
        if provider is LLMProvider.OPENAI:
            return OpenAIAdapter(
                api_key=self._unwrap_secret(self.settings.aeat_llm_openai_api_key),
                timeout_s=timeout_s,
            )
        if provider is LLMProvider.GEMINI:
            return GeminiAdapter(
                api_key=self._unwrap_secret(self.settings.aeat_llm_gemini_api_key),
                timeout_s=timeout_s,
            )
        return LocalAdapter(timeout_s=timeout_s)

    @staticmethod
    def _unwrap_secret(value: SecretStr | None) -> str:
        """Return the raw secret value for adapter construction.

        Args:
            value: Secret setting value.

        Returns:
            The underlying secret string, or an empty string when unset.
        """
        return "" if value is None else value.get_secret_value()

    @staticmethod
    def _request_id(request: LLMRequest) -> str:
        """Build a stable hash for a request payload.

        Args:
            request: Structured completion request.

        Returns:
            Stable SHA-256 request identifier.
        """
        payload = request.model_dump(mode="json", exclude_none=True)
        material = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(material.encode("utf-8")).hexdigest()
