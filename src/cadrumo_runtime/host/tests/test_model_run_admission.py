"""The runtime forwards a model run only to a service its installed descriptor admits for ``model-run``.

Real encrypted profiles, the real runtime connection handling and the real
service client run here. Which installed descriptor a connection holds is
fixed when the runtime admits its natively verified peer; the service-record
fixture's verifier selects which connections are admitted, not what their
descriptors declare.
"""

from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from queue import Queue
from uuid import UUID, uuid4

import pytest

from cadrumo_client.contracts.model_runs import ModelRunLane, ModelRunOutcome, ModelRunRefusalCode, ModelRunRequested
from cadrumo_client.contracts.service_access import ServiceConnected
from cadrumo_client.transport.service_client import InstalledServiceClient

from ...contracts.worker_authorization import WorkerModelRun
from .test_service_records import OTHER_SERVICE_ID, SERVICE_ID, ServiceRecordRuntime, service_record_runtime

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows transport and workers"),
    pytest.mark.usefixtures("authority_operation"),
]

_LANE = ModelRunLane(provider_id="example", transport="cli", model="example-model-1")
_ANNOUNCEMENT_SECONDS = 30


def _admitted(runtime: ServiceRecordRuntime, service_id: str) -> tuple[InstalledServiceClient, Queue[UUID]]:
    """Connect and admit one service, collecting the run ids announced to its connection."""
    service = runtime.connect_service(service_id=service_id)
    assert isinstance(runtime.admit(service), ServiceConnected)
    assert service.claim() is not None
    announced: Queue[UUID] = Queue()
    connection_id = service.lease.connection_id if service.lease is not None else None

    def receive(event: ModelRunRequested) -> None:
        if event.connection_id == connection_id:
            announced.put(event.run_id)

    service.subscribe_model_runs(receive)
    return service, announced


def _lookup() -> WorkerModelRun:
    return WorkerModelRun(request_id=uuid4(), permit_id=uuid4(), command_id=uuid4(), role="text_extraction")


def test_a_service_whose_installed_descriptor_lacks_model_run_is_refused_unannounced(tmp_path: Path) -> None:
    with service_record_runtime(tmp_path, model_runs=False) as runtime:
        _admitted(runtime, SERVICE_ID)

        outcome, text = runtime.profiles._relay_model_run(runtime.profile_id, _lookup(), bytearray())

        assert outcome == ModelRunOutcome(refusal=ModelRunRefusalCode.SERVICE_UNAVAILABLE)
        assert text == bytearray()
        assert runtime.profiles._model_runs == {}


def test_a_service_whose_installed_descriptor_declares_model_run_is_forwarded_the_run(tmp_path: Path) -> None:
    with service_record_runtime(tmp_path, model_runs=True) as runtime:
        service, announced = _admitted(runtime, SERVICE_ID)
        with ThreadPoolExecutor(max_workers=1) as pool:
            waiting = pool.submit(runtime.profiles._relay_model_run, runtime.profile_id, _lookup(), bytearray())
            run_id = announced.get(timeout=_ANNOUNCEMENT_SECONDS)
            fetched = service.model_run_fetch(run_id)
            assert fetched is not None and fetched[0].header is None and fetched[1] == bytearray()
            assert service.model_run_complete(run_id, ModelRunOutcome(lane=_LANE), bytearray())
            outcome, _ = waiting.result(timeout=_ANNOUNCEMENT_SECONDS)

    assert outcome.lane == _LANE


def test_another_installed_descriptor_lends_no_capability_to_the_admitted_service(tmp_path: Path) -> None:
    """The capable descriptor is installed, but the only admitted connection holds the other one."""
    with service_record_runtime(tmp_path, model_runs=False, other_service_model_runs=True) as runtime:
        _admitted(runtime, SERVICE_ID)

        outcome, _ = runtime.profiles._relay_model_run(runtime.profile_id, _lookup(), bytearray())

        assert outcome == ModelRunOutcome(refusal=ModelRunRefusalCode.SERVICE_UNAVAILABLE)


def test_another_connection_can_neither_fetch_nor_answer_a_run_announced_to_the_admitted_one(tmp_path: Path) -> None:
    with service_record_runtime(tmp_path, model_runs=False, other_service_model_runs=True) as runtime:
        uncapable, _ = _admitted(runtime, SERVICE_ID)
        capable, announced = _admitted(runtime, OTHER_SERVICE_ID)
        with ThreadPoolExecutor(max_workers=1) as pool:
            waiting = pool.submit(runtime.profiles._relay_model_run, runtime.profile_id, _lookup(), bytearray())
            run_id = announced.get(timeout=_ANNOUNCEMENT_SECONDS)

            assert uncapable.model_run_fetch(run_id) is None
            assert not uncapable.model_run_complete(
                run_id, ModelRunOutcome(refusal=ModelRunRefusalCode.RUN_FAILED), bytearray()
            )

            assert capable.model_run_fetch(run_id) is not None
            assert capable.model_run_complete(run_id, ModelRunOutcome(lane=_LANE), bytearray())
            outcome, _ = waiting.result(timeout=_ANNOUNCEMENT_SECONDS)

    assert outcome.lane == _LANE
