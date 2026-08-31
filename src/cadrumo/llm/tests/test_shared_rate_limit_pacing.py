"""One rate limit paces the whole run, not one request.

A retry schedule paces the request that owns it. A run of N documents therefore
discovers the same account-wide limit N times and issues N calls into a window
that already refused the first -- which is not a rate limit being respected but
N of them being ignored in sequence.

Every case runs real dispatches against a loopback endpoint that answers 429
with a real ``Retry-After``, and observes the window on the SECOND dispatch,
which is the one a per-request policy cannot pace.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Iterator
from contextlib import contextmanager
from http import HTTPStatus
from pathlib import Path
from typing import override

import pytest

from ...adapters.outbound.llm._cache import LLMCache
from ...adapters.outbound.llm._run_telemetry import LLMRunTelemetryRecorder
from ...adapters.outbound.llm._usage import UsageRecorder
from ...core.config import LLMProvider, override_settings
from ...tests.fixtures.settings import EnvFileFreeSettings
from ...tests.loopback_llm import (
    SilentLoopbackHandler,
    ollama_chat_reply,
    read_json_body,
    serving_loopback,
    write_json_response,
)
from ..client import (
    LLMClient,
    LLMRetryPolicy,
    provider_pacing_remaining_s,
    reset_on_host_inference_arena,
    reset_provider_pacing,
)
from ..errors import LLMRateLimitError
from ..models import LLMRequest

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_RETRY_AFTER_S = 0.6


@pytest.fixture(autouse=True)
def _fresh_process_state() -> Iterator[None]:
    """Clear the process-wide gates around each case.

    The pacing outlives a single client by design -- that is the property under
    test -- so a case would otherwise inherit a window armed by its predecessor
    and observe a wait it did not cause.
    """
    reset_provider_pacing()
    reset_on_host_inference_arena()
    yield
    reset_provider_pacing()
    reset_on_host_inference_arena()


@contextmanager
def _serve(*, rate_limited: bool) -> Iterator[tuple[str, list[float]]]:
    """Serve a loopback runtime, recording the arrival time of every request."""
    arrivals: list[float] = []

    class _Endpoint(SilentLoopbackHandler):
        @override
        def do_POST(self) -> None:
            read_json_body(self)
            arrivals.append(time.monotonic())
            limited = rate_limited and len(arrivals) == 1
            write_json_response(
                self,
                {"error": "rate limited"} if limited else ollama_chat_reply(" local completion "),
                status=HTTPStatus.TOO_MANY_REQUESTS if limited else HTTPStatus.OK,
                extra_headers={"retry-after": str(_RETRY_AFTER_S)} if limited else None,
            )

    with serving_loopback(_Endpoint, path="/api/chat") as endpoint:
        yield endpoint, arrivals


def _client(tmp_path: Path, *, attempts: int = 1) -> LLMClient:
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
        retry_policy=LLMRetryPolicy(max_attempts=attempts, initial_backoff_s=0.01, max_backoff_s=0.02, budget_s=30.0),
    )


def test_a_rate_limit_on_one_item_paces_the_next_item(tmp_path: Path) -> None:
    """The run-wide property: the second dispatch waits on the first one's window.

    Measured at the SERVER, on the gap between arrivals, because that is the
    only place the question is decided -- a client that recorded a delay and
    dispatched anyway would look identical from inside.
    """
    with _serve(rate_limited=True) as (endpoint, arrivals), override_settings(cadrumo_llm_ollama_chat_url=endpoint):
        client = _client(tmp_path)
        with pytest.raises(LLMRateLimitError):
            asyncio.run(client.complete(LLMRequest(prompt="first item")))

        assert provider_pacing_remaining_s(LLMProvider.LOCAL) > 0, "the shared window was never armed"

        response = asyncio.run(client.complete(LLMRequest(prompt="second item")))

    assert response.text == "local completion"
    assert len(arrivals) == 2
    gap = arrivals[1] - arrivals[0]
    assert gap >= _RETRY_AFTER_S * 0.8, (
        f"the second dispatch arrived {gap:.2f}s after the first, inside the {_RETRY_AFTER_S}s window "
        "the server asked for; the backoff paced one request rather than the run"
    )


def test_without_a_rate_limit_the_second_item_is_not_delayed(tmp_path: Path) -> None:
    """The positive control, and the proof that the window OPENS rather than merely closing.

    Same two dispatches, same server, same client -- only the 429 differs. It
    establishes both halves at once: that a paced item genuinely would have
    dispatched immediately without the injection, and that the measured gap
    above is the pacing rather than the fixture's own overhead.
    """
    with _serve(rate_limited=False) as (endpoint, arrivals), override_settings(cadrumo_llm_ollama_chat_url=endpoint):
        client = _client(tmp_path)
        asyncio.run(client.complete(LLMRequest(prompt="first item")))
        asyncio.run(client.complete(LLMRequest(prompt="second item")))

    assert provider_pacing_remaining_s(LLMProvider.LOCAL) == 0
    assert len(arrivals) == 2
    gap = arrivals[1] - arrivals[0]
    assert gap < _RETRY_AFTER_S * 0.5, f"an unpaced second dispatch took {gap:.2f}s; the fixture is measuring overhead"


def test_the_window_is_shared_across_clients(tmp_path: Path) -> None:
    """A second client is a second batch item, and the limit belongs to the account.

    Per-client state would pace neither: a run that builds one client per
    document -- which is how the readers are constructed -- would rediscover the
    same limit for every document.
    """
    with _serve(rate_limited=True) as (endpoint, arrivals), override_settings(cadrumo_llm_ollama_chat_url=endpoint):
        with pytest.raises(LLMRateLimitError):
            asyncio.run(_client(tmp_path / "first").complete(LLMRequest(prompt="first item")))

        asyncio.run(_client(tmp_path / "second").complete(LLMRequest(prompt="second item")))

    gap = arrivals[1] - arrivals[0]
    assert gap >= _RETRY_AFTER_S * 0.8


def test_a_limit_discovered_on_the_last_attempt_still_paces_the_run(tmp_path: Path) -> None:
    """The item that gives up must not be the one that tells nobody.

    Arming only where the loop decides to retry would leave the final attempt's
    limit unrecorded, and the next item would walk straight into it -- the
    failure being least visible exactly when the run is already struggling.
    """
    with _serve(rate_limited=True) as (endpoint, _arrivals), override_settings(cadrumo_llm_ollama_chat_url=endpoint):
        # One attempt: the loop never reaches its retry branch at all.
        with pytest.raises(LLMRateLimitError):
            asyncio.run(_client(tmp_path, attempts=1).complete(LLMRequest(prompt="only attempt")))

        assert provider_pacing_remaining_s(LLMProvider.LOCAL) > 0


def test_the_shared_wait_is_bounded_by_the_retry_budget(tmp_path: Path) -> None:
    """A vendor may name a window measured in minutes; a batch must not silently sleep it.

    The window stays armed and readable so a surface can report it, but no
    single dispatch blocks longer than the budget it was given.
    """
    settings = EnvFileFreeSettings(
        cadrumo_llm_provider=LLMProvider.LOCAL,
        cadrumo_llm_model="gpt-oss",
        cadrumo_llm_cache_dir=tmp_path / "cache",
        cadrumo_llm_usage_dir=tmp_path / "usage",
        cadrumo_llm_run_telemetry_dir=tmp_path / "run-telemetry",
    )
    client = LLMClient(
        settings=settings,
        cache=LLMCache(root_dir=settings.cadrumo_llm_cache_dir),
        usage_recorder=UsageRecorder(root_dir=settings.cadrumo_llm_usage_dir),
        run_telemetry_recorder=LLMRunTelemetryRecorder(root_dir=settings.cadrumo_llm_run_telemetry_dir),
        retry_policy=LLMRetryPolicy(max_attempts=1, initial_backoff_s=0.01, max_backoff_s=0.02, budget_s=0.2),
    )

    with _serve(rate_limited=True) as (endpoint, _arrivals), override_settings(cadrumo_llm_ollama_chat_url=endpoint):
        with pytest.raises(LLMRateLimitError):
            asyncio.run(client.complete(LLMRequest(prompt="first item")))

        started = time.monotonic()
        asyncio.run(client.complete(LLMRequest(prompt="second item")))
        waited = time.monotonic() - started

    assert waited < _RETRY_AFTER_S, f"the dispatch slept {waited:.2f}s, past the 0.2s budget it was given"
