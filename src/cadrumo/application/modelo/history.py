"""Chronological bucket-event history assembly at two subject grains.

Surfaces a unified timeline of every event the operator's work emitted across
its lifecycle: creation, renames, calculations, verifications, filings,
supersessions, amendments, and discards.

Two subjects are assembled here, and they are genuinely different queries
rather than one query with a parameter. :func:`assemble_work_unit_history`
narrows to a single :class:`~WorkUnit` and walks the object-scoped streams that
belong to it. :func:`assemble_modelo_lifecycle_history` spans every work unit that filed
one modelo, selecting on the ``modelo`` subject key events carry in their own
payload. They share this module because they share a substrate, a projection
row and an ordering; they are not layered on one another, because neither
narrows to the other.

The catalogue substrate is the bucket-scoped append-only event log loaded from
:class:`BucketEventHistoryRepository`. Events scoped to a work unit land under
four :class:`cadrumo.domain.buckets.BucketEventObjectType` values:
``WORK_UNIT``, ``CALCULATION_REVISION``, ``VERIFICATION_REPORT``, and
``FILING_RECORD``. The assembler walks each related object id and merges the
emitted :class:`cadrumo.domain.buckets.BucketEvent` streams in
chronological order.

The normalized records remain the source of relational truth:
:class:`~WorkUnit` selects the lifecycle root,
:class:`CalculationRevision` identifies calculation attempts under it,
:class:`~VerificationReport` identifies verification outcomes
for those revisions, and :class:`ModeloRecord` identifies local filing records.
The event history explains how those records changed; it does not replace their
catalogues.

The assembler is pure read: no mutation, no remote contact.

See Also:
    :func:`cadrumo.application.modelo.create_work_unit`:
        Emits work-unit create, rename, and discard events.
    :func:`cadrumo.application.modelo.calculate_modelo_work_revision`:
        Persists calculation revisions and ``MODELO_CALCULATION_CREATED`` events.
    :func:`cadrumo.application.modelo.verify_modelo_revision`:
        Persists verification reports and verification pass/refusal events.
    :func:`cadrumo.application.modelo.file_modelo_revision`:
        Persists local filing records and filing/supersession events.
"""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import BaseModel, Field, ValidationError

from ...adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ...adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ...adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ...adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from ...adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ...core.identity import BucketId, WorkUnitId
from ...core.models import STRICT_FROZEN_CONFIG
from ...domain.buckets.event import (
    BucketEvent,
    BucketEventObjectType,
    BucketEventType,
    bucket_event_order_key,
)
from ...domain.buckets.protocols import BucketEventHistoryRepositoryProtocol
from ...domain.modelos.codes import ModeloCode
from ...domain.modelos.protocols import (
    CalculationRevisionCatalogueRepositoryProtocol,
    ModeloRecordCatalogueRepositoryProtocol,
    VerificationReportCatalogueRepositoryProtocol,
)
from ...domain.modelos.work_unit import WorkUnitCatalogue
from .action_errors import WorkUnitNotFoundError
from .work_addressing import (
    ModeloWorkResolution,
    ModeloWorkSelectorRequest,
    ModeloWorkSelectorState,
    resolve_modelo_work_bucket,
    select_modelo_work_resolution,
)


class WorkUnitHistory(BaseModel):
    """Chronologically ordered event timeline for one :class:`~WorkUnit`."""

    model_config = STRICT_FROZEN_CONFIG

    bucket_id: BucketId
    work_unit_id: WorkUnitId
    events: tuple[BucketEvent, ...] = Field(default_factory=tuple)


def _select_history_work_unit(
    request: ModeloWorkSelectorRequest,
    *,
    catalogue: WorkUnitCatalogue,
    bucket_id: str,
) -> ModeloWorkResolution:
    """Select a history root from the caller-captured catalogue."""
    return select_modelo_work_resolution(request, catalogue=catalogue, bucket_id=bucket_id)


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

    Events are merged from object-scoped
    :class:`cadrumo.domain.buckets.BucketEvent` streams and ordered by
    :func:`bucket_event_order_key`. The work unit itself is loaded to confirm it
    exists (raising :class:`WorkUnitNotFoundError` if not) and to discover every
    :class:`CalculationRevision`, :class:`~VerificationReport`,
    and :class:`ModeloRecord` id that belongs to its lifecycle.

    Rows are the validated :class:`cadrumo.domain.buckets.BucketEvent` values
    themselves, not a restatement of them: a read model repeating that field set
    can only lose constraints its source already enforces, and this one had
    already dropped ``bucket_id``, ``payload_version`` and the content-address
    derivation. ``aeat app modelo work history`` projects onto its own wire
    schema at the entrypoint, which is where the loosening belongs.

    The function never writes to repositories and never contacts AEAT; mutation
    and event emission stay with the lifecycle services that produce the
    underlying records.

    See Also:
        :meth:`cadrumo.domain.buckets.BucketEventHistoryCatalogue.for_object`:
            Supplies each object-scoped event stream merged here.
        :class:`WorkUnitHistory`:
            The immutable read model returned to callers.
    """
    wu_repo = work_unit_repository or WorkUnitCatalogueRepository()
    cr_repo = calculation_repository or CalculationRevisionCatalogueRepository()
    fr_repo = filing_repository or ModeloRecordCatalogueRepository()
    vr_repo = verification_repository or VerificationReportCatalogueRepository()
    bv_repo = bucket_event_repository or BucketEventHistoryRepository()

    try:
        request = ModeloWorkSelectorRequest(work_unit_id=work_unit_id)
    except ValidationError as exc:
        raise WorkUnitNotFoundError(
            translated_message="application.modelo.errors.work_unit_not_found",
            context={"work_unit_id": work_unit_id},
        ) from exc
    bucket_id = wu_repo.bucket_id or resolve_modelo_work_bucket(request)
    resolution = _select_history_work_unit(
        request,
        catalogue=wu_repo.load(),
        bucket_id=bucket_id,
    )
    if resolution.state is ModeloWorkSelectorState.ABSENT or resolution.work_unit is None:
        raise WorkUnitNotFoundError(
            translated_message="application.modelo.errors.work_unit_not_found",
            context={"work_unit_id": work_unit_id},
        )
    work_unit = resolution.work_unit

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

    # The merge order of the per-object streams above is not meaningful, so
    # same-instant events would otherwise inherit it. Ordering on the shared
    # key keeps this projection identical to every other bucket-event view.
    collected.sort(key=bucket_event_order_key)
    return WorkUnitHistory(
        bucket_id=work_unit.bucket_id,
        work_unit_id=work_unit_id,
        events=tuple(collected),
    )


_MODELO_HISTORY_TAXONOMY_PREFIX = "MODELO_"
"""Enum-member prefix naming the declared modelo bucket-event family.

Keyed on the member NAME rather than the value string on purpose. Three
:class:`BucketEventType` members carry values beginning ``modelo.036.`` while
belonging to the declared CENSO family, so a value-prefix derivation would
widen this history into censo territory -- a product decision, not a
projection detail.
"""


def admitted_modelo_history_event_types() -> frozenset[BucketEventType]:
    """Return every event type admissible into a per-modelo history, derived from the taxonomy.

    Derived at call time from :class:`cadrumo.domain.buckets.BucketEventType`
    rather than recorded as a literal set, because a literal one drifts
    silently. The adapter this policy was lifted from held a hand-written set
    admitting 11 of the 22 live members, and the drift was not theoretical:
    ``MODELO_LIVE_EVIDENCE_STAMPED`` and ``MODELO_WORK_UNIT_CREATED`` both
    carry the ``modelo``, ``filing_year`` and ``period`` payload keys this
    history filters on and were both dropped, so the operator was shown a work
    unit being discarded but never created, under a command documented as
    covering every lifecycle stage. Nothing failed, because a stale literal
    reports absence exactly as it reports emptiness.

    Admission by type is deliberately broad: it is
    :func:`assemble_modelo_lifecycle_history`'s SUBJECT filter that selects, and an event
    carrying no ``modelo`` payload key self-excludes there. That division is
    what makes a newly declared event type impossible to drop by omission.
    """
    return frozenset(
        event_type for event_type in BucketEventType if event_type.name.startswith(_MODELO_HISTORY_TAXONOMY_PREFIX)
    )


def _event_filing_year(payload: Mapping[str, str]) -> str:
    """Return the filing year a persisted event payload declares.

    ``year`` is read as a fallback for ``filing_year``. No live emitter writes
    it -- every module emitting a ``MODELO_*`` event writes ``filing_year`` --
    but the bucket-event log is append-only and persisted, and the modelo
    payload schema has already moved a version, so payloads written under the
    older shape may still be on disk. The version constant records no migration
    note either way, so the fallback is kept rather than dropped: losing a
    persisted history row would be invisible to the operator, and an absence
    that reports as an empty result is the failure this projection exists to
    avoid.
    """
    return (payload.get("filing_year") or payload.get("year") or "").strip()


class ModeloLifecycleHistory(BaseModel):
    """Chronologically ordered event timeline for one modelo across every work unit.

    The sibling of :class:`WorkUnitHistory` at the other subject grain: that
    one narrows to a single :class:`~WorkUnit` lifecycle, this one spans every
    work unit that filed the same modelo, optionally narrowed to one filing
    year and period.
    """

    model_config = STRICT_FROZEN_CONFIG

    modelo: ModeloCode
    filing_year: int | None = None
    period: str | None = None
    events: tuple[BucketEvent, ...] = Field(default_factory=tuple)


def assemble_modelo_lifecycle_history(
    modelo: str,
    *,
    filing_year: int | None = None,
    period: str | None = None,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol | None = None,
) -> ModeloLifecycleHistory:
    """Return a :class:`ModeloLifecycleHistory` covering every bucket event recorded against ``modelo``.

    Serves ``aeat app modelo history``. Admission is the taxonomy-derived set
    from :func:`admitted_modelo_history_event_types`; selection is the event
    payload's own ``modelo`` subject key, optionally narrowed by
    ``filing_year`` and ``period``.

    ``modelo`` is validated into :class:`ModeloCode` before anything is loaded,
    so a malformed identifier is refused rather than answered with an empty
    timeline. An empty result then means the modelo has no history, which is a
    different fact from the identifier never having been able to have one.

    Rows are ordered by :func:`bucket_event_order_key`, the shared total order
    every other bucket-event view uses. ``occurred_at`` alone does not order
    these events: emissions inside one operation share an instant by design, so
    ties would fall through to catalogue mapping order and two readers could
    render the operator different timelines with nothing invalid anywhere.

    The function never writes to repositories and never contacts AEAT.

    See Also:
        :func:`assemble_work_unit_history`:
            The same projection at the single-work-unit subject grain.
    """
    subject = ModeloCode(modelo)
    repository = bucket_event_repository or BucketEventHistoryRepository()
    admitted = admitted_modelo_history_event_types()
    wanted_year = None if filing_year is None else str(filing_year)

    collected: list[BucketEvent] = []
    for event in repository.load().events.values():
        if event.event_type not in admitted:
            continue
        payload = dict(event.payload)
        if payload.get("modelo", "") != subject:
            continue
        if wanted_year is not None and _event_filing_year(payload) != wanted_year:
            continue
        if period is not None and payload.get("period", "") != period:
            continue
        collected.append(event)

    collected.sort(key=bucket_event_order_key)
    return ModeloLifecycleHistory(
        modelo=subject,
        filing_year=filing_year,
        period=period,
        events=tuple(collected),
    )


__all__ = [
    "ModeloLifecycleHistory",
    "WorkUnitHistory",
    "admitted_modelo_history_event_types",
    "assemble_modelo_lifecycle_history",
    "assemble_work_unit_history",
]
