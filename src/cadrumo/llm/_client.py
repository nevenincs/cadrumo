"""Async-first public LLM client.

Coordinates :class:`~adapters.outbound.llm.LLMRequest` inputs,
:class:`~adapters.outbound.llm.LLMCache` lookup/write-through,
:class:`~adapters.outbound.llm.UsageRecorder` accounting, and concrete
:class:`~adapters.outbound.llm.LLMProvider` adapters before returning an
:class:`~adapters.outbound.llm.LLMResponse`.
"""

from __future__ import annotations

import asyncio
import secrets
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from ..core.config import Settings
from ..core.errors import get_registered_error_code
from ..core.hashing import content_hash_hex
from ..core.i18n import tr
from ..core.logging import get_logger
from ..core.time import now
from ._consent import EVIDENCE_CONSENT_REFUSAL_LOCALE_KEY, provider_reads_off_host
from ._errors import LLMBusyError, LLMCacheError, LLMConfigError, LLMConsentError

if TYPE_CHECKING:
    # The three persistence-touching stores stay on the CORE side of the
    # boundary (they resolve secure storage; this package must not). They are
    # injected here, so the client needs their TYPES but never constructs
    # them at import time. Type-only imports keep the annotation honest while
    # leaving the runtime edge deferred, which is what breaks the cycle the
    # split creates: the stores import this package for the shared error and
    # model types, and the client refers back to them.
    from ..adapters.outbound.llm import (
        EvidenceConsentLedger,
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
from ._providers.base import ProviderCompletion, _ProviderAdapter

# AnthropicAdapter stays lazy here so provider construction remains behind the
# optional-extra guard in _build_adapter.

_LOGGER = get_logger(__name__)

_EVIDENCE_CONSENT_DISPATCH_REFUSAL_LOCALE_KEY = "llm.evidence.consent.dispatch_refused"


def _elapsed_ms(monotonic_start: float) -> int:
    """Return the whole-millisecond elapsed duration since ``monotonic_start``."""
    return max(0, round((time.monotonic() - monotonic_start) * 1000))


def transport_retry_permitted(exc: BaseException) -> bool:
    """Whether ``exc`` may be retried by re-sending the identical request.

    **Derived from the error taxonomy, never listed here.** Every
    :class:`~core.errors.CadrumoError` subclass is required to carry a
    registered :class:`~core.errors.ErrorCode`, and that record already declares
    ``retryable`` for the operator-facing envelope. Reading the answer from
    there means a new failure class cannot be silently omitted from a retry set:
    it cannot exist at all without declaring the answer, because the registry
    bind refuses an unregistered subclass at class-creation time. A hand-kept
    set is the shape that has already shipped in this repository carrying half
    its members.

    Anything that is not a registered error is NOT retryable. That is the
    fail-closed direction: an exception leaking from a dependency has made no
    statement about whether re-sending is safe, and inventing one for it is how
    a contention or consent refusal would end up retried by accident.

    Args:
        exc: The exception raised by the provider adapter.

    Returns:
        True only when the taxonomy declares this failure class retryable.
    """
    try:
        return get_registered_error_code(exc).retryable
    except ValueError:
        # An unregistered exception type. Not a retry decision to guess at.
        return False


class LLMRetryPolicy(BaseModel):
    """The typed, bounded retry policy applied to one transport dispatch.

    Data on the client rather than behaviour scattered through the adapters, so
    the answer to "how many times, how long, and for which failures" is one
    readable record instead of four vendor-specific loops.

    **Scoped by the taxonomy, not by this model.** Which failures are eligible
    is :func:`transport_retry_permitted`'s answer, read from the registered
    error code; this model only decides how often and how long. That separation
    is deliberate: the eligibility question has exactly one right answer for the
    whole process, while the timing is a deployment tuning knob.

    Attributes:
        max_attempts: Total attempts including the first. One disables retrying.
        initial_backoff_s: The first backoff, doubling per subsequent attempt.
        max_backoff_s: Ceiling on a single backoff, before jitter.
        budget_s: Total wall-clock ceiling across every attempt and every wait.
            A bounded budget, not merely a bounded count: a retry schedule whose
            waits grow can otherwise outlive the operator's patience while
            technically respecting its attempt limit.
    """

    model_config = ConfigDict(strict=True, frozen=True)

    max_attempts: int = Field(default=3, ge=1)
    initial_backoff_s: float = Field(default=0.5, gt=0.0)
    max_backoff_s: float = Field(default=8.0, gt=0.0)
    budget_s: float = Field(default=30.0, gt=0.0)

    def backoff_for(self, attempt: int, *, retry_after_s: float | None = None) -> float:
        """Return the wait before the attempt following ``attempt``.

        Exponential from :attr:`initial_backoff_s`, capped at
        :attr:`max_backoff_s`, then jittered into the upper half of that
        interval. Jitter is not decoration: without it, a batch that failed
        together retries together, and the synchronised burst is itself a
        plausible cause of the next failure.

        A server-supplied ``Retry-After`` wins whenever it asks for LONGER than
        the computed backoff. It is never allowed to shorten the wait, because a
        vendor's hint about its own rate window says nothing about this
        machine's recovery.

        Args:
            attempt: The 1-based number of the attempt that just failed.
            retry_after_s: A server-supplied delay hint, when the failure
                carried one.

        Returns:
            Seconds to wait before the next attempt.
        """
        exponential = self.initial_backoff_s * (2 ** (attempt - 1))
        capped = min(exponential, self.max_backoff_s)
        # Full-jitter in the upper half: still spreads a synchronised batch,
        # while never collapsing the backoff toward zero the way [0, capped)
        # would on an unlucky draw.
        jittered = capped * (0.5 + secrets.randbelow(501) / 1000)
        if retry_after_s is not None:
            return max(jittered, retry_after_s)
        return jittered


class _OnHostInferenceArena:
    """The process-wide occupancy bound on concurrent on-host inference.

    **Refusal, not queueing, and the choice is argued from the failure
    direction rather than from ergonomics.** A queue does not help when the
    bound is too permissive -- both designs admit whatever the bound says -- and
    it actively hurts when the bound is right: a waiting request holds its
    decoded pages in the very memory under pressure for as long as it waits, so
    the queue itself becomes an allocation that grows with load, and it runs
    against headroom that was measured *before* it waited, which is the one
    reading the contention check exists to keep fresh. A refusal is synchronous,
    typed, and observable at the caller; the caller retries after quiesce, which
    is the same remediation a contention refusal already names.

    Loop-agnostic on purpose. A :class:`asyncio.Semaphore` binds to the event
    loop that created it, and this process runs LLM work under several
    short-lived loops (each ``asyncio.run`` from a synchronous CLI path opens a
    new one), so a loop-bound primitive would silently bound nothing across
    them. The occupancy count is guarded by a plain
    :class:`threading.Lock` instead, which holds across loops and threads
    alike, and is only ever held for the duration of an integer comparison --
    never across an await.
    """

    def __init__(self, limit: int) -> None:
        self._limit = limit
        self._held = 0
        self._lock = threading.Lock()

    @property
    def limit(self) -> int:
        """Return the configured number of simultaneous on-host inference slots."""
        return self._limit

    @property
    def held(self) -> int:
        """Return how many slots are occupied right now."""
        with self._lock:
            return self._held

    def try_acquire(self) -> bool:
        """Take a slot if one is free, without ever blocking.

        Returns:
            True when a slot was taken and the caller must release it; False
            when the arena is full and the caller must refuse.
        """
        with self._lock:
            if self._held >= self._limit:
                return False
            self._held += 1
            return True

    def release(self) -> None:
        """Give a slot back.

        Raises:
            RuntimeError: When more releases than acquisitions have run. This is
                a bug in the dispatch path rather than an operator condition,
                and it must be loud: a release that silently underflows would
                let the arena admit more than its limit forever after, which is
                the failure this whole class exists to prevent.
        """
        with self._lock:
            if self._held <= 0:
                msg = "on-host inference arena released more slots than it holds"
                raise RuntimeError(msg)
            self._held -= 1


_ON_HOST_ARENA: _OnHostInferenceArena | None = None
_ON_HOST_ARENA_LOCK = threading.Lock()


def _on_host_inference_arena(settings: Settings) -> _OnHostInferenceArena:
    """Return the process-wide on-host inference arena, sized on first use.

    A singleton for the reason the bound exists at all: the resource it protects
    is the machine, not the client object, so two :class:`LLMClient` instances
    -- which production builds freely, one per caller -- must contend for the
    same slots. Sized from settings at first use rather than rebuilt per client,
    because a rebuild would hand a fresh, empty arena to the second client and
    the bound would hold for neither.
    """
    global _ON_HOST_ARENA
    with _ON_HOST_ARENA_LOCK:
        if _ON_HOST_ARENA is None:
            _ON_HOST_ARENA = _OnHostInferenceArena(settings.cadrumo_llm_local_inference_concurrency)
        return _ON_HOST_ARENA


def reset_on_host_inference_arena() -> None:
    """Drop the process-wide arena so the next dispatch rebuilds it from settings.

    Exists because the arena is sized once per process while settings are
    per-configuration: a test (or a genuine settings reload) that changes the
    concurrency bound would otherwise keep the first size forever.

    Raises:
        RuntimeError: When a slot is currently held. Rebuilding under an
            in-flight request would hand the next arrival an empty arena while
            a real inference is still resident, which is precisely the double
            load the bound prevents -- so this refuses rather than resetting.
    """
    global _ON_HOST_ARENA
    with _ON_HOST_ARENA_LOCK:
        if _ON_HOST_ARENA is not None and _ON_HOST_ARENA.held:
            msg = "cannot reset the on-host inference arena while a slot is held"
            raise RuntimeError(msg)
        _ON_HOST_ARENA = None


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
        retry_policy: Optional :class:`LLMRetryPolicy` override governing how
            often and how long a transient transport failure is re-sent. Which
            failures qualify is not tunable here -- that is the error taxonomy's
            answer, read through :func:`transport_retry_permitted`.
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
        consent_ledger: EvidenceConsentLedger | None = None,
        prompt_registry: PromptRegistry | None = None,
        retry_policy: LLMRetryPolicy | None = None,
        caller: str = "cadrumo.llm.client",
        prompt_id: str = "adhoc",
    ) -> None:
        # Deferred: the three persistence-touching stores live on the CORE side
        # of the boundary and import this package for the shared error and model
        # types, so binding them at module load would close the cycle. Resolved
        # here, at construction, through that package's public facade -- the
        # sanctioned cycle-break target, never a private submodule.
        from ..adapters.outbound.llm import (
            EvidenceConsentLedger,
            LLMCache,
            LLMRunTelemetryRecorder,
            UsageRecorder,
        )

        self.settings = settings or Settings()
        self.cache = cache or LLMCache(root_dir=self.settings.cadrumo_llm_cache_dir)
        self.usage_recorder = usage_recorder or UsageRecorder(root_dir=self.settings.cadrumo_llm_usage_dir)
        self.run_telemetry_recorder = run_telemetry_recorder or LLMRunTelemetryRecorder(
            root_dir=self.settings.cadrumo_llm_run_telemetry_dir,
        )
        # Not swept by _sweep_retention_stores below, and deliberately so: the
        # consent ledger is an audit trail a withdrawal reads, not a diagnostic
        # store, so it has no prune to call.
        self.consent_ledger = consent_ledger or EvidenceConsentLedger()
        self.prompt_registry = prompt_registry or PromptRegistry.seeded()
        self.retry_policy = retry_policy or LLMRetryPolicy()
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
        self._require_evidence_consent(provider, model, request)
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
            with self._on_host_admission(provider):
                completion = await self._complete_with_retries(adapter, provider_request)
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

    async def _complete_with_retries(
        self,
        adapter: _ProviderAdapter,
        provider_request: ProviderRequest,
    ) -> ProviderCompletion:
        """Run one dispatch, re-sending it only while the taxonomy permits.

        **Inside the admission slot, not around it.** A retrying request keeps
        its on-host slot across its waits, which is the safe direction:
        releasing it would let a second request take the arena and turn this
        one's next attempt into a busy refusal -- converting a transient
        failure into a different refusal for no reason. The bounded budget is
        what keeps holding the slot honest.

        The budget is checked BEFORE sleeping, so a wait that would outlive the
        budget is not taken at all: the caller gets the real failure at the
        moment the budget is spent rather than after one last pointless pause.

        Args:
            adapter: The resolved provider adapter.
            provider_request: The normalized request, re-sent unchanged on every
                attempt -- an attempt that altered the request would be a
                different question, and its success would not mean the first one
                would have worked.

        Returns:
            The provider completion from whichever attempt succeeded.

        Raises:
            Exception: The final attempt's failure, re-raised unchanged, so a
                caller still sees the typed refusal it would have seen with no
                retry policy at all.
        """
        policy = self.retry_policy
        started = time.monotonic()
        attempt = 1
        while True:
            try:
                return await adapter.complete(provider_request)
            except Exception as exc:  # classification is the taxonomy's job, not this loop's
                if attempt >= policy.max_attempts or not transport_retry_permitted(exc):
                    raise
                delay = policy.backoff_for(attempt, retry_after_s=getattr(exc, "retry_after_seconds", None))
                if time.monotonic() - started + delay > policy.budget_s:
                    raise
                _LOGGER.info(
                    "llm transport retry attempt=%d/%d after=%s in=%.2fs",
                    attempt,
                    policy.max_attempts,
                    type(exc).__name__,
                    delay,
                )
                await asyncio.sleep(delay)
                attempt += 1

    @contextmanager
    def _on_host_admission(self, provider: LLMProvider) -> Iterator[None]:
        """Hold one on-host inference slot for the duration of a dispatch.

        Applied at the client's single dispatch point, like every other boundary
        on this path, and scoped to on-host providers through
        :func:`~adapters.outbound.llm.provider_reads_off_host` rather than a
        hand-kept list of local transports -- so a provider added later is
        off-host by construction, and correctly unbounded here, because an
        off-host dispatch occupies none of this machine's device memory. The
        resource this bound protects is local, so the bound is local too.

        Wrapped around the adapter call ONLY, not around the whole method: a
        cache hit runs no inference and returns before this point, and holding a
        slot through a cache read would refuse a second request over work that
        never touches the device.

        Args:
            provider: The resolved provider this dispatch runs at.

        Yields:
            Nothing; the slot is held for the body and released on any exit.

        Raises:
            LLMBusyError: When every on-host slot is already occupied.
        """
        if provider_reads_off_host(provider):
            yield
            return
        arena = _on_host_inference_arena(self.settings)
        if not arena.try_acquire():
            msg = (
                f"This process already runs {arena.limit} on-host inference request(s), "
                f"its configured maximum, so this one was refused rather than queued."
            )
            raise LLMBusyError(
                message=msg,
                suggestion=(
                    "Retry once the running read finishes. Raise "
                    "CADRUMO_LLM_LOCAL_INFERENCE_CONCURRENCY only on a machine with "
                    "headroom for a second simultaneous model load."
                ),
            )
        try:
            yield
        finally:
            arena.release()

    def _require_evidence_consent(self, provider: LLMProvider, model: str, request: LLMRequest) -> None:
        """Refuse an off-host dispatch of taxpayer evidence without consent.

        Per-invocation consent is required; permitted dispatches are recorded.

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

        **The audit append lives here, in the branch that HONOURS the token,
        not beside it.** Recording and permitting are one code path, so the
        ledger is complete by construction rather than by every caller
        remembering: there is no ordering in which a consented request reaches
        the cache read, an adapter, or the wire without its entry already
        written. The append is allowed to raise for the same reason -- a
        best-effort log that can silently miss an entry is worse than none,
        because a later audit reads it as complete. A failed append therefore
        refuses the dispatch.

        The append is also ahead of the cache read, so a consented invocation
        served from a primed entry is recorded too. That is the honest side to
        err on: the response is still cloud-derived, so a withdrawal must list
        it as a re-derivation candidate.

        Args:
            provider: The resolved provider this request would dispatch at.
            model: The resolved model this request would dispatch at, recorded
                in the ledger entry.
            request: The request, carrying its evidence marker and any token.

        Raises:
            LLMConsentError: When an evidence-derived request would be
                dispatched off-host without a valid per-invocation consent
                token, in a gestor deployment at all, or when the consent
                ledger cannot record the permitted dispatch.
        """
        if not request.evidence_derived or not provider_reads_off_host(provider):
            return
        token = request.consent_token
        if self.settings.cadrumo_evidence_gestor_mode or token is None:
            raise LLMConsentError(
                tr(_EVIDENCE_CONSENT_DISPATCH_REFUSAL_LOCALE_KEY, provider=provider.value),
                suggestion=tr(EVIDENCE_CONSENT_REFUSAL_LOCALE_KEY),
            )
        self.consent_ledger.append(
            evidence_content_address=token.evidence_content_address,
            provider=provider.value,
            model=model,
            surface=token.surface,
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
