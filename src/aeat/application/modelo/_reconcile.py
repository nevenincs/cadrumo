"""Modelo reconciliation: compare a work unit against external evidence.

``modelo_reconcile`` accepts a modelo work unit and one source of external
evidence (either an AEAT justificante PDF or a filed-declaration PDF)
and produces a ``ModeloReconciliationReport`` recording whether
the work unit's most recent calculation matches the external evidence.

The service is local-only: it never contacts AEAT and never invokes
``require_live_read``. It reimplements the metadata-level comparison
(modelo, period, ``ejercicio``, tax id) inline against the justificante
parser for the supplied source kind. :class:`BucketEventHistoryRepository`
receives a ``MODELO_RECONCILED`` event for each reconciliation run.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.errors import AeatError
from ...core.identity import BucketId
from ...core.time import now
from ...domain.modelos._ids import WorkUnitId
from ._action_errors import WorkUnitNotFoundError

if TYPE_CHECKING:
    from ...domain.justificante import Justificante


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


class ModeloReconciliationBytesCommand(BaseModel):
    """Strict input contract for reconciling secure-storage evidence bytes.

    Used by authenticated live pulls after the captured justificante has
    already been persisted in secure storage. The raw bytes remain in memory;
    ``source_ref`` is the non-file secure-storage reference recorded in the
    reconciliation event.
    """

    model_config = _STRICT_FROZEN

    work_unit_id: WorkUnitId
    source_kind: ModeloReconciliationSourceKind
    source_bytes: bytes = Field(min_length=1)
    source_ref: str = Field(min_length=1, max_length=512)
    actor: str = Field(default="operator", min_length=1, max_length=64)


class ModeloReconciliationReport(BaseModel):
    """Outcome of ``modelo_reconcile``.

    The verdict summarises the comparison at the work-unit level. The
    diff list enumerates the header-field disagreements (modelo, period,
    ``ejercicio``, tax id; empty on ``matches``); it does not compare
    individual casilla values.
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


def _evidence_invalid_refusal(exc: BaseException) -> ReconciliationEvidenceInvalidError:
    """Translate a justificante parse failure into a clean typed refusal.

    The parser raises with a redacted, parser-internal message (e.g.
    ``"pdfplumber failed to open <input-pdf>: PdfminerException"``). Surfacing
    that verbatim leaks the parser backend's exception class to the operator and
    omits the documented "is this the right document?" guidance. This helper
    drops the raw cause into structured ``context`` for diagnostics and routes
    the operator-facing text through the
    ``errors.refused.reconciliation_evidence_invalid`` locale key, which carries
    the documented ``evidence_invalid`` guidance. The exception ``__cause__``
    chain preserves the original parse error for logs.
    """
    return ReconciliationEvidenceInvalidError(
        translated_message="errors.refused.reconciliation_evidence_invalid",
        context={"parse_failure": type(exc).__name__},
        suggestion="aeat app modelo reconcile file WORK_UNIT_ID --file PATH/TO/justificante.pdf",
    )


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
    Reimplements the metadata comparison inline against the justificante
    parser at :mod:`aeat.adapters.inbound.justificante`.

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
    from ...domain.justificante import JustificanteParseError

    try:
        justificante = parse_justificante(command.source_path)
    except JustificanteParseError as exc:
        raise _evidence_invalid_refusal(exc) from exc
    return _reconcile_parsed_justificante(
        work_unit_id=command.work_unit_id,
        source_kind=command.source_kind,
        source_ref=str(command.source_path),
        actor=command.actor,
        justificante=justificante,
    )


def modelo_reconcile_bytes(command: ModeloReconciliationBytesCommand) -> ModeloReconciliationReport:
    """Reconcile secure-storage evidence bytes without materialising a plaintext file.

    Returns:
        The :class:`ModeloReconciliationReport` comparing the parsed evidence to
        the work unit.
    """
    if command.source_kind is ModeloReconciliationSourceKind.DECLARATION:
        raise ReconciliationDeclaracionSourceUnsupportedError(
            translated_message="application.modelo.errors.reconcile_declaration_unsupported",
        )

    from ...adapters.inbound.justificante import parse_justificante_bytes
    from ...domain.justificante import JustificanteParseError

    try:
        justificante = parse_justificante_bytes(command.source_bytes)
    except JustificanteParseError as exc:
        raise _evidence_invalid_refusal(exc) from exc
    return _reconcile_parsed_justificante(
        work_unit_id=command.work_unit_id,
        source_kind=command.source_kind,
        source_ref=command.source_ref,
        actor=command.actor,
        justificante=justificante,
    )


def _reconcile_parsed_justificante(
    *,
    work_unit_id: WorkUnitId,
    source_kind: ModeloReconciliationSourceKind,
    source_ref: str,
    actor: str,
    justificante: Justificante,
) -> ModeloReconciliationReport:
    from ...domain.buckets import (
        BucketEvent,
        BucketEventHistoryRepository,
        BucketEventObjectType,
        BucketEventType,
        append_bucket_event,
        derive_bucket_event_id,
    )
    from ...domain.modelos._repository import WorkUnitCatalogueRepository
    from ..workflow._persistence import workflow_state_repository

    active_bucket_id = workflow_state_repository().load().active_profile_bucket_id()
    if active_bucket_id is None:
        raise WorkUnitNotFoundError(
            translated_message="application.modelo.errors.reconcile_no_active_bucket",
        )

    catalogue = WorkUnitCatalogueRepository().load()
    work_unit = catalogue.work_units.get(work_unit_id)
    if work_unit is None:
        raise WorkUnitNotFoundError(
            f"work unit {work_unit_id!r} not found in the active bucket catalogue",
        )
    if work_unit.bucket_id != active_bucket_id:
        raise ReconciliationCrossBucketRefusedError(
            f"work unit {work_unit_id!r} belongs to bucket "
            f"{work_unit.bucket_id!r} but the active profile bucket is "
            f"{active_bucket_id!r}; switch profile before reconciling",
        )

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
    if work_unit.period != justificante.period:
        diffs.append(
            ModeloReconciliationDiff(
                field_name="period",
                work_unit_value=work_unit.period.registry_token,
                evidence_value=justificante.period.registry_token,
                kind="period_mismatch",
            ),
        )
    profile_tax_id = _active_profile_tax_id(active_bucket_id)
    if profile_tax_id and profile_tax_id != _normalise_tax_id(justificante.tax_id):
        diffs.append(
            ModeloReconciliationDiff(
                field_name="tax_id",
                work_unit_value=profile_tax_id,
                evidence_value=justificante.tax_id,
                kind="tax_id_mismatch",
            ),
        )

    verdict = ModeloReconciliationVerdict.MATCHES if not diffs else ModeloReconciliationVerdict.MISMATCHES
    narrative = (
        f"reconciled modelo {justificante.modelo} for ejercicio {justificante.ejercicio or '?'} "
        f"against work unit {work_unit_id}; verdict={verdict.value}; diffs={len(diffs)}"
    )
    reconciled_at = now()
    report = ModeloReconciliationReport(
        work_unit_id=work_unit_id,
        bucket_id=work_unit.bucket_id,
        source_kind=source_kind,
        source_path=source_ref,
        verdict=verdict,
        diffs=tuple(diffs),
        reconciled_at=reconciled_at,
        narrative=narrative,
    )

    event_payload = {
        "work_unit_id": work_unit_id,
        "source_kind": source_kind.value,
        "source_path": source_ref,
        "verdict": verdict.value,
        "diffs": str(len(diffs)),
    }
    actor = actor.strip()
    event_id = derive_bucket_event_id(
        bucket_id=work_unit.bucket_id,
        event_type=BucketEventType.MODELO_RECONCILED,
        occurred_at=reconciled_at,
        actor=actor,
        object_type=BucketEventObjectType.WORK_UNIT,
        object_id=work_unit_id,
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
            object_id=work_unit_id,
            payload_version=1,
            payload=event_payload,
        ),
    )
    catalogue_repo.save(next_catalogue)

    return report


def _active_profile_tax_id(bucket_id: str) -> str:
    from ..user_profile import record_to_path_values, record_to_values
    from ..user_profile._orchestration import build_lifecycle_service

    record = build_lifecycle_service(bucket_id=bucket_id).read(bucket_id)
    path_values = record_to_path_values(record)
    profile_tax_id = _normalise_tax_id(path_values.get("identity.tax_id"))
    if profile_tax_id:
        return profile_tax_id
    selector_values = record_to_values(record)
    return _normalise_tax_id(selector_values.get("tax.id"))


def _normalise_tax_id(value: object) -> str:
    return str(value or "").strip().upper()


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
    "ModeloReconciliationBytesCommand",
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
    "modelo_reconcile_bytes",
]
