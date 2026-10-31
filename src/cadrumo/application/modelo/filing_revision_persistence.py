"""Local filing revision persistence and guarded co-commit."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from ...core.casilla_id import CasillaId, validated_casilla_id
from ...core.identity.hex_ids import VerificationReportId
from ...core.modelo import Modelo
from ...core.result_disposition import ResultDisposition, result_disposition_is_refund
from ...core.secure_object_write import SecureObjectWrite
from ...domain.buckets.event import BucketEvent, BucketEventObjectType, BucketEventType
from ...domain.buckets.event_repository import bucket_event_history_write
from ...domain.buckets.protocols import BucketEventHistoryRepositoryProtocol
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.prorrata_register_catalogue import (
    general_prorrata_register_regime,
    ninguna_prorrata_register_regime,
)
from ...domain.calculations.registry.result_casillas import canonical_result_amount, result_disposition_casilla_ids
from ...domain.calculations.registry.schema_references import RegistrySnapshotRef
from ...domain.iva.m303_settlement import is_m303_annual_settlement_period
from ...domain.justificante.protocols import JustificanteRepositoryProtocol
from ...domain.modelos.calculation_repository import upsert_calculation_revision
from ...domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionCatalogue,
    CalculationRevisionState,
)
from ...domain.modelos.calculation_revision_aggregate import CalculationRevisionAggregateContext
from ...domain.modelos.calculation_revision_amendment import CalculationRevisionAmendmentKind
from ...domain.modelos.calculation_revision_m303_handoff import (
    FilingInstanceEvidence,
)
from ...domain.modelos.filing_record import (
    AeatConfirmationState,
    FilingDeclarationKind,
    FilingOrigin,
    IvaCreditSnapshot,
    IvaSettlementRefundState,
    IvaSettlementSnapshot,
    ModeloRecord,
    ModeloRecordCatalogue,
    ModeloRecordStatus,
    derive_filing_record_id,
)
from ...domain.modelos.filing_repository import upsert_filing_record
from ...domain.modelos.participation_index import TransactionRevisionParticipation, upsert_transaction_participation
from ...domain.modelos.protocols import (
    CalculationRevisionCatalogueRepositoryProtocol,
    ModeloRecordCatalogueRepositoryProtocol,
    TransactionParticipationIndexRepositoryProtocol,
    VerificationReportCatalogueRepositoryProtocol,
)
from ...domain.modelos.repository import upsert_work_unit
from ...domain.modelos.verification_report import VerificationReport, VerificationReportCatalogue
from ...domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue
from ...domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol
from ...domain.prorrata_register.protocols import ProrrataRegisterRepositoryProtocol
from ...domain.prorrata_register.register import ProrrataRegister, ProrrataRegisterEntry
from ..calculations.iva_compensation_history_ports import IvaCompensationHistoryRepositoryProtocol
from ..calculations.observations_repository import (
    CalculationObservationRepositoryProtocol,
    PriorDomiciliationElectionProjection,
)
from ..calculations.verification_report_gate import require_verification_report_coordinates_current
from ..filing.retention import try_record_filing_retention_snapshot
from ..prorrata_register.service import require_prorrata_register_coordinates_current
from .action_errors import (
    CalculationRevisionStateError,
    M303FilingEvidenceError,
    VerificationReportNotFoundError,
    WorkUnitMutationRefusedError,
)
from .filed_revision_observation import (
    PreparedFiledRevisionObservation,
    filed_revision_observation_writes,
    prepare_filed_revision_observation,
    require_filing_result_disposition,
)
from .m303_filing_evidence import m303_filing_evidence_failure
from .modelo_bucket_events import build_modelo_bucket_event

_PRORRATA_VOLUMEN_TOTAL_CASILLA = validated_casilla_id(
    "iva.prorrata-volumen-total",
    surface="prorrata settlement volumen total casilla id",
)

_PRORRATA_VOLUMEN_CON_DERECHO_CASILLA = validated_casilla_id(
    "iva.prorrata-volumen-con-derecho",
    surface="prorrata settlement volumen con derecho casilla id",
)

_PRORRATA_PORCENTAJE_CASILLA = validated_casilla_id(
    "iva.prorrata-porcentaje",
    surface="prorrata settlement definitive percentage casilla id",
)


def require_filing_instance_evidence_for_work_unit(
    *,
    work_unit: WorkUnit,
    revision: CalculationRevision,
) -> FilingInstanceEvidence | None:
    """Return persisted evidence only when it is valid for the selected work unit.

    Core types:
    :class:`~cadrumo.domain.modelos.calculation_revision.CalculationRevision`.
    """
    return validate_filing_instance_evidence_for_work_unit(
        work_unit=work_unit,
        evidence=revision.filing_instance_evidence,
        operation="verification or export",
    )


def validate_filing_instance_evidence_for_work_unit(
    *,
    work_unit: WorkUnit,
    evidence: FilingInstanceEvidence | None,
    operation: str,
) -> FilingInstanceEvidence | None:
    """Validate the closed Modelo 303 evidence branch at creation or replay."""
    if work_unit.modelo == Modelo("303").value:
        if evidence is None:
            raise M303FilingEvidenceError(
                precondition_failure=m303_filing_evidence_failure(
                    "missing",
                    {"modelo": str(work_unit.modelo), "evidence_present": False, "operation": operation},
                ),
            )
        if evidence.m303.period != work_unit.period:
            raise M303FilingEvidenceError(
                precondition_failure=m303_filing_evidence_failure(
                    "period_mismatch",
                    {
                        "work_unit_period": work_unit.period.registry_token,
                        "evidence_period": evidence.m303.period.registry_token,
                        "periods_match": False,
                    },
                ),
            )
        return evidence
    if evidence is not None:
        raise M303FilingEvidenceError(
            precondition_failure=m303_filing_evidence_failure(
                "unsupported_modelo",
                {"modelo": str(work_unit.modelo), "evidence_present": True},
            ),
        )
    return None


def _build_filed_participation_writes(
    *,
    filed_target: CalculationRevision,
    work_unit: WorkUnit,
    filing_record_id: str,
    participation_index_repository: TransactionParticipationIndexRepositoryProtocol,
) -> tuple[SecureObjectWrite, ...]:
    """Build the per-transaction participation writes for a filed revision.

    For each ``source_transaction_id`` of the filed revision, load that
    transaction's
    :class:`~TransactionRevisionParticipationIndex`, upsert
    the ``PRESENTADO`` participation carrying the ``filing_record_id``
    (replacing the prior verified entry for the same revision in place), and
    return the resulting ``SecureObjectWrite`` so the caller co-emits them in
    the same atomic unit of work as the filing save.
    """
    writes: list[SecureObjectWrite] = []
    for transaction_id in filed_target.source_transaction_ids:
        index = participation_index_repository.load(transaction_id)
        participation = TransactionRevisionParticipation(
            calculation_revision_id=filed_target.calculation_revision_id,
            work_unit_id=work_unit.work_unit_id,
            modelo=work_unit.modelo,
            filing_year=work_unit.filing_year,
            period=work_unit.period,
            revision_state=CalculationRevisionState.PRESENTADO.value,
            filing_record_id=filing_record_id,
        )
        updated = upsert_transaction_participation(index, participation)
        writes.append(participation_index_repository.to_secure_object_write(updated))
    return tuple(writes)


def _build_prorrata_settlement_write(
    *,
    filed_target: CalculationRevision,
    work_unit: WorkUnit,
    prorrata_register_repository: ProrrataRegisterRepositoryProtocol,
    operation: PinnedAuthorityOperation,
) -> SecureObjectWrite | None:
    """Build the settlement prorrata-register write for an M303 year close."""
    values = _prorrata_settlement_values(filed_target=filed_target, work_unit=work_unit)
    if values is None:
        return None

    # Revisioned: the write this returns joins the caller's co-commit batch, so
    # it cannot self-commit, and an unguarded read would put the whole register
    # back over a sector entry another writer added in between.
    register, register_revision_id = prorrata_register_repository.load_revisioned()
    register = require_prorrata_register_coordinates_current(register, operation=operation)
    entry = _settled_prorrata_register_entry(
        work_unit=work_unit,
        register=register,
        volumen_total=values[0],
        volumen_con_derecho=values[1],
        definitive_percentage=values[2],
    )
    retained = tuple(
        existing
        for existing in register.entries
        if (existing.ejercicio, existing.sector_id) != (entry.ejercicio, entry.sector_id)
    )
    return prorrata_register_repository.to_secure_object_write(
        ProrrataRegister(
            entries=(*retained, entry),
            sector_definitions=register.sector_definitions,
            activity_rows=register.activity_rows,
        ),
        expected_revision_id=register_revision_id,
    )


def _prorrata_settlement_values(
    *,
    filed_target: CalculationRevision,
    work_unit: WorkUnit,
) -> tuple[Decimal, Decimal, Decimal] | None:
    if str(work_unit.modelo) != Modelo("303").value:
        return None
    if not is_m303_annual_settlement_period(work_unit.period):
        return None

    casilla_values = filed_target.casilla_values
    volumen_total = casilla_values.get(_PRORRATA_VOLUMEN_TOTAL_CASILLA)
    volumen_con_derecho = casilla_values.get(_PRORRATA_VOLUMEN_CON_DERECHO_CASILLA)
    definitive_percentage = casilla_values.get(_PRORRATA_PORCENTAJE_CASILLA)
    if volumen_total is None or volumen_con_derecho is None or definitive_percentage is None:
        return None
    return volumen_total, volumen_con_derecho, definitive_percentage


def _settled_prorrata_register_entry(
    *,
    work_unit: WorkUnit,
    register: ProrrataRegister,
    volumen_total: Decimal,
    volumen_con_derecho: Decimal,
    definitive_percentage: Decimal,
) -> ProrrataRegisterEntry:
    volumen_sin_derecho = volumen_total - volumen_con_derecho
    settlement_snapshot_ref = RegistrySnapshotRef(
        modelo=work_unit.modelo,
        revision_id=work_unit.revision_id,
        modelo_year=work_unit.filing_year,
        period=work_unit.period.registry_token,
    )
    settlement_fields = {
        "definitive_percentage": definitive_percentage,
        "definitive_volume_con_derecho": volumen_con_derecho,
        "definitive_volume_sin_derecho": volumen_sin_derecho,
    }
    existing = register.entry_for(work_unit.filing_year)
    if existing is not None:
        return ProrrataRegisterEntry.model_validate(
            {
                **existing.model_dump(),
                **settlement_fields,
                "source_registry_snapshot_refs": tuple(
                    dict.fromkeys((*existing.source_registry_snapshot_refs, settlement_snapshot_ref))
                ),
            }
        )

    regime = (
        general_prorrata_register_regime() if volumen_sin_derecho > Decimal("0") else ninguna_prorrata_register_regime()
    )
    return ProrrataRegisterEntry(
        ejercicio=work_unit.filing_year,
        regime=regime,
        especial_transition=None,
        definitive_percentage=definitive_percentage,
        definitive_volume_con_derecho=volumen_con_derecho,
        definitive_volume_sin_derecho=volumen_sin_derecho,
        source_registry_snapshot_refs=(settlement_snapshot_ref,),
    )


def _new_local_filing_record(
    *,
    filing_record_id: str,
    target: CalculationRevision,
    work_unit: WorkUnit,
    notes: str | None,
    actor: str,
    now: datetime,
    settlement: IvaSettlementSnapshot | None = None,
) -> ModeloRecord:
    return ModeloRecord(
        filing_record_id=filing_record_id,
        work_unit_id=target.work_unit_id,
        calculation_revision_id=target.calculation_revision_id,
        bucket_id=work_unit.bucket_id,
        modelo=work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=work_unit.period,
        filed_at=now,
        filed_by=actor.strip(),
        notes=notes.strip() if (notes is not None and notes) else None,
        origin=FilingOrigin.LOCAL,
        confirmation=AeatConfirmationState.PENDIENTE,
        declaration_kind=FilingDeclarationKind.ORIGINAL,
        status=ModeloRecordStatus.VIGENTE,
        source_transaction_ids=target.source_transaction_ids,
        settlement=settlement,
    )


def _require_m303_settlement_result_values(
    target: CalculationRevision, work_unit: WorkUnit, result_ids: tuple[CasillaId, ...] | None
) -> dict[CasillaId, Decimal]:
    """Require the declared result casillas after admitting the credit-state operands."""
    if result_ids is None or any(casilla_id not in target.casilla_values for casilla_id in result_ids):
        raise M303FilingEvidenceError(
            precondition_failure=m303_filing_evidence_failure(
                "missing", {"modelo": str(work_unit.modelo), "operation": "settlement_snapshot"}
            )
        )
    return {casilla_id: target.casilla_values[casilla_id] for casilla_id in result_ids}


def _new_local_m303_settlement_snapshot(
    *,
    target: CalculationRevision,
    work_unit: WorkUnit,
    prepared_observation: PreparedFiledRevisionObservation,
    result_disposition: ResultDisposition | None,
) -> IvaSettlementSnapshot | None:
    """Derive a new local M303 settlement snapshot from filing-time owners only."""
    if work_unit.modelo != Modelo("303").value:
        return None
    state = prepared_observation.iva_compensation_state
    result_ids = result_disposition_casilla_ids(str(work_unit.modelo))
    if state is None or state.prior_pending_amount is None or state.applied_amount is None:
        raise M303FilingEvidenceError(
            precondition_failure=m303_filing_evidence_failure(
                "missing",
                {"modelo": str(work_unit.modelo), "operation": "settlement_snapshot"},
            ),
        )
    result_values = _require_m303_settlement_result_values(target, work_unit, result_ids)
    result_amount = canonical_result_amount(str(work_unit.modelo), result_values)
    if result_amount is None or result_disposition is None:
        raise M303FilingEvidenceError(
            precondition_failure=m303_filing_evidence_failure(
                "missing",
                {"modelo": str(work_unit.modelo), "operation": "settlement_snapshot"},
            ),
        )
    return IvaSettlementSnapshot(
        calculation_revision_id=target.calculation_revision_id,
        declared_liability=max(result_amount, Decimal("0")),
        payment_evidence=(),
        refund_election_intent=result_disposition_is_refund(result_disposition),
        refund_state=IvaSettlementRefundState.NOT_REQUESTED,
        refund_requested_amount=Decimal("0"),
        refund_approved_amount=Decimal("0"),
        refund_paid_amount=Decimal("0"),
        credit_snapshot=IvaCreditSnapshot(
            opening_amount=state.prior_pending_amount,
            generated_amount=state.generated_amount,
            applied_amount=state.applied_amount,
            remaining_amount=state.available_end_amount,
        ),
    )


def _filed_calculation_revision(
    *,
    target: CalculationRevision,
    actor: str,
    now: datetime,
) -> CalculationRevision:
    return target.model_copy(
        update={
            "state": CalculationRevisionState.PRESENTADO,
            "filed_at": now,
            "filed_by": actor.strip(),
            "updated_at": now,
        },
    )


def supersede_prior_current_filing(
    prior_current: ModeloRecord,
    *,
    filing_catalogue: ModeloRecordCatalogue,
    revisions: CalculationRevisionCatalogue,
    new_filing_id: str,
    now: datetime,
) -> tuple[ModeloRecordCatalogue, CalculationRevisionCatalogue]:
    """Supersede the prior current filing record and its PRESENTADO revision.

    Marks ``prior_current`` SUPERSEDIDO (stamped with ``new_filing_id``) and, when
    its calculation revision is still PRESENTADO, advances that revision to
    PRESENTADO_SUPERSEDIDO. A prior entry AEAT never confirmed was never
    presented, so it is also marked DESCARTADA. Returns the updated
    ``(filing_catalogue, revisions)``.

    Takes ``prior_current`` as a :class:`ModeloRecord`.
    """
    update: dict[str, object] = {
        "status": ModeloRecordStatus.SUPERSEDIDO,
        "superseded_at": now,
        "superseded_by_filing_record_id": new_filing_id,
    }
    if prior_current.confirmation is AeatConfirmationState.PENDIENTE:
        update["confirmation"] = AeatConfirmationState.DESCARTADA
    superseded_prior = prior_current.model_copy(update=update)
    updated_filing_catalogue = upsert_filing_record(filing_catalogue, superseded_prior)
    prior_revision = revisions.get(prior_current.calculation_revision_id)
    if prior_revision is not None and prior_revision.state is CalculationRevisionState.PRESENTADO:
        superseded_revision = prior_revision.model_copy(
            update={
                "state": CalculationRevisionState.PRESENTADO_SUPERSEDIDO,
                "superseded_at": now,
                "updated_at": now,
            },
        )
        revisions = upsert_calculation_revision(revisions, superseded_revision)
    return updated_filing_catalogue, revisions


def prior_domiciliation_payload(
    election: PriorDomiciliationElectionProjection | None,
) -> dict[str, str]:
    """Project the prior-domiciliation election onto its ``MODELO_FILED`` payload keys.

    Every key is emitted in both branches, in one order, so the event payload
    shape never depends on whether an election was resolved. An absent
    election and an election with an absent baseline field are both recorded
    as the empty-string absence marker the payload contract already used.
    """
    if election is None:
        return {
            "prior_domiciliation_election": "",
            "prior_domiciliation_baseline_filing_record_id": "",
            "prior_domiciliation_baseline_evidence_reference_id": "",
            "prior_domiciliation_baseline_result_disposition": "",
            "prior_domiciliation_baseline_source_header_locator": "",
        }
    baseline_disposition = election.baseline_result_disposition
    return {
        "prior_domiciliation_election": election.election.value,
        "prior_domiciliation_baseline_filing_record_id": election.baseline_filing_record_id or "",
        "prior_domiciliation_baseline_evidence_reference_id": election.baseline_evidence_reference_id or "",
        "prior_domiciliation_baseline_result_disposition": (
            baseline_disposition.value if baseline_disposition is not None else ""
        ),
        "prior_domiciliation_baseline_source_header_locator": election.baseline_source_header_locator or "",
    }


def _refresh_filing_retention_snapshot(
    *,
    bucket_id: str,
    catalogue: ModeloRecordCatalogue,
    observed_at: datetime,
) -> None:
    """Record the filing facts a later deletion preflight will assess.

    Runs AFTER the catalogue has durably saved, and delegates the write to the
    filing package's best-effort recorder, which never raises. The ordering and
    the never-raising are the same decision from two sides: a filing that
    succeeded with a stale snapshot is recoverable, while a filing refused
    because a deletion-support record could not be written is not.

    This is the moment the retention position changes and the only moment a
    session for the bucket is held by construction, which is why the producer
    lives here rather than at the deletion preflight that consumes it.
    """
    try_record_filing_retention_snapshot(
        bucket_id=bucket_id,
        records=tuple(catalogue.records.values()),
        observed_at=observed_at,
    )


def _rectificativa_aggregate_context(
    revision: CalculationRevision,
    *,
    work_unit: WorkUnit,
    work_units: WorkUnitCatalogue,
    filing_catalogue: ModeloRecordCatalogue,
    justificante_repository: JustificanteRepositoryProtocol | None,
    taxpayer_nif: str | None,
    operation: PinnedAuthorityOperation,
) -> CalculationRevisionAggregateContext | None:
    """Join the evidence a rectificativa revalidates against, or ``None`` for any other revision."""
    identity = revision.amendment_identity
    if identity is None or identity.kind is not CalculationRevisionAmendmentKind.RECTIFICATIVA:
        return None
    if justificante_repository is None:
        raise ValueError("filing a rectificativa requires the justificante repository its evidence resolves against")
    return CalculationRevisionAggregateContext(
        work_units=work_units,
        filing_records=filing_catalogue,
        justificantes=tuple(justificante_repository.iter_justificantes()),
        registry_snapshots={
            work_unit.work_unit_id: operation.snapshot(
                Modelo("303").value,
                filing_year=work_unit.filing_year,
                period=work_unit.period.registry_token,
            )
        }
        if work_unit.modelo == Modelo("303").value
        else {},
        expected_taxpayer_tax_id=taxpayer_nif,
    )


def _approved_verification_report_differs(
    report: VerificationReport, granting_reports: tuple[VerificationReport, ...], target: CalculationRevision
) -> bool:
    """Bind the exact granting report to revision, authority and stored verification facts."""
    return (
        report.calculation_revision_id != target.calculation_revision_id
        or report.registry_snapshot_ref != target.registry_snapshot_ref
        or not report.granted_verificado_completo
        or len(granting_reports) != 1
        or granting_reports[0] != report
        or report.run_at != target.verified_at
        or report.verified_by != target.verified_by
    )


def require_approved_verification_report(
    *,
    target: CalculationRevision,
    approved_verification_report_id: VerificationReportId,
    catalogue: VerificationReportCatalogue,
    operation: PinnedAuthorityOperation,
) -> VerificationReport:
    """Bind a filing to the current granting report for its :class:`CalculationRevision`."""
    report = catalogue.get(approved_verification_report_id)
    granting_reports = tuple(
        candidate
        for candidate in catalogue.reports.values()
        if candidate.calculation_revision_id == target.calculation_revision_id and candidate.granted_verificado_completo
    )
    if report is None or _approved_verification_report_differs(report, granting_reports, target):
        raise VerificationReportNotFoundError(
            translated_message="application.modelo.errors.verification_report_not_found",
            context={
                "calculation_revision_id": target.calculation_revision_id,
                "verification_report_id": approved_verification_report_id,
            },
        )
    require_verification_report_coordinates_current(catalogue, operation=operation)
    return report


def _build_filing_events(
    *,
    work_unit: WorkUnit,
    prior_current: ModeloRecord | None,
    new_filing_id: str,
    calculation_revision_id: str,
    target: CalculationRevision,
    actor: str,
    now: datetime,
    prior_domiciliation_election: PriorDomiciliationElectionProjection | None,
) -> tuple[BucketEvent, ...]:
    filed_events: list[BucketEvent] = []
    if prior_current is not None:
        filed_events.append(
            build_modelo_bucket_event(
                bucket_id=work_unit.bucket_id,
                event_type=BucketEventType.MODELO_FILED_SUPERSEDED,
                occurred_at=now,
                actor=actor,
                object_type=BucketEventObjectType.FILING_RECORD,
                object_id=prior_current.filing_record_id,
                payload={
                    "superseded_by_filing_record_id": new_filing_id,
                    "calculation_revision_id": prior_current.calculation_revision_id,
                    "modelo": work_unit.modelo,
                    "filing_year": str(work_unit.filing_year),
                    "period": work_unit.period.registry_token,
                },
            ),
        )
    filed_events.append(
        build_modelo_bucket_event(
            bucket_id=work_unit.bucket_id,
            event_type=BucketEventType.MODELO_FILED,
            occurred_at=now,
            actor=actor,
            object_type=BucketEventObjectType.FILING_RECORD,
            object_id=new_filing_id,
            payload={
                "calculation_revision_id": calculation_revision_id,
                "work_unit_id": target.work_unit_id,
                "modelo": work_unit.modelo,
                "filing_year": str(work_unit.filing_year),
                "period": work_unit.period.registry_token,
                "supersedes_filing_record_id": prior_current.filing_record_id if prior_current is not None else "",
                **prior_domiciliation_payload(prior_domiciliation_election),
            },
        ),
    )

    return tuple(filed_events)


def _load_filing_baselines(
    *,
    target: CalculationRevision,
    work_unit: WorkUnit,
    work_units: WorkUnitCatalogue,
    approved_verification_report_id: VerificationReportId,
    filing_baseline_revision_id: str,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol,
    verification_repository: VerificationReportCatalogueRepositoryProtocol,
    filing_repository: ModeloRecordCatalogueRepositoryProtocol,
    operation: PinnedAuthorityOperation,
) -> tuple[
    CalculationRevisionCatalogue,
    str,
    WorkUnitCatalogue,
    str,
    VerificationReportCatalogue,
    str,
    ModeloRecordCatalogue,
    str,
]:
    calculation_revision_id = target.calculation_revision_id
    revisions, revisions_revision_id = calculation_repository.load_revisioned(operation=operation)
    if revisions.get(calculation_revision_id) != target:
        raise CalculationRevisionStateError(
            translated_message="errors.error.error_modelo_calculation_revision_state",
            context={"calculation_revision_id": calculation_revision_id, "reason": "filing_baseline_stale"},
        )
    current_work_units, work_units_revision_id = work_unit_repository.load_revisioned()
    if current_work_units != work_units or current_work_units.get(work_unit.work_unit_id) != work_unit:
        raise WorkUnitMutationRefusedError(
            translated_message="application.modelo.errors.work_unit_mutation_refused",
            context={"work_unit_id": work_unit.work_unit_id, "reason": "filing_baseline_stale"},
        )
    reports, reports_revision_id = verification_repository.load_revisioned(operation=operation)
    require_approved_verification_report(
        target=target,
        approved_verification_report_id=approved_verification_report_id,
        catalogue=reports,
        operation=operation,
    )
    filing_catalogue, filing_revision_id = filing_repository.load_revisioned()
    if filing_revision_id != filing_baseline_revision_id:
        raise CalculationRevisionStateError(
            translated_message="errors.error.error_modelo_calculation_revision_state",
            context={"calculation_revision_id": calculation_revision_id, "reason": "filing_baseline_stale"},
        )
    return (
        revisions,
        revisions_revision_id,
        current_work_units,
        work_units_revision_id,
        reports,
        reports_revision_id,
        filing_catalogue,
        filing_revision_id,
    )


def _prepare_filing_catalogues_and_writes(
    *,
    target: CalculationRevision,
    work_unit: WorkUnit,
    current_work_units: WorkUnitCatalogue,
    filing_catalogue: ModeloRecordCatalogue,
    revisions: CalculationRevisionCatalogue,
    new_filing_id: str,
    notes: str | None,
    actor: str,
    now: datetime,
    settlement: IvaSettlementSnapshot | None,
    justificante_repository: JustificanteRepositoryProtocol | None,
    taxpayer_nif: str | None,
    operation: PinnedAuthorityOperation,
    participation_index_repository: TransactionParticipationIndexRepositoryProtocol,
    prorrata_register_repository: ProrrataRegisterRepositoryProtocol,
) -> tuple[
    ModeloRecord | None,
    ModeloRecord,
    ModeloRecordCatalogue,
    CalculationRevisionCatalogue,
    tuple[SecureObjectWrite, ...],
    SecureObjectWrite | None,
    WorkUnitCatalogue,
]:
    calculation_revision_id = target.calculation_revision_id
    prior_current = filing_catalogue.current_for(
        bucket_id=work_unit.bucket_id,
        modelo=work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=work_unit.period,
    )

    new_filing = _new_local_filing_record(
        filing_record_id=new_filing_id,
        target=target,
        work_unit=work_unit,
        notes=notes,
        actor=actor,
        now=now,
        settlement=settlement,
    )

    # Revisioned: this catalogue is composed into a co-commit, so it cannot
    # use a self-committing mutation, and an unguarded read would write the
    # whole singleton row back over a revision another calculate run added.
    updated_filing_catalogue = filing_catalogue
    if prior_current is not None:
        updated_filing_catalogue, revisions = supersede_prior_current_filing(
            prior_current,
            filing_catalogue=updated_filing_catalogue,
            revisions=revisions,
            new_filing_id=new_filing_id,
            now=now,
        )

    updated_filing_catalogue = upsert_filing_record(updated_filing_catalogue, new_filing)
    filed_target = _filed_calculation_revision(target=target, actor=actor, now=now)
    revisions = upsert_calculation_revision(
        revisions,
        filed_target,
        aggregate_context=_rectificativa_aggregate_context(
            filed_target,
            work_unit=work_unit,
            work_units=current_work_units,
            filing_catalogue=updated_filing_catalogue,
            justificante_repository=justificante_repository,
            taxpayer_nif=taxpayer_nif,
            operation=operation,
        ),
    )

    participation_writes = _build_filed_participation_writes(
        filed_target=filed_target,
        work_unit=work_unit,
        filing_record_id=new_filing_id,
        participation_index_repository=participation_index_repository,
    )
    prorrata_write = _build_prorrata_settlement_write(
        filed_target=filed_target,
        work_unit=work_unit,
        prorrata_register_repository=prorrata_register_repository,
        operation=operation,
    )
    advanced_work_units = upsert_work_unit(
        current_work_units,
        work_unit.model_copy(
            update={
                "filed_calculation_revision_id": calculation_revision_id,
                "current_filing_record_id": new_filing_id,
                "updated_at": now,
            },
        ),
    )

    return (
        prior_current,
        new_filing,
        updated_filing_catalogue,
        revisions,
        participation_writes,
        prorrata_write,
        advanced_work_units,
    )


def persist_filed_revision(
    *,
    target: CalculationRevision,
    approved_verification_report_id: VerificationReportId,
    filing_baseline_revision_id: str,
    work_unit: WorkUnit,
    work_units: WorkUnitCatalogue,
    notes: str | None,
    actor: str,
    now: datetime,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol,
    filing_repository: ModeloRecordCatalogueRepositoryProtocol,
    verification_repository: VerificationReportCatalogueRepositoryProtocol,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol,
    calculation_observation_repository: CalculationObservationRepositoryProtocol,
    iva_compensation_history_repository: IvaCompensationHistoryRepositoryProtocol,
    participation_index_repository: TransactionParticipationIndexRepositoryProtocol,
    prorrata_register_repository: ProrrataRegisterRepositoryProtocol,
    operation: PinnedAuthorityOperation,
    result_disposition: ResultDisposition | None = None,
    prior_domiciliation_election: PriorDomiciliationElectionProjection | None = None,
    taxpayer_nif: str | None = None,
    justificante_repository: JustificanteRepositoryProtocol | None = None,
) -> ModeloRecord:
    """Persist a verified revision and its local filing in one guarded transition.

    Takes ``target`` as a :class:`CalculationRevision`.
    """
    # Refuse missing disposition before any write in the transition.
    require_filing_result_disposition(work_unit=work_unit, result_disposition=result_disposition)
    calculation_revision_id = target.calculation_revision_id
    (
        revisions,
        revisions_revision_id,
        current_work_units,
        work_units_revision_id,
        reports,
        reports_revision_id,
        filing_catalogue,
        filing_revision_id,
    ) = _load_filing_baselines(
        target=target,
        work_unit=work_unit,
        work_units=work_units,
        approved_verification_report_id=approved_verification_report_id,
        filing_baseline_revision_id=filing_baseline_revision_id,
        calculation_repository=calculation_repository,
        work_unit_repository=work_unit_repository,
        verification_repository=verification_repository,
        filing_repository=filing_repository,
        operation=operation,
    )
    new_filing_id = derive_filing_record_id(
        work_unit_id=target.work_unit_id,
        calculation_revision_id=calculation_revision_id,
        filed_by=actor.strip(),
    )
    # Validate carry and evidence displacement before the co-commit.
    prepared_observation = prepare_filed_revision_observation(
        revision=target,
        work_unit=work_unit,
        repository=calculation_observation_repository,
        iva_compensation_history_repository=iva_compensation_history_repository,
        captured_at=now,
        result_disposition=result_disposition,
        prior_domiciliation_election=prior_domiciliation_election,
        taxpayer_nif=taxpayer_nif,
        filing_record_id=new_filing_id,
    )
    settlement = _new_local_m303_settlement_snapshot(
        target=target,
        work_unit=work_unit,
        prepared_observation=prepared_observation,
        result_disposition=result_disposition,
    )

    (
        prior_current,
        new_filing,
        updated_filing_catalogue,
        revisions,
        participation_writes,
        prorrata_write,
        advanced_work_units,
    ) = _prepare_filing_catalogues_and_writes(
        target=target,
        work_unit=work_unit,
        current_work_units=current_work_units,
        filing_catalogue=filing_catalogue,
        revisions=revisions,
        new_filing_id=new_filing_id,
        notes=notes,
        actor=actor,
        now=now,
        settlement=settlement,
        justificante_repository=justificante_repository,
        taxpayer_nif=taxpayer_nif,
        operation=operation,
        participation_index_repository=participation_index_repository,
        prorrata_register_repository=prorrata_register_repository,
    )

    filed_events = _build_filing_events(
        work_unit=work_unit,
        prior_current=prior_current,
        new_filing_id=new_filing_id,
        calculation_revision_id=calculation_revision_id,
        target=target,
        actor=actor,
        now=now,
        prior_domiciliation_election=prior_domiciliation_election,
    )

    extra_writes = (
        calculation_repository.to_secure_object_write(revisions, expected_revision_id=revisions_revision_id),
        verification_repository.to_secure_object_write(
            reports, expected_revision_id=reports_revision_id, operation=operation
        ),
        *participation_writes,
    )
    if prorrata_write is not None:
        extra_writes = (*extra_writes, prorrata_write)
    extra_writes = (
        *extra_writes,
        work_unit_repository.to_secure_object_write(advanced_work_units, expected_revision_id=work_units_revision_id),
        bucket_event_history_write(bucket_event_repository, filed_events),
        *filed_revision_observation_writes(
            prepared_observation,
            repository=calculation_observation_repository,
            taxpayer_nif=taxpayer_nif,
            filing_record_id=new_filing_id,
        ),
    )

    # Co-commit filing, revision, participation, prorrata, pointer, events and observations.
    filing_repository.save_with_secure_object_writes(
        updated_filing_catalogue,
        extra_writes,
        expected_revision_id=filing_revision_id,
    )

    _refresh_filing_retention_snapshot(
        bucket_id=work_unit.bucket_id,
        catalogue=updated_filing_catalogue,
        observed_at=now,
    )

    return new_filing
