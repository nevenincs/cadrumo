"""A worker's model run crosses the runtime to the profile's admitted service and back.

Real encrypted profiles, real workers, the real runtime connection handling
and the real service client and relay run here. Only the agent-side lane
policy behind the relay is a recording stand-in, and the service verifier is
the explicitly controlled one the service-record tests use.
"""

from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from uuid import uuid4

import pytest

from cadrumo_agent_service.host.model_run_relay import ModelRunRelay
from cadrumo_client.contracts.model_runs import (
    ModelRunBody,
    ModelRunHeader,
    ModelRunLane,
    ModelRunOutput,
    ModelRunRefusal,
    ModelRunRefusalCode,
    ModelRunRoleSelection,
    ModelRunSelectedModel,
    decode_model_run_body,
    encode_model_run_body,
)
from cadrumo_client.contracts.service_access import ServiceConnected
from cadrumo_client.transport.service_client import InstalledServiceClient
from cadrumo_runtime.contracts.worker_authorization import WorkerModelRun
from cadrumo_runtime.host.tests.test_service_records import ServiceRecordRuntime, service_record_runtime

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows transport and workers"),
    pytest.mark.usefixtures("authority_operation"),
]

_LANE = ModelRunLane(provider_id="example", transport="cli", model="example-model-1")
_STATES = (
    ModelRunRoleSelection(
        role="text_extraction",
        selected=ModelRunSelectedModel(lane_id="example_cli", model=_LANE.model),
        lane=_LANE,
    ),
    ModelRunRoleSelection(role="vision_transcription", refusal=ModelRunRefusalCode.NO_SELECTION),
)


class _Runs:
    """The agent-side answer behind the relay: one lane, and a run that echoes what it received."""

    def __init__(self) -> None:
        self.bodies: list[ModelRunBody] = []
        self.started = Event()
        self.release = Event()
        self.block = False

    def lookup(self, role: str) -> ModelRunLane | ModelRunRefusal:
        return _LANE

    def selections(self) -> tuple[ModelRunRoleSelection, ...] | ModelRunRefusal:
        return _STATES

    def run(self, header: ModelRunHeader, body: ModelRunBody) -> ModelRunOutput | ModelRunRefusal:
        self.bodies.append(body)
        self.started.set()
        if self.block:
            self.release.wait()
        return ModelRunOutput(
            text=f"read: {body.prompt}",
            provider_id=_LANE.provider_id,
            transport=_LANE.transport,
            model=_LANE.model,
            agent_version="test",
        )


def _admitted_service(runtime: ServiceRecordRuntime, runs: _Runs) -> tuple[InstalledServiceClient, ModelRunRelay]:
    service = runtime.connect_service()
    assert isinstance(runtime.admit(service), ServiceConnected)
    assert service.claim() is not None
    relay = ModelRunRelay(client=service, runs=lambda: runs)
    service.subscribe_model_runs(relay.announce)
    return service, relay


def _lookup() -> WorkerModelRun:
    return WorkerModelRun(request_id=uuid4(), permit_id=uuid4(), command_id=uuid4(), role="text_extraction")


def _run(body: bytearray) -> WorkerModelRun:
    header = ModelRunHeader(role="text_extraction", deadline_seconds=30)
    return WorkerModelRun(
        request_id=uuid4(),
        permit_id=uuid4(),
        command_id=uuid4(),
        role=header.role,
        header=header,
        body_byte_count=len(body),
    )


def test_a_lookup_reaches_the_admitted_service_and_returns_its_lane(tmp_path: Path) -> None:
    with service_record_runtime(tmp_path, model_runs=True) as runtime:
        runs = _Runs()
        _, relay = _admitted_service(runtime, runs)
        try:
            outcome, text = runtime.profiles._relay_model_run(runtime.profile_id, _lookup(), bytearray())
        finally:
            relay.close()

    assert outcome.lane == _LANE
    assert text == bytearray()


def test_a_selections_read_reaches_the_admitted_service_and_returns_every_role_state(tmp_path: Path) -> None:
    read = WorkerModelRun(request_id=uuid4(), permit_id=uuid4(), command_id=uuid4(), role=None)
    with service_record_runtime(tmp_path, model_runs=True) as runtime:
        runs = _Runs()
        _, relay = _admitted_service(runtime, runs)
        try:
            outcome, text = runtime.profiles._relay_model_run(runtime.profile_id, read, bytearray())
        finally:
            relay.close()

    assert outcome.selections == _STATES
    assert text == bytearray()


def test_a_run_carries_its_body_to_the_service_and_its_reply_back(tmp_path: Path) -> None:
    body = encode_model_run_body(ModelRunBody(prompt="Factura 42", max_output_tokens=16))
    with service_record_runtime(tmp_path, model_runs=True) as runtime:
        runs = _Runs()
        _, relay = _admitted_service(runtime, runs)
        try:
            outcome, text = runtime.profiles._relay_model_run(runtime.profile_id, _run(body), body)
        finally:
            relay.close()

    assert outcome.served is not None and outcome.served.model == _LANE.model
    assert text.decode("utf-8") == "read: Factura 42"
    assert [received.prompt for received in runs.bodies] == ["Factura 42"]
    assert body == bytearray(len(body)), "the relayed body is wiped once handed on"


def test_a_service_whose_descriptor_declares_no_model_runs_is_never_asked(tmp_path: Path) -> None:
    with service_record_runtime(tmp_path, model_runs=False) as runtime:
        runs = _Runs()
        _, relay = _admitted_service(runtime, runs)
        try:
            outcome, _ = runtime.profiles._relay_model_run(runtime.profile_id, _lookup(), bytearray())
        finally:
            relay.close()

    assert outcome.refusal is ModelRunRefusalCode.SERVICE_UNAVAILABLE
    assert runs.bodies == []


def test_a_run_waiting_on_a_service_that_goes_away_is_answered_at_once(tmp_path: Path) -> None:
    """The service's connection ends mid-run; the waiting worker learns it then, not at its deadline."""
    body = encode_model_run_body(ModelRunBody(prompt="Factura 7", max_output_tokens=16))
    with service_record_runtime(tmp_path, model_runs=True) as runtime:
        runs = _Runs()
        runs.block = True
        service, relay = _admitted_service(runtime, runs)
        with ThreadPoolExecutor(max_workers=1) as pool:
            waiting = pool.submit(runtime.profiles._relay_model_run, runtime.profile_id, _run(body), body)
            assert runs.started.wait(30), "the service never received the run"
            service.connection.close()
            outcome, _ = waiting.result(timeout=30)
            runs.release.set()
            relay.close()

    assert outcome.refusal is ModelRunRefusalCode.SERVICE_UNAVAILABLE
    assert decode_model_run_body(encode_model_run_body(runs.bodies[0])).prompt == "Factura 7"
