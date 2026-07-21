"""Async-first public LLM client.

Coordinates :class:`~adapters.outbound.llm.LLMRequest` inputs,
:class:`~adapters.outbound.llm.LLMCache` lookup/write-through,
:class:`~adapters.outbound.llm.UsageRecorder` accounting, and concrete
:class:`~adapters.outbound.llm.LLMProvider` adapters before returning an
:class:`~adapters.outbound.llm.LLMResponse`.
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from uuid import uuid4

from pydantic import SecretStr

from ....core.config import Settings
from ....core.hashing import sha256_hex
from ....core.logging import get_logger
from ....core.time import now
from ._cache import LLMCache
from ._errors import LLMCacheError, LLMConfigError
from ._models import LLMProvider, LLMRequest, LLMResponse, PromptRegistry
from ._pricing import estimate_cost_usd
from ._providers import (
    GeminiAdapter,
    LocalAdapter,
    OpenAIAdapter,
    ProviderRequest,
)
from ._providers.base import _ProviderAdapter
from ._run_telemetry import LLMRunRecord, LLMRunTelemetryRecorder

# AnthropicAdapter stays lazy here so provider construction remains behind the
# optional-extra guard in _build_adapter.
from ._usage import UsageRecorder

_LOGGER = get_logger(__name__)


def _elapsed_ms(monotonic_start: float) -> int:
    """Return the whole-millisecond elapsed duration since ``monotonic_start``."""
    return max(0, round((time.monotonic() - monotonic_start) * 1000))


class LLMClient:
    """Public async-first LLM completion entry point.

    Args:
        settings: Optional :class:`~core.config.Settings` override used
            for provider selection and defaults.
        cache: Optional :class:`~adapters.outbound.llm.LLMCache`
            implementation override.
        usage_recorder: Optional
            :class:`~adapters.outbound.llm.UsageRecorder` override.
        run_telemetry_recorder: Optional
            :class:`~adapters.outbound.llm.LLMRunTelemetryRecorder` override.
        prompt_registry: Optional
            :class:`~adapters.outbound.llm.PromptRegistry` override.
        caller: Stable caller identifier recorded in usage logs.
        prompt_id: Stable prompt identifier recorded in usage logs.
    """

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        cache: LLMCache | None = None,
        usage_recorder: UsageRecorder | None = None,
        run_telemetry_recorder: LLMRunTelemetryRecorder | None = None,
        prompt_registry: PromptRegistry | None = None,
        caller: str = "cadrumo.adapters.outbound.llm.client",
        prompt_id: str = "adhoc",
    ) -> None:
        self.settings = settings or Settings()
        self.cache = cache or LLMCache(root_dir=self.settings.cadrumo_llm_cache_dir)
        self.usage_recorder = usage_recorder or UsageRecorder(root_dir=self.settings.cadrumo_llm_usage_dir)
        self.run_telemetry_recorder = run_telemetry_recorder or LLMRunTelemetryRecorder(
            root_dir=self.settings.cadrumo_llm_run_telemetry_dir,
        )
        self.prompt_registry = prompt_registry or PromptRegistry.seeded()
        self.caller = caller
        self.prompt_id = prompt_id
        self._sweep_retention_stores()

    def _sweep_retention_stores(self) -> None:
        """Enforce the retention lifecycle for the three LLM diagnostic stores.

        Building an :class:`LLMClient` is the once-per-run production entry point
        into the LLM surface, so pruning the response cache, usage records, and
        run-telemetry here bounds their growth without a separate scheduler and
        without pruning on every append (which would rescan the whole encrypted
        store per call). Each prune is best-effort and independent: a failure of
        one (or an absent active bucket at construction time) is logged and never
        blocks client construction or the other prunes.
        """
        for label, prune in (
            ("cache", self.cache.prune),
            ("usage", self.usage_recorder.prune),
            ("run_telemetry", self.run_telemetry_recorder.prune),
        ):
            try:
                prune()
            except Exception:  # LLM stores are diagnostic; retention must never block a client
                _LOGGER.debug("llm retention sweep failed for %s store", label, exc_info=True)

    async def complete(self, request: LLMRequest) -> LLMResponse:
        """Complete a prompt request.

        Args:
            request: Structured :class:`~adapters.outbound.llm.LLMRequest`.

        Returns:
            A :class:`~adapters.outbound.llm.LLMResponse` enriched with
            cache and cost metadata.

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

        adapter = self._build_adapter(provider)
        provider_request = ProviderRequest(
            request_id=request_id,
            model=model,
            prompt=request.prompt,
            system=request.system,
            max_tokens=request.max_tokens or self.settings.cadrumo_llm_default_max_tokens,
            temperature=(
                request.temperature
                if request.temperature is not None
                else self.settings.cadrumo_llm_default_temperature
            ),
            timeout_s=self.settings.cadrumo_llm_default_timeout_s,
            images=tuple(image.base64_data for image in request.images),
        )
        run_started_at = now()
        run_clock_start = time.monotonic()
        try:
            completion = await adapter.complete(provider_request)
        except Exception as exc:  # LLM provider adapters surface heterogeneous exceptions; log+re-raise here
            _LOGGER.error(
                "llm request failed provider=%s model=%s request_id=%s",
                provider.value,
                model,
                request_id,
                exc_info=True,
            )
            self._record_run_telemetry(
                provider=provider.value,
                model=model,
                started_at=run_started_at,
                duration_ms=_elapsed_ms(run_clock_start),
                succeeded=False,
                error_kind=type(exc).__name__,
            )
            raise
        self._record_run_telemetry(
            provider=provider.value,
            model=completion.model,
            started_at=run_started_at,
            duration_ms=_elapsed_ms(run_clock_start),
            succeeded=True,
            error_kind="",
        )
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

    def _record_run_telemetry(
        self,
        *,
        provider: str,
        model: str,
        started_at: datetime,
        duration_ms: int,
        succeeded: bool,
        error_kind: str,
    ) -> None:
        """Best-effort append of one local run-timing record.

        A run-telemetry write failure must never mask the real completion
        result or a real provider error, so this swallows
        :exc:`~adapters.outbound.llm.LLMCacheError` (the recorder's only
        declared failure mode) after a debug log; the completion call's own
        return or exception always wins.
        """
        try:
            self.run_telemetry_recorder.record(
                LLMRunRecord(
                    run_id=uuid4().hex,
                    caller=self.caller,
                    provider=provider,
                    model=model,
                    duration_ms=duration_ms,
                    succeeded=succeeded,
                    error_kind=error_kind,
                    started_at=started_at,
                ),
            )
        except LLMCacheError:
            _LOGGER.debug("llm run-telemetry write failed; continuing without it", exc_info=True)

    def _default_provider(self) -> LLMProvider:
        raw_provider = self.settings.cadrumo_llm_provider
        try:
            return LLMProvider(raw_provider)
        except ValueError as exc:
            msg = f"Unsupported CADRUMO_LLM_PROVIDER value: {raw_provider!r}"
            raise LLMConfigError(msg) from exc

    def _default_model(self, provider: LLMProvider) -> str:
        if provider is self._default_provider():
            return self.settings.cadrumo_llm_model
        defaults = {
            LLMProvider.ANTHROPIC: "claude-sonnet-4-6",
            LLMProvider.OPENAI: "gpt-4.1",
            LLMProvider.GEMINI: "gemini-2.5-pro",
            LLMProvider.LOCAL: "gpt-oss",
        }
        return defaults[provider]

    def _build_adapter(self, provider: LLMProvider) -> _ProviderAdapter:
        timeout_s = self.settings.cadrumo_llm_default_timeout_s
        if provider is LLMProvider.ANTHROPIC:
            # The Anthropic-API provider needs the optional `anthropic` extra. Guard
            # before the lazy import so a missing extra is an instructive
            # LLMConfigError, not a deep ModuleNotFoundError.
            from ....core import ANTHROPIC_EXTRA, MissingOptionalExtraError, require_optional_extra

            try:
                require_optional_extra(ANTHROPIC_EXTRA)
            except MissingOptionalExtraError as exc:
                raise LLMConfigError(message=str(exc), suggestion=exc.install_hint) from exc
            from ._providers.anthropic import AnthropicAdapter

            return AnthropicAdapter(
                api_key=self._unwrap_secret(self.settings.cadrumo_llm_anthropic_api_key),
                timeout_s=timeout_s,
            )
        if provider is LLMProvider.OPENAI:
            return OpenAIAdapter(
                api_key=self._unwrap_secret(self.settings.cadrumo_llm_openai_api_key),
                timeout_s=timeout_s,
            )
        if provider is LLMProvider.GEMINI:
            return GeminiAdapter(
                api_key=self._unwrap_secret(self.settings.cadrumo_llm_gemini_api_key),
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
        return sha256_hex(material.encode("utf-8"))
