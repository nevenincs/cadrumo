"""The runtime forwards a model run only to a service its installed descriptor admits for ``model-run``.

Real encrypted profiles, the real runtime connection handling and the real
service client run here. Which installed descriptor a connection holds is
fixed when the runtime admits its natively verified peer; the service-record
fixture's verifier selects which connections are admitted, not what their
descriptors declare.
"""

from __future__ import annotations

import sys
import time
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from queue import Queue
from uuid import UUID, uuid4

import pytest

from cadrumo_client.contracts.contracts import ByteChannel
from cadrumo_client.contracts.model_runs import (
    MODEL_RUN_MAX_DEADLINE_SECONDS,
    ModelRunBody,
    ModelRunCompleteRequest,
    ModelRunFetchRequest,
    ModelRunHeader,
    ModelRunLane,
    ModelRunOutcome,
    ModelRunRefusalCode,
    ModelRunRequested,
    ModelRunServed,
    decode_model_run_body,
    encode_model_run_body,
)
from cadrumo_client.contracts.profile_access import SessionRequest, SessionsLocked
from cadrumo_client.contracts.service_access import ServiceConnected
from cadrumo_client.contracts.transport import ConnectionContext
from cadrumo_client.transport.service_client import InstalledServiceClient

from ...contracts.worker_authorization import WorkerModelRun
from .. import profile_connection_model_runs as model_runs_module
from ..profile_connections import RuntimeProfileConnections
from .test_service_records import OTHER_SERVICE_ID, SERVICE_ID, ServiceRecordRuntime, service_record_runtime

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows transport and workers"),
    pytest.mark.usefixtures("authority_operation"),
]

_LANE = ModelRunLane(
    provider_id="example",
    transport="cli",
    model="example-model-1",
    reads_off_host=True,
)
_ANNOUNCEMENT_SECONDS = 30
_SERVED = ModelRunServed(provider_id="example", transport="cli", model="example-model-1", agent_version="1")


def _admitted(
    runtime: ServiceRecordRuntime, service_id: str, *, seen: Queue[tuple[UUID, UUID]] | None = None
) -> tuple[InstalledServiceClient, Queue[UUID]]:
    """Connect and admit one service, collecting the run ids announced to its connection.

    ``seen``, when given, also receives each announcement as its connection id and run id.
    """
    service = runtime.connect_service(service_id=service_id)
    assert isinstance(runtime.admit(service), ServiceConnected)
    assert service.claim() is not None
    announced: Queue[UUID] = Queue()
    connection_id = service.lease.connection_id if service.lease is not None else None

    def receive(event: ModelRunRequested) -> None:
        if event.connection_id == connection_id:
            announced.put(event.run_id)
            if seen is not None:
                seen.put((event.connection_id, event.run_id))

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


def _run(body: bytearray) -> WorkerModelRun:
    # The longest deadline a run may carry: an answer that came by waiting it out would never arrive in the test.
    header = ModelRunHeader(role="text_extraction", deadline_seconds=MODEL_RUN_MAX_DEADLINE_SECONDS)
    return WorkerModelRun(
        request_id=uuid4(),
        permit_id=uuid4(),
        command_id=uuid4(),
        role=header.role,
        header=header,
        body_byte_count=len(body),
    )


def test_a_run_whose_service_connection_drops_after_fetching_it_settles_as_unavailable_at_once(
    tmp_path: Path,
) -> None:
    body = encode_model_run_body(ModelRunBody(prompt="Factura 7", max_output_tokens=16))
    with service_record_runtime(tmp_path, model_runs=True) as runtime:
        service, announced = _admitted(runtime, SERVICE_ID)
        with ThreadPoolExecutor(max_workers=1) as pool:
            waiting = pool.submit(runtime.profiles._relay_model_run, runtime.profile_id, _run(body), body)
            run_id = announced.get(timeout=_ANNOUNCEMENT_SECONDS)
            fetched = service.model_run_fetch(run_id)
            assert fetched is not None and decode_model_run_body(fetched[1]).prompt == "Factura 7"

            service.connection.close()

            outcome, text = waiting.result(timeout=_ANNOUNCEMENT_SECONDS)

        assert outcome == ModelRunOutcome(refusal=ModelRunRefusalCode.SERVICE_UNAVAILABLE)
        assert text == bytearray()
        assert body == bytearray(len(body)), "the relayed body is wiped once nobody waits for it"
        assert runtime.profiles._model_runs == {}


def test_a_second_connection_of_the_same_service_can_neither_fetch_nor_answer_the_first_one_s_run(
    tmp_path: Path,
) -> None:
    with service_record_runtime(tmp_path, model_runs=True) as runtime:
        seen: Queue[tuple[UUID, UUID]] = Queue()
        first, _ = _admitted(runtime, SERVICE_ID, seen=seen)
        second, _ = _admitted(runtime, SERVICE_ID, seen=seen)
        assert first.lease is not None and second.lease is not None
        assert first.lease.connection_id != second.lease.connection_id
        with ThreadPoolExecutor(max_workers=1) as pool:
            waiting = pool.submit(runtime.profiles._relay_model_run, runtime.profile_id, _lookup(), bytearray())
            owner_connection, run_id = seen.get(timeout=_ANNOUNCEMENT_SECONDS)
            owner, intruder = (first, second) if owner_connection == first.lease.connection_id else (second, first)

            assert intruder.model_run_fetch(run_id) is None
            assert not intruder.model_run_complete(
                run_id, ModelRunOutcome(refusal=ModelRunRefusalCode.RUN_FAILED), bytearray()
            )

            assert owner.model_run_fetch(run_id) is not None
            assert owner.model_run_complete(run_id, ModelRunOutcome(lane=_LANE), bytearray())
            outcome, _ = waiting.result(timeout=_ANNOUNCEMENT_SECONDS)

    assert outcome.lane == _LANE


def _lock_person(runtime: ServiceRecordRuntime) -> None:
    locked = runtime.human.session(
        SessionRequest(
            action="session_lock",
            request_id=uuid4(),
            profile_id=runtime.profile_id,
            session_id=runtime.person_session_id,
        ),
        deadline=time.monotonic() + 10,
    )
    assert isinstance(locked, SessionsLocked)
    assert runtime.person_session_id in locked.session_ids


def test_a_parent_session_retired_after_the_admission_recheck_receives_no_header_or_body(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    body = encode_model_run_body(ModelRunBody(prompt="Factura 7", max_output_tokens=16))
    with service_record_runtime(tmp_path, model_runs=True) as runtime:
        service, announced = _admitted(runtime, SERVICE_ID)
        recheck = model_runs_module._service_still_admitted

        def retire_after_recheck(
            connections: RuntimeProfileConnections,
            context: ConnectionContext,
            channel: ByteChannel,
            request: ModelRunFetchRequest | ModelRunCompleteRequest,
        ) -> bool:
            admitted = recheck(connections, context, channel, request)
            _lock_person(runtime)
            return admitted

        monkeypatch.setattr(model_runs_module, "_service_still_admitted", retire_after_recheck)
        with ThreadPoolExecutor(max_workers=1) as pool:
            waiting = pool.submit(runtime.profiles._relay_model_run, runtime.profile_id, _run(body), body)
            run_id = announced.get(timeout=_ANNOUNCEMENT_SECONDS)

            assert service.model_run_fetch(run_id) is None

            outcome, text = waiting.result(timeout=_ANNOUNCEMENT_SECONDS)

        assert outcome == ModelRunOutcome(refusal=ModelRunRefusalCode.SERVICE_UNAVAILABLE)
        assert text == bytearray()
        assert body == bytearray(len(body))


def test_a_lease_withdrawal_fails_its_pending_runs_before_the_retirement_returns(tmp_path: Path) -> None:
    with service_record_runtime(tmp_path, model_runs=True) as runtime:
        service, announced = _admitted(runtime, SERVICE_ID)
        with ThreadPoolExecutor(max_workers=1) as pool:
            waiting = pool.submit(runtime.profiles._relay_model_run, runtime.profile_id, _lookup(), bytearray())
            run_id = announced.get(timeout=_ANNOUNCEMENT_SECONDS)

            _lock_person(runtime)

            # Well inside the lookup's own deadline: the withdrawal answered it, nothing waited it out.
            outcome, _ = waiting.result(timeout=5)
            assert service.model_run_fetch(run_id) is None

    assert outcome == ModelRunOutcome(refusal=ModelRunRefusalCode.SERVICE_UNAVAILABLE)


def test_a_lease_withdrawal_waits_for_the_disclosure_already_being_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    body = encode_model_run_body(ModelRunBody(prompt="Factura 7", max_output_tokens=16))
    with service_record_runtime(tmp_path, model_runs=True) as runtime:
        service, announced = _admitted(runtime, SERVICE_ID)
        write = model_runs_module.write_secret_chunks
        retirement: list[Future[None]] = []
        order: list[str] = []

        def write_while_retiring(channel: ByteChannel, data: bytearray, *, deadline: float) -> None:
            retirement.append(retiring.submit(_lock_person, runtime))
            with pytest.raises(TimeoutError):
                retirement[0].result(timeout=1)
            order.append("written")
            write(channel, data, deadline=deadline)

        monkeypatch.setattr(model_runs_module, "write_secret_chunks", write_while_retiring)
        with ThreadPoolExecutor(max_workers=1) as pool, ThreadPoolExecutor(max_workers=1) as retiring:
            waiting = pool.submit(runtime.profiles._relay_model_run, runtime.profile_id, _run(body), body)
            run_id = announced.get(timeout=_ANNOUNCEMENT_SECONDS)

            fetched = service.model_run_fetch(run_id)
            retirement[0].result(timeout=_ANNOUNCEMENT_SECONDS)
            order.append("retired")
            outcome, _ = waiting.result(timeout=_ANNOUNCEMENT_SECONDS)

        assert fetched is not None and decode_model_run_body(fetched[1]).prompt == "Factura 7"
        assert order == ["written", "retired"]
        assert outcome == ModelRunOutcome(refusal=ModelRunRefusalCode.SERVICE_UNAVAILABLE)


def test_an_answer_whose_text_arrives_after_the_lease_is_withdrawn_is_wiped_and_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    body = encode_model_run_body(ModelRunBody(prompt="Factura 7", max_output_tokens=16))
    with service_record_runtime(tmp_path, model_runs=True) as runtime:
        service, announced = _admitted(runtime, SERVICE_ID)
        read = model_runs_module.read_secret_chunks
        received: list[bytearray] = []

        def withdraw_before_the_text(channel: ByteChannel, byte_count: int, *, deadline: float) -> bytearray:
            # The service holds the text back past SecretReady while its parent session retires.
            _lock_person(runtime)
            text = read(channel, byte_count, deadline=deadline)
            received.append(text)
            return text

        monkeypatch.setattr(model_runs_module, "read_secret_chunks", withdraw_before_the_text)
        with ThreadPoolExecutor(max_workers=1) as pool:
            waiting = pool.submit(runtime.profiles._relay_model_run, runtime.profile_id, _run(body), body)
            run_id = announced.get(timeout=_ANNOUNCEMENT_SECONDS)
            assert service.model_run_fetch(run_id) is not None

            accepted = service.model_run_complete(
                run_id, ModelRunOutcome(served=_SERVED, text_byte_count=6), bytearray(b"forged")
            )
            outcome, text = waiting.result(timeout=_ANNOUNCEMENT_SECONDS)

        assert not accepted
        assert received == [bytearray(6)], "the late text is wiped, not handed to the worker"
        assert outcome == ModelRunOutcome(refusal=ModelRunRefusalCode.SERVICE_UNAVAILABLE)
        assert text == bytearray()
