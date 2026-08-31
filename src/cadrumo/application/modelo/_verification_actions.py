"""Verification actions and predicates for modelo filings.

:func:`verify_modelo_revision` evaluates a draft
:class:`CalculationRevision` against its :class:`RegistrySnapshot`, workflow
:class:`TaxpayerProfile`, ledger diagnostics, registry verification predicates,
and cross-period clean-state verdicts before persisting a
:class:`VerificationReport`.

Verification findings are the operator-facing gate vocabulary. BLOCKING-severity
findings refuse the verified-complete transition; WARNING-severity ADVISORY
findings remain visible in the report without bricking verify, file, or export.
Calculate-path source diagnostics are separate
:class:`~cadrumo.application.aggregation.CalculationSourceDiagnostic` advisories;
this module converts only verify-time registry, profile, provenance, and
cross-period facts into :class:`ModeloVerificationFinding` records.

Verification emits bucket-history entries through
:class:`BucketEventHistoryRepository`, stores casilla-level
:class:`CasillaObservation` provenance, and uses
:class:`TransactionCatalogueRepository` only for evidence advisories over source
transactions.

Draft-construction structural validation is a distinct, nested stage, not a
parallel pipeline. When verification grants, this module runs the revision
workflow gate with :class:`~cadrumo.application.workflow.WorkflowPurpose.VERIFY`;
that gate builds a filing draft, and the draft builder stamps
:class:`ModeloValidationFinding` rows produced by
:class:`~cadrumo.domain.filing.ModeloValidator` onto the draft, which the
workflow engine re-scans for ERROR severity. Those structural findings answer
whether the draft is well-formed against the casilla collection;
:class:`ModeloVerificationFinding` answers operator-facing filing readiness and
carries registry ``legal_refs`` provenance the structural model does not. The
two vocabularies are not interchangeable.

See Also:
    :class:`~cadrumo.domain.filing.ModeloValidator`:
        Draft-construction structural validator reached through the workflow
        gate's draft builder; owns :class:`ModeloValidationFinding`.
    :func:`~cadrumo.application.calculations.evaluate_cross_period_clean_state`:
        Shared cross-period gate used by verify, file, and export.
    :mod:`~cadrumo.application.modelo._calculation_diagnostics`:
        Calculate-path diagnostics that feed advisory observations before verify.
    :mod:`~cadrumo.domain.modelos`:
        Finding kind, severity, and completeness-status authority.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Final

from ...adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ...adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ...adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ...adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from ...adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ...adapters.persistence.profile.participation_index import TransactionParticipationIndexRepository
from ...adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ...core.irnr import M210GrossIncomeSourceMode
from ...core.modelo import Modelo
from ...core.operator_action_enums import ActionEvidenceProvenance
from ...core.casilla_id import CasillaId
from ...core.aggregation import BindingSourceKind
from ...core.config import Settings
from ...core.identity import CalculationRevisionId
from ...core.time import now as _utc_now
from ...domain.buckets.event import BucketEventObjectType, BucketEventType
from ...domain.buckets.protocols import BucketEventHistoryRepositoryProtocol
from ...domain.calculations.registry.applicability import derive_taxpayer_files_economic_activity
from ...domain.calculations.registry.applicability_modelo202 import derive_modelo_202_modality
from ...domain.calculations.registry.authority import bundled_authority
from ...domain.calculations.registry.bindings import CasillaObservation
from ...domain.calculations.registry.ids import (
    LegalRefId,
    SourceRefId,
)
from ...domain.calculations.registry.schema import DataBindingDefinition, RegistrySnapshot
from ...domain.calculations.registry.schema_input_kind import InputKind
from ...domain.calculations.registry.schema_surfaces import CasillaDefinition
from ...domain.deadlines.models import TaxpayerProfile
from ...domain.iva.schema import CUOTA_LESS_M303_IVA_CATEGORIES
from ...domain.modelos.calculation_repository import upsert_calculation_revision
from ...domain.modelos.ledger_filing_snapshot import ManualFactBasisEntry
from ...domain.modelos.participation_index import TransactionRevisionParticipation, upsert_transaction_participation
from ...domain.modelos.protocols import CalculationRevisionCatalogueRepositoryProtocol, ModeloRecordCatalogueRepositoryProtocol, VerificationReportCatalogueRepositoryProtocol
from ...domain.modelos.repository import upsert_work_unit
from ...domain.modelos.verification_report import ModeloVerificationFinding, ModeloVerificationFindingKind, ModeloVerificationFindingSeverity, VerificationCompletenessStatus, VerificationReport, VerificationReportCatalogue, derive_verification_report_id
from ...domain.modelos.verification_repository import upsert_verification_report
from ...domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue
from ...domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionCatalogue,
    CalculationRevisionState,
    CalculationSourceIssue,
)
from ...domain.modelos.errors import ModeloValidationError
from ...domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol
from ..aggregation import (
    MISSING_DEDUCTIBLE_IVA_EVIDENCE_SOURCE_KIND,
    CalculationSourceDiagnostic,
    assert_evidence_covers_snapshot,
    compute_ledger_filing_evidence,
    compute_ledger_filing_snapshot,
    missing_evidence_advisory_observations,
)
from ..calculations import (
    M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA,
    CalculationObservationRepository,
    CrossPeriodDependencyEvidence,
    CrossPeriodExpectedMemberSet,
    validate_m303_regimen_simplificado_annual_summary_target_revision,
)
from ..workflow.engine import WorkflowEngine
from ..workflow.persistence import WorkflowRunRepository
from ..workflow.run_models import WorkflowPurpose
from ._action_errors import (
    WORKFLOW_GATE_LEGAL_REFS,
    CalculationRevisionNotFoundError,
    CalculationRevisionStateError,
    WorkUnitNotFoundError,
)
from ._art20_advisory import _art20_reduccion_advisory_finding
from ._art52_advisory import _art52_reduccion_advisory_finding
from ._art109_activity_income import derive_art109_activity_income_coverage_for_work_unit as _derive_art109_coverage
from ._attribution_received_advisory import _attribution_received_omission_advisory_findings
from ._autonomic_deduccion_advisory import _madrid_nacimiento_adopcion_advisory_finding_for_work_unit
from ._dt12_advisory import _dt12_reduccion_advisory_finding
from ._dt12_antiquity_advisory import _dt12_antiquity_advisory_finding
from ._iva_wallet_gate import (
    ModeloIvaWalletReconciliationBlocked,
)
from ._iva_wallet_gate import (
    require_persisted_iva_compensation_decision_matches_revision as _require_iva_compensation_revision_match,
)
from ._ledger_drift_gate import ledger_drift_findings
from ._m210_agrupacion_renta import m210_agrupacion_renta_verification_findings
from ._m210_convenio_lob_advisory import _m210_convenio_lob_advisory_finding
from ._m303_m349_reconcile import m303_m349_intracom_reconcile_findings
from ._m720_redeclaration_gate import modelo_720_redeclaration_findings
from ._objective_estimation_advisory import _objective_estimation_exclusion_advisory_findings
from ._preconditions import ModeloPreconditionFailure
from ._pulled_filing_reconcile import pulled_filing_divergence_findings
from ._registry_helpers import assert_revision_content_integrity as _assert_revision_content_integrity
from ._required_binding_gate import (
    require_persisted_revision_required_bindings_resolved as _require_persisted_required_bindings_resolved,
)
from ._revision_persistence import (
    emit_modelo_bucket_event as _emit_bucket_event,
)
from ._revision_persistence import (
    require_filing_instance_evidence_for_work_unit,
)
from ._verification_cross_period import (
    CROSS_PERIOD_ACTIVITY_START_LEGAL_REFS,
    CROSS_PERIOD_DEPENDENCY_LEGAL_REFS,
)
from ._verification_cross_period import (
    IVA_COMPENSATION_CARRY_LEGAL_REF as _IVA_COMPENSATION_CARRY_LEGAL_REF,
)
from ._verification_cross_period import (
    cross_period_clean_state_findings as _cross_period_clean_state_findings,
)
from ._verification_cross_period import (
    cross_period_clean_state_verdict_for_work_unit as _cross_period_clean_state_verdict_for_work_unit,
)
from ._verification_cross_period import (
    cross_period_expected_member_sets_from_profile as _cross_period_expected_member_sets_from_profile,
)
from ._verification_cross_period import (
    cross_period_expected_member_sets_from_profile as cross_period_expected_member_sets_from_profile,
)
from ._verification_cross_period import (
    modelo_202_incomplete_modality_finding as _modelo_202_incomplete_modality_finding,
)
from ._verification_cross_period import (
    require_cross_period_clean_state as _require_cross_period_clean_state,
)
from ._verification_cross_period import (
    zero_value_previous_filing_binding_ids as _zero_value_previous_filing_binding_ids,
)
from ._verification_preconditions import (
    ModeloVerificationResult,
    build_verification_precondition_failure,
    project_verification_findings,
)
from .work_lifecycle import RevisionParentOperation, require_revision_parent_active
from ._workflow_gate import build_revision_workflow_engine as _build_revision_workflow_engine
from ._workflow_gate import run_revision_workflow_gate as _run_revision_workflow_gate

if TYPE_CHECKING:
    from ...adapters.persistence.storage import SecureObjectWrite
    from ..calculations import IvaWalletDecisionRepository

from ._m303_regimen_simplificado_scope import m303_regimen_simplificado_annual_summary_applies
from ._verification_predicates import (
    M349_IMPORTE_RECTIFICACIONES_CASILLA as _M349_IMPORTE_RECTIFICACIONES_CASILLA,
)
from ._verification_predicates import (
    M349_NUMERO_RECTIFICACIONES_CASILLA as _M349_NUMERO_RECTIFICACIONES_CASILLA,
)
from ._verification_predicates import (
    evaluate_advisory_predicate_fires as evaluate_advisory_predicate_fires,
)
from ._verification_predicates import evaluate_applicability_filter
from ._verification_predicates import (
    evaluate_predicate_expression as evaluate_predicate_expression,
)
from ._verification_predicates import (
    evaluate_verification_predicates as _evaluate_verification_predicates,
)
from ._verification_predicates import (
    evaluate_verification_predicates as evaluate_verification_predicates,
)
from ._verification_predicates import (
    m210_unresolved_outcome_findings as _m210_unresolved_outcome_findings,
)

# Retain pinned verification-actions test imports while consuming public helper contracts.
_CROSS_PERIOD_ACTIVITY_START_LEGAL_REFS = CROSS_PERIOD_ACTIVITY_START_LEGAL_REFS
_CROSS_PERIOD_DEPENDENCY_LEGAL_REFS = CROSS_PERIOD_DEPENDENCY_LEGAL_REFS
_evaluate_advisory_predicate_fires = evaluate_advisory_predicate_fires
_evaluate_applicability_filter = evaluate_applicability_filter
_evaluate_predicate_expression = evaluate_predicate_expression


def _normalised_observation_refs(observations: Iterable[CasillaObservation | None], field_name: str) -> tuple[str, ...]:
    refs = tuple(
        dict.fromkeys(
            str(ref).strip()
            for observation in observations
            if observation is not None
            for ref in getattr(observation, field_name)
            if str(ref).strip()
        ),
    )
    if not refs:
        raise ModeloValidationError(
            translated_message="errors.error.error_modelos_validation",
            context={"field_name": field_name, "observation_present": False},
        )
    return refs


def _optional_observation_refs(observations: Iterable[CasillaObservation | None], field_name: str) -> tuple[str, ...]:
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


def _manual_fact_basis_entries(
    input_values_by_casilla_id: Mapping[CasillaId, str],
    observations: Iterable[CasillaObservation],
    *,
    m210_gross_income_source_mode: M210GrossIncomeSourceMode | None,
) -> tuple[ManualFactBasisEntry, ...]:
    """Project a revision's operator casilla inputs into manual fact-basis entries.

    The ``input_values_by_casilla_id`` holds the caller-supplied (operator-entered) casilla
    values that are not ledger-derived; each non-empty entry is part of the fact
    basis a filing artefact must explain. Blank values are skipped (they carry no
    fact). The M210 ledger-derived ``rendimientos_integros`` input is deliberately
    excluded: it is present in the replay map so formula replay is exact, but its
    fact basis is the fingerprinted transaction evidence rather than a manual
    declaration.
    """
    observations_by_casilla_id = {observation.casilla_id: observation for observation in observations}
    return tuple(
        ManualFactBasisEntry(
            casilla_id=casilla,
            value=value,
            legal_refs=_normalised_observation_refs(
                (observations_by_casilla_id.get(casilla),),
                "legal_refs",
            ),
            source_refs=_normalised_observation_refs(
                (observations_by_casilla_id.get(casilla),),
                "source_refs",
            ),
        )
        for casilla, value in sorted(input_values_by_casilla_id.items())
        if value.strip()
        and not (
            m210_gross_income_source_mode is M210GrossIncomeSourceMode.LEDGER and casilla == "rendimientos_integros"
        )
    )


#: Stands in a finding fact whose subject genuinely does not exist, so the fact
#: can be supplied on EVERY branch. ``tr()`` leaves an unsupplied placeholder in
#: the rendered string rather than raising, so a conditionally-supplied fact
#: reaches the operator as a literal ``%{binding_id}``. The marker is the
#: established spelling for this on adjacent findings (``_pulled_filing_reconcile``,
#: ``_attribution_received_advisory``) and says which case it is: an absent
#: subject reads differently from one whose id is blank.
_ABSENT_FACT: Final[str] = "absent"

#: Legal grounding for missing IVA evidence. Deducting input IVA requires the
#: original factura (LIVA art. 97, RD 1619/2012 art. 2). Output-IVA evidence
#: gaps stay advisory until the transaction model can distinguish every valid
#: issued-invoice support path without over-blocking.
_MISSING_EVIDENCE_LEGAL_REFS: tuple[str, ...] = (
    "ley-37-1992:art-97",
    "rd-1619-2012:art-2",
)


#: Legal grounding for a cuota-less row that declares no base. LIVA art. 164.Uno.6
#: obliges the taxpayer to declare the operations; the M303 base casillas are
#: where an exempt, zero-rated, not-subject or intra-community operation is
#: reported, since by law it carries no cuota. RD 1624/1992 art. 71.7 fixes the
#: content of the periodic self-assessment those bases feed.
_CUOTA_LESS_WITHOUT_BASE_LEGAL_REFS: tuple[str, ...] = (
    "ley-37-1992:art-164",
    "rd-1624-1992:art-71",
)


def _cuota_less_without_base_findings(
    *,
    target: CalculationRevision,
    work_unit: WorkUnit,
    transaction_repository: TransactionCatalogueRepository | None = None,
    blocking_finding_observer: Callable[[ModeloVerificationFinding, str, str], None] | None = None,
) -> list[ModeloVerificationFinding]:
    """Refuse a row whose declared category can only ever contribute a base it lacks.

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
    tx_repo = transaction_repository or TransactionCatalogueRepository(bucket_id=work_unit.bucket_id)
    catalogue = tx_repo.load()
    registry_source_refs = _optional_observation_refs(target.observations, "source_refs")

    findings: list[ModeloVerificationFinding] = []
    for transaction_id in sorted(target.source_transaction_ids):
        transaction = catalogue.get(transaction_id)
        if transaction is None:
            continue
        category = transaction.iva_category
        if category is None or category not in CUOTA_LESS_M303_IVA_CATEGORIES:
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
            legal_refs=_CUOTA_LESS_WITHOUT_BASE_LEGAL_REFS,
            source_refs=registry_source_refs,
        )
        findings.append(finding)
        if blocking_finding_observer is not None:
            blocking_finding_observer(finding, transaction_id, category.value)
    return findings


def _missing_evidence_findings(
    *,
    target: CalculationRevision,
    work_unit: WorkUnit,
    transaction_repository: TransactionCatalogueRepository | None,
    blocking_finding_observer: Callable[[ModeloVerificationFinding, CalculationSourceDiagnostic], None] | None = None,
) -> list[ModeloVerificationFinding]:
    """Build verification findings for evidence-less positive IVA rows.

    Loads the :class:`CalculationRevision` source transactions for the supplied
    :class:`WorkUnit` and
    projects each
    :class:`~cadrumo.application.aggregation.CalculationSourceDiagnostic`
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
    tx_repo = transaction_repository or TransactionCatalogueRepository(bucket_id=work_unit.bucket_id)
    catalogue = tx_repo.load()
    transactions = [
        transaction
        for transaction_id in target.source_transaction_ids
        if (transaction := catalogue.get(transaction_id)) is not None
    ]
    diagnostics: tuple[CalculationSourceDiagnostic, ...] = missing_evidence_advisory_observations(transactions)
    findings: list[ModeloVerificationFinding] = []
    registry_source_refs = _optional_observation_refs(target.observations, "source_refs")
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
            "binding_id": str(diagnostic.binding_id) if diagnostic.binding_id is not None else _ABSENT_FACT,
        }
        if diagnostic.source_ref is not None:
            message_facts["source_ref"] = diagnostic.source_ref
        if is_deductible_gap:
            finding = ModeloVerificationFinding(
                kind=ModeloVerificationFindingKind.BLOCKING_RULE,
                severity=ModeloVerificationFindingSeverity.BLOCKING,
                message_locale_key="application.modelo.findings.transaction_evidence_missing_deductible",
                message_facts=message_facts,
                legal_refs=_MISSING_EVIDENCE_LEGAL_REFS,
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
                legal_refs=_MISSING_EVIDENCE_LEGAL_REFS,
                source_refs=registry_source_refs,
            ),
        )
    return findings


def _collect_verification_gate_findings(
    *,
    work_unit: WorkUnit,
    target: CalculationRevision,
    workflow_profile: TaxpayerProfile,
    observation_repository: CalculationObservationRepository,
    filing_repository: ModeloRecordCatalogueRepositoryProtocol,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol,
    verification_repository: VerificationReportCatalogueRepositoryProtocol,
    transaction_repository: TransactionCatalogueRepository | None,
    iva_compensation_decision_repository: IvaWalletDecisionRepository | None,
    cross_period_expected_member_sets: Iterable[CrossPeriodExpectedMemberSet],
) -> tuple[
    list[ModeloVerificationFinding],
    list[CasillaId],
    list[CasillaId],
    dict[int, ModeloPreconditionFailure],
]:
    findings, resolved_casilla_ids, missing_required_casilla_ids, failures_by_finding_id = (
        _collect_revision_verification_findings(
            work_unit=work_unit,
            target=target,
            profile=workflow_profile,
            transaction_repository=transaction_repository,
        )
    )
    incomplete_modality_finding = _modelo_202_incomplete_modality_finding(
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
            subject_leaf_key="modelo.work.verify",
        )
    except ModeloIvaWalletReconciliationBlocked as exc:
        finding = _iva_wallet_error_verification_finding(exc)
        findings.append(finding)
        failures_by_finding_id[id(finding)] = exc.precondition_failure
    clean_state_verdict = _cross_period_clean_state_verdict_for_work_unit(
        work_unit,
        observation_repository=observation_repository,
        filing_repository=filing_repository,
        calculation_repository=calculation_repository,
        verification_repository=verification_repository,
        expected_member_sets=_cross_period_expected_member_sets_from_profile(
            workflow_profile,
            cross_period_expected_member_sets,
        ),
        taxpayer_tax_id=workflow_profile.tax_id,
        activity_start_date=workflow_profile.activity_start_date,
        modelo_202_modality=derive_modelo_202_modality(workflow_profile).modality,
        taxpayer_files_economic_activity=derive_taxpayer_files_economic_activity(workflow_profile),
        workflow_profile=workflow_profile,
        zero_value_previous_filing_binding_ids=_zero_value_previous_filing_binding_ids(target),
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
        _cross_period_clean_state_findings(
            clean_state_verdict,
            iva_compensation_decision=iva_compensation_decision,
            activity_start_date=workflow_profile.activity_start_date,
            blocking_finding_observer=_observe_cross_period_finding,
        ),
    )
    missing_evidence_findings = _missing_evidence_findings(
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
    findings.extend(missing_evidence_findings)
    # Beside the evidence gate and for the same reason: both refuse a draft whose
    # rows cannot support what it declares, and both block at verify so the later
    # export and filing refusals are unreachable rather than merely later.
    cuota_less_findings = _cuota_less_without_base_findings(
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
    drift_findings = ledger_drift_findings(
        target=target,
        work_unit=work_unit,
        transaction_repository=transaction_repository,
        source_refs=_optional_observation_refs(target.observations, "source_refs"),
        blocking_finding_observer=lambda finding, anchored, changed_ids, removed_ids: (
            failures_by_finding_id.__setitem__(
                id(finding),
                build_verification_precondition_failure(
                    calculation_revision_id=target.calculation_revision_id,
                    work_unit_id=target.work_unit_id,
                    condition_id="modelo.work.verify.ledger_snapshot.current",
                    scenario_id="modelo.work.verify.ledger_snapshot.drift_detected",
                    evidence_id="modelo.work.verify.ledger_snapshot",
                    evidence_values={
                        "snapshot_anchored": anchored,
                        "changed_transaction_count": len(changed_ids),
                        "changed_transaction_ids": "|".join(changed_ids),
                        "removed_transaction_count": len(removed_ids),
                        "removed_transaction_ids": "|".join(removed_ids),
                    },
                    provenance=ActionEvidenceProvenance.PERSISTED_STATE,
                ),
            )
        ),
    )
    findings.extend(drift_findings)
    return findings, resolved_casilla_ids, missing_required_casilla_ids, failures_by_finding_id


def _existing_granting_verification_report(
    catalogue: VerificationReportCatalogue,
    calculation_revision_id: CalculationRevisionId,
) -> VerificationReport | None:
    """Return the granting verification report for a locked revision, or ``None``.

    Used by the idempotent re-verify no-op: a revision that has transitioned out
    of ``BORRADOR`` (``VERIFICADO_COMPLETO`` / ``PRESENTADO``) was granted
    verification, so exactly one granting :class:`VerificationReport` exists for
    it; ``None`` flags an inconsistent state (a non-draft revision with no
    granting report) that the caller refuses rather than papering over.
    """
    for report in catalogue.reports.values():
        if report.calculation_revision_id == calculation_revision_id and report.granted_verificado_completo:
            return report
    return None


def _build_verification_report(
    *,
    calculation_revision_id: CalculationRevisionId,
    findings: Iterable[ModeloVerificationFinding],
    resolved_casilla_ids: Iterable[CasillaId],
    missing_required_casilla_ids: Iterable[CasillaId],
    completeness: VerificationCompletenessStatus,
    granted: bool,
    actor: str,
    run_at: datetime,
) -> VerificationReport:
    """Build the immutable, content-addressed verification report."""
    frozen_findings = tuple(findings)
    verified_by = actor.strip()
    return VerificationReport(
        verification_report_id=derive_verification_report_id(
            calculation_revision_id=calculation_revision_id,
            completeness_status=completeness,
            findings=frozen_findings,
            verified_by=verified_by,
        ),
        calculation_revision_id=calculation_revision_id,
        completeness_status=completeness,
        findings=frozen_findings,
        resolved_casilla_ids=tuple(resolved_casilla_ids),
        missing_required_casilla_ids=tuple(missing_required_casilla_ids),
        run_at=run_at,
        verified_by=verified_by,
        granted_verificado_completo=granted,
    )


def _append_model_specific_findings(
    findings: list[ModeloVerificationFinding],
    *,
    failures_by_finding_id: dict[int, ModeloPreconditionFailure],
    work_unit: WorkUnit,
    target: CalculationRevision,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol,
    observation_repository: CalculationObservationRepository,
) -> None:
    """Append cross-model and detail-row verification findings in one place."""
    findings.extend(
        m303_m349_intracom_reconcile_findings(
            work_unit=work_unit,
            target=target,
            work_unit_repository=work_unit_repository,
            calculation_repository=calculation_repository,
        ),
    )
    findings.extend(
        pulled_filing_divergence_findings(
            work_unit=work_unit,
            target=target,
            observation_repository=observation_repository,
        ),
    )
    m210_agrupacion_findings = m210_agrupacion_renta_verification_findings(work_unit=work_unit, revision=target)
    findings.extend(m210_agrupacion_findings)
    for finding in m210_agrupacion_findings:
        failures_by_finding_id[id(finding)] = build_verification_precondition_failure(
            calculation_revision_id=target.calculation_revision_id,
            work_unit_id=target.work_unit_id,
            condition_id="modelo.work.verify.m210.agrupacion.valid",
            scenario_id="modelo.work.verify.m210.agrupacion.invalid",
            evidence_id="modelo.work.verify.m210.agrupacion",
            evidence_values={
                "detail_row_count": len(target.detail_rows),
                "official_tipo_renta_present": target.m210_official_tipo_renta_code is not None,
            },
            provenance=ActionEvidenceProvenance.PERSISTED_STATE,
        )
    findings.extend(
        modelo_720_redeclaration_findings(
            work_unit=work_unit,
            revision=target,
            observation_repository=observation_repository,
        ),
    )


@dataclass(frozen=True, slots=True)
class _VerificationRepositories:
    """Resolved repository ports for one verification run."""

    calculation: CalculationRevisionCatalogueRepositoryProtocol
    work_unit: WorkUnitCatalogueRepositoryProtocol
    verification: VerificationReportCatalogueRepositoryProtocol
    filing: ModeloRecordCatalogueRepositoryProtocol
    observation: CalculationObservationRepository
    bucket_event: BucketEventHistoryRepositoryProtocol
    run: WorkflowRunRepository


def _resolve_verification_repositories(
    *,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol | None,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol | None,
    verification_repository: VerificationReportCatalogueRepositoryProtocol | None,
    filing_repository: ModeloRecordCatalogueRepositoryProtocol | None,
    calculation_observation_repository: CalculationObservationRepository | None,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol | None,
) -> _VerificationRepositories:
    """Default every unset verification repository port and derive the workflow-run store."""
    cr_repo = calculation_repository or CalculationRevisionCatalogueRepository()
    wu_repo = work_unit_repository or WorkUnitCatalogueRepository()
    vr_repo = verification_repository or VerificationReportCatalogueRepository()
    fr_repo = filing_repository or ModeloRecordCatalogueRepository()
    obs_repo = calculation_observation_repository or CalculationObservationRepository()
    bv_repo = bucket_event_repository or BucketEventHistoryRepository()
    _secure_objects = bv_repo.secure_object_repository if isinstance(bv_repo, BucketEventHistoryRepository) else None
    run_repo = WorkflowRunRepository(objects=_secure_objects)
    return _VerificationRepositories(
        calculation=cr_repo,
        work_unit=wu_repo,
        verification=vr_repo,
        filing=fr_repo,
        observation=obs_repo,
        bucket_event=bv_repo,
        run=run_repo,
    )


def verify_modelo_revision_with_preconditions(
    calculation_revision_id: CalculationRevisionId,
    *,
    actor: str,
    workflow_profile: TaxpayerProfile,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol | None = None,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol | None = None,
    filing_repository: ModeloRecordCatalogueRepositoryProtocol | None = None,
    transaction_repository: TransactionCatalogueRepository | None = None,
    verification_repository: VerificationReportCatalogueRepositoryProtocol | None = None,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol | None = None,
    iva_compensation_decision_repository: IvaWalletDecisionRepository | None = None,
    calculation_observation_repository: CalculationObservationRepository | None = None,
    participation_index_repository: TransactionParticipationIndexRepository | None = None,
    cross_period_expected_member_sets: Iterable[CrossPeriodExpectedMemberSet] = (),
    workflow_engine: WorkflowEngine | None = None,
    workflow_runs_dir: Path | None = None,
    settings: Settings | None = None,
    clock: datetime | None = None,
) -> ModeloVerificationResult:
    """Evaluate a draft revision against registry, clean-state, provenance, and workflow gates.

    The verifier loads the draft
    :class:`CalculationRevision`,
    resolves its work unit and :class:`RegistrySnapshot`, builds verify-time findings,
    classifies the outcome, persists a :class:`VerificationReport`, records
    bucket history, and updates the :class:`CalculationRevision` only when the
    verified-complete transition is granted.

    The supplied :class:`TaxpayerProfile` scopes
    deadline/applicability decisions, while
    :class:`TransactionCatalogueRepository` supplies
    non-blocking transaction-evidence advisories for source rows attached to the
    revision. WARNING-severity advisories remain report content; only BLOCKING
    severity can refuse the transition.

    Args:
        calculation_revision_id: Stable id of the draft
            :class:`CalculationRevision` to verify.
        actor: Operator label recorded on the verification report and bucket
            history event.
        workflow_profile: :class:`TaxpayerProfile`
            supplying profile facts for workflow, deadline, applicability, and
            registry predicate gates.
        work_unit_repository: Optional work-unit repository port.
        calculation_repository: Optional calculation-revision repository port.
        filing_repository: Optional modelo-record repository port for filed-state
            and cross-period checks.
        transaction_repository: Optional
            :class:`TransactionCatalogueRepository` used for transaction-evidence
            advisories.
        verification_repository: Optional verification-report repository port.
        bucket_event_repository: Optional bucket-event history repository port.
        iva_compensation_decision_repository: Optional IVA-wallet decision
            repository used by Modelo 303 verification gates.
        calculation_observation_repository: Optional calculation-observation
            repository used by cross-period clean-state checks.
        participation_index_repository: Optional transaction participation-index
            repository co-emitted with verified revisions.
        cross_period_expected_member_sets: Optional expected-member overrides
            for the cross-period clean-state gate.
        workflow_engine: Optional :class:`~cadrumo.application.workflow.WorkflowEngine`
            override for tests and controlled workflow runs.
        workflow_runs_dir: Optional workflow-runs directory override.
        settings: Optional runtime settings for workflow-engine construction.
        clock: Optional timestamp override for deterministic verification.

    Returns:
        The application result containing the persisted
        :class:`VerificationReport` and its ordered typed preconditions.

    Raises:
        :class:`~cadrumo.application.modelo.CalculationRevisionNotFoundError`: The
            requested calculation revision does not exist in the active
            catalogue.
        :class:`~cadrumo.application.modelo.CalculationRevisionStateError`: The
            revision is not in ``BORRADOR`` state.
        :class:`~cadrumo.application.modelo.WorkUnitNotFoundError`: The owning work
            unit is missing.
        :class:`~cadrumo.application.modelo.ModeloCrossPeriodCleanStateError`: A
            required cross-period dependency has a blocking clean-state finding.
    """
    repos = _resolve_verification_repositories(
        calculation_repository=calculation_repository,
        work_unit_repository=work_unit_repository,
        verification_repository=verification_repository,
        filing_repository=filing_repository,
        calculation_observation_repository=calculation_observation_repository,
        bucket_event_repository=bucket_event_repository,
    )
    cr_repo = repos.calculation
    wu_repo = repos.work_unit
    vr_repo = repos.verification
    # Revisioned, and threaded to the persistence below: the catalogue is
    # composed into a co-commit there, so it cannot use a self-committing
    # mutation, and the revision belongs to whoever performed the read.
    revisions, revisions_revision_id = cr_repo.load_revisioned()
    target = revisions.get(calculation_revision_id)
    if target is None:
        raise CalculationRevisionNotFoundError(
            translated_message="application.modelo.errors.calculation_revision_not_found",
            context={"calculation_revision_id": calculation_revision_id},
        )
    work_units = wu_repo.load()
    work_unit = work_units.get(target.work_unit_id)
    if work_unit is None:
        raise WorkUnitNotFoundError(
            f"calculation revision {calculation_revision_id!r} references missing work_unit_id={target.work_unit_id!r}",
        )
    require_revision_parent_active(
        work_unit=work_unit,
        calculation_revision_id=calculation_revision_id,
        operation=RevisionParentOperation.VERIFY,
    )
    if target.state is not CalculationRevisionState.BORRADOR:
        # Idempotent re-verify (aeat-cli-contract): a
        # revision that has already been verified-and-granted (VERIFICADO_COMPLETO,
        # or PRESENTADO after filing) is LOCKED — its content, and therefore its
        # verification outcome, cannot change — so a retry returns the existing
        # granting VerificationReport as a clean no-op: no re-run of the
        # verification gates, no duplicate report (the report id is clock-free —
        # derive_verification_report_id folds the outcome, not run_at), and no
        # second lifecycle event. The CLI surfaces the no-op as an info Notice.
        # A non-draft revision with no granting report is an inconsistent state,
        # so it falls through to the hard refusal below rather than fabricating
        # one. Mirrors the re-file no-op in file_modelo_revision.
        existing = _existing_granting_verification_report(vr_repo.load(), calculation_revision_id)
        if existing is not None:
            return ModeloVerificationResult(
                report=existing,
                finding_preconditions=project_verification_findings(
                    existing.findings,
                    failures_by_finding_id={},
                ),
            )
        raise CalculationRevisionStateError(
            translated_message="errors.error.error_modelo_calculation_revision_state",
            context={"calculation_revision_id": calculation_revision_id, "state": target.state.value},
        )

    _assert_revision_content_integrity(target)
    validate_m303_regimen_simplificado_annual_summary_target_revision(
        target_work_unit=work_unit,
        target_revision=target,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=repos.filing,
        regimen_simplificado_applies=m303_regimen_simplificado_annual_summary_applies(work_unit),
    )
    require_filing_instance_evidence_for_work_unit(work_unit=work_unit, revision=target)

    from ._profile_readiness_gate import require_profile_ready_for_work_unit

    require_profile_ready_for_work_unit(work_unit)
    _require_persisted_required_bindings_resolved(
        work_unit=work_unit,
        revision=target,
        action="verify",
    )

    findings, resolved_casilla_ids, missing_required_casilla_ids, failures_by_finding_id = (
        _collect_verification_gate_findings(
            work_unit=work_unit,
            target=target,
            workflow_profile=workflow_profile,
            observation_repository=repos.observation,
            filing_repository=repos.filing,
            calculation_repository=cr_repo,
            verification_repository=vr_repo,
            transaction_repository=transaction_repository,
            iva_compensation_decision_repository=iva_compensation_decision_repository,
            cross_period_expected_member_sets=cross_period_expected_member_sets,
        )
    )
    _append_model_specific_findings(
        findings,
        failures_by_finding_id=failures_by_finding_id,
        work_unit=work_unit,
        target=target,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        observation_repository=repos.observation,
    )
    completeness, granted = _classify_verification_outcome(
        findings=findings,
        missing_required=missing_required_casilla_ids,
    )

    now = clock or _utc_now()
    report = _build_verification_report(
        calculation_revision_id=calculation_revision_id,
        findings=findings,
        resolved_casilla_ids=resolved_casilla_ids,
        missing_required_casilla_ids=missing_required_casilla_ids,
        completeness=completeness,
        granted=granted,
        actor=actor,
        run_at=now,
    )

    if granted:
        gate_engine = workflow_engine or _build_revision_workflow_engine(
            revision=target,
            work_unit=work_unit,
            profile=workflow_profile,
            actor=actor.strip(),
            clock=now,
            settings=settings,
        )
        _run_revision_workflow_gate(
            engine=gate_engine,
            profile=workflow_profile,
            work_unit=work_unit,
            today=now.date(),
            runs_dir=workflow_runs_dir,
            run_repository=repos.run,
            purpose=WorkflowPurpose.VERIFY,
        )

    # Persist the report regardless of outcome — failed attempts
    # are part of the audit trail.
    vr_repo.save(upsert_verification_report(vr_repo.load(), report))

    if granted:
        _persist_verified_revision_evidence(
            target=target,
            actor=actor,
            now=now,
            revisions=revisions,
            revisions_revision_id=revisions_revision_id,
            work_unit=work_unit,
            transaction_repository=transaction_repository,
            calculation_repository=cr_repo,
            participation_index_repository=participation_index_repository,
        )
        _repair_verified_revision_current_pointer(
            work_unit=work_unit,
            calculation_revision_id=calculation_revision_id,
            verified_at=now,
            work_unit_repository=wu_repo,
        )

    _emit_verification_bucket_event(
        repository=repos.bucket_event,
        work_unit=work_unit,
        target=target,
        report_id=report.verification_report_id,
        calculation_revision_id=calculation_revision_id,
        completeness=completeness,
        granted=granted,
        finding_count=len(findings),
        missing_required_count=len(missing_required_casilla_ids),
        actor=actor,
        occurred_at=now,
    )

    return ModeloVerificationResult(
        report=report,
        finding_preconditions=project_verification_findings(
            findings,
            failures_by_finding_id=failures_by_finding_id,
        ),
    )


def verify_modelo_revision(
    calculation_revision_id: CalculationRevisionId,
    *,
    actor: str,
    workflow_profile: TaxpayerProfile,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol | None = None,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol | None = None,
    filing_repository: ModeloRecordCatalogueRepositoryProtocol | None = None,
    transaction_repository: TransactionCatalogueRepository | None = None,
    verification_repository: VerificationReportCatalogueRepositoryProtocol | None = None,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol | None = None,
    iva_compensation_decision_repository: IvaWalletDecisionRepository | None = None,
    calculation_observation_repository: CalculationObservationRepository | None = None,
    participation_index_repository: TransactionParticipationIndexRepository | None = None,
    cross_period_expected_member_sets: Iterable[CrossPeriodExpectedMemberSet] = (),
    workflow_engine: WorkflowEngine | None = None,
    workflow_runs_dir: Path | None = None,
    settings: Settings | None = None,
    clock: datetime | None = None,
) -> VerificationReport:
    """Persist and return the domain verification report without transport recovery data.

    The thin arm over :func:`verify_modelo_revision_with_preconditions`, for
    callers that want the report and none of the transport-recovery envelope.
    It takes the same inputs the gates are evaluated against: the
    :class:`TaxpayerProfile` the workflow gate reads, and the
    :class:`TransactionCatalogueRepository` the ledger-derived casillas are
    reconciled from.
    """
    return verify_modelo_revision_with_preconditions(
        calculation_revision_id,
        actor=actor,
        workflow_profile=workflow_profile,
        work_unit_repository=work_unit_repository,
        calculation_repository=calculation_repository,
        filing_repository=filing_repository,
        transaction_repository=transaction_repository,
        verification_repository=verification_repository,
        bucket_event_repository=bucket_event_repository,
        iva_compensation_decision_repository=iva_compensation_decision_repository,
        calculation_observation_repository=calculation_observation_repository,
        participation_index_repository=participation_index_repository,
        cross_period_expected_member_sets=cross_period_expected_member_sets,
        workflow_engine=workflow_engine,
        workflow_runs_dir=workflow_runs_dir,
        settings=settings,
        clock=clock,
    ).report


def _repair_verified_revision_current_pointer(
    *,
    work_unit: WorkUnit,
    calculation_revision_id: CalculationRevisionId,
    verified_at: datetime,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol,
) -> None:
    work_units = work_unit_repository.load()
    latest = work_units.get(work_unit.work_unit_id)
    if latest is None:
        raise WorkUnitNotFoundError(
            translated_message="application.modelo.errors.work_unit_not_found",
            context={"work_unit_id": work_unit.work_unit_id, "phase": "verification"},
        )
    if latest.current_calculation_revision_id == calculation_revision_id:
        return
    if latest.current_calculation_revision_id is not None:
        return

    # Guarded: stamping this pointer rewrites the WHOLE singleton catalogue, so
    # a work unit another operator created or advanced in the interim would be
    # discarded by a repair that was only meant to fill in one pointer. The
    # already-set and absent checks above ran against the catalogue this call
    # read; re-running them inside the mutation is what makes the retry honest,
    # because a concurrent verification may have set the very pointer this
    # repair exists to fill.
    def _stamp(current: WorkUnitCatalogue) -> WorkUnitCatalogue:
        """Fill in the pointer, unless the catalogue being written already has one."""
        present = current.get(work_unit.work_unit_id)
        if present is None or present.current_calculation_revision_id is not None:
            return current
        return upsert_work_unit(
            current,
            present.model_copy(
                update={
                    "current_calculation_revision_id": calculation_revision_id,
                    "updated_at": verified_at,
                },
            ),
        )

    work_unit_repository.mutate(_stamp)


def _build_participation_writes(
    *,
    verified: CalculationRevision,
    work_unit: WorkUnit,
    participation_index_repository: TransactionParticipationIndexRepository,
) -> tuple[SecureObjectWrite, ...]:
    """Build the per-transaction participation-index co-emission writes.

    For each ``source_transaction_id`` of the verified revision, load that
    transaction's existing
    :class:`~TransactionRevisionParticipationIndex`, upsert
    the new ``VERIFICADO_COMPLETO`` participation (replacing any prior entry for
    the same revision), and return the resulting ``SecureObjectWrite`` so the
    caller co-emits them in the same atomic unit of work as the revision save. A
    revision with no contributing transactions yields no writes.
    """
    writes: list[SecureObjectWrite] = []
    for transaction_id in verified.source_transaction_ids:
        index = participation_index_repository.load(transaction_id)
        participation = TransactionRevisionParticipation(
            calculation_revision_id=verified.calculation_revision_id,
            work_unit_id=work_unit.work_unit_id,
            modelo=work_unit.modelo,
            filing_year=work_unit.filing_year,
            period=work_unit.period,
            revision_state=CalculationRevisionState.VERIFICADO_COMPLETO.value,
        )
        updated = upsert_transaction_participation(index, participation)
        writes.append(participation_index_repository.to_secure_object_write(updated))
    return tuple(writes)


def _persist_verified_revision_evidence(
    *,
    target: CalculationRevision,
    actor: str,
    now: datetime,
    revisions: CalculationRevisionCatalogue,
    revisions_revision_id: str,
    work_unit: WorkUnit,
    transaction_repository: TransactionCatalogueRepository | None,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol,
    participation_index_repository: TransactionParticipationIndexRepository | None,
) -> None:
    tx_repo = transaction_repository or TransactionCatalogueRepository(bucket_id=work_unit.bucket_id)
    catalogue = tx_repo.load()
    filing_snapshot = compute_ledger_filing_snapshot(
        source_transaction_ids=target.source_transaction_ids,
        catalogue=catalogue,
        captured_at=now,
    )
    evidence_legal_refs = (
        _normalised_observation_refs(target.observations, "legal_refs") if target.source_transaction_ids else ()
    )
    evidence_source_refs = (
        _normalised_observation_refs(target.observations, "source_refs") if target.source_transaction_ids else ()
    )
    filing_evidence = compute_ledger_filing_evidence(
        source_transaction_ids=target.source_transaction_ids,
        catalogue=catalogue,
        snapshot_fingerprint=filing_snapshot.snapshot_fingerprint,
        captured_at=now,
        legal_refs=evidence_legal_refs,
        source_refs=evidence_source_refs,
        manual_entries=_manual_fact_basis_entries(
            target.input_values_by_casilla_id,
            target.observations,
            m210_gross_income_source_mode=target.m210_gross_income_source_mode,
        ),
    )
    assert_evidence_covers_snapshot(filing_snapshot, filing_evidence)
    verified = target.model_copy(
        update={
            "state": CalculationRevisionState.VERIFICADO_COMPLETO,
            "verified_at": now,
            "verified_by": actor.strip(),
            "updated_at": now,
            "ledger_filing_snapshot": filing_snapshot,
            "ledger_filing_evidence": filing_evidence,
        },
    )
    updated_catalogue = upsert_calculation_revision(revisions, verified)
    participation_repo = participation_index_repository or TransactionParticipationIndexRepository(
        bucket_id=work_unit.bucket_id,
    )
    participation_writes = _build_participation_writes(
        verified=verified,
        work_unit=work_unit,
        participation_index_repository=participation_repo,
    )
    # Co-emit the participation index atomically with the revision save (per the
    # composition-service single-writer discipline): the index and the verified
    # revision land or fail together. A revision with no contributing
    # transactions produces no extra writes and degenerates to the plain save.
    calculation_repository.save_with_secure_object_writes(
        updated_catalogue,
        participation_writes,
        expected_revision_id=revisions_revision_id,
    )


def _emit_verification_bucket_event(
    *,
    repository: BucketEventHistoryRepositoryProtocol,
    work_unit: WorkUnit,
    target: CalculationRevision,
    report_id: str,
    calculation_revision_id: CalculationRevisionId,
    completeness: VerificationCompletenessStatus,
    granted: bool,
    finding_count: int,
    missing_required_count: int,
    actor: str,
    occurred_at: datetime,
) -> None:
    _emit_bucket_event(
        repository=repository,
        bucket_id=work_unit.bucket_id,
        event_type=(
            BucketEventType.MODELO_VERIFICATION_PASSED if granted else BucketEventType.MODELO_VERIFICATION_REFUSED
        ),
        occurred_at=occurred_at,
        actor=actor,
        object_type=BucketEventObjectType.VERIFICATION_REPORT,
        object_id=report_id,
        payload={
            "calculation_revision_id": calculation_revision_id,
            "work_unit_id": target.work_unit_id,
            "modelo": work_unit.modelo,
            "filing_year": str(work_unit.filing_year),
            "period": work_unit.period.registry_token,
            "completeness_status": completeness.value,
            "finding_count": str(finding_count),
            "missing_required_count": str(missing_required_count),
        },
    )


def _append_revision_advisory_findings(
    findings: list[ModeloVerificationFinding],
    *,
    work_unit: WorkUnit,
    target: CalculationRevision,
    profile: TaxpayerProfile,
    snapshot: RegistrySnapshot,
) -> None:
    for finding in (
        _dt12_reduccion_advisory_finding(snapshot.revision, target.casilla_values),
        _art20_reduccion_advisory_finding(snapshot.revision, target.casilla_values),
        _art52_reduccion_advisory_finding(snapshot.revision, target.casilla_values),
        _dt12_antiquity_advisory_finding(snapshot.revision, target.casilla_values),
        _madrid_nacimiento_adopcion_advisory_finding_for_work_unit(
            snapshot,
            target.casilla_values,
            work_unit=work_unit,
        ),
        _m210_convenio_lob_advisory_finding(snapshot, profile, target.input_values_by_casilla_id),
    ):
        if finding is not None:
            findings.append(finding)
    findings.extend(_objective_estimation_exclusion_advisory_findings(work_unit=work_unit, profile=profile))
    findings.extend(
        _attribution_received_omission_advisory_findings(
            work_unit=work_unit,
            snapshot=snapshot,
            casilla_values=target.casilla_values,
        )
    )


_OSS_AGGREGATION_SOURCE = BindingSourceKind.LEDGER_OSS_AGGREGATION


def _m369_unresolved_oss_source_finding(
    *,
    work_unit: WorkUnit,
    target: CalculationRevision,
    snapshot: RegistrySnapshot,
) -> ModeloVerificationFinding | None:
    """Block Modelo 369 verification when its OSS source remained unresolved.

    The calculate path deliberately persists a zero-valued draft and emits an
    ``oss_no_live_source`` diagnostic when no OSS/IOSS-tagged issued invoice can
    be projected. Diagnostics are operator-facing calculate results, so a
    non-consumed positive observation is retained on the revision as a typed
    source issue, while resolved candidates remain in the positive source-
    provenance trace. This preserves a real zero-valued invoice line while
    refusing both a silent claimed-zero catalogue and a line outside the form.
    """
    if str(work_unit.modelo) != Modelo.M369.value:
        return None
    oss_bindings = tuple(binding for binding in snapshot.revision.bindings if binding.source is _OSS_AGGREGATION_SOURCE)
    if not oss_bindings:
        return None
    legal_refs, source_refs = _oss_binding_grounding(oss_bindings)
    unrouted_issues = tuple(
        issue
        for issue in target.source_issues
        if issue.binding_source is _OSS_AGGREGATION_SOURCE and issue.reason == "unrouted_observation"
    )
    if unrouted_issues:
        return _unrouted_oss_source_finding(unrouted_issues, legal_refs=legal_refs, source_refs=source_refs)
    if any(ref.resolved_binding_source is _OSS_AGGREGATION_SOURCE for ref in target.source_provenance):
        return None
    return _missing_oss_evidence_finding(legal_refs=legal_refs, source_refs=source_refs)


def _oss_binding_grounding(
    oss_bindings: tuple[DataBindingDefinition, ...],
) -> tuple[tuple[LegalRefId, ...], tuple[SourceRefId, ...]]:
    """Collect the sorted legal_refs / source_refs declared across the OSS bindings."""
    legal_refs = tuple(sorted({ref for binding in oss_bindings for ref in binding.legal_refs}))
    source_refs = tuple(sorted({ref for binding in oss_bindings for ref in binding.source_refs}))
    return legal_refs, source_refs


def _unrouted_oss_source_finding(
    unrouted_issues: tuple[CalculationSourceIssue, ...],
    *,
    legal_refs: tuple[LegalRefId, ...],
    source_refs: tuple[SourceRefId, ...],
) -> ModeloVerificationFinding:
    """Build the blocking finding for OSS observations no aggregation binding consumes."""
    source_ref_ids = tuple(issue.source_ref for issue in unrouted_issues if issue.source_ref is not None)
    message_facts: dict[str, str | int | bool | Decimal] = {
        "source_ref_count": len(source_ref_ids),
        "unidentified_source_count": len(unrouted_issues) - len(source_ref_ids),
        # Unconditional for the same reason as ``binding_id`` above: the message
        # names the unrouted refs, and an issue set carrying none would
        # otherwise render the placeholder itself. Every unrouted issue lacking
        # a source_ref is already counted by ``unidentified_source_count``, so
        # the marker is what distinguishes "none of them could be identified"
        # from a blank id.
        "source_ref_ids": "|".join(source_ref_ids) if source_ref_ids else _ABSENT_FACT,
    }
    return ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.BLOCKING_RULE,
        severity=ModeloVerificationFindingSeverity.BLOCKING,
        message_locale_key="application.modelo.findings.oss_source_unrouted",
        message_facts=message_facts,
        legal_refs=legal_refs or WORKFLOW_GATE_LEGAL_REFS,
        source_refs=source_refs,
    )


def _missing_oss_evidence_finding(
    *,
    legal_refs: tuple[LegalRefId, ...],
    source_refs: tuple[SourceRefId, ...],
) -> ModeloVerificationFinding:
    """Build the blocking finding for a declared-OSS revision with no persisted OSS evidence."""
    return ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.BLOCKING_RULE,
        severity=ModeloVerificationFindingSeverity.BLOCKING,
        message_locale_key="application.modelo.findings.oss_evidence_missing",
        message_facts={},
        legal_refs=legal_refs or WORKFLOW_GATE_LEGAL_REFS,
        source_refs=source_refs,
    )


def _resolve_verification_snapshot(
    *,
    work_unit: WorkUnit,
    target: CalculationRevision,
    findings: list[ModeloVerificationFinding],
    failures_by_finding_id: dict[int, ModeloPreconditionFailure],
) -> RegistrySnapshot | None:
    from ...domain.calculations.registry.errors import (
        RegistrySnapshotError,
        RegistryValidationError,
    )

    try:
        authority = bundled_authority()
        return authority.snapshot(
            work_unit.modelo,
            filing_year=work_unit.filing_year,
            period=work_unit.period.registry_token,
        )
    except RegistryValidationError as exc:
        # A revision that resolves but declares less than filing authority is a
        # DIFFERENT operator situation from one that cannot be resolved, and it
        # reaches here as RegistryValidationError, which is not a subclass of
        # RegistrySnapshotError -- so without this clause the refusal escaped a
        # gate whose entire purpose is to enumerate why a revision is not fit to
        # file, and the operator got a traceback instead of a finding.
        classification = getattr(exc, "registry_failure", None)
        facts = dict(getattr(classification, "facts", {}) or {})
        finding = ModeloVerificationFinding(
            kind=ModeloVerificationFindingKind.BLOCKING_RULE,
            severity=ModeloVerificationFindingSeverity.BLOCKING,
            message_locale_key="application.modelo.findings.registry_authority_grade_insufficient",
            message_facts={
                "modelo": str(work_unit.modelo),
                "filing_year": work_unit.filing_year,
                "period": work_unit.period.registry_token,
                "declared_grade": str(facts.get("declared_authority_grade", "")),
                "requested_grade": str(facts.get("requested_authority_grade", "")),
            },
            legal_refs=WORKFLOW_GATE_LEGAL_REFS,
        )
        findings.append(finding)
        failures_by_finding_id[id(finding)] = build_verification_precondition_failure(
            calculation_revision_id=target.calculation_revision_id,
            work_unit_id=target.work_unit_id,
            condition_id="modelo.work.verify.registry_snapshot.filing_authority",
            scenario_id="modelo.work.verify.registry_snapshot.authority_grade_insufficient",
            evidence_id="modelo.work.verify.registry_snapshot",
            evidence_values={
                "modelo": str(work_unit.modelo),
                "year": work_unit.filing_year,
                "period": work_unit.period.registry_token,
                "declared_authority_grade": str(facts.get("declared_authority_grade", "")),
                "requested_authority_grade": str(facts.get("requested_authority_grade", "")),
            },
            provenance=ActionEvidenceProvenance.REGISTRY_RECORD,
        )
        return None
    except (FileNotFoundError, RegistrySnapshotError):
        finding = ModeloVerificationFinding(
            kind=ModeloVerificationFindingKind.BLOCKING_RULE,
            severity=ModeloVerificationFindingSeverity.BLOCKING,
            message_locale_key="application.modelo.findings.registry_snapshot_unresolved",
            message_facts={
                "modelo": str(work_unit.modelo),
                "filing_year": work_unit.filing_year,
                "period": work_unit.period.registry_token,
            },
            legal_refs=WORKFLOW_GATE_LEGAL_REFS,
        )
        findings.append(finding)
        failures_by_finding_id[id(finding)] = build_verification_precondition_failure(
            calculation_revision_id=target.calculation_revision_id,
            work_unit_id=target.work_unit_id,
            condition_id="modelo.work.verify.registry_snapshot.available",
            scenario_id="modelo.work.verify.registry_snapshot.unavailable",
            evidence_id="modelo.work.verify.registry_snapshot",
            evidence_values={
                "modelo": str(work_unit.modelo),
                "year": work_unit.filing_year,
                "period": work_unit.period.registry_token,
            },
            provenance=ActionEvidenceProvenance.REGISTRY_RECORD,
            action_id="operator.registry.verify",
        )
        return None


def _append_required_casilla_findings(
    *,
    work_unit: WorkUnit,
    target: CalculationRevision,
    snapshot: RegistrySnapshot,
    findings: list[ModeloVerificationFinding],
    resolved_casilla_ids: list[CasillaId],
    missing_required_casilla_ids: list[CasillaId],
    failures_by_finding_id: dict[int, ModeloPreconditionFailure],
) -> None:
    revision_keys = set(target.input_values_by_casilla_id)
    for casilla in snapshot.revision.casillas:
        if casilla.input_kind != InputKind.MANUAL or not casilla.required:
            continue
        if _detail_row_template_casilla_is_satisfied(work_unit=work_unit, target=target, casilla=casilla):
            resolved_casilla_ids.append(casilla.id)
            continue
        if casilla.id in revision_keys:
            resolved_casilla_ids.append(casilla.id)
            continue
        missing_required_casilla_ids.append(casilla.id)
        finding = _missing_required_casilla_finding(casilla.id, casilla_def=casilla)
        findings.append(finding)
        failures_by_finding_id[id(finding)] = build_verification_precondition_failure(
            calculation_revision_id=target.calculation_revision_id,
            work_unit_id=target.work_unit_id,
            condition_id="modelo.work.verify.required_casillas.complete",
            scenario_id="modelo.work.verify.required_casillas.missing",
            evidence_id="modelo.work.verify.required_casillas",
            evidence_values={
                "modelo": str(work_unit.modelo),
                "year": work_unit.filing_year,
                "period": work_unit.period.registry_token,
                "casilla_id": str(casilla.id),
            },
            provenance=ActionEvidenceProvenance.REGISTRY_RECORD,
        )


def _append_oss_verification_finding(
    *,
    work_unit: WorkUnit,
    target: CalculationRevision,
    snapshot: RegistrySnapshot,
    findings: list[ModeloVerificationFinding],
    failures_by_finding_id: dict[int, ModeloPreconditionFailure],
) -> None:
    oss_source_finding = _m369_unresolved_oss_source_finding(
        work_unit=work_unit,
        target=target,
        snapshot=snapshot,
    )
    if oss_source_finding is None:
        return
    findings.append(oss_source_finding)
    unrouted_issue_count = sum(
        1
        for issue in target.source_issues
        if issue.binding_source is _OSS_AGGREGATION_SOURCE and issue.reason == "unrouted_observation"
    )
    is_unrouted = unrouted_issue_count > 0
    failures_by_finding_id[id(oss_source_finding)] = build_verification_precondition_failure(
        calculation_revision_id=target.calculation_revision_id,
        work_unit_id=target.work_unit_id,
        condition_id=(
            "modelo.work.verify.oss_source.routed" if is_unrouted else "modelo.work.verify.oss_evidence.present"
        ),
        scenario_id=(
            "modelo.work.verify.oss_source.unrouted" if is_unrouted else "modelo.work.verify.oss_evidence.missing"
        ),
        evidence_id=("modelo.work.verify.oss_source" if is_unrouted else "modelo.work.verify.oss_evidence"),
        evidence_values={
            "modelo": str(work_unit.modelo),
            "unrouted_issue_count": unrouted_issue_count,
            "source_ref_count": len(oss_source_finding.source_refs),
        },
        provenance=ActionEvidenceProvenance.APPLICATION_STATE,
    )


def _append_registry_predicate_findings(
    *,
    work_unit: WorkUnit,
    target: CalculationRevision,
    snapshot: RegistrySnapshot,
    predicate_profile: TaxpayerProfile,
    findings: list[ModeloVerificationFinding],
    failures_by_finding_id: dict[int, ModeloPreconditionFailure],
) -> None:
    findings.extend(
        _evaluate_verification_predicates(
            snapshot.revision.verification_predicates,
            target.casilla_values,
            predicate_profile,
            target.input_values_by_casilla_id,
            blocking_finding_observer=lambda finding, predicate: failures_by_finding_id.__setitem__(
                id(finding),
                build_verification_precondition_failure(
                    calculation_revision_id=target.calculation_revision_id,
                    work_unit_id=target.work_unit_id,
                    condition_id="modelo.work.verify.registry_predicate.satisfied",
                    scenario_id="modelo.work.verify.registry_predicate.failed",
                    evidence_id="modelo.work.verify.registry_predicate",
                    evidence_values={"predicate_id": predicate.predicate_id},
                    provenance=ActionEvidenceProvenance.REGISTRY_RECORD,
                ),
            ),
        ),
    )


def _append_unresolved_outcome_findings(
    *,
    work_unit: WorkUnit,
    target: CalculationRevision,
    snapshot: RegistrySnapshot,
    predicate_profile: TaxpayerProfile,
    findings: list[ModeloVerificationFinding],
    failures_by_finding_id: dict[int, ModeloPreconditionFailure],
) -> None:
    findings.extend(
        _m210_unresolved_outcome_findings(
            target.unresolved_outcomes,
            profile=predicate_profile,
            snapshot=snapshot,
            year=work_unit.filing_year,
            tipo_renta="",
            blocking_finding_observer=lambda finding, outcome: failures_by_finding_id.__setitem__(
                id(finding),
                build_verification_precondition_failure(
                    calculation_revision_id=target.calculation_revision_id,
                    work_unit_id=target.work_unit_id,
                    condition_id="modelo.work.verify.m210.rate.resolved",
                    scenario_id="modelo.work.verify.m210.rate.unresolved",
                    evidence_id="modelo.work.verify.m210.rate",
                    evidence_values={
                        "reason_code": outcome.reason.value,
                        "tipo_renta": outcome.context.get("tipo_renta", ""),
                        "year": work_unit.filing_year,
                    },
                    provenance=ActionEvidenceProvenance.DOMAIN_EVALUATION,
                ),
            ),
        ),
    )


def _collect_revision_verification_findings(
    *,
    work_unit: WorkUnit,
    target: CalculationRevision,
    profile: TaxpayerProfile,
    transaction_repository: TransactionCatalogueRepository | None,
) -> tuple[
    list[ModeloVerificationFinding],
    list[CasillaId],
    list[CasillaId],
    dict[int, ModeloPreconditionFailure],
]:
    """Build the verification finding list for one calculation revision.

    Returns ``(findings, resolved_casilla_ids, missing_required_casilla_ids)``. A
    revision whose ``(modelo, year, period)`` triple does not resolve
    against the registry yields a single BLOCKING_RULE finding and
    empty resolved/missing lists — there is no per-casilla check to
    perform without a registry snapshot.

    With a snapshot present, the operator-supplied
    ``input_values_by_casilla_id`` keys are compared against the registry's
    required-input casilla set. Each missing required casilla
    produces a MISSING_REQUIRED_CASILLA finding plus an entry in the
    missing-required list; each present required casilla lands in
    the resolved-casilla-ids list.

    Registry-authored predicates are evaluated after required-input checks.
    ADVISORY findings are returned beside blocking findings so the report can
    expose non-silent under-declaration warnings without changing the grant rule.
    """
    findings: list[ModeloVerificationFinding] = []
    resolved_casilla_ids: list[CasillaId] = []
    missing_required_casilla_ids: list[CasillaId] = []
    failures_by_finding_id: dict[int, ModeloPreconditionFailure] = {}
    snapshot = _resolve_verification_snapshot(
        work_unit=work_unit,
        target=target,
        findings=findings,
        failures_by_finding_id=failures_by_finding_id,
    )
    if snapshot is None:
        return findings, resolved_casilla_ids, missing_required_casilla_ids, failures_by_finding_id

    _append_required_casilla_findings(
        work_unit=work_unit,
        target=target,
        snapshot=snapshot,
        findings=findings,
        resolved_casilla_ids=resolved_casilla_ids,
        missing_required_casilla_ids=missing_required_casilla_ids,
        failures_by_finding_id=failures_by_finding_id,
    )
    _append_oss_verification_finding(
        work_unit=work_unit,
        target=target,
        snapshot=snapshot,
        findings=findings,
        failures_by_finding_id=failures_by_finding_id,
    )
    predicate_profile = _profile_with_art109_period_evidence(
        work_unit=work_unit,
        profile=profile,
        transaction_repository=transaction_repository,
    )
    _append_registry_predicate_findings(
        work_unit=work_unit,
        target=target,
        snapshot=snapshot,
        predicate_profile=predicate_profile,
        findings=findings,
        failures_by_finding_id=failures_by_finding_id,
    )
    _append_unresolved_outcome_findings(
        work_unit=work_unit,
        target=target,
        snapshot=snapshot,
        predicate_profile=predicate_profile,
        findings=findings,
        failures_by_finding_id=failures_by_finding_id,
    )
    _append_revision_advisory_findings(
        findings,
        work_unit=work_unit,
        target=target,
        profile=profile,
        snapshot=snapshot,
    )
    return findings, resolved_casilla_ids, missing_required_casilla_ids, failures_by_finding_id


def _profile_with_art109_period_evidence(
    *,
    work_unit: WorkUnit,
    profile: TaxpayerProfile,
    transaction_repository: TransactionCatalogueRepository | None,
) -> TaxpayerProfile:
    coverage = _derive_art109_coverage(
        work_unit,
        transaction_repository=transaction_repository,
    )
    if not coverage.is_proven or coverage.meets_threshold is None:
        return profile
    return profile.model_copy(
        update={"art109_activity_income_withholding_ge_70pct": coverage.meets_threshold},
    )


def _detail_row_template_casilla_is_satisfied(
    *,
    work_unit: WorkUnit,
    target: CalculationRevision,
    casilla: CasillaDefinition,
) -> bool:
    if str(work_unit.modelo) != Modelo.M349.value or not casilla.section:
        return False
    section = str(casilla.section[0])
    if section == "operador":
        return any(getattr(row, "row_type", None) == "operador" for row in target.detail_rows)
    if section != "rectificacion":
        return False
    if any(getattr(row, "row_type", None) == "rectificacion" for row in target.detail_rows):
        return True
    return target.casilla_values.get(_M349_NUMERO_RECTIFICACIONES_CASILLA, Decimal("0")) == Decimal(
        "0"
    ) and target.casilla_values.get(_M349_IMPORTE_RECTIFICACIONES_CASILLA, Decimal("0")) == Decimal("0")


require_cross_period_clean_state = _require_cross_period_clean_state


def _missing_required_casilla_finding(
    casilla_id: CasillaId,
    *,
    casilla_def: CasillaDefinition | None = None,
) -> ModeloVerificationFinding:
    if casilla_def is None:
        raise ModeloValidationError(
            f"missing-required finding for casilla {casilla_id!r} requires registry casilla definition provenance",
        )
    legal_refs: tuple[str, ...] = tuple(str(r) for r in casilla_def.legal_refs)
    source_refs: tuple[str, ...] = tuple(str(r) for r in casilla_def.source_refs)
    if not legal_refs or not source_refs:
        raise ModeloValidationError(
            f"missing-required finding for casilla {casilla_id!r} requires legal_refs/source_refs provenance",
        )
    return ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.MISSING_REQUIRED_CASILLA,
        severity=ModeloVerificationFindingSeverity.BLOCKING,
        casilla_id=casilla_id,
        message_locale_key="application.modelo.findings.missing_required_casilla",
        message_facts={"casilla_id": str(casilla_id)},
        legal_refs=legal_refs,
        source_refs=source_refs,
    )


missing_required_casilla_finding = _missing_required_casilla_finding


def _iva_wallet_error_verification_finding(error: ModeloIvaWalletReconciliationBlocked) -> ModeloVerificationFinding:
    return ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.BLOCKING_RULE,
        severity=ModeloVerificationFindingSeverity.BLOCKING,
        casilla_id=M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA,
        message_locale_key="application.modelo.findings.iva_wallet_precondition_failed",
        message_facts={
            "condition_id": error.precondition_failure.verdict.failed_condition_id,
            "scenario_id": error.precondition_failure.scenario_id,
        },
        legal_refs=(_IVA_COMPENSATION_CARRY_LEGAL_REF,),
    )


def _classify_verification_outcome(
    *,
    findings: list[ModeloVerificationFinding],
    missing_required: list[CasillaId],
) -> tuple[VerificationCompletenessStatus, bool]:
    """Compute the completeness status + granted flag from finding shape.

    With no BLOCKING-severity finding, the report is COMPLETE and the
    verified-complete transition is granted, even if WARNING ADVISORY findings
    are present. With at least one BLOCKING_RULE finding, the report is BLOCKED.
    With BLOCKING findings that are exclusively MISSING_REQUIRED_CASILLA, the
    report is INCOMPLETE so the operator sees that completing the inputs unblocks
    the transition.
    """
    has_blocking = any(f.severity is ModeloVerificationFindingSeverity.BLOCKING for f in findings)
    if not has_blocking:
        return VerificationCompletenessStatus.COMPLETE, True
    has_blocking_rule = any(f.kind is ModeloVerificationFindingKind.BLOCKING_RULE for f in findings)
    if missing_required and not has_blocking_rule:
        return VerificationCompletenessStatus.INCOMPLETE, False
    return VerificationCompletenessStatus.BLOCKED, False
