"""The process-wide bound on concurrent on-host inference.

Every case here drives two REAL concurrent requests through the production
:class:`LLMClient`, the production ``LocalAdapter`` and real HTTP against a
loopback Ollama-shaped service that holds the first request open until the
second has been admitted or refused. Nothing is patched, and no semaphore is
simulated: the arrival ordering is established by the server telling the test it
has the first request, so the second one genuinely contends.

The bound exists because two simultaneous model loads on consumer hardware are
an out-of-memory kill that takes the FIRST read down with it, so a test that
proved the refusal by stubbing the gate would prove nothing about the machine.
"""

from __future__ import annotations

import asyncio
import contextvars
import threading
from collections.abc import Generator
from contextlib import contextmanager
from http import HTTPStatus
from pathlib import Path
from queue import Queue
from typing import override

import pytest

from ...adapters.outbound.llm.cache import LLMCache
from ...adapters.outbound.llm.run_telemetry import LLMRunTelemetryRecorder
from ...adapters.outbound.llm.usage import UsageRecorder
from ...core.config import LLMProvider, override_settings
from ...core.operator_action_enums import NoRecoveryOutcome
from ...tests.fixtures.settings import EnvFileFreeSettings
from ...tests.loopback_llm import (
    SilentLoopbackHandler,
    ollama_chat_reply,
    read_json_body,
    serving_loopback,
    write_json_response,
)
from ..client import LLMClient
from ..errors import LLMBusyError, LLMProviderError
from ..models import LLMRequest
from ._arena_fixtures import _fresh_arena

__all__ = ["_fresh_arena"]

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_SERVER_WAIT_S = 10.0


def _settings(tmp_path: Path, *, concurrency: int) -> EnvFileFreeSettings:
    return EnvFileFreeSettings(
        cadrumo_llm_provider=LLMProvider.LOCAL,
        cadrumo_llm_model="gpt-oss",
        cadrumo_llm_local_inference_concurrency=concurrency,
        cadrumo_llm_cache_dir=tmp_path / "cache",
        cadrumo_llm_usage_dir=tmp_path / "usage",
        cadrumo_llm_run_telemetry_dir=tmp_path / "run-telemetry",
    )


def _client(tmp_path: Path, *, concurrency: int) -> LLMClient:
    settings = _settings(tmp_path, concurrency=concurrency)
    return LLMClient(
        settings=settings,
        cache=LLMCache(root_dir=settings.cadrumo_llm_cache_dir),
        usage_recorder=UsageRecorder(root_dir=settings.cadrumo_llm_usage_dir),
        run_telemetry_recorder=LLMRunTelemetryRecorder(root_dir=settings.cadrumo_llm_run_telemetry_dir),
    )


class _HeldRuntime:
    """A loopback Ollama endpoint that holds each request until released."""

    def __init__(self) -> None:
        self.arrived: Queue[str] = Queue()
        self.release = threading.Event()
        self.status = HTTPStatus.OK


@contextmanager
def _serve_held_ollama(runtime: _HeldRuntime) -> Generator[str]:
    """Serve ``/api/chat`` on loopback, blocking every request until released."""

    class _Endpoint(SilentLoopbackHandler):
        @override
        def do_POST(self) -> None:
            body = read_json_body(self)
            messages = body["messages"]
            assert isinstance(messages, list)
            runtime.arrived.put(str(messages[-1]["content"]))
            # The whole point of the case: the first request must still be
            # in-flight, holding its slot, when the second one is admitted or
            # refused. Blocking inside the handler is what makes that ordering
            # a fact rather than a hope about scheduling.
            runtime.release.wait(_SERVER_WAIT_S)
            payload = (
                ollama_chat_reply(" local completion ")
                if runtime.status is HTTPStatus.OK
                else {"error": runtime.status.phrase}
            )
            write_json_response(self, payload, status=runtime.status)

    with serving_loopback(_Endpoint, path="/api/chat") as endpoint:
        try:
            yield endpoint
        finally:
            # Released BEFORE the shared teardown shuts the server down: a
            # handler still blocked on this event would otherwise hold the
            # serve thread past its join budget and surface as a hang here
            # rather than in the case that left a request in flight.
            runtime.release.set()


def _run_in_thread(client: LLMClient, prompt: str) -> tuple[threading.Thread, list[object]]:
    """Start one completion on its own thread and event loop, capturing the outcome.

    The thread runs inside a COPY of the caller's context, because
    ``override_settings`` binds a :class:`contextvars.ContextVar` and a plain
    thread starts with an empty context -- the adapter would then resolve the
    real runtime URL instead of the loopback server, and the case would measure
    a connection failure rather than admission control.
    """
    outcome: list[object] = []
    context = contextvars.copy_context()

    def _run() -> None:
        try:
            outcome.append(context.run(asyncio.run, client.complete(LLMRequest(prompt=prompt))))
        except BaseException as exc:  # captured and re-asserted by the caller
            outcome.append(exc)

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return thread, outcome


def test_second_concurrent_on_host_request_is_refused_while_the_first_holds_the_slot(tmp_path: Path) -> None:
    """With the default bound of one, exactly one of two concurrent requests proceeds."""
    runtime = _HeldRuntime()
    with _serve_held_ollama(runtime) as endpoint, override_settings(cadrumo_llm_ollama_chat_url=endpoint):
        client = _client(tmp_path, concurrency=1)
        first_thread, first_outcome = _run_in_thread(client, "first")
        # Established by the server, not by a sleep: the first request is inside
        # the arena and cannot leave it until the release below.
        assert runtime.arrived.get(timeout=_SERVER_WAIT_S) == "first"

        with pytest.raises(LLMBusyError) as refusal:
            asyncio.run(client.complete(LLMRequest(prompt="second")))

        runtime.release.set()
        first_thread.join(timeout=_SERVER_WAIT_S)

    assert len(first_outcome) == 1
    permitted = first_outcome[0]
    assert not isinstance(permitted, BaseException), permitted
    assert getattr(permitted, "text", None) == "local completion"
    # The refused request never reached the runtime: the arena is admission
    # control, not a post-hoc failure, so nothing was loaded and abandoned.
    assert runtime.arrived.empty()
    verdict = refusal.value.terminal_precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == "llm.local_inference.slot_available"
    assert verdict.action is None
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.OPERATOR_DECISION
    assert verdict.evidence[0].values == {
        "local_inference_limit": 1,
        "local_inference_slot_available": False,
        "provider": LLMProvider.LOCAL.value,
    }


def test_both_concurrent_requests_proceed_when_the_bound_permits_two(tmp_path: Path) -> None:
    """The positive control: the refusal above is the bound, not a broken configuration.

    Same two concurrent requests, same server, same client construction -- only
    the configured bound differs. Without this case a passing refusal test is
    indistinguishable from a dispatch path that could not have succeeded anyway.
    """
    runtime = _HeldRuntime()
    with _serve_held_ollama(runtime) as endpoint, override_settings(cadrumo_llm_ollama_chat_url=endpoint):
        # One client per concurrent caller, each with its own response cache --
        # the production shape, and it keeps this case measuring admission
        # rather than two threads writing one cache partition at once.
        client = _client(tmp_path / "first", concurrency=2)
        second_client = _client(tmp_path / "second", concurrency=2)
        first_thread, first_outcome = _run_in_thread(client, "first")
        assert runtime.arrived.get(timeout=_SERVER_WAIT_S) == "first"
        second_thread, second_outcome = _run_in_thread(second_client, "second")
        assert runtime.arrived.get(timeout=_SERVER_WAIT_S) == "second"

        runtime.release.set()
        first_thread.join(timeout=_SERVER_WAIT_S)
        second_thread.join(timeout=_SERVER_WAIT_S)

    for outcome in (first_outcome, second_outcome):
        assert len(outcome) == 1
        assert not isinstance(outcome[0], BaseException), outcome[0]


def test_the_bound_is_shared_across_clients(tmp_path: Path) -> None:
    """Two clients contend for the same slots, because the resource is the machine.

    A per-instance bound would hold for neither: production builds one client
    per caller, so a second caller would get a fresh, empty arena while the
    first request is still resident on the device.
    """
    runtime = _HeldRuntime()
    with _serve_held_ollama(runtime) as endpoint, override_settings(cadrumo_llm_ollama_chat_url=endpoint):
        holder = _client(tmp_path / "holder", concurrency=1)
        arrival = _client(tmp_path / "arrival", concurrency=1)
        first_thread, _first_outcome = _run_in_thread(holder, "first")
        assert runtime.arrived.get(timeout=_SERVER_WAIT_S) == "first"

        with pytest.raises(LLMBusyError):
            asyncio.run(arrival.complete(LLMRequest(prompt="second")))

        runtime.release.set()
        first_thread.join(timeout=_SERVER_WAIT_S)


def test_a_failed_dispatch_gives_its_slot_back(tmp_path: Path) -> None:
    """A refusal or transport failure must not strand the arena at full occupancy.

    The failure this guards is silent and permanent: one leaked slot with a
    bound of one refuses every subsequent read for the life of the process, and
    the symptom (everything is busy, nothing is running) points nowhere near the
    release path.
    """
    from ..client import _on_host_inference_arena

    runtime = _HeldRuntime()
    runtime.status = HTTPStatus.SERVICE_UNAVAILABLE
    runtime.release.set()
    with _serve_held_ollama(runtime) as endpoint, override_settings(cadrumo_llm_ollama_chat_url=endpoint):
        client = _client(tmp_path, concurrency=1)
        arena = _on_host_inference_arena(client.settings)
        with pytest.raises(LLMProviderError):
            asyncio.run(client.complete(LLMRequest(prompt="doomed")))
        assert arena.held == 0

        runtime.status = HTTPStatus.OK
        response = asyncio.run(client.complete(LLMRequest(prompt="after")))

    assert response.text == "local completion"
    assert arena.held == 0


def test_an_off_host_provider_does_not_occupy_an_on_host_slot(tmp_path: Path) -> None:
    """The bound protects local device memory, so it binds only on-host dispatch.

    Asserted on the arena directly rather than by dispatching at a cloud vendor:
    the point is which provider takes a slot, and a real cloud call is exactly
    what this repository must never make in a test.
    """
    from ..client import _on_host_inference_arena

    client = _client(tmp_path, concurrency=1)
    arena = _on_host_inference_arena(client.settings)

    with client._on_host_admission(LLMProvider.LOCAL):
        assert arena.held == 1
        with client._on_host_admission(LLMProvider.OPENAI):
            assert arena.held == 1
    assert arena.held == 0
