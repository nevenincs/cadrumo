"""The transport retry policy: transient only, bounded, and taxonomy-scoped.

Every dispatch case here runs against a real loopback HTTP server scripted to
exhibit one genuine failure shape -- a 5xx, a 4xx, a 2xx whose body does not
match the provider schema, a connection dropped mid-request -- and counts what
actually arrived at the server. Nothing is patched and no transport is
simulated, because the question this policy gets wrong in production is
precisely "did it send that again", which only the receiving end can answer.

The scoping cases matter more than the retrying ones. Re-sending a transient
failure costs a wait; re-sending a refusal re-attempts something the system
already decided not to do.
"""

from __future__ import annotations

import asyncio
import json
import threading
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from http import HTTPStatus
from pathlib import Path
from typing import override

import pytest

from ...adapters.outbound.llm import LLMCache, LLMRunTelemetryRecorder, UsageRecorder
from ...core.config import LLMProvider, override_settings
from ...tests.fixtures.settings import EnvFileFreeSettings
from ...tests.loopback_llm import (
    SilentLoopbackHandler,
    ollama_chat_reply,
    read_json_body,
    serving_loopback,
    write_raw_response,
)
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
from ._arena_fixtures import _fresh_arena

__all__ = ["_fresh_arena"]

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_OK_BODY: Mapping[str, object] = ollama_chat_reply(" local completion ")

# Short enough to keep the suite quick, long enough that a wait is observable.
_FAST_POLICY = LLMRetryPolicy(max_attempts=3, initial_backoff_s=0.02, max_backoff_s=0.1, budget_s=5.0)


@dataclass
class _Script:
    """What the loopback runtime does, response by response.

    Attributes:
        responses: One ``(status, body)`` per arrival; the last entry repeats
            once the script is exhausted, so a "always fails" case needs one row.
        drop_connection: Arrival indices (0-based) where the server accepts the
            request and then closes without answering -- a real
            ``httpx.RemoteProtocolError``, which is what a runtime dying
            mid-load looks like from here.
        retry_after: Optional ``Retry-After`` header value sent with a 429.
        bodies: Every request body the server received, in arrival order.
    """

    responses: list[tuple[HTTPStatus, object]]
    drop_connection: frozenset[int] = frozenset()
    retry_after: str | None = None
    bodies: list[dict[str, object]] = field(default_factory=list)

    @property
    def arrivals(self) -> int:
        """Return how many requests actually reached the server."""
        return len(self.bodies)


@contextmanager
def _serve_scripted(script: _Script) -> Iterator[str]:
    """Serve ``/api/chat`` on loopback following ``script``."""
    lock = threading.Lock()

    class _Endpoint(SilentLoopbackHandler):
        @override
        def do_POST(self) -> None:
            body = read_json_body(self)
            with lock:
                index = len(script.bodies)
                script.bodies.append(dict(body))
            if index in script.drop_connection:
                self.close_connection = True
                return
            status, payload = script.responses[min(index, len(script.responses) - 1)]
            # The schema-violating case sends a body that is NOT valid JSON, so
            # it goes out verbatim rather than through the serialising writer.
            encoded = payload.encode("utf-8") if isinstance(payload, str) else json.dumps(payload).encode("utf-8")
            retry_after = script.retry_after if status is HTTPStatus.TOO_MANY_REQUESTS else None
            write_raw_response(
                self,
                encoded,
                status=status,
                extra_headers={"retry-after": retry_after} if retry_after is not None else None,
            )

    with serving_loopback(_Endpoint, path="/api/chat") as endpoint:
        yield endpoint


def _client(tmp_path: Path, *, policy: LLMRetryPolicy | None = None) -> LLMClient:
    settings = EnvFileFreeSettings(
        cadrumo_llm_provider=LLMProvider.LOCAL,
        cadrumo_llm_model="gpt-oss",
        cadrumo_llm_cache_dir=tmp_path / "cache",
        cadrumo_llm_usage_dir=tmp_path / "usage",
        cadrumo_llm_run_telemetry_dir=tmp_path / "run-telemetry",
    )
    return LLMClient(
        settings=settings,
        cache=LLMCache(root_dir=settings.cadrumo_llm_cache_dir),
        usage_recorder=UsageRecorder(root_dir=settings.cadrumo_llm_usage_dir),
        run_telemetry_recorder=LLMRunTelemetryRecorder(root_dir=settings.cadrumo_llm_run_telemetry_dir),
        retry_policy=policy or _FAST_POLICY,
    )


def test_a_transient_server_error_is_retried_until_it_succeeds(tmp_path: Path) -> None:
    """Two 5xx answers then a good one: the caller sees the completion, the server sees three arrivals."""
    script = _Script(
        responses=[
            (HTTPStatus.SERVICE_UNAVAILABLE, {"error": "loading"}),
            (HTTPStatus.BAD_GATEWAY, {"error": "loading"}),
            (HTTPStatus.OK, _OK_BODY),
        ],
    )
    with _serve_scripted(script) as endpoint, override_settings(cadrumo_llm_ollama_chat_url=endpoint):
        response = asyncio.run(_client(tmp_path).complete(LLMRequest(prompt="hello")))

    assert response.text == "local completion"
    assert script.arrivals == 3
    # Every attempt asked the identical question. An attempt that altered the
    # request would be a different question, and its success would say nothing
    # about whether the first one would have worked.
    assert script.bodies[0] == script.bodies[1] == script.bodies[2]


def test_a_dropped_connection_is_retried(tmp_path: Path) -> None:
    """A runtime that accepts and dies mid-request is the transient case the design names."""
    script = _Script(responses=[(HTTPStatus.OK, _OK_BODY)], drop_connection=frozenset({0, 1}))
    with _serve_scripted(script) as endpoint, override_settings(cadrumo_llm_ollama_chat_url=endpoint):
        response = asyncio.run(_client(tmp_path).complete(LLMRequest(prompt="hello")))

    assert response.text == "local completion"
    assert script.arrivals == 3


def test_a_client_error_is_never_retried(tmp_path: Path) -> None:
    """A 4xx is deterministic: the identical request fails identically forever."""
    script = _Script(responses=[(HTTPStatus.BAD_REQUEST, {"error": "bad model"})])
    with (
        _serve_scripted(script) as endpoint,
        override_settings(cadrumo_llm_ollama_chat_url=endpoint),
        pytest.raises(LLMProviderError) as raised,
    ):
        asyncio.run(_client(tmp_path).complete(LLMRequest(prompt="hello")))

    assert not isinstance(raised.value, LLMTransientTransportError)
    assert script.arrivals == 1


def test_a_schema_refusal_is_never_retried(tmp_path: Path) -> None:
    """A 2xx whose body does not match the provider schema is a semantic failure.

    Retrying it would launder a wrong answer into a retry statistic, and the
    server would return the same wrong shape every time.
    """
    script = _Script(responses=[(HTTPStatus.OK, {"model": "gpt-oss", "unexpected": True})])
    with (
        _serve_scripted(script) as endpoint,
        override_settings(cadrumo_llm_ollama_chat_url=endpoint),
        pytest.raises(LLMProviderError) as raised,
    ):
        asyncio.run(_client(tmp_path).complete(LLMRequest(prompt="hello")))

    assert raised.value.context == {
        "provider_name": LLMProvider.LOCAL.value,
        "provider_response_error_type": "ValidationError",
        "provider_response_valid": False,
    }
    assert script.arrivals == 1


def test_a_permanently_failing_runtime_stops_at_the_attempt_bound(tmp_path: Path) -> None:
    """The budget is bounded: a runtime that is simply down does not retry forever."""
    script = _Script(responses=[(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "down"})])
    with (
        _serve_scripted(script) as endpoint,
        override_settings(cadrumo_llm_ollama_chat_url=endpoint),
        pytest.raises(LLMTransientTransportError),
    ):
        asyncio.run(_client(tmp_path).complete(LLMRequest(prompt="hello")))

    assert script.arrivals == _FAST_POLICY.max_attempts


def test_the_wall_clock_budget_cuts_the_schedule_short(tmp_path: Path) -> None:
    """A budget smaller than the first backoff stops after the first attempt.

    The attempt count and the budget are separate bounds on purpose: a schedule
    whose waits grow can respect its attempt limit while outliving the
    operator's patience, so the wall clock has to bound it independently.
    """
    starved = LLMRetryPolicy(max_attempts=5, initial_backoff_s=2.0, max_backoff_s=2.0, budget_s=0.1)
    script = _Script(responses=[(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "down"})])
    with (
        _serve_scripted(script) as endpoint,
        override_settings(cadrumo_llm_ollama_chat_url=endpoint),
        pytest.raises(LLMTransientTransportError),
    ):
        asyncio.run(_client(tmp_path, policy=starved).complete(LLMRequest(prompt="hello")))

    assert script.arrivals == 1


def test_a_rate_limit_is_retried_and_honours_the_server_delay(tmp_path: Path) -> None:
    """A 429 carrying Retry-After is retried, and the server's delay is not shortened."""
    script = _Script(
        responses=[(HTTPStatus.TOO_MANY_REQUESTS, {"error": "slow down"}), (HTTPStatus.OK, _OK_BODY)],
        retry_after="0.05",
    )
    with _serve_scripted(script) as endpoint, override_settings(cadrumo_llm_ollama_chat_url=endpoint):
        response = asyncio.run(_client(tmp_path).complete(LLMRequest(prompt="hello")))

    assert response.text == "local completion"
    assert script.arrivals == 2


def test_a_retry_disabled_policy_sends_exactly_once(tmp_path: Path) -> None:
    """The positive control on the retry cases above: one attempt is a real configuration.

    Without it, "the server saw three arrivals" is consistent with a loop that
    cannot be turned off, and the transient cases would prove only that the
    dispatch runs at all.
    """
    script = _Script(responses=[(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "down"})])
    once = LLMRetryPolicy(max_attempts=1)
    with (
        _serve_scripted(script) as endpoint,
        override_settings(cadrumo_llm_ollama_chat_url=endpoint),
        pytest.raises(LLMTransientTransportError),
    ):
        asyncio.run(_client(tmp_path, policy=once).complete(LLMRequest(prompt="hello")))

    assert script.arrivals == 1


def test_a_consent_refusal_never_reaches_the_transport_at_all(tmp_path: Path) -> None:
    """An off-host evidence read without consent is refused before any dispatch.

    Asserted at the server, not at the exception: the property that matters is
    that nothing was SENT, and an exception type alone cannot distinguish
    "refused before dispatch" from "dispatched, then refused".
    """
    script = _Script(responses=[(HTTPStatus.OK, _OK_BODY)])
    request = LLMRequest(prompt="read this invoice", evidence_derived=True, provider_override=LLMProvider.OPENAI)
    with (
        _serve_scripted(script) as endpoint,
        override_settings(cadrumo_llm_ollama_chat_url=endpoint),
        pytest.raises(LLMConsentError),
    ):
        asyncio.run(_client(tmp_path).complete(request))

    assert script.arrivals == 0


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
