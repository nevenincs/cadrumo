"""Per-work-unit chronological history assembly.

Surfaces a unified timeline of every event the operator's work unit
emitted across its lifecycle: creation, renames, calculations,
verifications, filings, supersessions, amendments, and discards.

The catalogue substrate is the bucket-scoped append-only event log loaded from
:class:`BucketEventHistoryRepository`. Events scoped to a work unit land under
four object types — ``WORK_UNIT``, ``CALCULATION_REVISION``,
``VERIFICATION_REPORT``, and ``FILING_RECORD`` — so the assembler walks each
related object id and merges the emitted :class:`BucketEvent` streams in
chronological order.

The normalized records remain the source of relational truth:
:class:`WorkUnit` selects the lifecycle root, :class:`CalculationRevision`
identifies calculation attempts under it, :class:`VerificationReport` identifies
verification outcomes for those revisions, and :class:`ModeloRecord` identifies
local filing records. The event history explains how those records changed; it
does not replace their catalogues.

The assembler is pure read: no mutation, no remote contact.

See Also:
    :mod:`aeat.application.modelo._work_lifecycle`:
        Emits work-unit create, rename, and discard events.
    :mod:`aeat.application.modelo._calculation_actions`:
        Persists calculation revisions and ``MODELO_CALCULATION_CREATED`` events.
    :mod:`aeat.application.modelo._verification_actions`:
        Persists verification reports and verification pass/refusal events.
    :mod:`aeat.application.modelo._filing_actions`:
        Persists local filing records and filing/supersession events.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from ...core import STRICT_FROZEN_CONFIG
from ...core.identity import BucketId
from ...domain.buckets import (
    BucketEventHistoryRepository,
    BucketEventObjectType,
    BucketEventType,
)
from ...domain.buckets._protocols import BucketEventHistoryRepositoryProtocol
from ...domain.modelos._calculation_repository import CalculationRevisionCatalogueRepository
from ...domain.modelos._filing_repository import ModeloRecordCatalogueRepository
from ...domain.modelos._ids import WorkUnitId
from ...domain.modelos._protocols import (
    CalculationRevisionCatalogueRepositoryProtocol,
    ModeloRecordCatalogueRepositoryProtocol,
    VerificationReportCatalogueRepositoryProtocol,
)
from ...domain.modelos._repository import WorkUnitCatalogueRepository
from ...domain.modelos._verification_repository import VerificationReportCatalogueRepository
from ._action_errors import WorkUnitNotFoundError


class WorkUnitHistoryEvent(BaseModel):
    """One projected :class:`BucketEvent` row in a work-unit history stream."""

    model_config = STRICT_FROZEN_CONFIG

    event_id: str = Field(min_length=1)
    occurred_at: datetime
    event_type: BucketEventType
    object_type: BucketEventObjectType
    object_id: str = Field(min_length=1)
    actor: str = Field(default="")
    payload: dict[str, str] = Field(default_factory=dict)


class WorkUnitHistory(BaseModel):
    """Chronologically ordered event timeline for one :class:`WorkUnit`."""

    model_config = STRICT_FROZEN_CONFIG

    bucket_id: BucketId
    work_unit_id: WorkUnitId
    events: tuple[WorkUnitHistoryEvent, ...] = Field(default_factory=tuple)


def assemble_work_unit_history(
    work_unit_id: str,
    *,
    work_unit_repository: WorkUnitCatalogueRepository | None = None,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol | None = None,
    filing_repository: ModeloRecordCatalogueRepositoryProtocol | None = None,
    verification_repository: VerificationReportCatalogueRepositoryProtocol | None = None,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol | None = None,
) -> WorkUnitHistory:
    """Return a :class:`WorkUnitHistory` covering every bucket event scoped to ``work_unit_id``.

    Events are merged from object-scoped :class:`BucketEvent` streams and ordered
    by ``occurred_at`` ascending. The work unit itself is loaded to confirm it
    exists (raising :class:`WorkUnitNotFoundError` if not) and to discover every
    :class:`CalculationRevision`, :class:`VerificationReport`, and
    :class:`ModeloRecord` id that belongs to its lifecycle.

    The returned :class:`WorkUnitHistoryEvent` rows copy event payloads into a
    read model for ``aeat app modelo work history``. The function never writes to
    repositories and never contacts AEAT; mutation and event emission stay with
    the lifecycle services that produce the underlying records.

    See Also:
        :meth:`BucketEventHistoryCatalogue.for_object`:
            Supplies each object-scoped event stream merged here.
        :class:`WorkUnitHistory`:
            The immutable read model returned to callers.
    """
    wu_repo = work_unit_repository or WorkUnitCatalogueRepository()
    cr_repo = calculation_repository or CalculationRevisionCatalogueRepository()
    fr_repo = filing_repository or ModeloRecordCatalogueRepository()
    vr_repo = verification_repository or VerificationReportCatalogueRepository()
    bv_repo = bucket_event_repository or BucketEventHistoryRepository()

    work_units = wu_repo.load()
    work_unit = work_units.get(work_unit_id)
    if work_unit is None:
        raise WorkUnitNotFoundError(
            translated_message="application.modelo.errors.work_unit_not_found",
            context={"work_unit_id": work_unit_id},
        )

    catalogue = bv_repo.load()

    # Work-unit-scoped events (create / rename / discard) live under
    # object_type=WORK_UNIT keyed by work_unit_id.
    collected = list(
        catalogue.for_object(
            object_type=BucketEventObjectType.WORK_UNIT,
            object_id=work_unit_id,
        ),
    )

    revisions = cr_repo.load()
    for revision in revisions.values():
        if revision.work_unit_id != work_unit_id:
            continue
        collected.extend(
            catalogue.for_object(
                object_type=BucketEventObjectType.CALCULATION_REVISION,
                object_id=revision.calculation_revision_id,
            ),
        )

    revision_ids = {
        revision.calculation_revision_id for revision in revisions.values() if revision.work_unit_id == work_unit_id
    }
    verifications = vr_repo.load()
    for report in verifications.values():
        if report.calculation_revision_id not in revision_ids:
            continue
        collected.extend(
            catalogue.for_object(
                object_type=BucketEventObjectType.VERIFICATION_REPORT,
                object_id=report.verification_report_id,
            ),
        )

    filings = fr_repo.load()
    for filing in filings.values():
        if filing.work_unit_id != work_unit_id:
            continue
        collected.extend(
            catalogue.for_object(
                object_type=BucketEventObjectType.FILING_RECORD,
                object_id=filing.filing_record_id,
            ),
        )

    collected.sort(key=lambda event: event.occurred_at)
    events = tuple(
        WorkUnitHistoryEvent(
            event_id=event.event_id,
            occurred_at=event.occurred_at,
            event_type=event.event_type,
            object_type=event.object_type,
            object_id=event.object_id,
            actor=event.actor,
            payload=dict(event.payload),
        )
        for event in collected
    )

    return WorkUnitHistory(
        bucket_id=work_unit.bucket_id,
        work_unit_id=work_unit_id,
        events=events,
    )


__all__ = [
    "WorkUnitHistory",
    "WorkUnitHistoryEvent",
    "assemble_work_unit_history",
]
