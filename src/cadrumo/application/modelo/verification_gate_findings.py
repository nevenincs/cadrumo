"""Compose pinned verification gates and evidence advisories before publication.

Evaluate a :class:`CalculationRevision` against its :class:`TaxpayerProfile`
and retain evidence references from :class:`CasillaObservation` values.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from cadrumo.application.calculations.observations_repository import (
    CalculationObservationRepositoryProtocol,
    IvaWalletDecisionRepositoryProtocol,
)

from ...core.casilla_id import CasillaId
from ...core.operator_action_enums import ActionEvidenceProvenance
from ...domain.calculations.registry.applicability import derive_taxpayer_files_economic_activity
from ...domain.calculations.registry.applicability_modelo202 import derive_modelo_202_modality
from ...domain.calculations.registry.bindings import CasillaObservation
from ...domain.calculations.registry.casilla_membership import (
    casillas_by_id,
)
from ...domain.calculations.registry.iva_compensation_annual_partition_bindings import (
    M303_COMPENSATION_PENDING_PRIOR_CASILLA as M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA,
)
from ...domain.deadlines.models import TaxpayerProfile
from ...domain.iva.components import registry_category_projection
from ...domain.justificante.protocols import JustificanteRepositoryProtocol
from ...domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionCatalogue,
)
from ...domain.modelos.errors import ModeloValidationError
from ...domain.modelos.protocols import (
    CalculationRevisionCatalogueRepositoryProtocol,
    ModeloRecordCatalogueRepositoryProtocol,
    VerificationReportCatalogueRepositoryProtocol,
)
from ...domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from ...domain.modelos.work_unit import WorkUnit
from ...domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
from ..aggregation.evidence_advisory import (
    MISSING_DEDUCTIBLE_IVA_EVIDENCE_SOURCE_KIND,
    missing_evidence_advisory_observations,
)
from ..aggregation.ledger_membership import LedgerMembershipPorts, query_ledger_membership
from ..aggregation.source_mesh import (
    CalculationSourceDiagnostic,
)
from ..calculations.cross_period_models import CrossPeriodDependencyEvidence, CrossPeriodExpectedMemberSet
from ..calculations.iva_compensation_history_ports import IvaCompensationHistoryRepositoryProtocol
from ._ledger_drift_gate import ledger_drift_findings
from .iva_wallet_gate import ModeloIvaWalletReconciliationBlocked
from .iva_wallet_gate import (
    require_persisted_iva_compensation_decision_matches_revision as _require_iva_compensation_revision_match,
)
from .preconditions import ModeloPreconditionFailure
from .verification_cross_period import (
    cross_period_clean_state_findings,
    cross_period_clean_state_verdict_for_work_unit,
    cross_period_expected_member_sets_from_profile,
    registry_modality_finding,
    zero_value_previous_filing_binding_ids,
)
from .verification_finding_contracts import (
    ABSENT_FACT,
    CUOTA_LESS_WITHOUT_BASE_LEGAL_REFS,
    MISSING_EVIDENCE_LEGAL_REFS,
    REGISTRY_SNAPSHOT_REFUSAL_SCENARIOS,
)
from .verification_preconditions import (
    build_verification_precondition_failure,
)
from .verification_revision_findings import collect_revision_verification_findings

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from ...domain.invoices.protocols import InvoiceCatalogueRepositoryProtocol
    from .work_profile import ModeloWorkProfile


def optional_observation_refs(observations: Iterable[CasillaObservation | None], field_name: str) -> tuple[str, ...]:
    """Preserve each :class:`CasillaObservation` reference's first occurrence."""
    refs = tuple(
        dict.fromkeys(
            str(ref).strip()
            for observation in observations
            if observation is not None
            for ref in getattr(observation, field_name)
            if str(ref).strip()
        ),
    )
    return refs


def cuota_less_without_base_findings(
    *,
    target: CalculationRevision,
    work_unit: WorkUnit,
    transaction_repository: TransactionCatalogueRepositoryProtocol,
    blocking_finding_observer: Callable[[ModeloVerificationFinding, str, str], None] | None = None,
) -> list[ModeloVerificationFinding]:
    """Refuse a row whose declared category can only ever contribute a base it lacks.

    Inspect the source transactions consumed by the target :class:`CalculationRevision`.

    A cuota-less category -- exempt, zero-rated, not-subject, intra-community
    supply, export -- carries no cuota BY LAW. The base is therefore the row's
    only possible contribution to the return, and a row declaring such a
    category with no taxable base contributes nothing at all while looking, in
    the ledger, like a declared operation.

    This is the one shape in the missing-substrate family where the direction of
    error is certain. Elsewhere a missing base is ambiguous: a cuota-bearing row
    still contributes through its quota, and a renta row falls back to its bank
    cash, so refusing would block filings that are merely imprecise. Here there
    is no second measure to fall back to and no offsetting effect -- the base
    casilla is understated by exactly the operation's amount, every time.

    BLOCKING for the reason the evidence gate above states: an advisory at
    verify grants and freezes a gap-carrying bundle, and the later export and
    filing refusals then arrive after the operator has been told the draft is
    fine. A non-granting verify leaves the revision BORRADOR, so the base can be
    entered and the draft re-verified through the normal calculation lifecycle.

    Scoped to rows the revision actually consumed: a cuota-less row outside
    ``source_transaction_ids`` reached no casilla and is not this gate's business.
    """
    if not target.source_transaction_ids:
        return []
    catalogue = transaction_repository.load()
    registry_source_refs = optional_observation_refs(target.observations, "source_refs")

    cuota_less_categories = registry_category_projection("cuota_less_m303")
    findings: list[ModeloVerificationFinding] = []
    for transaction_id in sorted(target.source_transaction_ids):
        transaction = catalogue.get(transaction_id)
        if transaction is None:
            continue
        category = transaction.iva_category
        if category is None or category not in cuota_less_categories:
            continue
        if transaction.taxable_base is not None:
            continue
        finding = ModeloVerificationFinding(
            kind=ModeloVerificationFindingKind.BLOCKING_RULE,
            severity=ModeloVerificationFindingSeverity.BLOCKING,
            message_locale_key="application.modelo.findings.cuota_less_ledger_row_base_missing",
            message_facts={
                "transaction_id": transaction_id,
                "iva_category_code": category.value,
            },
            legal_refs=CUOTA_LESS_WITHOUT_BASE_LEGAL_REFS,
            source_refs=registry_source_refs,
        )
        findings.append(finding)
        if blocking_finding_observer is not None:
            blocking_finding_observer(finding, transaction_id, category.value)
    return findings


def missing_evidence_findings(
    *,
    target: CalculationRevision,
    work_unit: WorkUnit,
    transaction_repository: TransactionCatalogueRepositoryProtocol,
    blocking_finding_observer: Callable[[ModeloVerificationFinding, CalculationSourceDiagnostic], None] | None = None,
) -> list[ModeloVerificationFinding]:
    """Build verification findings for evidence-less positive IVA rows.

    Loads the :class:`CalculationRevision` source transactions for the supplied
    :class:`WorkUnit` and
    projects each
    :class:`~cadrumo.application.aggregation.source_mesh.CalculationSourceDiagnostic`
    (reason ``missing_transaction_evidence``) into a
    :class:`ModeloVerificationFinding`. A deductible input-IVA gap BLOCKS the
    verified-complete transition; an output-IVA gap stays advisory. A revision
    with no contributing transactions, or whose significant rows all carry
    evidence, yields no findings.

    The split is deliberate and legally grounded rather than a severity
    preference. Deducting input IVA requires the original factura, so a
    deductible row without one is not a filing the operator may complete. Output
    IVA has no equivalent constitutive requirement and no CLI path that mints
    issued-invoice evidence, so blocking it would refuse a taxpayer who has no
    way to comply.

    Blocking here is what keeps the export and local-filing refusals on the same
    condition unreachable rather than merely later: they remain in place as
    defence in depth over a state this gate no longer lets form.
    """
    if not target.source_transaction_ids:
        return []
    catalogue = transaction_repository.load()
    transactions = [
        transaction
        for transaction_id in target.source_transaction_ids
        if (transaction := catalogue.get(transaction_id)) is not None
    ]
    diagnostics: tuple[CalculationSourceDiagnostic, ...] = missing_evidence_advisory_observations(transactions)
    findings: list[ModeloVerificationFinding] = []
    registry_source_refs = optional_observation_refs(target.observations, "source_refs")
    for diagnostic in diagnostics:
        is_deductible_gap = diagnostic.source_kind == MISSING_DEDUCTIBLE_IVA_EVIDENCE_SOURCE_KIND
        message_facts: dict[str, str | int | bool | Decimal] = {
            "diagnostic_reason_code": str(diagnostic.reason),
            "source_kind_code": diagnostic.source_kind,
            # Supplied on every diagnostic, not only the bound ones. The message
            # names the binding, and a fact supplied conditionally renders as a
            # literal placeholder rather than raising, so a diagnostic with no
            # binding would print "%{binding_id}" to the operator. The marker
            # also says which case this is: "there is no binding" reads
            # differently from a binding whose id is blank.
            "binding_id": str(diagnostic.binding_id) if diagnostic.binding_id is not None else ABSENT_FACT,
        }
        if diagnostic.source_ref is not None:
            message_facts["source_ref"] = diagnostic.source_ref
        if is_deductible_gap:
            finding = ModeloVerificationFinding(
                kind=ModeloVerificationFindingKind.BLOCKING_RULE,
                severity=ModeloVerificationFindingSeverity.BLOCKING,
                message_locale_key="application.modelo.findings.transaction_evidence_missing_deductible",
                message_facts=message_facts,
                legal_refs=MISSING_EVIDENCE_LEGAL_REFS,
                source_refs=registry_source_refs,
            )
            findings.append(finding)
            if blocking_finding_observer is not None:
                blocking_finding_observer(finding, diagnostic)
            continue
        findings.append(
            ModeloVerificationFinding(
                kind=ModeloVerificationFindingKind.ADVISORY,
                severity=ModeloVerificationFindingSeverity.WARNING,
                message_locale_key="application.modelo.findings.transaction_evidence_missing_output",
                message_facts=message_facts,
                legal_refs=MISSING_EVIDENCE_LEGAL_REFS,
                source_refs=registry_source_refs,
            ),
        )
    return findings


def collect_verification_gate_findings(
    *,
    work_unit: WorkUnit,
    target: CalculationRevision,
    workflow_profile: TaxpayerProfile,
    observation_repository: CalculationObservationRepositoryProtocol,
    filing_repository: ModeloRecordCatalogueRepositoryProtocol,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol,
    verification_repository: VerificationReportCatalogueRepositoryProtocol,
    justificante_repository: JustificanteRepositoryProtocol,
    transaction_repository: TransactionCatalogueRepositoryProtocol,
    invoice_repository: InvoiceCatalogueRepositoryProtocol,
    iva_compensation_history_repository: IvaCompensationHistoryRepositoryProtocol,
    iva_compensation_decision_repository: IvaWalletDecisionRepositoryProtocol,
    cross_period_expected_member_sets: Iterable[CrossPeriodExpectedMemberSet],
    operation: PinnedAuthorityOperation,
    work_profile: ModeloWorkProfile,
    ledger_membership_ports: LedgerMembershipPorts,
    evaluated_at: datetime | None = None,
    calculation_catalogue: CalculationRevisionCatalogue | None = None,
) -> tuple[
    list[ModeloVerificationFinding],
    list[CasillaId],
    list[CasillaId],
    dict[int, ModeloPreconditionFailure],
]:
    """Compose :class:`CalculationRevision` findings against a :class:`TaxpayerProfile`.

    Pin registry, ledger, and cross-period evidence before publication.
    """
    findings, resolved_casilla_ids, missing_required_casilla_ids, failures_by_finding_id = (
        collect_revision_verification_findings(
            work_unit=work_unit,
            target=target,
            profile=workflow_profile,
            transaction_repository=transaction_repository,
            invoice_repository=invoice_repository,
            operation=operation,
            work_profile=work_profile,
        )
    )
    incomplete_modality_finding = registry_modality_finding(
        work_unit=work_unit,
        profile=workflow_profile,
    )
    if incomplete_modality_finding is not None:
        findings.append(incomplete_modality_finding)
        failures_by_finding_id[id(incomplete_modality_finding)] = build_verification_precondition_failure(
            calculation_revision_id=target.calculation_revision_id,
            work_unit_id=target.work_unit_id,
            condition_id="modelo.work.verify.m202.modality.complete",
            scenario_id="modelo.work.verify.m202.modality.incomplete",
            evidence_id="modelo.work.verify.m202.modality",
            evidence_values={
                "modelo": str(work_unit.modelo),
                "year": work_unit.filing_year,
                "period": work_unit.period.registry_token,
                "profile_fact_id": "taxpayer_type.incn_prior_12_months",
                "modality_code": "incomplete",
            },
            provenance=ActionEvidenceProvenance.DOMAIN_EVALUATION,
        )
    iva_compensation_decision = None
    try:
        iva_compensation_decision = _require_iva_compensation_revision_match(
            work_unit,
            target,
            repository=iva_compensation_decision_repository,
            observation_repository=observation_repository,
            history_repository=iva_compensation_history_repository,
            operation=operation,
            subject_leaf_key="modelo.work.verify",
            evaluated_at=evaluated_at,
        )
    except ModeloIvaWalletReconciliationBlocked as exc:
        finding = iva_wallet_error_verification_finding(exc, work_unit=work_unit, operation=operation)
        findings.append(finding)
        failures_by_finding_id[id(finding)] = exc.precondition_failure
    clean_state_verdict = cross_period_clean_state_verdict_for_work_unit(
        work_unit,
        observation_repository=observation_repository,
        filing_repository=filing_repository,
        calculation_repository=calculation_repository,
        calculation_catalogue=calculation_catalogue,
        verification_repository=verification_repository,
        justificante_repository=justificante_repository,
        expected_member_sets=cross_period_expected_member_sets_from_profile(
            workflow_profile,
            cross_period_expected_member_sets,
        ),
        taxpayer_tax_id=workflow_profile.tax_id,
        activity_start_date=workflow_profile.activity_start_date,
        modelo_202_modality=derive_modelo_202_modality(
            workflow_profile,
            effective_date=date(work_unit.filing_year, 12, 31),
        ).modality,
        taxpayer_files_economic_activity=derive_taxpayer_files_economic_activity(workflow_profile),
        workflow_profile=workflow_profile,
        zero_value_previous_filing_binding_ids=zero_value_previous_filing_binding_ids(target),
        operation=operation,
    )

    def _observe_cross_period_finding(
        finding: ModeloVerificationFinding,
        evidence: CrossPeriodDependencyEvidence | None,
    ) -> None:
        if evidence is None:
            failures_by_finding_id[id(finding)] = build_verification_precondition_failure(
                calculation_revision_id=target.calculation_revision_id,
                work_unit_id=target.work_unit_id,
                condition_id="modelo.work.verify.activity_start_date.present",
                scenario_id="modelo.work.verify.activity_start_date.missing_for_first_filer_adjudication",
                evidence_id="modelo.work.verify.activity_start_date",
                evidence_values={
                    "modelo": str(work_unit.modelo),
                    "dependency_count": len(clean_state_verdict.dependencies) if clean_state_verdict is not None else 0,
                },
                provenance=ActionEvidenceProvenance.APPLICATION_STATE,
            )
            return
        requirement = evidence.requirement
        failures_by_finding_id[id(finding)] = build_verification_precondition_failure(
            calculation_revision_id=target.calculation_revision_id,
            work_unit_id=target.work_unit_id,
            condition_id="modelo.work.verify.cross_period_dependency.clean",
            scenario_id="modelo.work.verify.cross_period_dependency.unclean",
            evidence_id="modelo.work.verify.cross_period_dependency",
            evidence_values={
                "source_modelo": requirement.source_modelo,
                "year": requirement.filing_year,
                "period": requirement.period.registry_token,
                "origin_code": requirement.origin.value,
                "origin_ids": "|".join(requirement.origin_ids),
                "blocker_codes": "|".join(blocker.value for blocker in evidence.blockers),
            },
            provenance=ActionEvidenceProvenance.DOMAIN_EVALUATION,
        )

    findings.extend(
        cross_period_clean_state_findings(
            clean_state_verdict,
            iva_compensation_decision=iva_compensation_decision,
            activity_start_date=workflow_profile.activity_start_date,
            blocking_finding_observer=_observe_cross_period_finding,
        ),
    )
    evidence_findings = missing_evidence_findings(
        target=target,
        work_unit=work_unit,
        transaction_repository=transaction_repository,
        blocking_finding_observer=lambda finding, diagnostic: failures_by_finding_id.__setitem__(
            id(finding),
            build_verification_precondition_failure(
                calculation_revision_id=target.calculation_revision_id,
                work_unit_id=target.work_unit_id,
                condition_id="modelo.work.verify.deductible_iva_evidence.present",
                scenario_id="modelo.work.verify.deductible_iva_evidence.missing",
                evidence_id="modelo.work.verify.deductible_iva_evidence",
                evidence_values={
                    "diagnostic_reason_code": str(diagnostic.reason),
                    "source_kind_code": diagnostic.source_kind,
                    "transaction_id": str(diagnostic.binding_id or ""),
                    "binding_id": str(diagnostic.binding_id or ""),
                    "casilla_id": str(diagnostic.casilla_id or ""),
                    "source_ref": str(diagnostic.source_ref or ""),
                },
                provenance=ActionEvidenceProvenance.DOMAIN_EVALUATION,
            ),
        ),
    )
    findings.extend(evidence_findings)
    # Beside the evidence gate and for the same reason: both refuse a draft whose
    # rows cannot support what it declares, and both block at verify so the later
    # export and filing refusals are unreachable rather than merely later.
    cuota_less_findings = cuota_less_without_base_findings(
        target=target,
        work_unit=work_unit,
        transaction_repository=transaction_repository,
        blocking_finding_observer=lambda finding, transaction_id, category_code: failures_by_finding_id.__setitem__(
            id(finding),
            build_verification_precondition_failure(
                calculation_revision_id=target.calculation_revision_id,
                work_unit_id=target.work_unit_id,
                condition_id="modelo.work.verify.ledger_row.taxable_base_present",
                scenario_id="modelo.work.verify.ledger_row.cuota_less_base_missing",
                evidence_id="modelo.work.verify.ledger_row",
                evidence_values={
                    "transaction_id": transaction_id,
                    "iva_category_code": category_code,
                },
                provenance=ActionEvidenceProvenance.DOMAIN_EVALUATION,
            ),
        ),
    )
    findings.extend(cuota_less_findings)
    # Runs beside the evidence gate, not inside it: that gate reads the live
    # ledger while the casilla values come from the stored draft, and this is
    # what refuses the case where those two views have drifted apart.
    if any(failure.scenario_id in REGISTRY_SNAPSHOT_REFUSAL_SCENARIOS for failure in failures_by_finding_id.values()):
        return findings, resolved_casilla_ids, missing_required_casilla_ids, failures_by_finding_id
    current_membership = query_ledger_membership(
        target=target,
        work_unit=work_unit,
        revision=operation.revision(work_unit.modelo, work_unit.revision_id),
        profile=work_profile,
        ports=ledger_membership_ports,
        operation=operation,
    )
    drift_findings = ledger_drift_findings(
        target=target,
        work_unit=work_unit,
        transaction_repository=transaction_repository,
        current_membership=current_membership,
        source_refs=optional_observation_refs(target.observations, "source_refs"),
        blocking_finding_observer=lambda finding, anchored, changed_ids, removed_ids, added_ids: (
            failures_by_finding_id.__setitem__(
                id(finding),
                build_verification_precondition_failure(
                    calculation_revision_id=target.calculation_revision_id,
                    work_unit_id=target.work_unit_id,
                    condition_id="modelo.work.verify.ledger_snapshot.current",
                    scenario_id=(
                        "modelo.work.verify.ledger_snapshot.drift_detected"
                        if current_membership.available
                        else "modelo.work.verify.ledger_snapshot.membership_unavailable"
                    ),
                    evidence_id="modelo.work.verify.ledger_snapshot",
                    evidence_values={
                        "snapshot_anchored": anchored,
                        "changed_transaction_count": len(changed_ids),
                        "changed_transaction_ids": "|".join(changed_ids),
                        "removed_transaction_count": len(removed_ids),
                        "removed_transaction_ids": "|".join(removed_ids),
                        "added_transaction_count": len(added_ids),
                        "added_transaction_ids": "|".join(added_ids),
                        "membership_available": current_membership.available,
                    },
                    provenance=ActionEvidenceProvenance.PERSISTED_STATE,
                ),
            )
        ),
    )
    findings.extend(drift_findings)
    return findings, resolved_casilla_ids, missing_required_casilla_ids, failures_by_finding_id


def iva_wallet_error_verification_finding(
    error: ModeloIvaWalletReconciliationBlocked,
    *,
    work_unit: WorkUnit,
    operation: PinnedAuthorityOperation,
) -> ModeloVerificationFinding:
    # The block concerns the carried-compensation casilla, so its provenance is
    # that casilla's own registry grounding for the work unit's revision.
    """Project a retained wallet refusal into its grounded verification finding."""
    snapshot = operation.snapshot(
        work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=work_unit.period.registry_token,
    )
    casilla_def = casillas_by_id(snapshot.revision).get(M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA)
    if casilla_def is None or not casilla_def.legal_refs or not casilla_def.source_refs:
        raise ModeloValidationError(
            "IVA wallet finding requires the compensation casilla's legal_refs/source_refs provenance",
        )
    return ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.BLOCKING_RULE,
        severity=ModeloVerificationFindingSeverity.BLOCKING,
        casilla_id=M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA,
        message_locale_key="application.modelo.findings.iva_wallet_precondition_failed",
        message_facts={
            "condition_id": error.precondition_failure.verdict.failed_condition_id,
            "scenario_id": error.precondition_failure.scenario_id,
        },
        legal_refs=tuple(str(ref) for ref in casilla_def.legal_refs),
        source_refs=tuple(str(ref) for ref in casilla_def.source_refs),
    )
