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

from ...core.aggregation import BindingSourceKind
from ...core.casilla_id import CasillaId
from ...core.operator_action_enums import ActionEvidenceProvenance, NoRecoveryOutcome
from ...domain.calculations.registry.applicability import derive_taxpayer_files_economic_activity
from ...domain.calculations.registry.applicability_modelo202 import derive_modelo_202_modality
from ...domain.calculations.registry.binding_selector_utils import provider_member
from ...domain.calculations.registry.bindings import CasillaObservation
from ...domain.calculations.registry.casilla_membership import (
    casillas_by_id,
)
from ...domain.calculations.registry.iva_compensation_annual_partition_bindings import (
    M303_COMPENSATION_PENDING_PRIOR_CASILLA as M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA,
)
from ...domain.calculations.registry.ledger_iva_bindings import LedgerIvaProvider
from ...domain.deadlines.models import TaxpayerProfile
from ...domain.invoices.models import Invoice
from ...domain.iva.components import registry_category_projection
from ...domain.iva.flow import IvaFlowDirection, is_deducible_flow, is_devengada_flow
from ...domain.iva_compensation.reconciliation import IvaCompensationReconciliationDecision
from ...domain.justificante.protocols import JustificanteRepositoryProtocol
from ...domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionCatalogue,
)
from ...domain.modelos.errors import ModeloValidatedRecord, ModeloValidationError
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
from ...domain.transactions.dates import transaction_operation_date
from ...domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
from ..aggregation.evidence_advisory import (
    MISSING_DEDUCTIBLE_IVA_EVIDENCE_SOURCE_KIND,
    MISSING_OUTPUT_IVA_EVIDENCE_SOURCE_KIND,
    calculation_revision_claims_ledger_iva,
    missing_evidence_advisory_observations,
)
from ..aggregation.invoice_iva_source import (
    documented_invoice_ids,
    invoices_missing_source_document,
    issued_invoices_missing_source_document,
)
from ..aggregation.ledger_membership import LedgerMembershipPorts, query_ledger_membership
from ..aggregation.source_mesh import (
    CalculationSourceDiagnostic,
)
from ..calculations.cross_period_models import (
    CrossPeriodCleanStateVerdict,
    CrossPeriodDependencyEvidence,
    CrossPeriodExpectedMemberSet,
)
from ..calculations.iva_compensation_history_ports import IvaCompensationHistoryRepositoryProtocol
from .imputation_filings import imputation_filings_from_repositories
from .invoice_drift_gate import invoice_drift_findings
from .iva_wallet_gate import require_persisted_iva_compensation_decision_matches_revision
from .iva_wallet_refusal import ModeloIvaWalletReconciliationBlocked
from .ledger_drift_gate import ledger_drift_findings, undetermined_mixed_use_contributor_finding
from .preconditions import ModeloPreconditionFailure, build_modelo_precondition_failure_for_scenario
from .verification_cross_period import (
    CrossPeriodDoor,
    cross_period_clean_state_findings,
    cross_period_clean_state_verdict_for_work_unit,
    cross_period_door_operator_arguments,
    cross_period_door_reader,
    cross_period_expected_member_sets_from_profile,
    operator_value_attestations,
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
    from ...domain.attachments.protocols import AttachmentStoreProtocol
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from ...domain.calculations.registry.schema import ModeloRevision
    from ...domain.invoices.protocols import InvoiceCatalogueRepositoryProtocol
    from ...domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol
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

    findings: list[ModeloVerificationFinding] = []
    for transaction_id in sorted(target.source_transaction_ids):
        transaction = catalogue.get(transaction_id)
        if transaction is None:
            continue
        category = transaction.iva_category
        if category is None or category not in registry_category_projection(
            "cuota_less_m303",
            effective_date=transaction_operation_date(transaction),
        ):
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
    operation: PinnedAuthorityOperation,
    blocking_finding_observer: Callable[[ModeloVerificationFinding, CalculationSourceDiagnostic], None] | None = None,
) -> list[ModeloVerificationFinding]:
    """Build verification findings for IVA-bearing rows that lack their evidence.

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
    diagnostics: tuple[CalculationSourceDiagnostic, ...] = missing_evidence_advisory_observations(
        transactions,
        revision_claims_ledger_iva=calculation_revision_claims_ledger_iva(target, operation=operation),
    )
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
            "binding_id": diagnostic.binding_id if diagnostic.binding_id is not None else ABSENT_FACT,
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


def _append_cross_period_findings(
    clean_state_verdict: CrossPeriodCleanStateVerdict | None,
    iva_compensation_decision: IvaCompensationReconciliationDecision | None,
    workflow_profile: TaxpayerProfile,
    target: CalculationRevision,
    work_unit: WorkUnit,
    findings: list[ModeloVerificationFinding],
    failures_by_finding_id: dict[int, ModeloPreconditionFailure],
    door_of: Callable[[CrossPeriodDependencyEvidence], CrossPeriodDoor],
) -> None:
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
        door = door_of(evidence)
        failures_by_finding_id[id(finding)] = build_modelo_precondition_failure_for_scenario(
            subject_leaf_key="modelo.work.verify",
            scenario_id=f"modelo.work.verify.cross_period_dependency.{door.scenario}",
            evidence_id="modelo.work.verify.cross_period_dependency",
            evidence_values={
                "calculation_revision_id": target.calculation_revision_id,
                "work_unit_id": target.work_unit_id,
                "source_modelo": requirement.source_modelo,
                "year": requirement.filing_year,
                "period": requirement.period.registry_token,
                "origin_code": requirement.origin.value,
                "origin_ids": "|".join(requirement.origin_ids),
                "blocker_codes": "|".join(blocker.value for blocker in evidence.blockers),
            },
            provenance=ActionEvidenceProvenance.DOMAIN_EVALUATION,
            action_argument_values=door.action_argument_values,
            missing_action_arguments=cross_period_door_operator_arguments(door.scenario),
            alternative_actions=door.alternative_actions,
        )

    findings.extend(
        cross_period_clean_state_findings(
            clean_state_verdict,
            iva_compensation_decision=iva_compensation_decision,
            activity_start_date=workflow_profile.activity_start_date,
            blocking_finding_observer=_observe_cross_period_finding,
        ),
    )


def invoice_source_document_findings(
    *,
    target: CalculationRevision,
    invoice_repository: InvoiceCatalogueRepositoryProtocol,
    transaction_repository: TransactionCatalogueRepositoryProtocol,
    attachment_store: AttachmentStoreProtocol,
    registry_revision: ModeloRevision,
) -> list[ModeloVerificationFinding]:
    """Block a deduction a declared received invoice claims without its factura.

    The invoices are the ones the revision declared, by its invoice fingerprint
    rows. LIVA art. 97 grants the deduction on the factura itself, so a received
    invoice with a cuota needs its document stored with it, or a paying movement
    carrying registered purchase-invoice evidence. Each finding names the invoice,
    so the form can open it to attach the document.

    Only a return that deducts input IVA is held: a revision whose registry
    declares no deductible IVA binding (a Modelo 347 reads invoices for its
    counterpart totals) claims no deduction the factura must grant. A return
    that accrues output IVA warns, without blocking, on each declared issued
    invoice charging a cuota whose copy the records do not hold (RD 1619/2012
    art. 2): the cuota is owed on the operation whether or not the copy is kept.

    Core types:
    :class:`~cadrumo.domain.modelos.calculation_revision.CalculationRevision`,
    :class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision`.
    """
    fingerprint = target.invoice_fingerprint
    revision_date = registry_revision.valid_from
    deducts = _declares_iva_flow(registry_revision, lambda flow: is_deducible_flow(flow, effective_date=revision_date))
    accrues = _declares_iva_flow(registry_revision, lambda flow: is_devengada_flow(flow, effective_date=revision_date))
    if fingerprint is None or not fingerprint.rows or not (deducts or accrues):
        return []
    catalogue = invoice_repository.load()
    declared = tuple(invoice for row in fingerprint.rows if (invoice := catalogue.get(row.invoice_id)) is not None)
    documented = documented_invoice_ids(attachment_store)
    window = transaction_repository.load()
    received = _when(deducts, lambda: invoices_missing_source_document(declared, documented=documented, window=window))
    issued = _when(
        accrues, lambda: issued_invoices_missing_source_document(declared, documented=documented, window=window)
    )
    return [
        *(_received_invoice_document_finding(invoice) for invoice in received),
        *(_issued_invoice_document_finding(invoice) for invoice in issued),
    ]


def _when(applies: bool, select: Callable[[], tuple[Invoice, ...]]) -> tuple[Invoice, ...]:
    """The invoices ``select`` finds missing their document, or none when the return does not declare that flow."""
    return select() if applies else ()


def _received_invoice_document_finding(invoice: Invoice) -> ModeloVerificationFinding:
    """The blocking finding for a received invoice deducting without its factura."""
    return ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.BLOCKING_RULE,
        severity=ModeloVerificationFindingSeverity.BLOCKING,
        message_locale_key="application.modelo.findings.invoice_source_document_missing",
        message_facts={"invoice_id": invoice.invoice_id, "invoice_number": invoice.invoice_number},
        legal_refs=MISSING_EVIDENCE_LEGAL_REFS,
    )


def _issued_invoice_document_finding(invoice: Invoice) -> ModeloVerificationFinding:
    """The advisory for an issued invoice charging a cuota whose copy is not stored."""
    return ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.ADVISORY,
        severity=ModeloVerificationFindingSeverity.WARNING,
        message_locale_key="application.modelo.findings.transaction_evidence_missing_output",
        message_facts={
            "diagnostic_reason_code": "missing_transaction_evidence",
            "source_kind_code": MISSING_OUTPUT_IVA_EVIDENCE_SOURCE_KIND,
            "binding_id": invoice.invoice_id,
            "invoice_id": invoice.invoice_id,
            "invoice_number": invoice.invoice_number,
        },
        legal_refs=MISSING_EVIDENCE_LEGAL_REFS,
    )


def _declares_iva_flow(registry_revision: ModeloRevision, flow_test: Callable[[IvaFlowDirection], bool]) -> bool:
    """Whether a binding of this registry revision sums IVA of the flow ``flow_test`` admits."""
    return any(
        flow_test(provider_member(binding, LedgerIvaProvider).flow_direction)
        for binding in registry_revision.bindings
        if binding.source is BindingSourceKind.LEDGER_IVA_AGGREGATION
    )


def _append_invoice_source_document_findings(
    target: CalculationRevision,
    work_unit: WorkUnit,
    operation: PinnedAuthorityOperation,
    invoice_repository: InvoiceCatalogueRepositoryProtocol,
    transaction_repository: TransactionCatalogueRepositoryProtocol,
    attachment_store: AttachmentStoreProtocol,
    findings: list[ModeloVerificationFinding],
    failures_by_finding_id: dict[int, ModeloPreconditionFailure],
) -> None:
    for finding in invoice_source_document_findings(
        target=target,
        invoice_repository=invoice_repository,
        transaction_repository=transaction_repository,
        attachment_store=attachment_store,
        registry_revision=operation.reading_snapshot(
            work_unit.modelo,
            filing_year=work_unit.filing_year,
            period=work_unit.period.registry_token,
        ).revision,
    ):
        findings.append(finding)
        if finding.kind is not ModeloVerificationFindingKind.BLOCKING_RULE:
            continue
        failures_by_finding_id[id(finding)] = build_verification_precondition_failure(
            calculation_revision_id=target.calculation_revision_id,
            work_unit_id=target.work_unit_id,
            condition_id="modelo.work.verify.invoice_source_document.present",
            scenario_id="modelo.work.verify.invoice_source_document.missing",
            evidence_id="modelo.work.verify.invoice_source_document",
            evidence_values={"invoice_id": str(finding.message_facts["invoice_id"])},
            provenance=ActionEvidenceProvenance.PERSISTED_STATE,
        )


def _append_ledger_evidence_findings(
    target: CalculationRevision,
    work_unit: WorkUnit,
    transaction_repository: TransactionCatalogueRepositoryProtocol,
    operation: PinnedAuthorityOperation,
    findings: list[ModeloVerificationFinding],
    failures_by_finding_id: dict[int, ModeloPreconditionFailure],
) -> None:
    evidence_findings = missing_evidence_findings(
        target=target,
        work_unit=work_unit,
        transaction_repository=transaction_repository,
        operation=operation,
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
                    "transaction_id": diagnostic.binding_id or "",
                    "binding_id": diagnostic.binding_id or "",
                    "casilla_id": diagnostic.casilla_id or "",
                    "source_ref": diagnostic.source_ref or "",
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


def _append_modality_finding(
    work_unit: WorkUnit,
    workflow_profile: TaxpayerProfile,
    target: CalculationRevision,
    findings: list[ModeloVerificationFinding],
    failures_by_finding_id: dict[int, ModeloPreconditionFailure],
) -> None:
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


def _ledger_snapshot_findings(
    *,
    target: CalculationRevision,
    work_unit: WorkUnit,
    transaction_repository: TransactionCatalogueRepositoryProtocol,
    observation_repository: CalculationObservationRepositoryProtocol,
    filing_repository: ModeloRecordCatalogueRepositoryProtocol,
    operation: PinnedAuthorityOperation,
    work_profile: ModeloWorkProfile,
    ledger_membership_ports: LedgerMembershipPorts,
    failures_by_finding_id: dict[int, ModeloPreconditionFailure],
) -> list[ModeloVerificationFinding]:
    """Compare the live ledger membership with the stored calculation snapshot."""
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
        asset_register_drift_observer=lambda finding, recorded, current: failures_by_finding_id.__setitem__(
            id(finding),
            build_verification_precondition_failure(
                calculation_revision_id=target.calculation_revision_id,
                work_unit_id=target.work_unit_id,
                condition_id="modelo.work.verify.ledger_snapshot.current",
                scenario_id="modelo.work.verify.ledger_snapshot.drift_detected",
                evidence_id="modelo.work.verify.ledger_snapshot",
                evidence_values={
                    "snapshot_anchored": target.ledger_filing_snapshot is not None,
                    "recorded_claim_ids": "|".join(recorded.claim_ids),
                    "current_claim_ids": "|".join(current.claim_ids),
                    "recorded_schedule_fingerprints": "|".join(recorded.schedule_fingerprints),
                    "current_schedule_fingerprints": "|".join(current.schedule_fingerprints),
                    "membership_available": True,
                },
                provenance=ActionEvidenceProvenance.PERSISTED_STATE,
            ),
        ),
    )
    undetermined_mixed_use = undetermined_mixed_use_contributor_finding(
        target=target,
        work_unit=work_unit,
        transaction_repository=transaction_repository,
        operation=operation,
        source_refs=optional_observation_refs(target.observations, "source_refs"),
    )
    return [
        *drift_findings,
        *(() if undetermined_mixed_use is None else (undetermined_mixed_use,)),
        *invoice_drift_findings(
            target=target,
            work_unit=work_unit,
            revision=operation.revision(work_unit.modelo, work_unit.revision_id),
            ports=ledger_membership_ports.invoice_catalogue_read_ports,
            profile=work_profile,
            source_refs=optional_observation_refs(target.observations, "source_refs"),
            filings=imputation_filings_from_repositories(
                bucket_id=work_unit.bucket_id,
                year=work_unit.filing_year,
                observation_repository=observation_repository,
                filing_repository=filing_repository,
                authority=operation,
            ),
            narrower_scope_observer=lambda finding: failures_by_finding_id.__setitem__(
                id(finding),
                build_verification_precondition_failure(
                    calculation_revision_id=target.calculation_revision_id,
                    work_unit_id=target.work_unit_id,
                    condition_id="modelo.work.verify.invoice_fingerprint.current",
                    scenario_id="modelo.work.verify.invoice_fingerprint.scope_narrower",
                    evidence_id="modelo.work.verify.invoice_fingerprint",
                    evidence_values={
                        "catalogue_available": True,
                        "changed_invoice_ids": "",
                        "removed_invoice_ids": "",
                        "added_invoice_ids": "",
                    },
                    provenance=ActionEvidenceProvenance.PERSISTED_STATE,
                ),
            ),
            blocking_finding_observer=lambda finding, verdict: failures_by_finding_id.__setitem__(
                id(finding),
                build_verification_precondition_failure(
                    calculation_revision_id=target.calculation_revision_id,
                    work_unit_id=target.work_unit_id,
                    condition_id="modelo.work.verify.invoice_fingerprint.current",
                    scenario_id=(
                        "modelo.work.verify.invoice_fingerprint.catalogue_unavailable"
                        if verdict is None
                        else "modelo.work.verify.invoice_fingerprint.drift_detected"
                    ),
                    evidence_id="modelo.work.verify.invoice_fingerprint",
                    evidence_values={
                        "catalogue_available": verdict is not None,
                        "changed_invoice_ids": "" if verdict is None else "|".join(verdict.changed),
                        "removed_invoice_ids": "" if verdict is None else "|".join(verdict.removed),
                        "added_invoice_ids": "" if verdict is None else "|".join(verdict.added),
                    },
                    provenance=ActionEvidenceProvenance.PERSISTED_STATE,
                ),
            ),
        ),
    ]


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
    attachment_store: AttachmentStoreProtocol,
    iva_compensation_history_repository: IvaCompensationHistoryRepositoryProtocol,
    iva_compensation_decision_repository: IvaWalletDecisionRepositoryProtocol,
    cross_period_expected_member_sets: Iterable[CrossPeriodExpectedMemberSet],
    operation: PinnedAuthorityOperation,
    work_profile: ModeloWorkProfile,
    ledger_membership_ports: LedgerMembershipPorts,
    evaluated_at: datetime | None = None,
    calculation_catalogue: CalculationRevisionCatalogue | None = None,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol | None = None,
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
    _append_modality_finding(work_unit, workflow_profile, target, findings, failures_by_finding_id)
    iva_compensation_decision = None
    try:
        iva_compensation_decision = require_persisted_iva_compensation_decision_matches_revision(
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
        operator_value_attestations=operator_value_attestations(target),
        work_unit_repository=work_unit_repository,
        operation=operation,
    )

    _append_cross_period_findings(
        clean_state_verdict,
        iva_compensation_decision,
        workflow_profile,
        target,
        work_unit,
        findings,
        failures_by_finding_id,
        cross_period_door_reader(
            bucket_id=work_unit.bucket_id,
            work_unit_repository=work_unit_repository,
            calculation_repository=calculation_repository,
            calculation_catalogue=calculation_catalogue,
            operation=operation,
            target=work_unit,
        ),
    )
    _append_ledger_evidence_findings(
        target, work_unit, transaction_repository, operation, findings, failures_by_finding_id
    )
    # A refused registry snapshot is the verdict: the gates below read that same
    # snapshot, so they would only raise the refusal again instead of reporting it.
    if any(failure.scenario_id in REGISTRY_SNAPSHOT_REFUSAL_SCENARIOS for failure in failures_by_finding_id.values()):
        return findings, resolved_casilla_ids, missing_required_casilla_ids, failures_by_finding_id
    _append_invoice_source_document_findings(
        target,
        work_unit,
        operation,
        invoice_repository,
        transaction_repository,
        attachment_store,
        findings,
        failures_by_finding_id,
    )
    # Runs beside the evidence gate, not inside it: that gate reads the live
    # ledger while the casilla values come from the stored draft, and this is
    # what refuses the case where those two views have drifted apart.
    findings.extend(
        _ledger_snapshot_findings(
            target=target,
            work_unit=work_unit,
            transaction_repository=transaction_repository,
            observation_repository=observation_repository,
            filing_repository=filing_repository,
            operation=operation,
            work_profile=work_profile,
            ledger_membership_ports=ledger_membership_ports,
            failures_by_finding_id=failures_by_finding_id,
        ),
    )
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
    snapshot = operation.reading_snapshot(
        work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=work_unit.period.registry_token,
    )
    casilla_def = casillas_by_id(snapshot.revision).get(M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA)
    if casilla_def is None or not casilla_def.legal_refs or not casilla_def.source_refs:
        raise ModeloValidationError(
            "IVA wallet finding requires the compensation casilla's legal_refs/source_refs provenance",
            no_recovery_outcome=NoRecoveryOutcome.TERMINAL,
            record=ModeloValidatedRecord.REGISTRY_DECLARATION,
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
        legal_refs=tuple(casilla_def.legal_refs),
        source_refs=tuple(casilla_def.source_refs),
    )
