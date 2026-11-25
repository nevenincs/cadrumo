"""Control dispatch timing separates a handler's own work from peer and drain waits."""

from __future__ import annotations

import asyncio
import logging
import struct
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.persistence.storage.master_key.profile_worker_custody import ProfileWorkerCustody
from cadrumo.application.operations.drain import OperationDrainResult
from cadrumo.application.user_profile.access_contracts import ProfileAccessBinding
from cadrumo.tests.log_records import delivered_records
from cadrumo_client.contracts.contracts import Peer, RefusalCode, RefusalError
from cadrumo_client.contracts.sign_in_outcomes import ProfileLoginOutcome
from cadrumo_client.contracts.worker_identity import ProfileWorkerIdentity
from cadrumo_client.transport.frame_io import document_frame
from cadrumo_runtime.contracts.profile_worker import ProfileWorkerControlRequest, ProfileWorkerProofTransfer

from ...adapters.worker_transport import WorkerChannel
from .. import worker_service
from ..control_dispatch_waits import ControlDispatchWaits, awaiting, control_dispatch_waits
from ..operation_host import ProfileWorkerOperationHost
from ..profile_login import ProfileWorkerHumanLogin

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_SLOW = "profile_worker_control_dispatch_slow"
_WAITED = "profile_worker_control_dispatch_waited"


class _Clock:
    """A monotonic clock that only the scenario advances."""

    def __init__(self) -> None:
        self.now = 10.0

    def monotonic(self) -> float:
        return self.now


class _PeerChannel:
    """Real framing over queued bytes; each read stands for a peer that answers late."""

    def __init__(self, clock: _Clock, *, read_delay: float) -> None:
        self.peer = Peer(os_owner_id="synthetic-owner", process_id=41)
        self.incoming = bytearray()
        self.written: list[bytes] = []
        self._clock = clock
        self._read_delay = read_delay

    def read_exact(self, count: int, *, deadline: float) -> bytes:
        assert deadline > 0
        self._clock.now += self._read_delay
        if len(self.incoming) < count:
            raise RefusalError(RefusalCode.CONNECTION_CLOSED)
        result = bytes(self.incoming[:count])
        del self.incoming[:count]
        return result

    def write_all(self, payload: bytes | bytearray, *, deadline: float) -> None:
        assert deadline > 0
        self.written.append(bytes(payload))

    def close(self) -> None:
        pass


class _Attempt:
    def raise_if_cancelled(self) -> None:
        pass


class _Human:
    """Spend a scenario-chosen amount of the handler's own work on the proof."""

    def __init__(self, clock: _Clock, *, own_work: float) -> None:
        self._clock = clock
        self._own_work = own_work
        self.secrets: list[bytes] = []

    def require_attempt(self, attempt_id: UUID) -> _Attempt:
        del attempt_id
        return _Attempt()

    def _prove(self, secret: bytearray) -> tuple[UUID, ProfileLoginOutcome]:
        self.secrets.append(bytes(secret))
        self._clock.now += self._own_work
        instant = datetime.now(UTC)
        return uuid4(), ProfileLoginOutcome(
            bucket_id=str(uuid4()),
            label="Synthetic human profile",
            authenticated_at=instant,
            idle_deadline=instant,
            absolute_deadline=instant,
            session_persisted=False,
            already_authenticated=False,
        )

    def authenticate(
        self, secret: bytearray, *, timeout_deadline: float | None, attempt_id: UUID
    ) -> tuple[UUID, ProfileLoginOutcome]:
        del timeout_deadline, attempt_id
        return self._prove(secret)

    def resume(self, secret: bytearray, *, login_id: str | None, attempt_id: UUID) -> tuple[UUID, ProfileLoginOutcome]:
        del login_id, attempt_id
        return self._prove(secret)


class _Custody:
    def __init__(self) -> None:
        self.identity = ProfileWorkerIdentity(
            worker_id=uuid4(),
            runtime_boot_id=uuid4(),
            binding=ProfileAccessBinding(
                profile_id=uuid4(),
                installation_id=uuid4(),
                os_owner_id="synthetic-owner",
                custody_generation=1,
                dek_epoch=uuid4(),
            ),
        )


def _context(
    channel: _PeerChannel,
    *,
    human: _Human | None = None,
    operation_release: worker_service.worker_cleanup.WorkerRelease[OperationDrainResult] | None = None,
    upload_release: worker_service.worker_cleanup.WorkerRelease[None] | None = None,
) -> worker_service.WorkerControl:
    return worker_service.WorkerControl(
        channel=cast(WorkerChannel, channel),
        custody=cast(ProfileWorkerCustody, _Custody()),
        human=cast(ProfileWorkerHumanLogin, human or object()),
        operations=cast(ProfileWorkerOperationHost, object()),
        uploads=cast(worker_service.WorkerSubmissionStaging, object()),
        failed=asyncio.Event(),
        operation_release=operation_release
        or cast(worker_service.worker_cleanup.WorkerRelease[OperationDrainResult], object()),
        upload_release=upload_release or cast(worker_service.worker_cleanup.WorkerRelease[None], object()),
        changed=asyncio.Event(),
    )


def _proof_request(action: str) -> tuple[ProfileWorkerControlRequest, UUID]:
    attempt = uuid4()
    request = ProfileWorkerControlRequest.model_validate(
        {
            "request_id": uuid4(),
            "action": action,
            "proof_attempt_id": attempt,
            "originating_login_id": "synthetic-login" if action == "receipt" else None,
        }
    )
    return request, attempt


def _queue_proof(channel: _PeerChannel, attempt: UUID, secret: bytes) -> None:
    channel.incoming.extend(document_frame(ProfileWorkerProofTransfer(proof_attempt_id=attempt, cancelled=False)))
    channel.incoming.extend(b"S" + struct.pack("!I", len(secret)) + secret)


def _timing_records(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [
        record
        for record in delivered_records(caplog, worker_service.log.name)
        if record.getMessage() in {_SLOW, _WAITED}
    ]


@pytest.mark.parametrize(
    "action,own_work,warns,budget",
    [
        ("receipt", 0.3, False, 0.5),
        ("receipt", 0.6, True, 0.5),
        ("password", 0.6, False, 1.5),
        ("password", 1.6, True, 1.5),
    ],
)
def test_proof_dispatch_budget_counts_own_work_and_reports_peer_reads_apart(
    action: str,
    own_work: float,
    warns: bool,
    budget: float,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    clock = _Clock()
    monkeypatch.setattr(worker_service, "time", SimpleNamespace(monotonic=clock.monotonic))
    caplog.set_level(logging.DEBUG, logger=worker_service.log.name)
    # Four reads: the transfer header and body, then the secret header and body.
    channel = _PeerChannel(clock, read_delay=0.5)
    human = _Human(clock, own_work=own_work)
    request, attempt = _proof_request(action)
    _queue_proof(channel, attempt, b"synthetic-proof")

    disposition = asyncio.run(worker_service._timed_control_dispatch(_context(channel, human=human), request))

    assert disposition == "handled"
    assert human.secrets == [b"synthetic-proof"]
    assert channel.written, "the proof outcome is still written to the peer"
    [record] = _timing_records(caplog)
    assert record.getMessage() == (_SLOW if warns else _WAITED)
    assert record.levelno == (logging.WARNING if warns else logging.INFO)
    assert {
        "request_action": record.__dict__["request_action"],
        "elapsed_seconds": record.__dict__["elapsed_seconds"],
        "own_work_seconds": record.__dict__["own_work_seconds"],
        "peer_wait_seconds": record.__dict__["peer_wait_seconds"],
        "drain_wait_seconds": record.__dict__["drain_wait_seconds"],
        "budget_seconds": record.__dict__["budget_seconds"],
        "outcome": record.__dict__["outcome"],
    } == {
        "request_action": action,
        "elapsed_seconds": round(2.0 + own_work, 3),
        "own_work_seconds": own_work,
        "peer_wait_seconds": 2.0,
        "drain_wait_seconds": 0.0,
        "budget_seconds": budget,
        "outcome": "completed",
    }


def test_a_refused_peer_read_still_counts_as_peer_wait(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    clock = _Clock()
    monkeypatch.setattr(worker_service, "time", SimpleNamespace(monotonic=clock.monotonic))
    caplog.set_level(logging.DEBUG, logger=worker_service.log.name)
    # The peer never sends the transfer: one header read waits and is refused.
    channel = _PeerChannel(clock, read_delay=0.8)
    request, _attempt = _proof_request("receipt")

    with pytest.raises(RefusalError):
        asyncio.run(worker_service._timed_control_dispatch(_context(channel, human=_Human(clock, own_work=0)), request))

    [record] = _timing_records(caplog)
    assert record.getMessage() == _WAITED and record.levelno == logging.INFO
    assert (record.__dict__["peer_wait_seconds"], record.__dict__["own_work_seconds"]) == (0.8, 0.0)
    assert record.__dict__["outcome"] == "raised"


def test_stop_keeps_its_drain_and_final_peer_read_out_of_the_own_work_budget(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    clock = _Clock()
    monkeypatch.setattr(worker_service, "time", SimpleNamespace(monotonic=clock.monotonic))
    caplog.set_level(logging.DEBUG, logger=worker_service.log.name)
    channel = _PeerChannel(clock, read_delay=4.0)
    channel.incoming.extend(b"\x00")

    async def drain_operations() -> OperationDrainResult:
        clock.now += 3.0
        return OperationDrainResult(unresolved=(), recovery_required=())

    async def close_uploads() -> None:
        clock.now += 1.0

    context = _context(
        channel,
        operation_release=worker_service.worker_cleanup.WorkerRelease(drain_operations),
        upload_release=worker_service.worker_cleanup.WorkerRelease(close_uploads),
    )
    request = ProfileWorkerControlRequest(action="stop", request_id=uuid4())

    disposition = asyncio.run(worker_service._timed_control_dispatch(context, request))

    assert disposition == "stop"
    assert channel.written and not channel.incoming
    [record] = _timing_records(caplog)
    assert record.getMessage() == _WAITED and record.levelno == logging.INFO
    assert {
        "drain_wait_seconds": record.__dict__["drain_wait_seconds"],
        "peer_wait_seconds": record.__dict__["peer_wait_seconds"],
        "own_work_seconds": record.__dict__["own_work_seconds"],
    } == {"drain_wait_seconds": 4.0, "peer_wait_seconds": 4.0, "own_work_seconds": 0.0}


@pytest.mark.parametrize("own_work,warns", [(0.4, False), (0.6, True)])
def test_slow_dispatch_budget_subtracts_only_measured_waits(
    own_work: float, warns: bool, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    clock = _Clock()
    monkeypatch.setattr(worker_service, "time", SimpleNamespace(monotonic=clock.monotonic))
    caplog.set_level(logging.DEBUG, logger=worker_service.log.name)
    request = ProfileWorkerControlRequest(action="status", request_id=uuid4())
    waits = ControlDispatchWaits(clock.monotonic)
    with waits.measure("peer"):
        clock.now += 2.0
    clock.now += own_work

    worker_service.record_control_dispatch_elapsed(request, handler_started=10.0, outcome="completed", waits=waits)

    [record] = _timing_records(caplog)
    assert record.getMessage() == (_SLOW if warns else _WAITED)
    assert record.__dict__["own_work_seconds"] == own_work


def test_waits_outside_a_dispatch_are_not_attributed_and_each_dispatch_starts_empty() -> None:
    clock = _Clock()
    with awaiting("peer"):
        clock.now += 1.0
    with control_dispatch_waits(clock.monotonic) as first:
        with awaiting("peer"):
            clock.now += 1.0
        with control_dispatch_waits(clock.monotonic) as nested:
            assert nested.total() == 0.0
        with awaiting("drain"):
            clock.now += 0.5
    assert (first.seconds("peer"), first.seconds("drain")) == (1.0, 0.5)
    with control_dispatch_waits(clock.monotonic) as second:
        assert second.total() == 0.0
