"""Async-first public LLM client.

Coordinates :class:`~adapters.outbound.llm.LLMRequest` inputs,
:class:`~adapters.outbound.llm.LLMCache` lookup/write-through,
:class:`~adapters.outbound.llm.UsageRecorder` accounting, and concrete
:class:`~adapters.outbound.llm.LLMProvider` adapters before returning an
:class:`~adapters.outbound.llm.LLMResponse`.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from pydantic import SecretStr

from ..core.config import Settings
from ..core.hashing import content_hash_hex
from ..core.i18n import tr
from ..core.logging import get_logger
from ..core.time import now
from ._consent import EVIDENCE_CONSENT_REFUSAL_LOCALE_KEY, provider_reads_off_host
from ._errors import LLMCacheError, LLMConfigError, LLMConsentError

if TYPE_CHECKING:
    # The three persistence-touching stores stay on the CORE side of the
    # boundary (they resolve secure storage; this package must not). They are
    # injected here, so the client needs their TYPES but never constructs
    # them at import time. Type-only imports keep the annotation honest while
    # leaving the runtime edge deferred, which is what breaks the cycle the
    # split creates: the stores import this package for the shared error and
    # model types, and the client refers back to them.
    from ..adapters.outbound.llm import (
        LLMCache,
        LLMRunTelemetryRecorder,
        UsageRecorder,
    )
from ._models import LLMProvider, LLMRequest, LLMResponse, PromptRegistry
from ._pricing import estimate_cost_usd
from ._providers import (
    GeminiAdapter,
    LocalAdapter,
    OpenAIAdapter,
    ProviderRequest,
)
from ._providers.base import _ProviderAdapter

# AnthropicAdapter stays lazy here so provider construction remains behind the
# optional-extra guard in _build_adapter.

_LOGGER = get_logger(__name__)

_EVIDENCE_CONSENT_DISPATCH_REFUSAL_LOCALE_KEY = "llm.evidence.consent.dispatch_refused"


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
        caller: str = "cadrumo.llm.client",
        prompt_id: str = "adhoc",
    ) -> None:
        # Deferred: the three persistence-touching stores live on the CORE side
        # of the boundary and import this package for the shared error and model
        # types, so binding them at module load would close the cycle. Resolved
        # here, at construction, through that package's public facade -- the
        # sanctioned cycle-break target, never a private submodule.
        from ..adapters.outbound.llm import LLMCache, LLMRunTelemetryRecorder, UsageRecorder

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
        self._require_evidence_consent(provider, request)
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
            images=request.images,
        )
        self._require_image_support(adapter, provider_request)
        provider_request = self._omit_unsupported_parameters(adapter, provider_request)
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

    def _require_evidence_consent(self, provider: LLMProvider, request: LLMRequest) -> None:
        """Refuse an off-host dispatch of taxpayer evidence without per-invocation consent.

        The confidentiality boundary, enforced at the client's single dispatch
        point for the reason the image boundary is: which requests may leave the
        host is a property of the DISPATCH, never of each caller remembering to
        pin a provider. A caller may still pin
        :attr:`~adapters.outbound.llm.LLMProvider.LOCAL` as documentation, but
        no pin is load-bearing -- ``extract_invoice_fields_from_text`` is
        exported with none, and a reader constructed with a cloud provider
        reaches the same line as every other request.

        **Ordered before the cache read and before adapter construction, both
        deliberately.** Before the cache read, so priming an entry under consent
        cannot make a later unconsented invocation succeed. Before adapter
        construction, so the refusal is the CONSENT refusal rather than a
        missing-API-key configuration error -- an absent credential is an
        accident that looks like a control, and a gate whose refusal is
        indistinguishable from a misconfiguration cannot be relied on to have
        fired.

        The gestor bar is re-applied here rather than trusted from the token's
        minting site: a deployment that bars off-host reading must refuse even
        if a token reaches this point, because a defence that depends on the
        caller having remembered is not a defence.

        Args:
            provider: The resolved provider this request would dispatch at.
            request: The request, carrying its evidence marker and any token.

        Raises:
            LLMConsentError: When an evidence-derived request would be
                dispatched off-host without a valid per-invocation consent
                token, or in a gestor deployment at all.
        """
        if not request.evidence_derived or not provider_reads_off_host(provider):
            return
        if self.settings.cadrumo_evidence_gestor_mode or request.consent_token is None:
            raise LLMConsentError(
                tr(_EVIDENCE_CONSENT_DISPATCH_REFUSAL_LOCALE_KEY, provider=provider.value),
                suggestion=tr(EVIDENCE_CONSENT_REFUSAL_LOCALE_KEY),
            )

    @staticmethod
    def _omit_unsupported_parameters(adapter: _ProviderAdapter, request: ProviderRequest) -> ProviderRequest:
        """Clear request parameters the resolved model does not accept.

        Enforced at the same single dispatch point as the image boundary, and
        for the same reason: which parameters a model accepts is a property of
        the DISPATCH, never of each adapter remembering to check. Cleared to
        ``None`` here rather than skipped in each adapter's payload builder, so
        one omission decision serves every provider.

        Omitting rather than refusing is deliberate. An unsupported sampling
        parameter has a harmless fallback -- the vendor's own default -- whereas
        the image boundary refuses because its fallback is a model answering
        from a document it never received. The two capability axes therefore
        end in different verbs, and the difference is the size of the harm.
        """
        unsupported = adapter.unsupported_parameters(request.model)
        if not unsupported:
            return request
        cleared = {name: None for name in unsupported if getattr(request, name, None) is not None}
        if not cleared:
            return request
        return request.model_copy(update=cleared)

    @staticmethod
    def _require_image_support(adapter: _ProviderAdapter, request: ProviderRequest) -> None:
        """Refuse a vision request routed at an adapter that cannot carry images.

        :class:`~adapters.outbound.llm.ProviderRequest` carries ``images`` for
        EVERY provider, but only an adapter declaring ``supports_images``
        actually puts them on the wire. Without this gate a text-only adapter
        drops them
        silently and asks the model to read a document it was never sent -- and
        the model answers confidently from nothing. A plausible fabricated
        reading of an invoice is the costliest failure this product has, so the
        boundary refuses rather than degrades.

        Enforced here, at the client's single dispatch point, rather than inside
        each adapter: the same reasoning
        :func:`~adapters.outbound.llm.post_provider_request` records for the
        transport boundary -- a property of the dispatch, never of each
        adapter's memory to catch.

        Args:
            adapter: The resolved provider adapter about to run the request.
            request: The normalized request, carrying any image inputs.

        Raises:
            LLMConfigError: When the request carries images and the adapter does
                not forward them. This is a configuration fault with an
                operator-facing fix (route the vision read at a provider that
                supports it), not a provider or transport failure.
        """
        if not request.images or adapter.supports_images:
            return
        provider = adapter.provider.value
        msg = (
            f"Provider {provider!r} cannot accept images, but this request carries "
            f"{len(request.images)} image input(s); it would be sent as a text-only prompt."
        )
        raise LLMConfigError(
            message=msg,
            suggestion=(
                "Route the vision read at a provider that forwards images "
                "(set CADRUMO_LLM_PROVIDER, or pass provider_override on the request)."
            ),
        )

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
                _llm_run_record()(
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
            from ..core import ANTHROPIC_EXTRA, MissingOptionalExtraError, require_optional_extra

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
        return content_hash_hex(payload)


def _llm_run_record() -> type:
    """Resolve ``LLMRunRecord`` from the core-side telemetry store, deferred.

    The record type lives with the store that persists it, on the core side of
    the boundary. Imported through that package's public facade at call time
    rather than at module load, so the import cycle the split creates never
    closes (see the TYPE_CHECKING block above for why the edge exists at all).
    """
    from ..adapters.outbound.llm import LLMRunRecord

    return LLMRunRecord
