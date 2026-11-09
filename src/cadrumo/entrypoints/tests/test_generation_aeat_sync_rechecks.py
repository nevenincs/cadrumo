"""A generation reads the census and the notification custody count once, and rechecks each cheaply.

Every test runs the composed readers over a real encrypted profile bucket: the
operation journal, the encrypted result custody and the notification document
store are the production adapters, and journal records are written through the
journal's own create and settlement doors.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import timedelta
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest

from ...adapters.persistence.operations import journal as journal_module
from ...adapters.persistence.operations.journal import OperationJournalRepository
from ...adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from ...adapters.persistence.operations.secure_references import operation_secure_reference_repository
from ...adapters.persistence.operations.tests.test_journal import STARTED, journal_snapshot
from ...adapters.persistence.profile.notification_documents import notification_document_repository
from ...adapters.persistence.profile.snapshots import SecureSnapshotRepository
from ...adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from ...application.live.notification_documents import NotificationDocumentRecord
from ...application.operations.models import OperationIdentity, OperationTerminalReceipt
from ...application.operations.persistence.events import OperationTerminalEvent
from ...application.operations.persistence.journal import (
    OperationPersistedSnapshot,
    OperationSecureReferenceStore,
)
from ...application.operations.persistence.leases import (
    OperationLeaseDisposition,
    OperationOwnerLease,
    operation_conflict_scope_reference,
)
from ...application.overview.home import HomeAccountSession, HomeSessionPosture
from ...application.tests.workbench_generation_support import NOW, Repository, plain_generation_door, profile_record
from ...application.user_profile.censal_observation import CensalObservation
from ...application.user_profile.censal_preview_operation import (
    CENSAL_PREVIEW_OPERATION_DEFINITION_ID,
    CensalPreviewOperationResult,
)
from ...application.user_profile.censal_readback import CensalHistoryRead
from ...application.workbench_generation_reader import SecureProfileWorkbenchGenerationReadDoorV1
from ...core.config import load_settings
from ...core.errors.hierarchy import InternalInvariantError
from ...core.operations import (
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
    profile_operation_subject,
)
from ...core.paths import effective_storage_root
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ..censal_readback_composition import StoredCensalHistoryReader, read_stored_censal_observation
from ..workbench_generation_composition import StoredNotificationCustodyCounter
from .test_censal_operation_operand import censal_operation_operand

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("authority_operation")]

_BUCKET_ID = "7c1d2e3f-4a5b-4c6d-8e7f-90a1b2c3d4e5"
_PROFILE_ID = UUID(_BUCKET_ID)


@dataclass(frozen=True, slots=True)
class _InFlight:
    """A journaled operation still holding its lease, to be settled later."""

    initial: OperationPersistedSnapshot
    lease: OperationOwnerLease


def _observation(minutes: int) -> CensalObservation:
    observation = censal_operation_operand().observation
    return observation.model_copy(update={"captured_at": observation.captured_at + timedelta(minutes=minutes)})


async def _open(operation_id: str, *, definition_id: str, subject_ref: str) -> _InFlight:
    """Create one journal record and its owner lease through the canonical adapters."""
    root = effective_storage_root()
    template = journal_snapshot(revision=0, sequence=1)
    identity = OperationIdentity(operation_id=operation_id, definition_id=definition_id, subject_ref=subject_ref)
    initial = OperationPersistedSnapshot.model_validate(
        template.model_copy(
            update={"identity": identity, "events": (template.events[0].model_copy(update={"identity": identity}),)}
        ).model_dump(mode="python")
    )
    lease = OperationOwnerLease(
        operation_id=operation_id,
        scope_ref=operation_conflict_scope_reference(definition_id=definition_id, subject_ref=subject_ref),
        owner_id="e" * 64,
        token="f" * 64,
        acquired_at=STARTED,
        expires_at=STARTED + timedelta(hours=1),
    )
    acquired = await OperationLeaseFilesystemRepository(storage_root=root).acquire(lease, observed_at=STARTED)
    assert acquired.disposition is OperationLeaseDisposition.ACQUIRED
    await OperationJournalRepository(storage_root=root).create(initial, lease=lease)
    return _InFlight(initial=initial, lease=lease)


async def _settle(
    in_flight: _InFlight, *, operands: OperationSecureReferenceStore, observation: CensalObservation | None
) -> None:
    """Settle a record: successfully with a stored preview result when given an observation, else interrupted."""
    settled_at = STARTED + timedelta(minutes=1)
    identity = in_flight.initial.identity
    result_ref = (
        None
        if observation is None
        else await operands.put(
            CensalPreviewOperationResult(
                profile_id=_PROFILE_ID, source_url=observation.source_url, observation=observation
            ),
            written_at=settled_at,
        )
    )
    receipt = OperationTerminalReceipt(
        identity=identity,
        revision=1,
        condition=OperationTerminalCondition.INTERRUPTED
        if result_ref is None
        else OperationTerminalCondition.SUCCEEDED,
        effect=OperationEffect.NONE,
        settled_at=settled_at,
        result_ref=result_ref,
    )
    terminal_event = OperationTerminalEvent(
        identity=identity, revision=1, sequence=2, timestamp=settled_at, code="operation.terminal", receipt=receipt
    )
    successor = OperationPersistedSnapshot.model_validate(
        in_flight.initial.model_copy(
            update={
                "revision": 1,
                "lifecycle": OperationLifecycle.TERMINAL,
                "terminal_condition": receipt.condition,
                "effect": receipt.effect,
                "updated_at": settled_at,
                "event_cursor": 2,
                "events": (terminal_event,),
                "terminal_receipt": receipt,
            }
        ).model_dump(mode="python")
    )
    await OperationJournalRepository(storage_root=effective_storage_root()).commit_settlement(
        successor, expected_revision=0, lease=in_flight.lease
    )


def _census(operation_id: str) -> _InFlight:
    return asyncio.run(
        _open(
            operation_id,
            definition_id=CENSAL_PREVIEW_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(_BUCKET_ID),
        )
    )


def _capture_census(operation_id: str, operands: OperationSecureReferenceStore, observation: CensalObservation) -> None:
    asyncio.run(_settle(_census(operation_id), operands=operands, observation=observation))


def _other_operations(*characters: str, operands: OperationSecureReferenceStore) -> None:
    for character in characters:
        operation_id = character * 64
        in_flight = asyncio.run(_open(operation_id, definition_id="test.operation", subject_ref=f"subject:{character}"))
        asyncio.run(_settle(in_flight, operands=operands, observation=None))


@contextmanager
def _profile(tmp_path: Path) -> Generator[OperationSecureReferenceStore]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        yield operation_secure_reference_repository(objects=profile.repository)


@pytest.fixture
def decodes(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """The journal records the real repository decodes, by operation id."""
    decoded: list[str] = []
    original = journal_module.SnapshotJournalRepository._decode_payload

    def counted(self: Any, operation_id: str, raw: str) -> Any:
        decoded.append(operation_id)
        return original(self, operation_id, raw)

    monkeypatch.setattr(journal_module.SnapshotJournalRepository, "_decode_payload", counted)
    return decoded


def _full_read() -> CensalObservation | None:
    return asyncio.run(read_stored_censal_observation(_PROFILE_ID))


def test_a_recheck_reads_only_census_records_and_records_created_since_the_read(
    tmp_path: Path, decodes: list[str]
) -> None:
    """Records known to belong to another definition are named, never read again."""
    first = _observation(0)
    with _profile(tmp_path) as operands:
        _other_operations("a", "b", "c", operands=operands)
        _capture_census("d" * 64, operands, first)
        reader = StoredCensalHistoryReader(_PROFILE_ID)
        prior = reader.read()
        assert prior.observation == first
        _other_operations("e", "f", operands=operands)
        decodes.clear()

        assert reader.recheck(prior) == first
        assert sorted(set(decodes)) == ["d" * 64, "e" * 64, "f" * 64]
        assert _full_read() == first


def test_a_census_capture_landing_after_the_read_changes_the_recheck(tmp_path: Path) -> None:
    first, second = _observation(0), _observation(5)
    with _profile(tmp_path) as operands:
        _other_operations("a", operands=operands)
        _capture_census("b" * 64, operands, first)
        reader = StoredCensalHistoryReader(_PROFILE_ID)
        prior = reader.read()
        _capture_census("0" * 64, operands, second)

        assert reader.recheck(prior) == second == _full_read()


def test_a_census_capture_in_flight_at_the_read_changes_the_recheck_when_it_settles(tmp_path: Path) -> None:
    observation = _observation(0)
    with _profile(tmp_path) as operands:
        _other_operations("a", operands=operands)
        in_flight = _census("b" * 64)
        reader = StoredCensalHistoryReader(_PROFILE_ID)
        prior = reader.read()
        assert prior.observation is None
        assert prior.census_operations == frozenset({"b" * 64})
        asyncio.run(_settle(in_flight, operands=operands, observation=observation))

        assert reader.recheck(prior) == observation == _full_read()


def test_a_recheck_refuses_an_unreadable_record_created_since_the_read(tmp_path: Path) -> None:
    """A record the read never classified might be a census capture, exactly as in a full read."""
    with _profile(tmp_path) as operands:
        _other_operations("a", operands=operands)
        reader = StoredCensalHistoryReader(_PROFILE_ID)
        prior = reader.read()
        _other_operations("b", operands=operands)
        unreadable = OperationJournalRepository(storage_root=effective_storage_root())._repository.path_for("b" * 64)
        unreadable.write_text("{}", encoding="utf-8")

        with pytest.raises(InternalInvariantError, match="cannot be verified"):
            reader.recheck(prior)


@dataclass
class _CountedCensus:
    """The composed census reader, counting reads and rechecks and running a hook between them."""

    reader: StoredCensalHistoryReader
    reads: int = 0
    rechecks: int = 0

    def read(self) -> CensalHistoryRead:
        self.reads += 1
        return self.reader.read()

    def recheck(self, prior: CensalHistoryRead) -> CensalObservation | None:
        self.rechecks += 1
        return self.reader.recheck(prior)


def _generation_door(
    operation: PinnedAuthorityOperation, census: _CountedCensus, *, mid_generation: Callable[[], None]
) -> SecureProfileWorkbenchGenerationReadDoorV1:
    """A generation over one declaration-free profile whose second session check runs ``mid_generation``.

    A capture checks the account session once before it reads anything and
    once more after every source, the census included, has been read and
    before the capture is rechecked.
    """
    checks = iter((False, True))

    def account_session() -> HomeAccountSession:
        if next(checks):
            mid_generation()
        return HomeAccountSession(posture=HomeSessionPosture.ACTIVE, profile_label="Perfil local", expires_at=NOW)

    return replace(
        plain_generation_door(operation, profile=Repository(profile_record(operation))),
        census_observation_reader=census,
        account_session_reader=account_session,
    )


def test_a_generation_reads_the_census_once_and_rechecks_it_once(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    with _profile(tmp_path) as operands:
        _other_operations("a", "b", operands=operands)
        _capture_census("c" * 64, operands, _observation(0))
        census = _CountedCensus(StoredCensalHistoryReader(_PROFILE_ID))

        _generation_door(authority_operation, census, mid_generation=lambda: None).read_workbench_generation_inputs()

        assert (census.reads, census.rechecks) == (1, 1)


def test_a_census_capture_landing_mid_generation_refuses_the_generation(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    with _profile(tmp_path) as operands:
        _other_operations("a", "b", operands=operands)
        _capture_census("c" * 64, operands, _observation(0))
        census = _CountedCensus(StoredCensalHistoryReader(_PROFILE_ID))
        door = _generation_door(
            authority_operation,
            census,
            mid_generation=lambda: _capture_census("d" * 64, operands, _observation(5)),
        )

        with pytest.raises(InternalInvariantError, match="changed during capture"):
            door.read_workbench_generation_inputs()
        assert (census.reads, census.rechecks) == (1, 1)


def _notification_document(certificado_id: str) -> NotificationDocumentRecord:
    return NotificationDocumentRecord(
        certificado_id=certificado_id,
        bucket_id=_BUCKET_ID,
        attachment_id="a" * 64,
        document_sha256="a" * 64,
        byte_size=12,
        source_url="https://sede.agenciatributaria.gob.es/notificaciones/detalle",
        fetched_at=STARTED,
        parse_refusal="SancionParseError: no text layer",
    )


def test_the_custody_count_holds_on_unchanged_rows_and_is_counted_again_when_one_is_stored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    listings: list[str] = []
    original = SecureSnapshotRepository.list_snapshots

    def counted(self: Any) -> Any:
        listings.append("documents")
        return original(self)

    monkeypatch.setattr(SecureSnapshotRepository, "list_snapshots", counted)
    with _profile(tmp_path):
        documents = notification_document_repository(_BUCKET_ID, load_settings())
        documents.save(_notification_document("2699101808461"))
        counter = StoredNotificationCustodyCounter(_BUCKET_ID)
        prior = counter.count()
        assert prior.count == 1 and len(prior.stored_keys) == 1

        assert counter.recount(prior) == 1
        assert listings == ["documents"], "unchanged rows are not read again"
        documents.save(_notification_document("2596230606502"))
        assert counter.recount(prior) == 2
