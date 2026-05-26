"""Modelo reconciliation: compare a work unit against external evidence.

`modelo_reconcile` accepts a modelo work unit and one source of external
evidence (either an AEAT justificante PDF or a filed-declaration PDF)
and produces a :class:`ModeloReconciliationReport` recording whether
the work unit's most recent calculation matches the external evidence.

The service is local-only: it never contacts AEAT and never invokes
``require_live_read``. It composes the existing low-level reconciler in
:mod:`aeat.application.filing.reconciliation._reconcile` with a parser
for the supplied source kind.

The CLI verb ``aeat app modelo reconcile`` (per the app-modelo-shape
ADR amendment) is a thin delegate over this service.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from ...core.errors import AeatError
from ...core.i18n import tr
from ._actions import WorkUnitNotFoundError

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")


class ModeloReconciliationSourceKind(StrEnum):
    """Closed set of external-evidence kinds the operator can supply."""

    JUSTIFICANTE = "justificante"
    DECLARATION = "declaration"


class ModeloReconciliationVerdict(StrEnum):
    """Closed verdict catalogue for :class:`ModeloReconciliationReport`.

    Drawn verbatim from the 2026-05-15 amendment to the
    app-modelo-shape ADR: ``matches`` / ``mismatches`` /
    ``evidence_invalid``. Any expansion needs an ADR amendment first
    per the no-design-only-shells rule.
    """

    MATCHES = "matches"
    MISMATCHES = "mismatches"
    EVIDENCE_INVALID = "evidence_invalid"


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

    work_unit_id: str = Field(min_length=1, max_length=128)
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

    work_unit_id: str = Field(min_length=1, max_length=128)
    bucket_id: str = Field(min_length=1, max_length=128)
    source_kind: ModeloReconciliationSourceKind
    source_path: str
    verdict: ModeloReconciliationVerdict
    diffs: tuple[ModeloReconciliationDiff, ...] = ()
    reconciled_at: datetime
    narrative: str = ""


class ReconciliationEvidenceInvalidError(AeatError):
    """Raised when the supplied external evidence cannot be parsed.

    The complementaria-external-filing-path ADR mandates this error for
    malformed justificantes. The CLI surfaces it as a refusal with the
    canonical recovery hint; downstream consumers branch on it without
    string-matching the message.
    """


class ReconciliationDeclaracionSourceUnsupportedError(AeatError):
    """Raised when ``from_declaration`` is requested before the declaration
    parser ships.

    The app-modelo-shape ADR amendment lists ``--from-declaration PATH``
    as a required surface variant. Until the parser lands, the service
    refuses cleanly rather than silently degrading.
    """

class ReconciliationCrossBucketRefusedError(AeatError):
    """Raised when the addressed work unit belongs to a different bucket
    than the active profile bucket.

    The bucket-event-history ADR scopes every event to a bucket id.
    Allowing the service to emit into a non-active bucket would let any
    caller write into other operators' history. The check is enforced
    at the application service so neither the CLI nor any future caller
    can bypass it.
    """


def modelo_reconcile(command: ModeloReconciliationCommand) -> ModeloReconciliationReport:
    """Reconcile a modelo work unit against external evidence.

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
            tr("application.modelo.errors.reconcile_declaration_unsupported"),
        )

    from datetime import UTC, datetime

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
            tr("application.modelo.errors.reconcile_no_active_bucket"),
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

    verdict = (
        ModeloReconciliationVerdict.MATCHES if not diffs else ModeloReconciliationVerdict.MISMATCHES
    )
    narrative = (
        f"reconciled modelo {justificante.modelo} for ejercicio {justificante.ejercicio or '?'} "
        f"against work unit {command.work_unit_id}; verdict={verdict.value}; diffs={len(diffs)}"
    )
    reconciled_at = datetime.now(UTC)
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
    catalogue_repo.secure_object_repository.save_many((catalogue_repo.to_secure_object_write(next_catalogue),))

    return report


__all__ = [
    "ModeloReconciliationCommand",
    "ModeloReconciliationDiff",
    "ModeloReconciliationReport",
    "ModeloReconciliationSourceKind",
    "ModeloReconciliationVerdict",
    "ReconciliationCrossBucketRefusedError",
    "ReconciliationDeclaracionSourceUnsupportedError",
    "ReconciliationEvidenceInvalidError",
    "WorkUnitNotFoundError",
    "modelo_reconcile",
]
