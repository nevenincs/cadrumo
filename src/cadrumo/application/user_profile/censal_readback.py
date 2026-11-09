"""Read census evidence from its existing operation journals and encrypted operands."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from ...core.errors.hierarchy import InternalInvariantError
from ...core.operations import OperationLifecycle, OperationTerminalCondition, profile_operation_subject
from ..operations.models import OperationId
from ..operations.persistence.journal import (
    OperationJournal,
    OperationPersistedSnapshot,
    OperationRecoveryInventoryDeltaReader,
    OperationRecoveryInventoryDisposition,
    OperationRecoveryInventoryEntry,
    OperationSecureReferenceStore,
)
from .censal_observation import CensalObservation
from .censal_operation import CENSAL_OPERATION_DEFINITION_ID, CensalOperationResult, CensalReviewedOperand
from .censal_preview_operation import CENSAL_PREVIEW_OPERATION_DEFINITION_ID, CensalPreviewOperationResult

type CensalObservationReader = Callable[[UUID], Awaitable[CensalObservation | None]]


_INVENTORY_PAGE = 128


@dataclass(frozen=True, slots=True)
class CensalHistoryRead:
    """One census lookup's answer, with the journal records it was derived from.

    ``classified`` names every record the lookup classified and
    ``census_operations`` those opened for a census capture, at any stage. A
    record's definition is fixed when it is created, so together they say
    which records could change the answer later without reading any other.
    """

    observation: CensalObservation | None
    classified: frozenset[OperationId]
    census_operations: frozenset[OperationId]


class CensalHistoryJournal(OperationJournal, OperationRecoveryInventoryDeltaReader, Protocol):
    """A journal that can also name its records and classify only those a caller has not seen."""


class CensalHistoryReader(Protocol):
    """Read the stored census once, then answer it again from the records that could have changed it."""

    def read(self) -> CensalHistoryRead:
        """Read the newest stored census observation and the records it was derived from."""
        ...

    def recheck(self, prior: CensalHistoryRead) -> CensalObservation | None:
        """Answer the census lookup again now, as a full read would, from ``prior``'s records and new ones."""
        ...


def _census_subjects(profile_id: UUID) -> dict[str, str]:
    """The subject each census definition is opened for, for this profile."""
    return {
        CENSAL_OPERATION_DEFINITION_ID: str(profile_id),
        CENSAL_PREVIEW_OPERATION_DEFINITION_ID: profile_operation_subject(str(profile_id)),
    }


def _is_census_record(entry: OperationRecoveryInventoryEntry, subjects: dict[str, str]) -> bool:
    """Say whether a classified record was opened for a census capture, refusing an unreadable one."""
    if entry.disposition is OperationRecoveryInventoryDisposition.REFUSED:
        raise InternalInvariantError("census capture history cannot be verified")
    return entry.definition_id in subjects


async def read_latest_censal_observation(
    profile_id: UUID,
    *,
    journal: OperationJournal,
    operands: OperationSecureReferenceStore,
) -> CensalObservation | None:
    """Resolve the newest successful own-profile capture, including rejected local adoption.

    A preview or a review owns its evidence already. Reading that custody avoids
    a second mutable snapshot store. Failed operations cannot replace a previous
    capture, and a historical preview without evidence is not an empty census.
    """
    return (await read_censal_history(profile_id, journal=journal, operands=operands)).observation


async def read_censal_history(
    profile_id: UUID,
    *,
    journal: OperationJournal,
    operands: OperationSecureReferenceStore,
) -> CensalHistoryRead:
    """Resolve the newest census capture as :func:`read_latest_censal_observation` does, naming its records."""
    subjects = _census_subjects(profile_id)
    classified: set[OperationId] = set()
    census_operations: list[OperationId] = []
    after: str | None = None
    while True:
        page = await journal.inventory_page(after=after, limit=_INVENTORY_PAGE)
        for entry in page.entries:
            classified.add(entry.operation_id)
            # The inventory read each record to classify it, so a record opened for any other
            # definition is passed over without reading it again.
            if _is_census_record(entry, subjects):
                census_operations.append(entry.operation_id)
        if not page.has_more:
            break
        after = page.next_cursor
    return CensalHistoryRead(
        observation=await _latest_observation(census_operations, profile_id, subjects, journal, operands),
        classified=frozenset(classified),
        census_operations=frozenset(census_operations),
    )


async def refresh_censal_history(
    profile_id: UUID,
    prior: CensalHistoryRead,
    *,
    journal: CensalHistoryJournal,
    operands: OperationSecureReferenceStore,
) -> CensalHistoryRead:
    """Bring ``prior`` up to date as a full read would now, reading only the records that could change it.

    A record's definition and subject are fixed at creation and operation
    identifiers are never reused, so a record ``prior`` classified as another
    definition cannot become a census capture. The answer can change only
    through a census record ``prior`` saw (it settled, or it is gone) or a
    record created since; this reads exactly those. The records it names are
    the ones a full read would name now: every present record, and among them
    every census record. Unlike a full read it does not re-read records
    already known to belong to other definitions, so one of those becoming
    unreadable afterwards is not reported here.
    """
    subjects = _census_subjects(profile_id)
    delta = await journal.inventory_delta(known=prior.classified)
    created = frozenset(entry.operation_id for entry in delta.entries)
    created_census = frozenset(entry.operation_id for entry in delta.entries if _is_census_record(entry, subjects))
    census_operations = (prior.census_operations & delta.present) | created_census
    return CensalHistoryRead(
        observation=await _latest_observation(sorted(census_operations), profile_id, subjects, journal, operands),
        classified=(prior.classified & delta.present) | created,
        census_operations=census_operations,
    )


async def _latest_observation(
    census_operations: Iterable[OperationId],
    profile_id: UUID,
    subjects: dict[str, str],
    journal: OperationJournal,
    operands: OperationSecureReferenceStore,
) -> CensalObservation | None:
    """The newest observation among census records, read in identifier order; the first wins a tie."""
    latest: CensalObservation | None = None
    for operation_id in census_operations:
        snapshot = await journal.load(operation_id)
        if snapshot.lifecycle is not OperationLifecycle.TERMINAL:
            continue
        observation = await _snapshot_observation(snapshot, profile_id, subjects, operands)
        if observation is not None and (latest is None or observation.captured_at > latest.captured_at):
            latest = observation
    return latest


async def _snapshot_observation(
    snapshot: OperationPersistedSnapshot,
    profile_id: UUID,
    subjects: dict[str, str],
    operands: OperationSecureReferenceStore,
) -> CensalObservation | None:
    if (
        snapshot.identity.subject_ref != subjects.get(snapshot.identity.definition_id)
        or snapshot.terminal_condition is not OperationTerminalCondition.SUCCEEDED
    ):
        return None
    receipt = snapshot.terminal_receipt
    if receipt is None or receipt.result_ref is None:
        raise InternalInvariantError("settled census capture has no result reference")
    if snapshot.identity.definition_id == CENSAL_PREVIEW_OPERATION_DEFINITION_ID:
        preview = await operands.resolve(receipt.result_ref, CensalPreviewOperationResult)
        if preview.profile_id != profile_id:
            raise InternalInvariantError("stored census preview belongs to another profile")
        observation = preview.observation
    else:
        result = await operands.resolve(receipt.result_ref, CensalOperationResult)
        reviewed = await operands.resolve(result.reviewed_proposal_digest, CensalReviewedOperand)
        if reviewed.baseline.profile_id != str(profile_id):
            raise InternalInvariantError("stored census review belongs to another profile")
        observation = reviewed.observation
    return observation
