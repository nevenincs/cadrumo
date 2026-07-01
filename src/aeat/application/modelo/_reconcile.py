"""Modelo reconciliation: compare work-unit state and computed result against evidence.

``modelo_reconcile`` accepts a modelo work unit and an AEAT justificante PDF,
then produces a :class:`ModeloReconciliationReport` recording whether the work
unit's modelo, period, ``ejercicio``, and active-profile tax id match the
receipt, AND — where the revision declares ``reconciliation_total_casilla_ids``
and a persisted calculation revision exists — whether the receipt's printed
total equals the canonical computed result casilla
(``one-aggregation-path-pull-equals-calculate``). A filed-amount divergence
surfaces as a typed ``total`` diff carrying the reconciling expectation's legal
grounding; where the total could not be reconciled (no map, no revision, no
printed total) a ``totals_not_reconciled`` advisory discloses it so an
identity-only ``matches`` is never a silent false green. Filed-declaration
reconciliation is named in the command contract but refused until the
declaration parser ships.

The path-based service is local-only: it never contacts AEAT and never invokes
``require_live_read`` — the computed result is read from the already-persisted
:class:`~aeat.domain.modelos.CalculationRevision`, never a fresh calculation.
Authenticated live pulls use ``modelo_reconcile_bytes`` after storing captured
justificante bytes in secure storage. Both paths append a ``MODELO_RECONCILED``
:class:`~aeat.domain.buckets.BucketEvent` through
:class:`~aeat.domain.buckets.BucketEventHistoryRepository`, persisting the
structured diffs so ``reconcile history`` reports which fields diverged.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
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
    from ...domain.modelos._work_unit import WorkUnit


class ModeloReconciliationEvidenceKind(StrEnum):
    """Closed external-evidence labels accepted by reconciliation commands.

    ``DECLARATION`` is reserved for the filed-declaration parser and currently
    raises :class:`ReconciliationDeclaracionSourceUnsupportedError`.
    """

    JUSTIFICANTE = "justificante"
    DECLARATION = "declaration"


class ModeloReconciliationVerdict(StrEnum):
    """Closed verdict catalogue for :class:`ModeloReconciliationReport`.

    Closed set: ``matches`` / ``mismatches``. A reconcile that reaches a report
    has already parsed its evidence; an unparseable justificante is surfaced as
    the typed ``ReconciliationEvidenceInvalidError`` refusal
    (``REFUSED_RECONCILIATION_EVIDENCE_INVALID``) before any report is built, so
    there is no ``evidence_invalid`` verdict shell. Any expansion requires a
    design decision and must not add shells.
    """

    MATCHES = "matches"
    MISMATCHES = "mismatches"


class ModeloReconciliationDiffKind(StrEnum):
    """Closed category for a :class:`ModeloReconciliationDiff`.

    ``header_field`` — a receipt-identity disagreement (modelo, ejercicio,
    period, tax id). ``total`` — a filed-amount disagreement between the
    receipt total and the canonical computed result casilla. ``casilla`` is
    reserved for the future per-casilla receipt/declaration reconcile that the
    modelo-specific declaration parser will unlock; no code emits it yet.
    """

    HEADER_FIELD = "header_field"
    TOTAL = "total"
    CASILLA = "casilla"


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
    source_kind: ModeloReconciliationEvidenceKind
    source_path: str
    verdict: ModeloReconciliationVerdict
    diff_count: int = Field(ge=0)
    diffs: tuple[ModeloReconciliationDiff, ...] = ()
    actor: str = Field(min_length=1, max_length=64)
    reconciled_at: datetime


class ModeloReconciliationDiff(BaseModel):
    """One disagreement between work unit / profile / computed state and evidence.

    ``diff_kind`` is the closed category (header field vs filed total). ``kind``
    remains the specific mismatch token (``modelo_mismatch``,
    ``total_ingresar_mismatch``, …). A ``total`` diff carries the reconciling
    verification expectation's ``legal_refs`` / ``source_refs`` so the
    filed-amount divergence surfaces with its legal grounding
    (``aeat-calculation-grounding``); header diffs carry empty grounding.
    """

    model_config = _STRICT_FROZEN

    field_name: str = Field(min_length=1)
    work_unit_value: str = ""
    evidence_value: str = ""
    kind: str = Field(min_length=1)
    diff_kind: ModeloReconciliationDiffKind = ModeloReconciliationDiffKind.HEADER_FIELD
    legal_refs: tuple[str, ...] = ()
    source_refs: tuple[str, ...] = ()


class ModeloReconciliationAdvisory(BaseModel):
    """One non-blocking reconciliation advisory (surfaced as a CLI ``Notice``).

    Carries a stable ``code`` (``totals_not_reconciled`` /
    ``identity_anchor_unverified``), an operator-facing ``message``, and
    structured ``context`` (the reason, the anchor, the modelo). The CLI folds
    each advisory into a typed :class:`~aeat.core.json_contract.Notice` on the
    envelope's ``notices`` channel per
    ``cli-notices-are-the-only-diagnostic-channel`` — an advisory is never a
    bespoke result field. Advisories never flip the verdict: they disclose that
    a comparison could not be performed (so identity-only ``matches`` is never a
    silent false green), not that a value diverged.
    """

    model_config = _STRICT_FROZEN

    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    context: Mapping[str, str] = Field(default_factory=dict)


class ModeloReconciliationCommand(BaseModel):
    """Strict input contract for ``modelo_reconcile``.

    ``source_path`` points to the operator-supplied evidence file and
    ``source_kind`` records how that file must be parsed. Only justificante PDFs
    are supported today; declaration sources are refused before parsing.
    """

    model_config = _STRICT_FROZEN

    work_unit_id: WorkUnitId
    source_kind: ModeloReconciliationEvidenceKind
    source_path: Path
    actor: str = Field(default="operator", min_length=1, max_length=64)


class ModeloReconciliationBytesCommand(BaseModel):
    """Strict input contract for reconciling secure-storage justificante bytes.

    Used by authenticated live pulls after the captured justificante has
    already been persisted in secure storage. The raw bytes remain in memory;
    ``source_ref`` is the non-file secure-storage reference recorded in the
    reconciliation event.
    """

    model_config = _STRICT_FROZEN

    work_unit_id: WorkUnitId
    source_kind: ModeloReconciliationEvidenceKind
    source_bytes: bytes = Field(min_length=1)
    source_ref: str = Field(min_length=1, max_length=512)
    actor: str = Field(default="operator", min_length=1, max_length=64)


class ModeloReconciliationReport(BaseModel):
    """Outcome of ``modelo_reconcile``.

    The verdict summarises the comparison at the work-unit level. The diff list
    enumerates the disagreements — header-field (modelo, period, ``ejercicio``,
    tax id) and, where reconciled, the filed ``total`` against the computed
    result casilla; empty on ``matches``. Individual casilla declaration values
    are not compared (they require the modelo-specific declaration parser). The
    advisory list carries non-blocking disclosures (a total that could not be
    reconciled, an identity anchor that could not be verified); advisories never
    flip the verdict.
    """

    model_config = _STRICT_FROZEN

    work_unit_id: WorkUnitId
    bucket_id: BucketId
    source_kind: ModeloReconciliationEvidenceKind
    source_path: str
    verdict: ModeloReconciliationVerdict
    diffs: tuple[ModeloReconciliationDiff, ...] = ()
    advisories: tuple[ModeloReconciliationAdvisory, ...] = ()
    reconciled_at: datetime
    narrative: str = ""


class ReconciliationEvidenceInvalidError(AeatError):
    """Raised when the supplied external evidence cannot be parsed.

    Raised for malformed justificantes. The CLI surfaces it as a refusal
    with the canonical recovery hint; downstream consumers branch on it
    without string-matching the message.
    """


def _evidence_invalid_refusal(
    exc: BaseException,
    *,
    source_ref: str,
) -> ReconciliationEvidenceInvalidError:
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
        f"reconciliation evidence {source_ref!r} could not be parsed",
        translated_message="errors.refused.reconciliation_evidence_invalid",
        context={"parse_failure": type(exc).__name__, "source_ref": source_ref},
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
    """Reconcile a modelo work unit against a justificante PDF file.

    Local-only: never contacts AEAT and never invokes ``require_live_read``.
    Reimplements the metadata comparison inline against the justificante
    parser at :mod:`aeat.adapters.inbound.justificante`, then returns a
    :class:`ModeloReconciliationReport`.

    Emits ``MODELO_RECONCILED`` into the bucket-event-history catalogue.
    The verdict is included in the event payload so downstream
    auditors can replay the reconciliation timeline without
    re-parsing the evidence.

    The receipt totals ARE reconciled against the persisted revision's computed
    result where the revision declares ``reconciliation_total_casilla_ids``.
    Per-casilla diffs against the full declaration remain unavailable: a
    justificante PDF carries only modelo, period, ``ejercicio``, ``tax_id``, and
    totals, so casilla-level coverage requires the modelo-specific declaration
    parser that has not shipped yet.
    """
    if command.source_kind is ModeloReconciliationEvidenceKind.DECLARATION:
        raise ReconciliationDeclaracionSourceUnsupportedError(
            translated_message="application.modelo.errors.reconcile_declaration_unsupported",
        )

    from ...adapters.inbound.justificante import parse_justificante
    from ...domain.justificante import JustificanteParseError

    try:
        justificante = parse_justificante(command.source_path)
    except JustificanteParseError as exc:
        raise _evidence_invalid_refusal(exc, source_ref=str(command.source_path)) from exc
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
        The :class:`ModeloReconciliationReport` comparing the parsed
        justificante metadata to the work unit and active profile.
    """
    if command.source_kind is ModeloReconciliationEvidenceKind.DECLARATION:
        raise ReconciliationDeclaracionSourceUnsupportedError(
            translated_message="application.modelo.errors.reconcile_declaration_unsupported",
        )

    from ...adapters.inbound.justificante import parse_justificante_bytes
    from ...domain.justificante import JustificanteParseError

    try:
        justificante = parse_justificante_bytes(command.source_bytes)
    except JustificanteParseError as exc:
        raise _evidence_invalid_refusal(exc, source_ref=command.source_ref) from exc
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
    source_kind: ModeloReconciliationEvidenceKind,
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
    advisories: list[ModeloReconciliationAdvisory] = []
    if work_unit.modelo != justificante.modelo:
        diffs.append(
            ModeloReconciliationDiff(
                field_name="modelo",
                work_unit_value=work_unit.modelo,
                evidence_value=justificante.modelo,
                kind="modelo_mismatch",
                diff_kind=ModeloReconciliationDiffKind.HEADER_FIELD,
            ),
        )
    if justificante.ejercicio is None:
        advisories.append(_identity_anchor_unverified("ejercicio", modelo=str(work_unit.modelo)))
    elif str(work_unit.filing_year) != justificante.ejercicio:
        diffs.append(
            ModeloReconciliationDiff(
                field_name="ejercicio",
                work_unit_value=str(work_unit.filing_year),
                evidence_value=justificante.ejercicio,
                kind="ejercicio_mismatch",
                diff_kind=ModeloReconciliationDiffKind.HEADER_FIELD,
            ),
        )
    if work_unit.period != justificante.period:
        diffs.append(
            ModeloReconciliationDiff(
                field_name="period",
                work_unit_value=work_unit.period.registry_token,
                evidence_value=justificante.period.registry_token,
                kind="period_mismatch",
                diff_kind=ModeloReconciliationDiffKind.HEADER_FIELD,
            ),
        )
    profile_tax_id = _active_profile_tax_id(active_bucket_id)
    if not profile_tax_id:
        advisories.append(_identity_anchor_unverified("tax_id", modelo=str(work_unit.modelo)))
    elif profile_tax_id != _normalise_tax_id(justificante.tax_id):
        diffs.append(
            ModeloReconciliationDiff(
                field_name="tax_id",
                work_unit_value=profile_tax_id,
                evidence_value=justificante.tax_id,
                kind="tax_id_mismatch",
                diff_kind=ModeloReconciliationDiffKind.HEADER_FIELD,
            ),
        )

    total_diffs, total_advisories = _reconcile_receipt_totals(work_unit=work_unit, justificante=justificante)
    diffs.extend(total_diffs)
    advisories.extend(total_advisories)

    verdict = ModeloReconciliationVerdict.MATCHES if not diffs else ModeloReconciliationVerdict.MISMATCHES
    narrative = (
        f"reconciled modelo {justificante.modelo} for ejercicio {justificante.ejercicio or '?'} "
        f"against work unit {work_unit_id}; verdict={verdict.value}; diffs={len(diffs)}; "
        f"advisories={len(advisories)}"
    )
    reconciled_at = now()
    report = ModeloReconciliationReport(
        work_unit_id=work_unit_id,
        bucket_id=work_unit.bucket_id,
        source_kind=source_kind,
        source_path=source_ref,
        verdict=verdict,
        diffs=tuple(diffs),
        advisories=tuple(advisories),
        reconciled_at=reconciled_at,
        narrative=narrative,
    )

    event_payload = {
        "work_unit_id": work_unit_id,
        "source_kind": source_kind.value,
        "source_path": source_ref,
        "verdict": verdict.value,
        "diffs": str(len(diffs)),
        "diffs_detail": _encode_diffs(diffs),
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


def _identity_anchor_unverified(anchor: str, *, modelo: str) -> ModeloReconciliationAdvisory:
    """Advisory: a receipt / profile identity anchor could not be compared.

    A receipt that omits ``ejercicio``, or an active profile with no ``tax_id``,
    used to drop that anchor from the compare silently and could still reach
    ``matches``. This advisory discloses the skipped anchor so an identity-only
    ``matches`` is never a silent pass on a missing anchor
    (``no-silent-under-declaration``).
    """
    return ModeloReconciliationAdvisory(
        code="identity_anchor_unverified",
        message=(
            f"identity anchor {anchor!r} could not be verified for modelo {modelo}: "
            "the receipt or the active profile did not supply it"
        ),
        context={"anchor": anchor, "modelo": modelo},
    )


def _totals_not_reconciled(reason: str, *, modelo: str, detail: str = "") -> ModeloReconciliationAdvisory:
    """Advisory: the filed totals were not value-reconciled against the engine.

    Emitted when the revision declares no ``reconciliation_total_casilla_ids``
    map, no persisted calculation revision exists, the receipt printed no total,
    or the receipt's total kind is unmapped. The verdict stays scoped to
    identity; this advisory prevents a false green by disclosing that the filed
    amount was not checked against the computed result.
    """
    context = {"reason": reason, "modelo": modelo}
    if detail:
        context["detail"] = detail
    return ModeloReconciliationAdvisory(
        code="totals_not_reconciled",
        message=(
            f"filed totals were not reconciled against the computed result for modelo {modelo} "
            f"({reason}); verdict reflects receipt identity only"
        ),
        context=context,
    )


def _reconcile_receipt_totals(
    *,
    work_unit: WorkUnit,
    justificante: Justificante,
) -> tuple[list[ModeloReconciliationDiff], list[ModeloReconciliationAdvisory]]:
    """Reconcile the receipt total against the canonical computed result casilla.

    Resolves the registry snapshot for ``work_unit``, reads the
    ``reconciliation_total_casilla_ids`` map its verification expectations
    declare (the same map ``calculation_result_summary`` consumes), loads the
    filed / verified persisted :class:`~aeat.domain.modelos.CalculationRevision`,
    and compares the receipt's printed total against
    ``revision.casilla_values[target_casilla]`` at the expectation's declared
    tolerance. A divergence is a typed ``total`` diff carrying the reconciling
    expectation's ``legal_refs`` / ``source_refs``. Every branch that cannot
    perform the comparison returns a ``totals_not_reconciled`` advisory instead
    of silently passing.
    """
    modelo = str(work_unit.modelo)
    try:
        targets = _total_targets_for_work_unit(work_unit)
    except (LookupError, KeyError, AttributeError, ValueError, AeatError):
        return [], [_totals_not_reconciled("snapshot_unavailable", modelo=modelo)]
    if not targets:
        return [], [_totals_not_reconciled("map_not_declared", modelo=modelo)]

    receipt_kind, receipt_total = _receipt_total(justificante)
    if receipt_kind is None or receipt_total is None:
        return [], [_totals_not_reconciled("receipt_has_no_total", modelo=modelo)]

    target = targets.get(receipt_kind)
    if target is None:
        return [], [_totals_not_reconciled("receipt_kind_unmapped", modelo=modelo, detail=receipt_kind)]

    try:
        computed = _computed_result_value(work_unit, target.casilla_id)
    except (LookupError, KeyError, AttributeError, ValueError, AeatError):
        return [], [_totals_not_reconciled("no_persisted_revision", modelo=modelo)]
    if computed is None:
        return [], [_totals_not_reconciled("no_persisted_revision", modelo=modelo)]

    # The receipt prints a non-negative magnitude under its ingresar/devolver
    # heading; the result casilla carries its own sign convention. Compare the
    # magnitudes so a devolver casilla stored negative still reconciles, while a
    # genuine sign flip (result 0 vs a printed total) still surfaces.
    if abs(receipt_total - abs(computed)) <= target.tolerance:
        return [], []
    return (
        [
            ModeloReconciliationDiff(
                field_name=f"total_{receipt_kind}",
                work_unit_value=_format_decimal(abs(computed)),
                evidence_value=_format_decimal(receipt_total),
                kind=f"total_{receipt_kind}_mismatch",
                diff_kind=ModeloReconciliationDiffKind.TOTAL,
                legal_refs=target.legal_refs,
                source_refs=target.source_refs,
            ),
        ],
        [],
    )


class _TotalTarget:
    """A declared receipt-total → canonical result-casilla reconciliation target."""

    __slots__ = ("casilla_id", "legal_refs", "source_refs", "tolerance")

    def __init__(
        self,
        *,
        casilla_id: str,
        tolerance: Decimal,
        legal_refs: tuple[str, ...],
        source_refs: tuple[str, ...],
    ) -> None:
        self.casilla_id = casilla_id
        self.tolerance = tolerance
        self.legal_refs = legal_refs
        self.source_refs = source_refs


def _total_targets_for_work_unit(work_unit: WorkUnit) -> dict[str, _TotalTarget]:
    """Collect the ``{ingresar|devolver: _TotalTarget}`` map from the snapshot.

    First declaration wins per kind (mirroring ``calculation_result_summary``),
    so a revision that repeats a total across expectations resolves
    deterministically to one target casilla.
    """
    from ._calculation_helpers import resolve_registry_snapshot_for_work_unit

    snapshot = resolve_registry_snapshot_for_work_unit(work_unit)
    targets: dict[str, _TotalTarget] = {}
    for expectation in snapshot.revision.verification_expectations:
        for kind, casilla_id in expectation.reconciliation_total_casilla_ids.items():
            targets.setdefault(
                str(kind),
                _TotalTarget(
                    casilla_id=str(casilla_id),
                    tolerance=Decimal(expectation.tolerance),
                    legal_refs=tuple(str(ref) for ref in expectation.legal_refs),
                    source_refs=tuple(str(ref) for ref in expectation.source_refs),
                ),
            )
    return targets


def _computed_result_value(work_unit: WorkUnit, casilla_id: str) -> Decimal | None:
    """Return the canonical computed value of ``casilla_id`` for ``work_unit``.

    Reads the persisted filed / verified calculation revision (never a fresh
    calculation — the reconcile path stays local-only), so the value compared is
    the same canonical ``revision.casilla_values`` the result-summary and export
    surfaces render (``one-aggregation-path-pull-equals-calculate``). Returns
    ``None`` when no persisted revision carries the casilla.
    """
    from ...domain.modelos._calculation_repository import CalculationRevisionCatalogueRepository

    catalogue = CalculationRevisionCatalogueRepository().load()
    revision = _select_filed_revision(catalogue.for_work_unit(str(work_unit.work_unit_id)))
    if revision is None:
        return None
    return revision.casilla_values.get(casilla_id)


def _select_filed_revision(revisions: tuple[object, ...]) -> object | None:
    """Pick the revision that best represents what was filed.

    Prefers filed / verified states in priority order (``PRESENTADO`` >
    ``PRESENTADO_SUPERSEDIDO`` > ``VERIFICADO_COMPLETO``), then the most recent
    by ``updated_at``; falls back to the most recent revision of any state so a
    receipt can still be value-reconciled before the filing is recorded in-app.
    """
    from ...domain.modelos._calculation_revision import CalculationRevisionState

    if not revisions:
        return None
    priority = {
        CalculationRevisionState.PRESENTADO: 3,
        CalculationRevisionState.PRESENTADO_SUPERSEDIDO: 2,
        CalculationRevisionState.VERIFICADO_COMPLETO: 1,
    }
    return max(
        revisions,
        key=lambda rev: (priority.get(rev.state, 0), rev.updated_at),
    )


def _receipt_total(justificante: Justificante) -> tuple[str | None, Decimal | None]:
    """Return the receipt's printed total as a ``(kind, magnitude)`` pair.

    A justificante prints at most one of ``total_a_ingresar`` /
    ``total_a_devolver``. ``ingresar`` takes precedence when both are present.
    """
    if justificante.total_a_ingresar is not None:
        return "ingresar", abs(justificante.total_a_ingresar)
    if justificante.total_a_devolver is not None:
        return "devolver", abs(justificante.total_a_devolver)
    return None, None


def _format_decimal(value: Decimal) -> str:
    return f"{value:.2f}"


def _encode_diffs(diffs: list[ModeloReconciliationDiff]) -> str:
    """Serialise the structured diffs for the ``MODELO_RECONCILED`` payload.

    History persisted only a diff *count*; this JSON string carries *which*
    fields diverged so ``reconcile history`` is auditable after the fact.
    """
    return json.dumps([diff.model_dump(mode="json") for diff in diffs], separators=(",", ":"))


def _decode_diffs(raw: str) -> tuple[ModeloReconciliationDiff, ...]:
    if not raw:
        return ()
    try:
        payload = json.loads(raw)
    except (ValueError, TypeError):
        return ()
    decoded: list[ModeloReconciliationDiff] = []
    for item in payload:
        # The strict frozen model does not coerce JSON lists into its
        # ``tuple[str, ...]`` grounding fields; normalise them on the way in.
        normalised = dict(item)
        for grounding in ("legal_refs", "source_refs"):
            if grounding in normalised:
                normalised[grounding] = tuple(normalised[grounding])
        if "diff_kind" in normalised:
            normalised["diff_kind"] = ModeloReconciliationDiffKind(normalised["diff_kind"])
        decoded.append(ModeloReconciliationDiff.model_validate(normalised))
    return tuple(decoded)


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
                source_kind=ModeloReconciliationEvidenceKind(payload["source_kind"]),
                source_path=payload.get("source_path", ""),
                verdict=ModeloReconciliationVerdict(payload["verdict"]),
                diff_count=int(payload.get("diffs", "0")),
                diffs=_decode_diffs(payload.get("diffs_detail", "")),
                actor=event.actor,
                reconciled_at=event.occurred_at,
            ),
        )
    return tuple(entries)


__all__ = [
    "ModeloReconciliationAdvisory",
    "ModeloReconciliationBytesCommand",
    "ModeloReconciliationCommand",
    "ModeloReconciliationDiff",
    "ModeloReconciliationDiffKind",
    "ModeloReconciliationEvidenceKind",
    "ModeloReconciliationHistoryEntry",
    "ModeloReconciliationReport",
    "ModeloReconciliationVerdict",
    "ReconciliationCrossBucketRefusedError",
    "ReconciliationDeclaracionSourceUnsupportedError",
    "ReconciliationEvidenceInvalidError",
    "WorkUnitNotFoundError",
    "list_modelo_reconciliations",
    "modelo_reconcile",
    "modelo_reconcile_bytes",
]
