"""A read on this computer demands the local AI server first, and only from a manager of an admitted image."""

from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path
from uuid import uuid4

import pytest

from cadrumo_client.contracts.model_runs import (
    ModelRunBody,
    ModelRunLane,
    ModelRunOutput,
    ModelRunRefusal,
    ModelRunRefusalCode,
)

from ...providers.domain.catalog import BackgroundOption
from ...providers.domain.record import LocalEngine
from ..local_ai_demand import (
    DEMAND_PIPE_VARIABLE,
    DEMAND_SERVERS_VARIABLE,
    DemandOutcome,
    LocalAiDemandingRuns,
    ManagerPipeDemand,
    decode_demand_response,
    manager_demand_from_environment,
)

pytestmark = [pytest.mark.hex_outbound_adapter]

_VERBATIM = "\\\\?\\"
_LOCAL = ModelRunLane(provider_id="llamacpp", transport="api", model="synthetic-model", reads_off_host=False)
_OFF_HOST = ModelRunLane(provider_id="example", transport="api", model="example-model-1", reads_off_host=True)
_BODY = ModelRunBody(prompt="Read this.")


class _Runs:
    """Records each run it is handed and answers with a fixed reply."""

    def __init__(self, *, during: float = 0.0) -> None:
        self.lanes: list[ModelRunLane] = []
        self._during = during

    def run(
        self, *, lane: ModelRunLane, body: ModelRunBody, deadline_seconds: int, options: tuple[BackgroundOption, ...]
    ) -> ModelRunOutput | ModelRunRefusal:
        del body, deadline_seconds, options
        self.lanes.append(lane)
        time.sleep(self._during)
        return ModelRunOutput(
            text="read", provider_id=lane.provider_id, transport=lane.transport, model=lane.model, agent_version="1"
        )


class _Manager:
    """Answers each demand in turn, repeating the last answer; counts them."""

    def __init__(self, *answers: DemandOutcome | None) -> None:
        self._answers = list(answers)
        self.demands = 0
        self._lock = threading.Lock()

    def __call__(self) -> DemandOutcome | None:
        with self._lock:
            self.demands += 1
            return self._answers.pop(0) if len(self._answers) > 1 else self._answers[0]


def _gateway(runs: _Runs, manager: _Manager | None, *, listens: bool = True, **timing: float) -> LocalAiDemandingRuns:
    return LocalAiDemandingRuns(
        runs=runs,
        demand=manager,
        listens=lambda engine: listens and engine is LocalEngine.LLAMACPP,
        retry_seconds=timing.pop("retry_seconds", 0.001),
        listen_wait_seconds=timing.pop("listen_wait_seconds", 1.0),
        **timing,
    )


def _run(gateway: LocalAiDemandingRuns, lane: ModelRunLane) -> ModelRunOutput | ModelRunRefusal:
    return gateway.run(lane=lane, body=_BODY, deadline_seconds=30, options=())


@pytest.mark.unit
def test_a_read_elsewhere_demands_nothing() -> None:
    runs, manager = _Runs(), _Manager(DemandOutcome.NOT_RUNNING)

    assert isinstance(_run(_gateway(runs, manager), _OFF_HOST), ModelRunOutput)
    assert manager.demands == 0
    assert runs.lanes == [_OFF_HOST]


@pytest.mark.unit
def test_without_a_named_manager_a_local_read_runs_as_before() -> None:
    runs = _Runs()

    assert isinstance(_run(_gateway(runs, None), _LOCAL), ModelRunOutput)
    assert runs.lanes == [_LOCAL]


@pytest.mark.unit
def test_a_local_read_runs_once_its_demanded_server_listens() -> None:
    runs, manager = _Runs(), _Manager(DemandOutcome.DEMANDED)

    assert isinstance(_run(_gateway(runs, manager), _LOCAL), ModelRunOutput)
    assert manager.demands == 1
    assert runs.lanes == [_LOCAL]


@pytest.mark.unit
def test_a_held_demand_is_asked_again_until_it_is_taken() -> None:
    runs, manager = _Runs(), _Manager(DemandOutcome.HELD, DemandOutcome.HELD, DemandOutcome.DEMANDED)

    assert isinstance(_run(_gateway(runs, manager), _LOCAL), ModelRunOutput)
    assert manager.demands == 3


@pytest.mark.unit
@pytest.mark.parametrize("answer", [DemandOutcome.NOT_SET_UP, DemandOutcome.NOT_RUNNING, None])
def test_a_demand_not_taken_refuses_the_read_as_lane_unavailable(answer: DemandOutcome | None) -> None:
    runs, manager = _Runs(), _Manager(answer)

    assert _run(_gateway(runs, manager), _LOCAL) == ModelRunRefusal(code=ModelRunRefusalCode.LANE_UNAVAILABLE)
    assert manager.demands == 1
    assert runs.lanes == []


@pytest.mark.unit
def test_a_server_that_never_listens_refuses_the_read_after_the_wait() -> None:
    runs, manager = _Runs(), _Manager(DemandOutcome.DEMANDED)
    started = time.monotonic()

    refusal = _run(_gateway(runs, manager, listens=False, listen_wait_seconds=0.05), _LOCAL)

    assert refusal == ModelRunRefusal(code=ModelRunRefusalCode.LANE_UNAVAILABLE)
    assert time.monotonic() - started >= 0.05
    assert manager.demands == 1
    assert runs.lanes == []


@pytest.mark.unit
def test_the_demand_is_renewed_while_the_read_lasts_and_not_after() -> None:
    runs, manager = _Runs(during=0.2), _Manager(DemandOutcome.DEMANDED)

    assert isinstance(_run(_gateway(runs, manager, renew_seconds=0.02), _LOCAL), ModelRunOutput)
    renewed = manager.demands
    time.sleep(0.1)

    assert renewed >= 3
    assert manager.demands == renewed


@pytest.mark.unit
def test_only_a_demand_answer_decodes() -> None:
    assert decode_demand_response(b'{"schema":1,"outcome":"local_ai_demanded"}') is DemandOutcome.DEMANDED
    assert decode_demand_response(b'{"schema":1,"outcome":"local_ai_held"}') is DemandOutcome.HELD
    for payload in (
        b'{"schema":2,"outcome":"local_ai_demanded"}',
        b'{"schema":1,"outcome":"running"}',
        b'{"schema":1}',
        b'["local_ai_demanded"]',
        b'{"schema":1,"outcome":',
    ):
        assert decode_demand_response(payload) is None


@pytest.mark.unit
@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="the manager's pipe is a Windows named pipe")
def test_the_demand_is_the_one_the_desktop_names(tmp_path: Path) -> None:
    image = str(tmp_path / "manager.exe")
    pipe = r"\\.\pipe\synthetic.manager"

    named = manager_demand_from_environment({DEMAND_PIPE_VARIABLE: pipe, DEMAND_SERVERS_VARIABLE: json.dumps([image])})

    assert isinstance(named, ManagerPipeDemand)
    for environment in (
        {},
        {DEMAND_PIPE_VARIABLE: pipe},
        {DEMAND_SERVERS_VARIABLE: json.dumps([image])},
        {DEMAND_PIPE_VARIABLE: pipe, DEMAND_SERVERS_VARIABLE: "not json"},
        {DEMAND_PIPE_VARIABLE: pipe, DEMAND_SERVERS_VARIABLE: json.dumps([])},
        {DEMAND_PIPE_VARIABLE: pipe, DEMAND_SERVERS_VARIABLE: json.dumps(["manager.exe"])},
        {DEMAND_PIPE_VARIABLE: pipe, DEMAND_SERVERS_VARIABLE: json.dumps([image, 3])},
    ):
        assert manager_demand_from_environment(environment) is None


def _serve_one(pipe: str, answer: bytes, received: list[bytes], listening: threading.Event) -> None:
    """A message pipe of this process that takes one request and answers it, as the manager does."""
    import pywintypes
    import win32file
    import win32pipe

    handle = win32pipe.CreateNamedPipe(
        pipe,
        win32pipe.PIPE_ACCESS_DUPLEX,
        win32pipe.PIPE_TYPE_MESSAGE | win32pipe.PIPE_READMODE_MESSAGE | win32pipe.PIPE_REJECT_REMOTE_CLIENTS,
        1,
        4096,
        4096,
        0,
        pywintypes.SECURITY_ATTRIBUTES(),
    )
    try:
        listening.set()
        win32pipe.ConnectNamedPipe(handle, None)
        try:
            _, request = win32file.ReadFile(handle, 4096)
        except win32file.error:
            return
        received.append(bytes(request))
        win32file.WriteFile(handle, answer)
        win32file.FlushFileBuffers(handle)
    finally:
        win32file.CloseHandle(handle)


def _this_image() -> Path:
    import win32api

    from cadrumo_client.transport.windows_native_io import windows_image_path

    return windows_image_path(int(win32api.GetCurrentProcess()))


@pytest.mark.integration
@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="the manager's pipe is a Windows named pipe")
def test_a_demand_reaches_a_manager_of_an_admitted_image_and_reads_its_answer() -> None:
    pipe = rf"\\.\pipe\cadrumo-test-local-ai-demand-{uuid4().hex}"
    received: list[bytes] = []
    listening = threading.Event()
    server = threading.Thread(
        target=_serve_one, args=(pipe, b'{"schema":1,"outcome":"local_ai_demanded"}', received, listening)
    )
    server.start()
    assert listening.wait(5)

    # The desktop names the image as a canonical path does, with its verbatim prefix.
    demand = manager_demand_from_environment(
        {DEMAND_PIPE_VARIABLE: pipe, DEMAND_SERVERS_VARIABLE: json.dumps([_VERBATIM + str(_this_image())])}
    )
    assert demand is not None
    outcome = demand()
    server.join(5)

    assert outcome is DemandOutcome.DEMANDED
    assert [json.loads(request) for request in received] == [{"request": "demand_local_ai", "schema": 1}]


@pytest.mark.integration
@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="the manager's pipe is a Windows named pipe")
def test_a_server_of_another_image_is_sent_no_demand(tmp_path: Path) -> None:
    pipe = rf"\\.\pipe\cadrumo-test-local-ai-demand-{uuid4().hex}"
    received: list[bytes] = []
    listening = threading.Event()
    server = threading.Thread(
        target=_serve_one, args=(pipe, b'{"schema":1,"outcome":"local_ai_demanded"}', received, listening)
    )
    server.start()
    assert listening.wait(5)

    outcome = ManagerPipeDemand(pipe=pipe, servers=(tmp_path / "manager.exe",))()
    server.join(5)

    assert outcome is None
    assert received == []


@pytest.mark.integration
@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="the manager's pipe is a Windows named pipe")
def test_no_manager_on_the_pipe_answers_nothing() -> None:
    pipe = rf"\\.\pipe\cadrumo-test-local-ai-demand-{uuid4().hex}"

    assert ManagerPipeDemand(pipe=pipe, servers=(_this_image(),))() is None
