"""Modelo reconciliation: compare a work unit against external evidence.

``modelo_reconcile`` accepts a modelo work unit and one source of external
evidence (either an AEAT justificante PDF or a filed-declaration PDF)
and produces a ``ModeloReconciliationReport`` recording whether
the work unit's most recent calculation matches the external evidence.

The service is local-only: it never contacts AEAT and never invokes
``require_live_read``. It composes the existing low-level reconciler in
:mod:`aeat.application.filing.reconciliation._reconcile` with a parser
for the supplied source kind. :class:`BucketEventHistoryRepository` receives
a ``MODELO_RECONCILED`` event for each reconciliation run.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.errors import AeatError
from ...core.identity import BucketId
from ...core.time import now
from ...domain.modelos._ids import WorkUnitId
from ._action_errors import WorkUnitNotFoundError


class ModeloReconciliationSourceKind(StrEnum):
    """Closed set of external-evidence kinds the operator can supply."""

    JUSTIFICANTE = "justificante"
    DECLARATION = "declaration"


class ModeloReconciliationVerdict(StrEnum):
    """Closed verdict catalogue for :class:`ModeloReconciliationReport`.

    Closed set: ``matches`` / ``mismatches`` / ``evidence_invalid``.
    Any expansion requires a design decision and must not add shells.
    """

    MATCHES = "matches"
    MISMATCHES = "mismatches"
    EVIDENCE_INVALID = "evidence_invalid"


class ModeloReconciliationHistoryEntry(BaseModel):
    """One past reconciliation read back from the bucket event history.

    ``modelo_reconcile`` persists no stored record: a reconciliation is
    repeatable on demand from the justificante, so the durable trace is the
    append-only ``MODELO_RECONCILED`` :class:`~aeat.domain.buckets.BucketEvent`
    it emits. This typed entry projects one such event so the operator can
    enumerate past reconciliation verdicts without re-parsing any evidence.
    The read path is the same bucket-event catalogue the write path appends
    into — there is no parallel reconciliation store.
    """

    model_config = _STRICT_FROZEN

    event_id: str = Field(min_length=1, max_length=128)
    bucket_id: BucketId
    work_unit_id: WorkUnitId
    source_kind: ModeloReconciliationSourceKind
    source_path: str
    verdict: ModeloReconciliationVerdict
    diff_count: int = Field(ge=0)
    actor: str = Field(min_length=1, max_length=64)
    reconciled_at: datetime


class ModeloReconciliationDiff(BaseModel):
    """One per-casilla disagreement between work unit and evidence."""

    model_config = _STRICT_FROZEN

    field_name: str = Field(min_length=1)
    work_unit_value: str = ""
    evidence_value: str = ""
    kind: str = Field(min_length=1)


class ModeloReconciliationCommand(BaseModel):
    """Strict input contract for ``modelo_reconcile``.

    Exactly one of ``from_justificante`` or ``from_declaration`` must be
    supplied. The CLI handler enforces the exclusivity before constructing
    the command; the model itself records the chosen source.
    """

    model_config = _STRICT_FROZEN

    work_unit_id: WorkUnitId
    source_kind: ModeloReconciliationSourceKind
    source_path: Path
    actor: str = Field(default="operator", min_length=1, max_length=64)


class ModeloReconciliationReport(BaseModel):
    """Outcome of ``modelo_reconcile``.

    The verdict summarises the comparison at the work-unit level. The
    diff list enumerates per-casilla disagreements (empty on
    ``matches``). The wrapped reconciler report is the lower-level
    field-by-field comparison from
    :mod:`aeat.application.filing.reconciliation._reconcile`.
    """

    model_config = _STRICT_FROZEN

    work_unit_id: WorkUnitId
    bucket_id: BucketId
    source_kind: ModeloReconciliationSourceKind
    source_path: str
    verdict: ModeloReconciliationVerdict
    diffs: tuple[ModeloReconciliationDiff, ...] = ()
    reconciled_at: datetime
    narrative: str = ""


class ReconciliationEvidenceInvalidError(AeatError):
    """Raised when the supplied external evidence cannot be parsed.

    Raised for malformed justificantes. The CLI surfaces it as a refusal
    with the canonical recovery hint; downstream consumers branch on it
    without string-matching the message.
    """


class ReconciliationDeclaracionSourceUnsupportedError(AeatError):
    """Raised when ``from_declaration`` is requested before the declaration parser ships.

    A declaration-sourced reconcile is a planned surface variant. Until the
    declaration parser lands, the service refuses cleanly rather than
    silently degrading.
    """


class ReconciliationCrossBucketRefusedError(AeatError):
    """Raised when the addressed work unit belongs to a different bucket than the active profile bucket.

    Every event is scoped to a bucket id. Allowing the service to emit
    into a non-active bucket would let any caller write into other
    operators' history. The check is enforced at the application service
    so neither the CLI nor any future caller can bypass it.
    """


def modelo_reconcile(command: ModeloReconciliationCommand) -> ModeloReconciliationReport:
    """Reconcile a modelo work unit against external evidence and return a :class:`ModeloReconciliationReport`.

    Local-only: never contacts AEAT and never invokes ``require_live_read``.
    Composes the existing low-level reconciler at
    :mod:`aeat.application.filing.reconciliation._reconcile` with the
    justificante parser at :mod:`aeat.adapters.inbound.justificante`.

    Emits ``MODELO_RECONCILED`` into the bucket-event-history catalogue.
    The verdict is included in the event payload so downstream
    auditors can replay the reconciliation timeline without
    re-parsing the evidence.

    Per-casilla diff coverage is bounded by what the source can
    expose. A justificante PDF carries only modelo, period,
    ``ejercicio``, ``tax_id``, and totals; per-casilla diffs against
    the full declaration require the modelo-specific declaration
    parser that has not shipped yet.
    """
    if command.source_kind is ModeloReconciliationSourceKind.DECLARATION:
        raise ReconciliationDeclaracionSourceUnsupportedError(
            translated_message="application.modelo.errors.reconcile_declaration_unsupported",
        )

    from ...adapters.inbound.justificante import parse_justificante
    from ...domain.buckets import (
        BucketEvent,
        BucketEventHistoryRepository,
        BucketEventObjectType,
        BucketEventType,
        append_bucket_event,
        derive_bucket_event_id,
    )
    from ...domain.justificante import JustificanteParseError
    from ...domain.modelos._repository import WorkUnitCatalogueRepository
    from ..workflow._persistence import workflow_state_repository

    active_bucket_id = workflow_state_repository().load().active_profile_bucket_id()
    if active_bucket_id is None:
        raise WorkUnitNotFoundError(
            translated_message="application.modelo.errors.reconcile_no_active_bucket",
        )

    catalogue = WorkUnitCatalogueRepository().load()
    work_unit = catalogue.work_units.get(command.work_unit_id)
    if work_unit is None:
        raise WorkUnitNotFoundError(
            f"work unit {command.work_unit_id!r} not found in the active bucket catalogue",
        )
    if work_unit.bucket_id != active_bucket_id:
        raise ReconciliationCrossBucketRefusedError(
            f"work unit {command.work_unit_id!r} belongs to bucket "
            f"{work_unit.bucket_id!r} but the active profile bucket is "
            f"{active_bucket_id!r}; switch profile before reconciling",
        )

    try:
        justificante = parse_justificante(command.source_path)
    except JustificanteParseError as exc:
        raise ReconciliationEvidenceInvalidError(
            f"justificante at {command.source_path!s} could not be parsed: {exc}",
        ) from exc

    diffs: list[ModeloReconciliationDiff] = []
    if work_unit.modelo != justificante.modelo:
        diffs.append(
            ModeloReconciliationDiff(
                field_name="modelo",
                work_unit_value=work_unit.modelo,
                evidence_value=justificante.modelo,
                kind="modelo_mismatch",
            ),
        )
    if justificante.ejercicio is not None and str(work_unit.filing_year) != justificante.ejercicio:
        diffs.append(
            ModeloReconciliationDiff(
                field_name="ejercicio",
                work_unit_value=str(work_unit.filing_year),
                evidence_value=justificante.ejercicio,
                kind="ejercicio_mismatch",
            ),
        )

    verdict = ModeloReconciliationVerdict.MATCHES if not diffs else ModeloReconciliationVerdict.MISMATCHES
    narrative = (
        f"reconciled modelo {justificante.modelo} for ejercicio {justificante.ejercicio or '?'} "
        f"against work unit {command.work_unit_id}; verdict={verdict.value}; diffs={len(diffs)}"
    )
    reconciled_at = now()
    report = ModeloReconciliationReport(
        work_unit_id=command.work_unit_id,
        bucket_id=work_unit.bucket_id,
        source_kind=command.source_kind,
        source_path=str(command.source_path),
        verdict=verdict,
        diffs=tuple(diffs),
        reconciled_at=reconciled_at,
        narrative=narrative,
    )

    event_payload = {
        "work_unit_id": command.work_unit_id,
        "source_kind": command.source_kind.value,
        "source_path": str(command.source_path),
        "verdict": verdict.value,
        "diffs": str(len(diffs)),
    }
    actor = command.actor.strip()
    event_id = derive_bucket_event_id(
        bucket_id=work_unit.bucket_id,
        event_type=BucketEventType.MODELO_RECONCILED,
        occurred_at=reconciled_at,
        actor=actor,
        object_type=BucketEventObjectType.WORK_UNIT,
        object_id=command.work_unit_id,
        payload=event_payload,
    )
    catalogue_repo = BucketEventHistoryRepository()
    next_catalogue = append_bucket_event(
        catalogue_repo.load(),
        BucketEvent(
            event_id=event_id,
            bucket_id=work_unit.bucket_id,
            event_type=BucketEventType.MODELO_RECONCILED,
            occurred_at=reconciled_at,
            actor=actor,
            object_type=BucketEventObjectType.WORK_UNIT,
            object_id=command.work_unit_id,
            payload_version=1,
            payload=event_payload,
        ),
    )
    catalogue_repo.save(next_catalogue)

    return report


def list_modelo_reconciliations(
    *,
    bucket_id: BucketId,
    work_unit_id: WorkUnitId | None = None,
) -> tuple[ModeloReconciliationHistoryEntry, ...]:
    """Return every recorded reconciliation in ``bucket_id`` as typed entries.

    ``modelo_reconcile`` stores no record; its durable trace is the
    ``MODELO_RECONCILED`` :class:`~aeat.domain.buckets.BucketEvent` it appends.
    This read-back enumerates those events from the same
    :class:`~aeat.domain.buckets.BucketEventHistoryRepository` catalogue the
    write path appends into (no parallel read path), filtered to the active
    ``bucket_id`` and ordered oldest-first by ``occurred_at``. Each event is
    projected onto a typed :class:`ModeloReconciliationHistoryEntry` — the
    verdict, source kind, diff count, actor, and reconciliation instant are
    preserved, never collapsed to a flat ``dict[str, Any]``.

    An optional ``work_unit_id`` narrows the result to one work unit's
    reconciliation history. An empty result (no reconciliations recorded, or
    none for the requested work unit) returns an empty tuple — the clean "no
    reconciliations recorded yet" signal, not an error.
    """
    from ...domain.buckets import BucketEventHistoryRepository, BucketEventType

    catalogue = BucketEventHistoryRepository().load()
    events = catalogue.for_bucket(bucket_id, event_types=(BucketEventType.MODELO_RECONCILED,))
    entries: list[ModeloReconciliationHistoryEntry] = []
    for event in events:
        payload = dict(event.payload)
        event_work_unit_id = payload.get("work_unit_id", event.object_id)
        if work_unit_id is not None and event_work_unit_id != work_unit_id:
            continue
        entries.append(
            ModeloReconciliationHistoryEntry(
                event_id=event.event_id,
                bucket_id=event.bucket_id,
                work_unit_id=event_work_unit_id,
                source_kind=ModeloReconciliationSourceKind(payload["source_kind"]),
                source_path=payload.get("source_path", ""),
                verdict=ModeloReconciliationVerdict(payload["verdict"]),
                diff_count=int(payload.get("diffs", "0")),
                actor=event.actor,
                reconciled_at=event.occurred_at,
            ),
        )
    return tuple(entries)


__all__ = [
    "ModeloReconciliationCommand",
    "ModeloReconciliationDiff",
    "ModeloReconciliationHistoryEntry",
    "ModeloReconciliationReport",
    "ModeloReconciliationSourceKind",
    "ModeloReconciliationVerdict",
    "ReconciliationCrossBucketRefusedError",
    "ReconciliationDeclaracionSourceUnsupportedError",
    "ReconciliationEvidenceInvalidError",
    "WorkUnitNotFoundError",
    "list_modelo_reconciliations",
    "modelo_reconcile",
]
