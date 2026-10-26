"""The process-wide bound on concurrent on-host inference.

Every case drives REAL concurrent requests through the production
:class:`LLMClient` and the real agent adapter, on a lane whose catalogue entry
says it stays on this computer. The agent service behind the model-run port is
a recording stand-in that holds the first run open until the second request has
been admitted or refused. Nothing is patched, and no semaphore is simulated:
the ordering is established by the stand-in telling the test it has the first
run, so the second one genuinely contends.

The bound exists because two simultaneous model loads on consumer hardware are
an out-of-memory kill that takes the FIRST read down with it, so a test that
proved the refusal by stubbing the gate would prove nothing about the machine.
"""

from __future__ import annotations

import asyncio
import contextvars
import threading
from pathlib import Path
from queue import Queue

import pytest

from cadrumo_client.contracts.model_runs import ModelRunBody, ModelRunRefusalCode

from .....core.config_support import LLMProvider
from .....core.model_roles import ModelRole
from .....core.operator_action_enums import NoRecoveryOutcome
from .....tests.fixtures.settings import EnvFileFreeSettings
from ....persistence.llm.cache import LLMCache
from ....persistence.llm.run_records import LLMRunRecorder
from ....persistence.llm.usage import UsageRecorder
from ..client import LLMClient, _on_host_inference_arena
from ..errors import LLMBusyError, LLMProviderError
from ..models import LLMRequest
from ._arena_fixtures import _fresh_arena
from .model_run_support import DEFAULT_LANE, ON_HOST_LANE, serving_agent

__all__ = ["_fresh_arena"]

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_RUN_WAIT_S = 10.0


def _client(tmp_path: Path, *, concurrency: int) -> LLMClient:
    settings = EnvFileFreeSettings(
        cadrumo_llm_local_inference_concurrency=concurrency,
        cadrumo_llm_cache_dir=tmp_path / "cache",
        cadrumo_llm_usage_dir=tmp_path / "usage",
        cadrumo_llm_run_record_dir=tmp_path / "run-record",
    )
    return LLMClient(
        settings=settings,
        cache=LLMCache(root_dir=settings.cadrumo_llm_cache_dir),
        usage_recorder=UsageRecorder(root_dir=settings.cadrumo_llm_usage_dir),
        run_record_recorder=LLMRunRecorder(root_dir=settings.cadrumo_llm_run_record_dir),
    )


def _request(prompt: str) -> LLMRequest:
    return LLMRequest(prompt=prompt, model_role=ModelRole.TEXT_EXTRACTION)


class _HeldRuns:
    """Answers each run only once released, announcing its arrival first."""

    def __init__(self) -> None:
        self.arrived: Queue[str] = Queue()
        self.release = threading.Event()

    def answer(self, body: ModelRunBody) -> str:
        self.arrived.put(body.prompt)
        # The whole point of the case: the first run must still be in flight,
        # holding its slot, when the second request is admitted or refused.
        # Blocking inside the answer is what makes that ordering a fact rather
        # than a hope about scheduling.
        self.release.wait(_RUN_WAIT_S)
        return "agent completion"


def _run_in_thread(client: LLMClient, prompt: str) -> tuple[threading.Thread, list[object]]:
    """Start one completion on its own thread and event loop, capturing the outcome.

    The thread runs inside a COPY of the caller's context, because the bound
    model-run port is a :class:`contextvars.ContextVar` and a plain thread
    starts with an empty context -- the request would then find no service and
    the case would measure that refusal rather than admission control.
    """
    outcome: list[object] = []
    context = contextvars.copy_context()

    def _run() -> None:
        try:
            outcome.append(context.run(asyncio.run, client.complete(_request(prompt))))
        except BaseException as exc:  # captured and re-asserted by the caller
            outcome.append(exc)

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return thread, outcome


def test_second_concurrent_on_host_request_is_refused_while_the_first_holds_the_slot(tmp_path: Path) -> None:
    """With a bound of one, exactly one of two concurrent requests proceeds."""
    held = _HeldRuns()
    with serving_agent(lane=ON_HOST_LANE, answer=held.answer) as service:
        client = _client(tmp_path, concurrency=1)
        first_thread, first_outcome = _run_in_thread(client, "first")
        try:
            # Established by the stand-in, not by a sleep: the first run is
            # inside the arena and cannot leave it until the release below.
            assert held.arrived.get(timeout=_RUN_WAIT_S) == "first"

            with pytest.raises(LLMBusyError) as refusal:
                asyncio.run(client.complete(_request("second")))
        finally:
            held.release.set()
            first_thread.join()

    assert len(first_outcome) == 1
    permitted = first_outcome[0]
    assert not isinstance(permitted, BaseException), permitted
    assert getattr(permitted, "text", None) == "agent completion"
    # The refused request never reached the service: the arena is admission
    # control, not a post-hoc failure, so nothing was loaded and abandoned.
    assert [body.prompt for _, body in service.runs] == ["first"]
    verdict = refusal.value.terminal_precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == "llm.local_inference.slot_available"
    assert verdict.action is None
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.OPERATOR_DECISION
    assert verdict.evidence[0].values == {
        "local_inference_limit": 1,
        "local_inference_slot_available": False,
        "provider": LLMProvider.AGENT.value,
    }


def test_both_concurrent_requests_proceed_when_the_bound_permits_two(tmp_path: Path) -> None:
    """The positive control: the refusal above is the bound, not a broken configuration.

    Same two concurrent requests, same service, same client construction --
    only the configured bound differs.
    """
    held = _HeldRuns()
    with serving_agent(lane=ON_HOST_LANE, answer=held.answer):
        # One client per concurrent caller, each with its own response cache --
        # the production shape, and it keeps this case measuring admission
        # rather than two threads writing one cache partition at once.
        first_client = _client(tmp_path / "first", concurrency=2)
        second_client = _client(tmp_path / "second", concurrency=2)
        first_thread, first_outcome = _run_in_thread(first_client, "first")
        second_thread, second_outcome = first_thread, first_outcome
        try:
            assert held.arrived.get(timeout=_RUN_WAIT_S) == "first"
            second_thread, second_outcome = _run_in_thread(second_client, "second")
            assert held.arrived.get(timeout=_RUN_WAIT_S) == "second"
        finally:
            held.release.set()
            first_thread.join()
            second_thread.join()

    for outcome in (first_outcome, second_outcome):
        assert len(outcome) == 1
        assert not isinstance(outcome[0], BaseException), outcome[0]


def test_the_bound_is_shared_across_clients(tmp_path: Path) -> None:
    """Two clients contend for the same slots, because the resource is the machine.

    A per-instance bound would hold for neither: production builds one client
    per caller, so a second caller would get a fresh, empty arena while the
    first run is still resident on the device.
    """
    held = _HeldRuns()
    with serving_agent(lane=ON_HOST_LANE, answer=held.answer):
        holder = _client(tmp_path / "holder", concurrency=1)
        arrival = _client(tmp_path / "arrival", concurrency=1)
        first_thread, _first_outcome = _run_in_thread(holder, "first")
        try:
            assert held.arrived.get(timeout=_RUN_WAIT_S) == "first"

            with pytest.raises(LLMBusyError):
                asyncio.run(arrival.complete(_request("second")))
        finally:
            held.release.set()
            first_thread.join()


def test_a_failed_dispatch_gives_its_slot_back(tmp_path: Path) -> None:
    """A refused run must not strand the arena at full occupancy.

    The failure this guards is silent and permanent: one leaked slot with a
    bound of one refuses every subsequent read for the life of the process, and
    the symptom (everything is busy, nothing is running) points nowhere near the
    release path.
    """
    client = _client(tmp_path, concurrency=1)
    arena = _on_host_inference_arena(client.settings)
    with (
        serving_agent(lane=ON_HOST_LANE, run_refusal=ModelRunRefusalCode.RUN_FAILED),
        pytest.raises(LLMProviderError),
    ):
        asyncio.run(client.complete(_request("doomed")))
    assert arena.held == 0

    with serving_agent(lane=ON_HOST_LANE, replies=("agent completion",)):
        response = asyncio.run(client.complete(_request("after")))

    assert response.text == "agent completion"
    assert arena.held == 0


def test_an_off_host_lane_does_not_occupy_an_on_host_slot(tmp_path: Path) -> None:
    """The bound protects local device memory, so it binds only a lane that stays on this computer.

    Asserted on the arena directly: the point is which lane takes a slot, and
    the lane's ``reads_off_host`` flag is the only difference between the two.
    """
    client = _client(tmp_path, concurrency=1)
    arena = _on_host_inference_arena(client.settings)

    with client._on_host_admission(ON_HOST_LANE):
        assert arena.held == 1
        with client._on_host_admission(DEFAULT_LANE):
            assert arena.held == 1
    assert arena.held == 0
