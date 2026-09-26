"""The terminal journal record and the released conflict lease become durable together.

An operator acts on a settled operation as soon as its terminal state is
visible. If the conflict lease outlived that state, the next submission for
the same definition subject would be refused by an operation that is already
over. These proofs run the real filesystem journal and lease repositories.
"""

from __future__ import annotations

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from .....application.operations.capabilities import OperationRequestStoragePolicy
from .....application.operations.models import OperationIdentity, OperationTerminalReceipt
from .....application.operations.persistence.events import OperationPhaseEvent, OperationTerminalEvent
from .....application.operations.persistence.journal import OperationPersistedSnapshot
from .....application.operations.persistence.leases import (
    OperationLeaseDisposition,
    OperationLeaseObservationDisposition,
    OperationOwnerLease,
    operation_conflict_scope_reference,
)
from .....core.operations import OperationEffect, OperationLifecycle, OperationTerminalCondition
from .....tests.thread_file_io_probe import recording_file_io
from ...storage.errors import RepositoryError
from ..journal import OperationJournalRepository
from ..lease import OperationLeaseFilesystemRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_STARTED = datetime(2026, 9, 1, 9, tzinfo=UTC)
_SETTLED = _STARTED + timedelta(minutes=1)
_OPERATION_ID = "a" * 64
_DEFINITION_ID = "test.operation"
_SUBJECT_REF = "subject"
_SCOPE_REF = operation_conflict_scope_reference(definition_id=_DEFINITION_ID, subject_ref=_SUBJECT_REF)


def _identity() -> OperationIdentity:
    return OperationIdentity(operation_id=_OPERATION_ID, definition_id=_DEFINITION_ID, subject_ref=_SUBJECT_REF)


def _running() -> OperationPersistedSnapshot:
    event = OperationPhaseEvent(
        identity=_identity(),
        revision=0,
        sequence=1,
        timestamp=_STARTED,
        code="phase.0",
        phase_code="phase.0",
    )
    return OperationPersistedSnapshot(
        identity=_identity(),
        definition_contract_digest="c" * 64,
        request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
        request_reference="d" * 64,
        revision=0,
        lifecycle=OperationLifecycle.RUNNING,
        phase_code=event.phase_code,
        started_at=_STARTED,
        updated_at=_STARTED,
        execution_deadline=None,
        cleanup_deadline=None,
        cancellation_requested_at=None,
        cancellation_acknowledged_at=None,
        cancellation_deferred=False,
        event_cursor=1,
        events=(event,),
    )


def _progressed() -> OperationPersistedSnapshot:
    """A non-terminal successor, which only the ordinary commit may write."""
    event = OperationPhaseEvent(
        identity=_identity(),
        revision=1,
        sequence=2,
        timestamp=_SETTLED,
        code="phase.1",
        phase_code="phase.1",
    )
    return _running().model_copy(
        update={
            "revision": 1,
            "phase_code": event.phase_code,
            "updated_at": _SETTLED,
            "event_cursor": 2,
            "events": (event,),
        }
    )


def _terminal() -> OperationPersistedSnapshot:
    receipt = OperationTerminalReceipt(
        identity=_identity(),
        revision=1,
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=OperationEffect.NONE,
        settled_at=_SETTLED,
        result_ref="result:settled",
    )
    event = OperationTerminalEvent(
        identity=_identity(),
        revision=1,
        sequence=2,
        timestamp=_SETTLED,
        code="operation.terminal",
        receipt=receipt,
    )
    return OperationPersistedSnapshot.model_validate(
        _running()
        .model_copy(
            update={
                "revision": 1,
                "lifecycle": OperationLifecycle.TERMINAL,
                "terminal_condition": receipt.condition,
                "updated_at": _SETTLED,
                "event_cursor": 2,
                "events": (event,),
                "terminal_receipt": receipt,
            }
        )
        .model_dump()
    )


def _lease(*, token: str = "c" * 64) -> OperationOwnerLease:
    return OperationOwnerLease(
        operation_id=_OPERATION_ID,
        scope_ref=_SCOPE_REF,
        owner_id="b" * 64,
        token=token,
        acquired_at=_STARTED,
        expires_at=_STARTED + timedelta(hours=1),
    )


def _running_operation(storage_root: Path) -> OperationJournalRepository:
    """Hold the exact lease and write the running journal an owner would settle."""
    leases = OperationLeaseFilesystemRepository(storage_root=storage_root)
    acquired = asyncio.run(leases.acquire(_lease(), observed_at=_STARTED))
    assert acquired.disposition is OperationLeaseDisposition.ACQUIRED
    journal = OperationJournalRepository(storage_root=storage_root)
    asyncio.run(journal.create(_running(), lease=_lease()))
    return journal


def _observed_lease(storage_root: Path) -> OperationOwnerLease | None:
    observed = asyncio.run(
        OperationLeaseFilesystemRepository(storage_root=storage_root).inspect(
            _SCOPE_REF, _OPERATION_ID, observed_at=_SETTLED
        )
    )
    if observed.disposition is OperationLeaseObservationDisposition.ABSENT:
        return None
    return observed.current


def _durable_bytes(storage_root: Path) -> tuple[bytes, bytes]:
    journal_root = storage_root / "operation-journals"
    return (
        (journal_root / f"{_OPERATION_ID}.json").read_bytes(),
        (journal_root / f"{_SCOPE_REF}.lease.json").read_bytes(),
    )


def test_settlement_writes_the_terminal_record_and_frees_the_subject(tmp_path: Path) -> None:
    """After one settlement commit the journal is terminal and no lease holds the subject."""
    journal = _running_operation(tmp_path)
    assert _observed_lease(tmp_path) == _lease()

    asyncio.run(journal.commit_settlement(_terminal(), expected_revision=0, lease=_lease()))

    assert asyncio.run(journal.load(_OPERATION_ID)) == _terminal()
    assert _observed_lease(tmp_path) is None
    successor = OperationOwnerLease(
        operation_id="e" * 64,
        scope_ref=_SCOPE_REF,
        owner_id="1" * 64,
        token="2" * 64,
        acquired_at=_SETTLED,
        expires_at=_SETTLED + timedelta(minutes=10),
    )
    reacquired = asyncio.run(
        OperationLeaseFilesystemRepository(storage_root=tmp_path).acquire(successor, observed_at=_SETTLED)
    )
    assert reacquired.disposition is OperationLeaseDisposition.ACQUIRED


def test_settlement_writes_both_records_inside_one_hold_of_the_shared_lock(tmp_path: Path) -> None:
    """The journal-root lock is taken once, so no acquirer can run between the two writes.

    Lease acquisition takes this same lock. A settlement that released its
    lease in a second lock hold would show two acquisitions here, and a
    submitter could run between them and see a terminal operation still
    holding its subject.
    """
    journal = _running_operation(tmp_path)

    async def settle_on_one_known_worker() -> list[str]:
        loop = asyncio.get_running_loop()
        worker = ThreadPoolExecutor(max_workers=1)
        loop.set_default_executor(worker)
        worker_ident = await loop.run_in_executor(None, threading.get_ident)
        with recording_file_io(worker_ident) as recorded:
            await journal.commit_settlement(_terminal(), expected_revision=0, lease=_lease())
        return list(recorded)

    recorded = asyncio.run(settle_on_one_known_worker())

    lock_opens = [entry for entry in recorded if entry.startswith("open:") and entry.endswith(".repository.lock")]
    assert len(lock_opens) == 1, recorded
    after_lock = recorded[recorded.index(lock_opens[0]) + 1 :]
    installs = [entry for entry in after_lock if entry.startswith(("os.rename:", "os.replace:"))]
    assert any(f"{_OPERATION_ID}.json." in entry for entry in installs), recorded
    assert any(f"{_SCOPE_REF}.lease.json." in entry for entry in installs), recorded


def test_settlement_refuses_a_snapshot_that_is_not_terminal(tmp_path: Path) -> None:
    """Only a terminal successor gives up the lease; the stored records are untouched."""
    journal = _running_operation(tmp_path)
    before = _durable_bytes(tmp_path)

    with pytest.raises(RepositoryError, match="requires a terminal snapshot"):
        asyncio.run(journal.commit_settlement(_progressed(), expected_revision=0, lease=_lease()))

    assert _durable_bytes(tmp_path) == before
    assert _observed_lease(tmp_path) == _lease()


def test_settlement_refuses_a_lease_that_is_not_the_exact_holder(tmp_path: Path) -> None:
    """A settlement proves the exact live lease before it writes or releases anything."""
    journal = _running_operation(tmp_path)
    before = _durable_bytes(tmp_path)

    with pytest.raises(RepositoryError, match="exact current durable operation lease"):
        asyncio.run(journal.commit_settlement(_terminal(), expected_revision=0, lease=_lease(token="9" * 64)))

    assert _durable_bytes(tmp_path) == before
    assert _observed_lease(tmp_path) == _lease()
    assert asyncio.run(journal.load(_OPERATION_ID)).lifecycle is OperationLifecycle.RUNNING


def test_the_ordinary_commit_refuses_a_terminal_snapshot(tmp_path: Path) -> None:
    """No journal write can make an operation terminal while it keeps its lease."""
    journal = _running_operation(tmp_path)
    before = _durable_bytes(tmp_path)

    with pytest.raises(RepositoryError, match="only with its lease release"):
        asyncio.run(journal.commit(_terminal(), expected_revision=0, lease=_lease()))

    assert _durable_bytes(tmp_path) == before
    assert asyncio.run(journal.load(_OPERATION_ID)).lifecycle is OperationLifecycle.RUNNING

    asyncio.run(journal.commit(_progressed(), expected_revision=0, lease=_lease()))
    assert asyncio.run(journal.load(_OPERATION_ID)) == _progressed()
    assert _observed_lease(tmp_path) == _lease()
