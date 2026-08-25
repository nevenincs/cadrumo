"""Async-first public LLM client.

Coordinates :class:`~llm.LLMRequest` inputs,
:class:`~adapters.outbound.llm.LLMCache` lookup/write-through,
:class:`~adapters.outbound.llm.UsageRecorder` accounting, and concrete
:class:`~llm.LLMProvider` adapters before returning an
:class:`~llm.LLMResponse`.
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

from ..core import ActionEvidenceProvenance
from ..core.config import Settings
from ..core.errors import get_registered_error_code
from ..core.hashing import content_hash_hex
from ..core.logging import get_logger
from ..core.time import now
from ._consent import provider_reads_off_host
from .errors import (
    LLMBusyError,
    LLMCacheError,
    LLMConfigError,
    LLMConsentError,
    LLMContentionError,
    LLMRateLimitError,
)
from ._preconditions import LLMPreconditionCondition, llm_no_recovery_verdict

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

    # The headroom measurements the contention authority consumes. Type-only
    # for the same reason as the stores above: the runtime edge into the
    # application package stays deferred to the one call site that needs it.
    from ..application.provisioning import HardwareProfile, RuntimeResident
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
        random_fraction = float(secrets.randbelow(501)) / 1000
        jittered: float = capped * (0.5 + random_fraction)
        if retry_after_s is not None:
            return max(jittered, retry_after_s)
        return jittered


class _ProviderPacing:
    """The process-wide "not before" instant each provider is paced to.

    **A rate limit is a property of the ACCOUNT, not of the request that
    happened to meet it.** One request's retry schedule paces that request and
    nothing else, so a run of N documents each discovers the same limit
    independently and issues N calls into a window that already refused the
    first -- which is not a rate limit being respected, it is N of them being
    ignored in parallel. Arming a shared instant when one dispatch is limited
    makes every LATER dispatch at that provider wait out the same window
    without having to be told about it.

    Process-wide and keyed by provider, for the reason the inference arena is:
    the constraint belongs to the vendor account, which two clients and two
    batch runs share, so per-client state would pace neither. Off-host only in
    practice, because nothing local issues a rate limit.

    Monotonic instants rather than wall-clock, so a clock adjustment mid-run
    cannot arm a wait measured in hours.
    """

    def __init__(self) -> None:
        self._resume_at: dict[LLMProvider, float] = {}
        self._lock = threading.Lock()

    def arm(self, provider: LLMProvider, delay_s: float) -> None:
        """Pace ``provider`` for at least ``delay_s`` from now.

        Never shortens an existing pause: two limits arriving together mean the
        window is at least the longer of the two, and taking the shorter would
        release the run early into the same refusal.
        """
        if delay_s <= 0:
            return
        resume_at = time.monotonic() + delay_s
        with self._lock:
            self._resume_at[provider] = max(self._resume_at.get(provider, 0.0), resume_at)

    def remaining_s(self, provider: LLMProvider) -> float:
        """Return the seconds still owed before ``provider`` may be dispatched at."""
        with self._lock:
            resume_at = self._resume_at.get(provider)
        return 0.0 if resume_at is None else max(0.0, resume_at - time.monotonic())

    def clear(self) -> None:
        """Forget every armed pause."""
        with self._lock:
            self._resume_at.clear()


_PROVIDER_PACING = _ProviderPacing()


def provider_pacing_remaining_s(provider: LLMProvider) -> float:
    """Return how long ``provider`` is still paced for, in seconds.

    Exposed so a batch surface can REPORT that it is waiting on a shared rate
    limit rather than appearing to hang, and so a gate can observe the window
    was armed rather than inferring it from elapsed time alone.
    """
    return _PROVIDER_PACING.remaining_s(provider)


def reset_provider_pacing() -> None:
    """Forget every armed rate-limit pause.

    The pacing outlives a single client by design, so a test (or a genuinely
    new run after an operator resolved a quota) would otherwise inherit a
    window armed elsewhere.
    """
    _PROVIDER_PACING.clear()


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
    typed, and observable at the caller; the caller may retry after quiesce.

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
            :class:`~llm.PromptRegistry` override.
        retry_policy: Optional :class:`LLMRetryPolicy` override governing how
            often and how long a transient transport failure is re-sent. Which
            failures qualify is not tunable here -- that is the error taxonomy's
            answer, read through :func:`transport_retry_permitted`.
        hardware_profile: Optional measured
            :class:`~application.provisioning.HardwareProfile` used for the
            headroom check instead of probing this machine. Injecting the
            MEASUREMENT rather than the verdict keeps the real decision
            function on the path: a post-quiesce reading exercises the same
            comparison, margin and attribution production runs.
        runtime_residents: Optional resident set standing in for a live read of
            the runtime.
        runtime_residents_measured: False states the resident set could not be
            read, which is a different fact from a measured-empty one and
            reaches the fail-closed arm rather than the shortfall arm. The two
            are indistinguishable from the refusal alone, so a case that means
            to prove one must say which.
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
        hardware_profile: HardwareProfile | None = None,
        runtime_residents: tuple[RuntimeResident, ...] | None = None,
        runtime_residents_measured: bool = True,
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
        self.hardware_profile = hardware_profile
        self.runtime_residents = runtime_residents
        self.runtime_residents_measured = runtime_residents_measured
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
            request: Structured :class:`~llm.LLMRequest`.

        Returns:
            A :class:`~llm.LLMResponse` enriched with
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
                # Inside the slot and outside the retry loop, both load-bearing.
                # Inside, because a headroom reading taken before the slot is
                # held can be invalidated by another request loading a model
                # between the measurement and this dispatch. Outside, because a
                # refusal that the retry loop could see would be re-sent on a
                # schedule, turning one refusal into several while the memory it
                # waits for is still held.
                self._require_load_headroom(provider, provider_request.model)
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

    def _require_load_headroom(self, provider: LLMProvider, model: str) -> None:
        """Refuse an on-host dispatch this machine has no measured room for.

        **A wiring job, not a second detector.** The verdict comes from
        :func:`~application.provisioning.assess_model_load_contention`, which
        already owns the comparison, the safety margin, the fail-closed arm and
        the attribution of a shortfall to the runtime's own residents versus a
        peer process's device usage. That authority was deliberately
        consolidated out of four call sites; re-deriving any part of it here
        would undo the consolidation and give the dispatch point a second
        opinion that could disagree with the doctor surface an operator just
        read.

        Resolved through the application package's public facade at call time
        rather than at module load. The edge is downward and permitted, but this
        package is imported BY application code, so an eager binding would risk
        closing that loop at import time -- the same reason the stores above are
        deferred.

        **Assessed only where the catalogue makes a claim.** An uncatalogued
        model has no declared requirement, and inventing one would be worse than
        not checking: a requirement read as zero flows into the authority as the
        amount the model needs, and the check then reports the load ADMITTED on
        evidence nobody has. That is the reasoning
        :attr:`~application.provisioning.ModelSelection.assessable_load` records
        for every other caller, followed here rather than re-decided.

        Args:
            provider: The resolved provider this dispatch would run at.
            model: The resolved model whose load is being judged.

        Raises:
            LLMContentionError: When the measured verdict is not admitted,
                carrying the authority's typed precondition verdict, model, and
                causes.
        """
        if provider_reads_off_host(provider):
            return
        from ..application.provisioning import assess_model_load_contention
        from ..core import model_candidate

        candidate = model_candidate(model)
        requirement_bytes = None if candidate is None else candidate.memory_requirement_bytes
        if requirement_bytes is None:
            return
        snapshot = assess_model_load_contention(
            model,
            requirement_bytes,
            profile=self.hardware_profile,
            residents=self.runtime_residents,
            residents_measured=self.runtime_residents_measured,
            settings=self.settings,
        )
        if snapshot.admitted:
            return
        verdict = snapshot.precondition_verdict
        assert verdict is not None
        raise LLMContentionError(
            context={
                "model": model,
                "contention_causes": tuple(cause.value for cause in snapshot.causes),
            },
            precondition_verdict=verdict,
        )

    @staticmethod
    async def _await_shared_pacing(provider: LLMProvider, policy: LLMRetryPolicy) -> None:
        """Wait out any rate-limit window another dispatch already discovered.

        This is what makes the backoff apply ACROSS a run rather than within one
        request: the second document of a batch waits on the window the first
        one found, instead of issuing its own call into it and learning the same
        thing again.

        Bounded by the retry budget for the same reason every other wait here
        is: a vendor may name a window measured in minutes, and a batch that
        silently sleeps that long is indistinguishable from one that hung. The
        remaining window stays armed and readable, so a surface that wants to
        report "paced for another N seconds" can, rather than blocking on it.
        """
        remaining = min(_PROVIDER_PACING.remaining_s(provider), policy.budget_s)
        if remaining <= 0:
            return
        _LOGGER.info("llm dispatch paced provider=%s waiting=%.2fs", provider.value, remaining)
        await asyncio.sleep(remaining)

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
        await self._await_shared_pacing(adapter.provider, policy)
        while True:
            try:
                return await adapter.complete(provider_request)
            except Exception as exc:  # classification is the taxonomy's job, not this loop's
                delay = policy.backoff_for(attempt, retry_after_s=getattr(exc, "retry_after_seconds", None))
                if isinstance(exc, LLMRateLimitError):
                    # Arm the run-wide window before deciding whether THIS
                    # request may continue: a limit discovered on the last
                    # permitted attempt still governs every dispatch after it,
                    # and arming only on the retrying path would let the item
                    # that gave up be the one that told nobody.
                    _PROVIDER_PACING.arm(adapter.provider, min(delay, policy.budget_s))
                if attempt >= policy.max_attempts or not transport_retry_permitted(exc):
                    raise
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
        :func:`~llm._consent.provider_reads_off_host` rather than a
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
            raise LLMBusyError(
                context={
                    "provider": provider.value,
                    "local_inference_limit": arena.limit,
                    "local_inference_slot_available": False,
                },
                precondition_verdict=llm_no_recovery_verdict(
                    LLMPreconditionCondition.LOCAL_INFERENCE_SLOT_AVAILABLE,
                    facts={
                        "provider": provider.value,
                        "local_inference_limit": arena.limit,
                        "local_inference_slot_available": False,
                    },
                    provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
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
        :attr:`~llm.LLMProvider.LOCAL` as documentation, but
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
                translated_message=_EVIDENCE_CONSENT_DISPATCH_REFUSAL_LOCALE_KEY,
                context={
                    "provider": provider.value,
                    "gestor_mode": self.settings.cadrumo_evidence_gestor_mode,
                    "consent_token_present": token is not None,
                },
                precondition_verdict=llm_no_recovery_verdict(
                    LLMPreconditionCondition.EVIDENCE_OFF_HOST_DISPATCH_PERMITTED,
                    facts={
                        "provider": provider.value,
                        "gestor_mode": self.settings.cadrumo_evidence_gestor_mode,
                        "consent_token_present": token is not None,
                    },
                    provenance=ActionEvidenceProvenance.APPLICATION_STATE,
                ),
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

        :class:`~llm._providers.base.ProviderRequest` carries ``images`` for
        EVERY provider, but only an adapter declaring ``supports_images``
        actually puts them on the wire. Without this gate a text-only adapter
        drops them
        silently and asks the model to read a document it was never sent -- and
        the model answers confidently from nothing. A plausible fabricated
        reading of an invoice is the costliest failure this product has, so the
        boundary refuses rather than degrades.

        Enforced here, at the client's single dispatch point, rather than inside
        each adapter: the same reasoning
        :func:`~llm._providers.base.post_provider_request` records for the
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
        raise LLMConfigError(
            context={
                "provider": provider,
                "image_input_count": len(request.images),
                "vision_input_supported": False,
            },
            precondition_verdict=llm_no_recovery_verdict(
                LLMPreconditionCondition.VISION_INPUT_SUPPORTED,
                facts={
                    "provider": provider,
                    "image_input_count": len(request.images),
                    "vision_input_supported": False,
                },
                provenance=ActionEvidenceProvenance.APPLICATION_STATE,
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
        :exc:`~llm.LLMCacheError` (the recorder's only
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
            raise LLMConfigError(
                context={"configured_provider": raw_provider, "provider_selection_valid": False},
                precondition_verdict=llm_no_recovery_verdict(
                    LLMPreconditionCondition.PROVIDER_SELECTION_VALID,
                    facts={"configured_provider": raw_provider, "provider_selection_valid": False},
                    provenance=ActionEvidenceProvenance.APPLICATION_STATE,
                ),
            ) from exc

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
            from ..core import ANTHROPIC_EXTRA, require_optional_extra

            require_optional_extra(ANTHROPIC_EXTRA)
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
