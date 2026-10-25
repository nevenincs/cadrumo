"""The transport retry policy: transient only, bounded, and taxonomy-scoped.

The retry loop decides from the typed failure an adapter raises and nothing
else, so its cases drive the client's own loop with an adapter that plays one
failure shape per attempt -- a transient transport failure, a provider refusal,
a rate limit carrying a server delay -- and count the attempts that were sent.
The question this policy gets wrong in production is precisely "did it send
that again", and the attempts the adapter received answer it.

The scoping cases matter more than the retrying ones. Re-sending a transient
failure costs a wait; re-sending a refusal re-attempts something the system
already decided not to do.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from .....core.config_support import LLMProvider
from .....core.model_catalogue import ModelRole
from .....tests.fixtures.settings import EnvFileFreeSettings
from ....persistence.llm.cache import LLMCache
from ....persistence.llm.run_records import LLMRunRecorder
from ....persistence.llm.usage import UsageRecorder
from ..client import LLMClient, LLMRetryPolicy, transport_retry_permitted
from ..errors import (
    LLMBusyError,
    LLMCacheError,
    LLMConfigError,
    LLMConsentError,
    LLMError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTransientTransportError,
    LLMValidationError,
)
from ..models import LLMRequest
from ..providers.base import ProviderCompletion
from ._arena_fixtures import _fresh_arena
from .model_run_support import serving_agent
from .scripted_adapter_support import COMPLETION_TEXT, ScriptedAdapter, provider_request

__all__ = ["_fresh_arena"]

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter, pytest.mark.usefixtures("operation")]

# Short enough to keep the suite quick, long enough that a wait is observable.
_FAST_POLICY = LLMRetryPolicy(max_attempts=3, initial_backoff_s=0.02, max_backoff_s=0.1, budget_s=5.0)


def _client(tmp_path: Path, *, policy: LLMRetryPolicy | None = None) -> LLMClient:
    settings = EnvFileFreeSettings(
        cadrumo_llm_cache_dir=tmp_path / "cache",
        cadrumo_llm_usage_dir=tmp_path / "usage",
        cadrumo_llm_run_record_dir=tmp_path / "run-record",
    )
    return LLMClient(
        settings=settings,
        cache=LLMCache(root_dir=settings.cadrumo_llm_cache_dir),
        usage_recorder=UsageRecorder(root_dir=settings.cadrumo_llm_usage_dir),
        run_record_recorder=LLMRunRecorder(root_dir=settings.cadrumo_llm_run_record_dir),
        retry_policy=policy or _FAST_POLICY,
    )


def _dispatch(client: LLMClient, adapter: ScriptedAdapter) -> ProviderCompletion:
    return asyncio.run(client._complete_with_retries(adapter, provider_request()))


def _transient() -> LLMTransientTransportError:
    return LLMTransientTransportError(context={"http_status": 503})


def test_a_transient_failure_is_retried_until_it_succeeds(tmp_path: Path) -> None:
    """Two transient failures then a good answer: the caller sees the completion, three attempts were sent."""
    adapter = ScriptedAdapter([_transient(), _transient(), None])

    completion = _dispatch(_client(tmp_path), adapter)

    assert completion.text == COMPLETION_TEXT
    assert len(adapter.attempts) == 3
    # Every attempt asked the identical question. An attempt that altered the
    # request would be a different question, and its success would say nothing
    # about whether the first one would have worked.
    assert adapter.attempts[0] == adapter.attempts[1] == adapter.attempts[2]


def test_a_provider_refusal_is_never_retried(tmp_path: Path) -> None:
    """A provider refusal is deterministic: the identical request fails identically forever."""
    adapter = ScriptedAdapter([LLMProviderError(context={"http_status": 400})])

    with pytest.raises(LLMProviderError) as raised:
        _dispatch(_client(tmp_path), adapter)

    assert not isinstance(raised.value, LLMTransientTransportError)
    assert len(adapter.attempts) == 1


def test_a_permanently_failing_transport_stops_at_the_attempt_bound(tmp_path: Path) -> None:
    """The budget is bounded: a transport that is simply down does not retry forever."""
    adapter = ScriptedAdapter([_transient()])

    with pytest.raises(LLMTransientTransportError):
        _dispatch(_client(tmp_path), adapter)

    assert len(adapter.attempts) == _FAST_POLICY.max_attempts


def test_the_wall_clock_budget_cuts_the_schedule_short(tmp_path: Path) -> None:
    """A budget smaller than the first backoff stops after the first attempt.

    The attempt count and the budget are separate bounds on purpose: a schedule
    whose waits grow can respect its attempt limit while outliving the
    operator's patience, so the wall clock has to bound it independently.
    """
    starved = LLMRetryPolicy(max_attempts=5, initial_backoff_s=2.0, max_backoff_s=2.0, budget_s=0.1)
    adapter = ScriptedAdapter([_transient()])

    with pytest.raises(LLMTransientTransportError):
        _dispatch(_client(tmp_path, policy=starved), adapter)

    assert len(adapter.attempts) == 1


def test_a_rate_limit_is_retried_and_honours_the_server_delay(tmp_path: Path) -> None:
    """A rate limit carrying a server delay is retried once the delay has passed."""
    adapter = ScriptedAdapter([LLMRateLimitError(retry_after_seconds=0.05), None])

    completion = _dispatch(_client(tmp_path), adapter)

    assert completion.text == COMPLETION_TEXT
    assert len(adapter.attempts) == 2


def test_a_retry_disabled_policy_sends_exactly_once(tmp_path: Path) -> None:
    """The positive control on the retry cases above: one attempt is a real configuration.

    Without it, "three attempts were sent" is consistent with a loop that
    cannot be turned off, and the transient cases would prove only that the
    dispatch runs at all.
    """
    adapter = ScriptedAdapter([_transient()])

    with pytest.raises(LLMTransientTransportError):
        _dispatch(_client(tmp_path, policy=LLMRetryPolicy(max_attempts=1)), adapter)

    assert len(adapter.attempts) == 1


def test_a_consent_refusal_never_reaches_the_service_at_all(tmp_path: Path) -> None:
    """An off-host evidence read without consent is refused before any dispatch.

    Asserted at the service, not at the exception: the property that matters is
    that nothing was SENT, and an exception type alone cannot distinguish
    "refused before dispatch" from "dispatched, then refused".
    """
    request = LLMRequest(
        prompt="read this invoice",
        evidence_derived=True,
        provider_override=LLMProvider.AGENT,
        model_role=ModelRole.TEXT_EXTRACTION,
    )
    with serving_agent() as service, pytest.raises(LLMConsentError):
        asyncio.run(_client(tmp_path).complete(request))

    assert service.runs == []


def _llm_error_classes() -> list[type[LLMError]]:
    """Return every LLM error class the taxonomy currently declares."""
    seen: list[type[LLMError]] = []
    pending: list[type[LLMError]] = [LLMError]
    while pending:
        current = pending.pop()
        if current in seen:
            continue
        seen.append(current)
        pending.extend(current.__subclasses__())
    return seen


def test_only_transport_boundary_failures_are_retryable() -> None:
    """The retryable set is a PROPERTY of the taxonomy, not a list kept beside it.

    Stated as a property rather than an enumeration so it cannot be satisfied by
    updating a constant: a refusal made retryable anywhere in the hierarchy reds
    this, and so does a new retryable class that is not a transport failure.
    """
    retryable = [cls for cls in _llm_error_classes() if transport_retry_permitted(cls("probe"))]

    assert retryable, "the taxonomy declares no retryable failure at all; the policy would be inert"
    for cls in retryable:
        assert issubclass(cls, LLMProviderError), (
            f"{cls.__name__} is declared retryable but is not a provider-transport failure; "
            "only a dispatch that never reached a decision may be re-sent"
        )


@pytest.mark.parametrize(
    "refusal",
    [
        LLMConsentError("off-host read refused"),
        LLMBusyError("arena full"),
        LLMConfigError("cannot carry images"),
        LLMValidationError("bad shape"),
        LLMCacheError("cache write failed"),
    ],
)
def test_a_refusal_is_never_retryable(refusal: LLMError) -> None:
    """Consent, occupancy, capability, schema and storage refusals all stay put.

    Each names a decision the system already took, or a condition that does not
    decay on a timer. Re-sending re-attempts the decision.
    """
    assert transport_retry_permitted(refusal) is False


def test_a_transient_transport_failure_is_retryable() -> None:
    """The discriminating counterpart to the refusals above."""
    assert transport_retry_permitted(LLMTransientTransportError("connection refused")) is True
    assert transport_retry_permitted(LLMRateLimitError("slow down")) is True


def test_an_unregistered_exception_is_not_retryable() -> None:
    """Anything outside the taxonomy has made no statement, so it fails closed."""
    assert transport_retry_permitted(RuntimeError("something leaked from a dependency")) is False


def test_the_backoff_grows_capped_and_never_shortens_a_server_delay() -> None:
    """Backoff is exponential, capped, jittered, and floored by any server hint."""
    policy = LLMRetryPolicy(max_attempts=6, initial_backoff_s=1.0, max_backoff_s=4.0, budget_s=60.0)

    first = [policy.backoff_for(1) for _ in range(40)]
    second = [policy.backoff_for(2) for _ in range(40)]
    assert all(0.5 <= value <= 1.0 for value in first)
    assert all(1.0 <= value <= 2.0 for value in second)
    # Jitter is real, not a constant dressed up as one.
    assert len(set(first)) > 1
    # The cap holds however far the exponent runs.
    assert all(policy.backoff_for(10) <= policy.max_backoff_s for _ in range(20))
    # A server asking for longer wins; it can never ask for shorter.
    assert policy.backoff_for(1, retry_after_s=30.0) == pytest.approx(30.0)
    assert policy.backoff_for(1, retry_after_s=0.0) >= 0.5
