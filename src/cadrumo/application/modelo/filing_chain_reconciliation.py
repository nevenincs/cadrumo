"""Reconcile one AEAT register entry with the filing chain of its period.

The filing catalogue holds, per (bucket, modelo, year, period, member), a
linear chain of declarations. A local filing stays ``PENDIENTE`` until AEAT is
seen to hold it; AEAT register entries are the only proof of presentation.
:func:`reconcile_aeat_register_entry` is the single decision point that turns
one normalized register entry into a chain transition:

* ``ALREADY_RECORDED`` -- the register reference is already on the chain.
* ``CONFIRMED`` -- the in-force pending entry carries the content AEAT holds;
  it becomes ``CONFIRMADA`` and its pending-local observation layer becomes the
  official one.
* ``CONTRADICTED`` -- AEAT holds different content than the pending entry; the
  AEAT content is appended in force, amending the latest confirmed entry, and
  the pending entry becomes ``DISCREPANTE``.
* ``APPENDED`` -- no pending entry exists; the AEAT content is appended in
  force.
* ``UNVERIFIABLE`` -- the entry cannot be compared or materialized; nothing is
  stamped and a notice says why.

Every transition and its bucket event commit in one unit of work with the
filing catalogue.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING, Literal

from ...core.aeat_csv import normalise_aeat_csv
from ...core.casilla_id import CasillaId
from ...core.modelo import Modelo
from ...core.observed_header_fact import ObservedHeaderFact
from ...core.period import Period
from ...domain.buckets.event import BucketEvent, BucketEventObjectType, BucketEventType
from ...domain.buckets.event_repository import bucket_event_history_write
from ...domain.justificante.protocols import JustificanteRepositoryProtocol
from ...domain.justificante.schema import Justificante
from ...domain.modelos.calculation_revision import CalculationRevision, CalculationRevisionCatalogue
from ...domain.modelos.calculation_revision_m303_handoff import FilingInstanceEvidence
from ...domain.modelos.filing_record import (
    AeatConfirmationState,
    AeatRegisterRef,
    ExternalEvidence,
    ExternalEvidenceKind,
    FilingDeclarationKind,
    ModeloRecord,
    ModeloRecordCatalogue,
    derive_filing_record_id,
    is_justificante_backed_external_evidence,
    is_receipt_bound_external_evidence,
)
from ...domain.modelos.filing_repository import upsert_filing_record
from ...domain.modelos.protocols import (
    CalculationRevisionCatalogueRepositoryProtocol,
    ModeloRecordCatalogueRepositoryProtocol,
)
from ...domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue
from ..calculations.observations_repository import CalculationObservationRepositoryProtocol, ObservationSourceKind
from ._registry_helpers import reject_unknown_import_casillas
from .action_errors import ExternalModeloImportError
from .external_import_actions import (
    ExternalFilingTarget,
    advance_external_filing_work_unit,
    build_external_filing_observation_payload,
    build_external_filing_record,
    prepare_external_filing_revision,
    require_bound_justificante_artifact,
    resolve_external_filing_work_unit,
)
from .reconcile_casilla import detect_casilla_divergences
from .reconciliation import reconcile_receipt_totals
from .revision_persistence import build_modelo_bucket_event, supersede_prior_current_filing
from .work_lifecycle import ActiveWorkUnitUse, require_active_work_unit
from .work_lifecycle_ports import WorkLifecyclePorts

if TYPE_CHECKING:
    from ...core.secure_object_write import SecureObjectWrite
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation

FilingEvidenceBasis = Literal["casillas", "receipt_totals"]

_OFFICIAL_SOURCE_KIND_BY_EVIDENCE: Mapping[ExternalEvidenceKind, ObservationSourceKind] = {
    ExternalEvidenceKind.AEAT_CSV_REGISTER: ObservationSourceKind.AEAT_CSV_REGISTER,
    ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF: ObservationSourceKind.AEAT_SEDE_JUSTIFICANTE,
    ExternalEvidenceKind.AEAT_LIVE_CAPTURE: ObservationSourceKind.AEAT_SEDE_LIVE_CAPTURE,
}


class FilingReconciliationOutcome(StrEnum):
    """Closed result of reconciling one AEAT register entry."""

    ALREADY_RECORDED = "already_recorded"
    CONFIRMED = "confirmed"
    CONTRADICTED = "contradicted"
    APPENDED = "appended"
    UNVERIFIABLE = "unverifiable"


class FilingReconciliationNoticeCode(StrEnum):
    """Stable codes for conditions a reconciliation reports to the operator.

    * ``CONTENT_UNAVAILABLE`` -- the entry carries neither casillas nor a
      comparable receipt, or carries no casillas to record AEAT content from.
    * ``RECEIPT_TOTALS_NOT_RECONCILED`` -- the receipt total could not be
      compared; ``reason`` names why.
    * ``RECEIPT_TOTALS_MISMATCH`` -- the receipt total disagrees with the
      pending entry, but without casillas the AEAT content cannot be recorded.
    * ``RECEIPT_TOTALS_ONLY`` -- a confirmation rests on receipt totals rather
      than per-casilla equality.
    * ``DECLARATION_KIND_MISMATCH`` -- AEAT states a different declaration kind
      than the pending entry.
    * ``DECLARATION_KIND_UNDETERMINED`` -- AEAT presents after a confirmed
      declaration without stating the correction kind.
    * ``CORRECTION_WITHOUT_CONFIRMED_BASELINE`` -- AEAT states a correction kind
      but the chain holds no confirmed declaration to link it to.
    * ``FILING_INSTANCE_EVIDENCE_UNAVAILABLE`` -- the modelo's content can only
      be recorded with its filing-instance evidence, which the entry lacks.
    """

    CONTENT_UNAVAILABLE = "content_unavailable"
    RECEIPT_TOTALS_NOT_RECONCILED = "receipt_totals_not_reconciled"
    RECEIPT_TOTALS_MISMATCH = "receipt_totals_mismatch"
    RECEIPT_TOTALS_ONLY = "receipt_totals_only"
    DECLARATION_KIND_MISMATCH = "declaration_kind_mismatch"
    DECLARATION_KIND_UNDETERMINED = "declaration_kind_undetermined"
    CORRECTION_WITHOUT_CONFIRMED_BASELINE = "correction_without_confirmed_baseline"
    FILING_INSTANCE_EVIDENCE_UNAVAILABLE = "filing_instance_evidence_unavailable"


@dataclass(frozen=True, slots=True)
class FilingReconciliationNotice:
    """One reported condition, keyed by a stable code with identifier-only context."""

    code: FilingReconciliationNoticeCode
    context: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AeatRegisterEntry:
    """One normalized AEAT register entry for a filing coordinate.

    ``casilla_values`` are the values AEAT holds for the presentation, when the
    source exposes them, and ``source_lexicals`` their printed spellings when
    the source kept them; ``justificante`` is the parsed receipt, when one is
    available. ``tax_id`` is the presenting taxpayer's identifier.
    ``target_work_unit_id`` names the work unit AEAT content is recorded on
    when the caller has already chosen it.
    """

    bucket_id: str
    modelo: str
    filing_year: int
    period: Period
    register: AeatRegisterRef
    evidence_kind: ExternalEvidenceKind
    tax_id: str
    member_nif: str | None = None
    declared_kind: FilingDeclarationKind | None = None
    justificante: Justificante | None = None
    casilla_values: Mapping[CasillaId, Decimal] | None = None
    source_lexicals: Mapping[CasillaId, str] | None = None
    filing_instance_evidence: FilingInstanceEvidence | None = None
    source_headers: tuple[ObservedHeaderFact, ...] = ()
    target_work_unit_id: str | None = None

    def __post_init__(self) -> None:
        """Refuse an entry whose coordinate, content or receipt do not agree."""
        if self.period.filing_year != self.filing_year:
            raise ExternalModeloImportError(
                translated_message="application.modelo.errors.external_import_source_period_mismatch",
            )
        if self.casilla_values is not None and not self.casilla_values:
            raise ExternalModeloImportError(
                translated_message="application.modelo.errors.external_filing_no_casilla_values",
            )
        receipt = self.justificante
        if receipt is None:
            return
        csv_disagrees = self.register.csv is not None and receipt.csv != self.register.csv
        if csv_disagrees or not receipt.matches_filing_target(
            modelo=self.modelo,
            filing_year=self.filing_year,
            period=self.period,
            tax_id=self.tax_id,
        ):
            raise ExternalModeloImportError(
                translated_message="application.modelo.errors.external_import_justificante_mismatch",
                context={
                    "evidence_reference_id": receipt.csv,
                    "modelo": self.modelo,
                    "filing_year": str(self.filing_year),
                    "period": self.period.registry_token,
                },
            )


@dataclass(frozen=True, slots=True)
class FilingReconciliationResult:
    """What one reconciliation decided, reported as identifiers only.

    ``filing_record_id`` is the chain entry the outcome is about: the recorded,
    confirmed or appended entry, or the pending entry an unverifiable entry
    could not be compared with. ``affected_filing_record_ids`` lists every
    other chain entry whose state changed.
    """

    outcome: FilingReconciliationOutcome
    bucket_id: str
    modelo: str
    filing_year: int
    period: Period
    member_nif: str | None
    filing_record_id: str | None
    affected_filing_record_ids: tuple[str, ...] = ()
    differing_casilla_ids: tuple[CasillaId, ...] = ()
    evidence_basis: FilingEvidenceBasis | None = None
    notices: tuple[FilingReconciliationNotice, ...] = ()


@dataclass(frozen=True, slots=True)
class FilingReconciliationPorts:
    """Persistence authorities one reconciliation reads and co-commits."""

    filing_repository: ModeloRecordCatalogueRepositoryProtocol
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol
    work_lifecycle: WorkLifecyclePorts
    observation_repository: CalculationObservationRepositoryProtocol
    justificante_repository: JustificanteRepositoryProtocol


@dataclass(frozen=True, slots=True)
class _Comparison:
    matches: bool
    comparable: bool
    differing_casilla_ids: tuple[CasillaId, ...] = ()
    evidence_basis: FilingEvidenceBasis | None = None
    notices: tuple[FilingReconciliationNotice, ...] = ()


@dataclass(frozen=True, slots=True)
class _Context:
    entry: AeatRegisterEntry
    ports: FilingReconciliationPorts
    operation: PinnedAuthorityOperation
    actor: str
    now: datetime
    catalogue: ModeloRecordCatalogue
    catalogue_revision_id: str
    evidence_reference_id: str

    def current(self) -> ModeloRecord | None:
        entry = self.entry
        return self.catalogue.current_for(
            bucket_id=entry.bucket_id,
            modelo=entry.modelo,
            filing_year=entry.filing_year,
            period=entry.period,
            member_nif=entry.member_nif,
        )

    def latest_confirmed(self) -> ModeloRecord | None:
        entry = self.entry
        return self.catalogue.latest_confirmed_for(
            bucket_id=entry.bucket_id,
            modelo=entry.modelo,
            filing_year=entry.filing_year,
            period=entry.period,
            member_nif=entry.member_nif,
        )


def reconcile_aeat_register_entry(
    entry: AeatRegisterEntry,
    *,
    ports: FilingReconciliationPorts,
    operation: PinnedAuthorityOperation,
    actor: str,
    clock: datetime,
) -> FilingReconciliationResult:
    """Apply one AEAT register entry to its period's filing chain.

    The receipt, when present, is stored before any chain entry cites it. A
    register reference already on the chain is a no-op and emits no event, so
    re-reading the same register is idempotent. Every other outcome emits one
    ``modelo.filing.reconciled`` event in the same unit of work as its chain
    transition.

    Raises:
        ExternalModeloImportError: The entry's receipt evidence cannot be bound
            to the coordinate, or its casillas are not declared by the registry.
    """
    catalogue, catalogue_revision_id = ports.filing_repository.load_revisioned()
    history = catalogue.history_for(
        bucket_id=entry.bucket_id,
        modelo=entry.modelo,
        filing_year=entry.filing_year,
        period=entry.period,
        member_nif=entry.member_nif,
    )
    recorded = recorded_chain_entry(history, entry.register)
    if recorded is not None:
        return _result(entry, FilingReconciliationOutcome.ALREADY_RECORDED, recorded.filing_record_id)
    context = _Context(
        entry=entry,
        ports=ports,
        operation=operation,
        actor=actor.strip(),
        now=clock,
        catalogue=catalogue,
        catalogue_revision_id=catalogue_revision_id,
        evidence_reference_id=_evidence_reference_id(entry),
    )
    receipt = entry.justificante
    if receipt is not None and ports.justificante_repository.load(receipt.csv) != receipt:
        ports.justificante_repository.save(receipt)
    current = context.current()
    if current is None or current.confirmation is not AeatConfirmationState.PENDIENTE:
        return _append(context, current=current)
    comparison = _compare_with_pending(context, pending=current)
    if comparison.matches:
        return _confirm(context, pending=current, comparison=comparison)
    if not comparison.comparable or entry.casilla_values is None:
        return _unverifiable(context, subject=current, comparison=comparison)
    return _contradict(context, pending=current, comparison=comparison)


def recorded_chain_entry(history: tuple[ModeloRecord, ...], register: AeatRegisterRef) -> ModeloRecord | None:
    """Return the chain entry that already records ``register``, if any.

    An entry records the register when its stored register reference names the
    same expediente or CSV, or when its evidence reference is that expediente
    or CSV. CSVs compare in their canonical form, so one receipt spelled two
    ways is still one receipt.
    """
    expediente_id = register.expediente_id.strip()
    csv = normalise_aeat_csv(register.csv) if register.csv is not None else None
    for record in history:
        stored = record.aeat_register
        if stored is not None and (
            stored.expediente_id.strip() == expediente_id
            or (csv is not None and stored.csv is not None and normalise_aeat_csv(stored.csv) == csv)
        ):
            return record
        evidence = record.external_evidence
        if evidence is None:
            continue
        reference = evidence.reference_id.strip()
        if reference == expediente_id:
            return record
        if (
            csv is not None
            and is_justificante_backed_external_evidence(evidence.kind)
            and normalise_aeat_csv(reference) == csv
        ):
            return record
    return None


def _evidence_reference_id(entry: AeatRegisterEntry) -> str:
    """Return the evidence reference: the receipt CSV when the kind is receipt-bound."""
    if not is_receipt_bound_external_evidence(entry.evidence_kind):
        return entry.register.expediente_id
    csv = entry.register.csv or (entry.justificante.csv if entry.justificante is not None else None)
    if csv is None:
        raise ExternalModeloImportError(
            translated_message="application.modelo.errors.external_import_justificante_missing",
            context={
                "evidence_reference_id": entry.register.expediente_id,
                "evidence_kind": entry.evidence_kind.value,
            },
        )
    return csv


def _compare_with_pending(context: _Context, *, pending: ModeloRecord) -> _Comparison:
    entry = context.entry
    kind_notices: tuple[FilingReconciliationNotice, ...] = ()
    kind_matches = entry.declared_kind is None or entry.declared_kind is pending.declaration_kind
    if not kind_matches:
        kind_notices = (
            FilingReconciliationNotice(
                FilingReconciliationNoticeCode.DECLARATION_KIND_MISMATCH,
                {
                    "declared_kind": str(entry.declared_kind),
                    "pending_kind": pending.declaration_kind.value,
                },
            ),
        )
    revision = context.ports.calculation_repository.load().get(pending.calculation_revision_id)
    if entry.casilla_values is not None:
        snapshot, filed = reject_unknown_import_casillas(
            modelo=entry.modelo,
            filing_year=entry.filing_year,
            period=entry.period,
            casilla_values=entry.casilla_values,
        )
        computed = revision.casilla_values if revision is not None else {}
        divergences = detect_casilla_divergences(
            computed=computed,
            filed=filed,
            scope=filed,
            tolerance=snapshot.verification_policy().tolerance,
        )
        differing = tuple(divergence.casilla_id for divergence in divergences)
        return _Comparison(
            matches=kind_matches and not differing,
            comparable=True,
            differing_casilla_ids=differing,
            evidence_basis="casillas",
            notices=kind_notices,
        )
    if entry.justificante is None:
        return _Comparison(
            matches=False,
            comparable=False,
            notices=(*kind_notices, FilingReconciliationNotice(FilingReconciliationNoticeCode.CONTENT_UNAVAILABLE)),
        )
    work_unit = _chain_work_unit(context, pending)
    diffs, advisories = reconcile_receipt_totals(
        work_unit=work_unit,
        justificante=entry.justificante,
        revision=revision,
        operation=context.operation,
    )
    if advisories:
        return _Comparison(
            matches=False,
            comparable=False,
            notices=(
                *kind_notices,
                *(
                    FilingReconciliationNotice(
                        FilingReconciliationNoticeCode.RECEIPT_TOTALS_NOT_RECONCILED,
                        {"reason": advisory.context.get("reason", advisory.code)},
                    )
                    for advisory in advisories
                ),
            ),
        )
    if diffs:
        return _Comparison(
            matches=False,
            comparable=False,
            evidence_basis="receipt_totals",
            notices=(
                *kind_notices,
                *(
                    FilingReconciliationNotice(
                        FilingReconciliationNoticeCode.RECEIPT_TOTALS_MISMATCH,
                        {"field_name": diff.field_name},
                    )
                    for diff in diffs
                ),
            ),
        )
    return _Comparison(
        matches=kind_matches,
        comparable=True,
        evidence_basis="receipt_totals",
        notices=(*kind_notices, FilingReconciliationNotice(FilingReconciliationNoticeCode.RECEIPT_TOTALS_ONLY)),
    )


def _chain_work_unit(context: _Context, record: ModeloRecord) -> WorkUnit:
    repository = context.ports.work_lifecycle.work_unit_repository
    return require_active_work_unit(
        repository.load(),
        work_unit_id=record.work_unit_id,
        repository_bucket_id=repository.bucket_id,
        use=ActiveWorkUnitUse.IMPORT,
    )


def _confirm(context: _Context, *, pending: ModeloRecord, comparison: _Comparison) -> FilingReconciliationResult:
    entry = context.entry
    require_bound_justificante_artifact(
        evidence_kind=entry.evidence_kind,
        evidence_reference_id=context.evidence_reference_id,
        modelo=entry.modelo,
        filing_year=entry.filing_year,
        period=entry.period,
        expected_tax_id=entry.tax_id,
        justificante_repository=context.ports.justificante_repository,
    )
    confirmed = pending.model_copy(
        update={
            "confirmation": AeatConfirmationState.CONFIRMADA,
            "external_evidence": ExternalEvidence(
                kind=entry.evidence_kind,
                reference_id=context.evidence_reference_id,
                imported_at=context.now,
            ),
            "aeat_register": entry.register,
        },
    )
    observation_writes = context.ports.observation_repository.promote_pending_local(
        entry.modelo,
        entry.period,
        member_nif=entry.member_nif,
        source_kind=_OFFICIAL_SOURCE_KIND_BY_EVIDENCE[entry.evidence_kind],
        source_metadata=_official_source_metadata(context, filing_record_id=confirmed.filing_record_id),
        captured_at=context.now,
    )
    result = _result(
        entry,
        FilingReconciliationOutcome.CONFIRMED,
        confirmed.filing_record_id,
        evidence_basis=comparison.evidence_basis,
        notices=comparison.notices,
    )
    _commit(
        context,
        catalogue=upsert_filing_record(context.catalogue, confirmed),
        result=result,
        extra_writes=observation_writes,
    )
    return result


def _unverifiable(
    context: _Context,
    *,
    subject: ModeloRecord | None,
    comparison: _Comparison,
) -> FilingReconciliationResult:
    result = _result(
        context.entry,
        FilingReconciliationOutcome.UNVERIFIABLE,
        subject.filing_record_id if subject is not None else None,
        evidence_basis=comparison.evidence_basis,
        notices=comparison.notices,
    )
    _commit(context, catalogue=context.catalogue, result=result, extra_writes=())
    return result


def _append(context: _Context, *, current: ModeloRecord | None) -> FilingReconciliationResult:
    entry = context.entry
    if entry.casilla_values is None:
        return _unverifiable(
            context,
            subject=current,
            comparison=_Comparison(
                matches=False,
                comparable=False,
                notices=(FilingReconciliationNotice(FilingReconciliationNoticeCode.CONTENT_UNAVAILABLE),),
            ),
        )
    notices: tuple[FilingReconciliationNotice, ...] = ()
    if entry.declared_kind is not None:
        kind = entry.declared_kind
    elif current is None:
        kind = FilingDeclarationKind.ORIGINAL
    else:
        return _unverifiable(
            context,
            subject=current,
            comparison=_Comparison(
                matches=False,
                comparable=False,
                notices=(FilingReconciliationNotice(FilingReconciliationNoticeCode.DECLARATION_KIND_UNDETERMINED),),
            ),
        )
    if current is None and kind is not FilingDeclarationKind.ORIGINAL:
        notices = (FilingReconciliationNotice(FilingReconciliationNoticeCode.CORRECTION_WITHOUT_CONFIRMED_BASELINE),)
    return _record_aeat_content(
        context,
        outcome=FilingReconciliationOutcome.APPENDED,
        kind=kind,
        superseded=current,
        baseline=current,
        comparison=_Comparison(matches=False, comparable=True, notices=notices),
    )


def _contradict(context: _Context, *, pending: ModeloRecord, comparison: _Comparison) -> FilingReconciliationResult:
    entry = context.entry
    baseline = context.latest_confirmed()
    kind = entry.declared_kind or pending.declaration_kind
    notices = comparison.notices
    if baseline is None and kind is not FilingDeclarationKind.ORIGINAL:
        notices = (
            *notices,
            FilingReconciliationNotice(FilingReconciliationNoticeCode.CORRECTION_WITHOUT_CONFIRMED_BASELINE),
        )
    return _record_aeat_content(
        context,
        outcome=FilingReconciliationOutcome.CONTRADICTED,
        kind=kind,
        superseded=pending,
        baseline=baseline,
        comparison=_Comparison(
            matches=False,
            comparable=True,
            differing_casilla_ids=comparison.differing_casilla_ids,
            evidence_basis=comparison.evidence_basis,
            notices=notices,
        ),
    )


def _record_aeat_content(
    context: _Context,
    *,
    outcome: FilingReconciliationOutcome,
    kind: FilingDeclarationKind,
    superseded: ModeloRecord | None,
    baseline: ModeloRecord | None,
    comparison: _Comparison,
) -> FilingReconciliationResult:
    """Append AEAT's content as the in-force entry, retiring a contradicted pending entry.

    ``superseded`` is the current entry leaving force. ``baseline`` is the
    confirmed declaration the new entry amends, if any.
    """
    entry = context.entry
    casilla_values = entry.casilla_values
    if casilla_values is None:
        raise ExternalModeloImportError(
            translated_message="application.modelo.errors.external_filing_no_casilla_values",
        )
    if entry.modelo == Modelo("303").value and entry.filing_instance_evidence is None:
        return _unverifiable(
            context,
            subject=superseded,
            comparison=_Comparison(
                matches=False,
                comparable=False,
                differing_casilla_ids=comparison.differing_casilla_ids,
                evidence_basis=comparison.evidence_basis,
                notices=(
                    *comparison.notices,
                    FilingReconciliationNotice(FilingReconciliationNoticeCode.FILING_INSTANCE_EVIDENCE_UNAVAILABLE),
                ),
            ),
        )
    work_unit = _target_work_unit(context, superseded)
    draft = prepare_external_filing_revision(
        work_unit_id=work_unit.work_unit_id,
        casilla_values=casilla_values,
        source_lexical_values_by_casilla_id=entry.source_lexicals,
        evidence_kind=entry.evidence_kind,
        evidence_reference_id=context.evidence_reference_id,
        filing_instance_evidence=entry.filing_instance_evidence,
        expected_tax_id=entry.tax_id,
        actor=context.actor,
        now=context.now,
        work_unit_repository=context.ports.work_lifecycle.work_unit_repository,
        calculation_repository=context.ports.calculation_repository,
        justificante_repository=context.ports.justificante_repository,
    )
    revision = draft.revision
    new_id = derive_filing_record_id(
        work_unit_id=draft.work_unit.work_unit_id,
        calculation_revision_id=revision.calculation_revision_id,
        filed_by=context.actor,
        member_nif=entry.member_nif,
    )
    catalogue, revisions, affected = _retire_for_aeat_entry(
        context,
        new_id=new_id,
        superseded=superseded,
        baseline=baseline,
        revisions=draft.revisions,
    )
    new_record = build_external_filing_record(
        filing_record_id=new_id,
        work_unit=draft.work_unit,
        calculation_revision_id=revision.calculation_revision_id,
        filed_at=context.now,
        filed_by=context.actor,
        evidence_kind=entry.evidence_kind,
        evidence_reference_id=draft.evidence_reference_id,
        declaration_kind=kind,
        member_nif=entry.member_nif,
        amends_filing_record_id=baseline.filing_record_id if baseline is not None else None,
        aeat_register=entry.register,
    )
    catalogue = upsert_filing_record(catalogue, new_record)
    result = _result(
        entry,
        outcome,
        new_id,
        affected=affected,
        differing=comparison.differing_casilla_ids,
        evidence_basis=comparison.evidence_basis,
        notices=comparison.notices,
    )
    _commit(
        context,
        catalogue=catalogue,
        result=result,
        extra_writes=_aeat_content_writes(
            context,
            draft_revisions=(revisions, draft.revisions_revision_id),
            work_units=advance_external_filing_work_unit(
                draft.work_units,
                work_unit=draft.work_unit,
                revision_id=revision.calculation_revision_id,
                filing_record_id=new_id,
                now=context.now,
            ),
            work_unit=draft.work_unit,
            revision=revision,
            filing_record_id=new_id,
            clear_pending=outcome is FilingReconciliationOutcome.CONTRADICTED,
        ),
    )
    return result


def _target_work_unit(context: _Context, chain_record: ModeloRecord | None) -> WorkUnit:
    entry = context.entry
    if entry.target_work_unit_id is not None:
        repository = context.ports.work_lifecycle.work_unit_repository
        return require_active_work_unit(
            repository.load(),
            work_unit_id=entry.target_work_unit_id,
            repository_bucket_id=repository.bucket_id,
            use=ActiveWorkUnitUse.IMPORT,
        )
    if chain_record is not None:
        return _chain_work_unit(context, chain_record)
    return resolve_external_filing_work_unit(
        ExternalFilingTarget(modelo=entry.modelo, filing_year=entry.filing_year, period=entry.period),
        bucket_id=entry.bucket_id,
        actor=context.actor,
        ports=context.ports.work_lifecycle,
        operation=context.operation,
        clock=context.now,
    )


def _retire_for_aeat_entry(
    context: _Context,
    *,
    new_id: str,
    superseded: ModeloRecord | None,
    baseline: ModeloRecord | None,
    revisions: CalculationRevisionCatalogue,
) -> tuple[ModeloRecordCatalogue, CalculationRevisionCatalogue, tuple[str, ...]]:
    """Take ``superseded`` out of force and point ``baseline`` at the new entry.

    A superseded pending entry is marked ``DISCREPANTE``: AEAT holds other
    content for the period. The baseline's successor link moves to the new
    entry so the amendment link stays two-sided.
    """
    catalogue = context.catalogue
    affected: list[str] = []
    if superseded is not None:
        catalogue, revisions = supersede_prior_current_filing(
            superseded,
            filing_catalogue=catalogue,
            revisions=revisions,
            new_filing_id=new_id,
            now=context.now,
        )
        if superseded.confirmation is AeatConfirmationState.PENDIENTE:
            retired = catalogue.records[superseded.filing_record_id].model_copy(
                update={"confirmation": AeatConfirmationState.DISCREPANTE},
            )
            catalogue = upsert_filing_record(catalogue, retired)
        affected.append(superseded.filing_record_id)
    if baseline is not None:
        stored_baseline = catalogue.records[baseline.filing_record_id]
        if stored_baseline.superseded_by_filing_record_id != new_id:
            catalogue = upsert_filing_record(
                catalogue,
                stored_baseline.model_copy(update={"superseded_by_filing_record_id": new_id}),
            )
        if baseline.filing_record_id not in affected:
            affected.append(baseline.filing_record_id)
    return catalogue, revisions, tuple(affected)


def _aeat_content_writes(
    context: _Context,
    *,
    draft_revisions: tuple[CalculationRevisionCatalogue, str],
    work_units: WorkUnitCatalogue,
    work_unit: WorkUnit,
    revision: CalculationRevision,
    filing_record_id: str,
    clear_pending: bool,
) -> tuple[SecureObjectWrite, ...]:
    entry = context.entry
    ports = context.ports
    revisions, revisions_revision_id = draft_revisions
    writes: list[SecureObjectWrite] = [
        ports.calculation_repository.to_secure_object_write(revisions, expected_revision_id=revisions_revision_id),
        ports.work_lifecycle.work_unit_repository.to_secure_object_write(work_units),
    ]
    observation_payload = build_external_filing_observation_payload(
        evidence_kind=entry.evidence_kind,
        observation_repository=ports.observation_repository,
        work_unit=work_unit,
        revision=revision,
        occurred_at=context.now,
        cleaned_reference=context.evidence_reference_id,
        expected_tax_id=entry.tax_id,
        filing_record_id=filing_record_id,
        source_headers=entry.source_headers,
    )
    # Both layers live in one row, so clearing the pending layer and placing
    # AEAT's content must be one write; two writes would each carry a stale copy.
    cleared = (
        ports.observation_repository.clear_pending_local(
            entry.modelo,
            entry.period,
            member_nif=entry.member_nif,
            replacement_official=observation_payload,
        )
        if clear_pending
        else ()
    )
    writes.extend(cleared)
    if observation_payload is not None and not cleared:
        writes.append(ports.observation_repository.to_secure_object_write(observation_payload))
    return tuple(writes)


def _official_source_metadata(context: _Context, *, filing_record_id: str) -> dict[str, str]:
    register = context.entry.register
    metadata = {
        "aeat_expediente_id": register.expediente_id,
        "authenticated_identity": context.entry.tax_id.strip(),
        "external_evidence_reference_id": context.evidence_reference_id,
        "filing_record_id": filing_record_id,
    }
    if register.csv is not None:
        metadata["aeat_csv"] = register.csv
    return metadata


def _commit(
    context: _Context,
    *,
    catalogue: ModeloRecordCatalogue,
    result: FilingReconciliationResult,
    extra_writes: tuple[SecureObjectWrite, ...],
) -> None:
    event = _reconciliation_event(context, result)
    context.ports.filing_repository.save_with_secure_object_writes(
        catalogue,
        (*extra_writes, bucket_event_history_write(context.ports.work_lifecycle.bucket_event_repository, (event,))),
        expected_revision_id=context.catalogue_revision_id,
    )


def _reconciliation_event(context: _Context, result: FilingReconciliationResult) -> BucketEvent:
    entry = context.entry
    if result.filing_record_id is not None:
        object_type, object_id = BucketEventObjectType.FILING_RECORD, result.filing_record_id
    else:
        object_type, object_id = BucketEventObjectType.BUCKET, entry.bucket_id
    return build_modelo_bucket_event(
        bucket_id=entry.bucket_id,
        event_type=BucketEventType.MODELO_FILING_RECONCILED,
        occurred_at=context.now,
        actor=context.actor,
        object_type=object_type,
        object_id=object_id,
        payload={
            "outcome": result.outcome.value,
            "modelo": entry.modelo,
            "filing_year": str(entry.filing_year),
            "period": entry.period.registry_token,
            "member_nif": entry.member_nif or "",
            "filing_record_id": result.filing_record_id or "",
            "affected_filing_record_ids": ",".join(result.affected_filing_record_ids),
            "differing_casilla_ids": ",".join(result.differing_casilla_ids),
            "evidence_basis": result.evidence_basis or "",
            "evidence_kind": entry.evidence_kind.value,
            "aeat_expediente_id": entry.register.expediente_id,
            "notices": ",".join(notice.code.value for notice in result.notices),
        },
    )


def _result(
    entry: AeatRegisterEntry,
    outcome: FilingReconciliationOutcome,
    filing_record_id: str | None,
    *,
    affected: tuple[str, ...] = (),
    differing: tuple[CasillaId, ...] = (),
    evidence_basis: FilingEvidenceBasis | None = None,
    notices: tuple[FilingReconciliationNotice, ...] = (),
) -> FilingReconciliationResult:
    return FilingReconciliationResult(
        outcome=outcome,
        bucket_id=entry.bucket_id,
        modelo=entry.modelo,
        filing_year=entry.filing_year,
        period=entry.period,
        member_nif=entry.member_nif,
        filing_record_id=filing_record_id,
        affected_filing_record_ids=affected,
        differing_casilla_ids=differing,
        evidence_basis=evidence_basis,
        notices=notices,
    )


__all__ = [
    "AeatRegisterEntry",
    "FilingEvidenceBasis",
    "FilingReconciliationNotice",
    "FilingReconciliationNoticeCode",
    "FilingReconciliationOutcome",
    "FilingReconciliationPorts",
    "FilingReconciliationResult",
    "reconcile_aeat_register_entry",
    "recorded_chain_entry",
]
