"""Direct contract tests for operation journal ports and lease facts."""

from __future__ import annotations

import asyncio
import inspect
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from pydantic import BaseModel, ConfigDict, TypeAdapter, ValidationError

from ....core import OperationLifecycle
from ....core.identity import ContentDigest
from .. import (
    OperationEventStream,
    OperationIdentity,
    OperationJournal,
    OperationLeaseDisposition,
    OperationLeaseRepository,
    OperationLeaseResult,
    OperationOwnerLease,
    OperationReplayLimit,
    OperationReplayPage,
    OperationReplayStatus,
    OperationRequest,
    OperationSecureReferenceStore,
)
from .._events import OperationEvent, OperationPhaseEvent
from .._models import OperationRevision, OperationSnapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


class Operand(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    value: str


class JournalPort:
    def __init__(self, snapshot: OperationSnapshot[Operand]) -> None:
        self.snapshot = snapshot
        self.committed = False

    async def load(self, operation_id: str) -> OperationSnapshot[BaseModel]:
        assert operation_id == self.snapshot.identity.operation_id
        return self.snapshot

    async def commit(
        self,
        snapshot: OperationSnapshot[BaseModel],
        events: tuple[OperationEvent, ...],
        *,
        expected_revision: OperationRevision,
        lease: OperationOwnerLease,
    ) -> None:
        assert snapshot == self.snapshot
        assert events == ()
        assert expected_revision == snapshot.revision
        assert lease.operation_id == snapshot.identity.operation_id
        self.committed = True


class EventStreamPort:
    async def read_after(self, operation_id: str, cursor: int, *, limit: int) -> OperationReplayPage:
        assert operation_id == "a" * 64
        assert limit == 10
        return OperationReplayPage(
            status=OperationReplayStatus.CAUGHT_UP, requested_cursor=cursor, events=(), next_cursor=cursor
        )


class LeasePort:
    def __init__(self, result: OperationLeaseResult) -> None:
        self.result = result

    async def acquire(self, operation_id: str, owner_id: str, *, expires_at: datetime) -> OperationLeaseResult:
        assert operation_id == "a" * 64 and owner_id == "b" * 64 and expires_at > self.result.observed_at
        return self.result

    async def inspect(self, operation_id: str) -> OperationLeaseResult:
        assert operation_id == "a" * 64
        return self.result

    async def compare_and_swap(
        self, predecessor: OperationOwnerLease | None, *, owner_id: str, expires_at: datetime
    ) -> OperationLeaseResult:
        assert predecessor is None and owner_id == "b" * 64 and expires_at > self.result.observed_at
        return self.result

    async def release(self, lease: OperationOwnerLease) -> OperationLeaseResult:
        assert lease == self.result.current
        return self.result


class SecureReferencePort:
    def __init__(self, operand: Operand) -> None:
        self.operand = operand

    async def put(self, operand: BaseModel) -> ContentDigest:
        assert operand == self.operand
        return "d" * 64

    async def resolve(self, reference: ContentDigest, operand_type: type[Operand]) -> Operand:
        assert reference == "d" * 64 and isinstance(self.operand, operand_type)
        return self.operand


def _snapshot() -> OperationSnapshot[Operand]:
    observed = datetime(2026, 8, 13, 20, tzinfo=UTC)
    identity = OperationIdentity(operation_id="a" * 64, definition_id="test.operation", subject_ref="subject")
    return OperationSnapshot[Operand](
        identity=identity,
        request=OperationRequest[Operand](
            definition_id=identity.definition_id,
            subject_ref=identity.subject_ref,
            payload=Operand(value="operand"),
        ),
        revision=0,
        lifecycle=OperationLifecycle.RUNNING,
        updated_at=observed,
    )


def test_public_ports_accept_complete_structural_implementations_and_invoke_every_method() -> None:
    snapshot = _snapshot()
    lease = OperationOwnerLease(
        operation_id=snapshot.identity.operation_id,
        owner_id="b" * 64,
        token="c" * 64,
        acquired_at=snapshot.updated_at,
        expires_at=datetime(2026, 8, 13, 20, 1, tzinfo=UTC),
    )
    result = OperationLeaseResult(
        disposition=OperationLeaseDisposition.ACQUIRED,
        observed_at=snapshot.updated_at,
        evidence_ref="d" * 64,
        current=lease,
    )
    journal, stream, leases = JournalPort(snapshot), EventStreamPort(), LeasePort(result)
    secure = SecureReferencePort(snapshot.request.payload)
    assert isinstance(journal, OperationJournal)
    assert isinstance(stream, OperationEventStream)
    assert isinstance(leases, OperationLeaseRepository)
    assert isinstance(secure, OperationSecureReferenceStore)
    assert asyncio.run(journal.load(snapshot.identity.operation_id)) == snapshot
    asyncio.run(journal.commit(snapshot, (), expected_revision=0, lease=lease))
    assert journal.committed
    assert asyncio.run(stream.read_after("a" * 64, 0, limit=10)).status is OperationReplayStatus.CAUGHT_UP
    assert asyncio.run(leases.acquire("a" * 64, "b" * 64, expires_at=lease.expires_at)) == result
    assert asyncio.run(leases.inspect("a" * 64)) == result
    assert asyncio.run(leases.compare_and_swap(None, owner_id="b" * 64, expires_at=lease.expires_at)) == result
    assert asyncio.run(leases.release(lease)) == result
    reference = asyncio.run(secure.put(snapshot.request.payload))
    assert asyncio.run(secure.resolve(reference, Operand)) == snapshot.request.payload


def test_public_port_signatures_pin_keywords() -> None:
    assert tuple(inspect.signature(OperationJournal.commit).parameters) == (
        "self",
        "snapshot",
        "events",
        "expected_revision",
        "lease",
    )
    assert tuple(inspect.signature(OperationEventStream.read_after).parameters) == (
        "self",
        "operation_id",
        "cursor",
        "limit",
    )
    assert tuple(inspect.signature(OperationLeaseRepository.acquire).parameters) == (
        "self",
        "operation_id",
        "owner_id",
        "expires_at",
    )
    assert tuple(inspect.signature(OperationLeaseRepository.compare_and_swap).parameters) == (
        "self",
        "predecessor",
        "owner_id",
        "expires_at",
    )
    assert tuple(inspect.signature(OperationSecureReferenceStore.resolve).parameters) == (
        "self",
        "reference",
        "operand_type",
    )


def test_public_ports_refuse_incomplete_implementations() -> None:
    assert not isinstance(SimpleNamespace(load=lambda: None), OperationJournal)
    assert not isinstance(SimpleNamespace(), OperationEventStream)
    assert not isinstance(SimpleNamespace(acquire=lambda: None, inspect=lambda: None), OperationLeaseRepository)
    assert not isinstance(SimpleNamespace(resolve=lambda: None), OperationSecureReferenceStore)


def test_owner_lease_requires_a_positive_utc_window() -> None:
    acquired = datetime(2026, 8, 13, 20, tzinfo=UTC)
    with pytest.raises(ValidationError):
        OperationOwnerLease(
            operation_id="a" * 64, owner_id="b" * 64, token="c" * 64, acquired_at=acquired, expires_at=acquired
        )


def test_lease_and_replay_results_are_fail_closed() -> None:
    observed = datetime(2026, 8, 13, 20, tzinfo=UTC)
    for disposition in OperationLeaseDisposition:
        with pytest.raises(ValidationError):
            OperationLeaseResult(disposition=disposition, observed_at=observed, evidence_ref="d" * 64)
    with pytest.raises(ValidationError, match="at least one event"):
        OperationReplayPage(status=OperationReplayStatus.PAGE, requested_cursor=0, events=(), next_cursor=0)
    with pytest.raises(ValidationError):
        OperationReplayPage(status=OperationReplayStatus.CAUGHT_UP, requested_cursor=0, events=(), next_cursor=-1)
    with pytest.raises(ValidationError):
        TypeAdapter(OperationReplayLimit).validate_python(0)
    with pytest.raises(ValidationError):
        TypeAdapter(OperationReplayLimit).validate_python(1_001)


def test_replay_page_binds_ordered_events_to_next_cursor() -> None:
    snapshot = _snapshot()
    first = OperationPhaseEvent(
        identity=snapshot.identity,
        revision=0,
        sequence=1,
        timestamp=snapshot.updated_at,
        code="phase.started",
        phase_code="phase.started",
    )
    second = first.model_copy(update={"sequence": 2})
    assert (
        OperationReplayPage(
            status=OperationReplayStatus.PAGE, requested_cursor=0, events=(first, second), next_cursor=2
        ).next_cursor
        == 2
    )
    with pytest.raises(ValidationError, match="contiguous"):
        OperationReplayPage(
            status=OperationReplayStatus.PAGE, requested_cursor=0, events=(second, first), next_cursor=1
        )
    with pytest.raises(ValidationError, match="final event sequence"):
        OperationReplayPage(
            status=OperationReplayStatus.PAGE, requested_cursor=0, events=(first, second), next_cursor=1
        )


def test_lease_transition_correlations_refuse_planted_identity_and_time_mutations() -> None:
    observed = datetime(2026, 8, 13, 20, 2, tzinfo=UTC)
    predecessor = OperationOwnerLease(
        operation_id="a" * 64,
        owner_id="b" * 64,
        token="c" * 64,
        acquired_at=datetime(2026, 8, 13, 20, tzinfo=UTC),
        expires_at=datetime(2026, 8, 13, 20, 1, tzinfo=UTC),
    )
    current = OperationOwnerLease(
        operation_id="a" * 64,
        owner_id="e" * 64,
        token="f" * 64,
        acquired_at=observed,
        expires_at=datetime(2026, 8, 13, 20, 3, tzinfo=UTC),
    )
    accepted = OperationLeaseResult(
        disposition=OperationLeaseDisposition.TAKEN_OVER,
        observed_at=observed,
        evidence_ref="d" * 64,
        predecessor=predecessor,
        current=current,
    )
    assert accepted.current == current
    for mutation, message in (
        ({"current": current.model_copy(update={"operation_id": "9" * 64})}, "operation identity"),
        ({"current": current.model_copy(update={"owner_id": predecessor.owner_id})}, "change owner and token"),
        ({"current": current.model_copy(update={"token": predecessor.token})}, "change owner and token"),
        (
            {"predecessor": predecessor.model_copy(update={"expires_at": current.expires_at})},
            "expired predecessor",
        ),
    ):
        with pytest.raises(ValidationError, match=message):
            OperationLeaseResult(
                disposition=OperationLeaseDisposition.TAKEN_OVER,
                observed_at=observed,
                evidence_ref="d" * 64,
                predecessor=mutation.get("predecessor", predecessor),
                current=mutation.get("current", current),
            )


def test_replay_statuses_bind_requested_cursor_and_restart_boundary() -> None:
    caught_up = OperationReplayPage(
        status=OperationReplayStatus.CAUGHT_UP, requested_cursor=8, events=(), next_cursor=8
    )
    assert caught_up.next_cursor == caught_up.requested_cursor
    for status in (OperationReplayStatus.EXPIRED, OperationReplayStatus.COMPACTED):
        page = OperationReplayPage(status=status, requested_cursor=2, events=(), next_cursor=7, restart_cursor=7)
        assert page.restart_cursor == 7
        with pytest.raises(ValidationError, match="advance beyond"):
            OperationReplayPage(
                status=status,
                requested_cursor=100,
                events=(),
                next_cursor=7,
                restart_cursor=7,
            )
    with pytest.raises(ValidationError, match="preserve the requested cursor"):
        OperationReplayPage(status=OperationReplayStatus.CAUGHT_UP, requested_cursor=8, events=(), next_cursor=9)
    with pytest.raises(ValidationError, match="contiguous"):
        snapshot = _snapshot()
        stale = OperationPhaseEvent(
            identity=snapshot.identity,
            revision=0,
            sequence=1,
            timestamp=snapshot.updated_at,
            code="phase.started",
            phase_code="phase.started",
        )
        OperationReplayPage(status=OperationReplayStatus.PAGE, requested_cursor=1, events=(stale,), next_cursor=1)
