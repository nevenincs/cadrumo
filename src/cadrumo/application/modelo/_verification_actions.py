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

See Also:
    :func:`~cadrumo.application.calculations.evaluate_cross_period_clean_state`:
        Shared cross-period gate used by verify, file, and export.
    :mod:`~cadrumo.application.modelo._calculation_diagnostics`:
        Calculate-path diagnostics that feed advisory observations before verify.
    :mod:`~cadrumo.domain.modelos`:
        Finding kind, severity, and completeness-status authority.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING

from ...adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ...adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ...adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ...adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ...adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from ...adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ...adapters.persistence.profile.participation_index import TransactionParticipationIndexRepository
from ...adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ...core import BindingSourceKind, M210GrossIncomeSourceMode, Modelo
from ...core.config import Settings
from ...core.i18n import tr
from ...core.time import now as _utc_now
from ...domain.buckets import BucketEventHistoryRepositoryProtocol, BucketEventObjectType, BucketEventType
from ...domain.calculations.registry import (
    CasillaDefinition,
    CasillaId,
    CasillaObservation,
    InputKind,
    RegistrySnapshot,
    derive_modelo_202_modality,
)
from ...domain.deadlines import TaxpayerProfile
from ...domain.modelos import (
    CalculationRevision,
    CalculationRevisionCatalogue,
    CalculationRevisionCatalogueRepositoryProtocol,
    CalculationRevisionState,
    LedgerFilingEvidence,
    LedgerFilingSnapshot,
    ManualFactBasisEntry,
    ModeloError,
    ModeloRecordCatalogueRepositoryProtocol,
    ModeloValidationError,
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
    TransactionRevisionParticipation,
    VerificationCompletenessStatus,
    VerificationReport,
    VerificationReportCatalogue,
    VerificationReportCatalogueRepositoryProtocol,
    WorkUnit,
    WorkUnitCatalogueRepositoryProtocol,
    derive_verification_report_id,
    upsert_calculation_revision,
    upsert_transaction_participation,
    upsert_verification_report,
    upsert_work_unit,
)
from ..aggregation import (
    MISSING_DEDUCTIBLE_VAT_EVIDENCE_SOURCE_KIND,
    CalculationSourceContext,
    CalculationSourceDiagnostic,
    OssIossLedgerSourceResolver,
    compute_ledger_filing_evidence,
    compute_ledger_filing_snapshot,
    missing_evidence_advisory_observations,
)
from ..calculations import CalculationObservationRepository, CrossPeriodExpectedMemberSet
from ..workflow import WorkflowEngine, WorkflowPurpose, WorkflowRunRepository
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
    iva_wallet_blocked_message as _iva_wallet_blocked_message,
)
from ._iva_wallet_gate import (
    require_persisted_iva_compensation_decision_matches_revision as _require_iva_compensation_revision_match,
)
from ._m210_agrupacion_renta import m210_agrupacion_renta_verification_findings
from ._m210_convenio_lob_advisory import _m210_convenio_lob_advisory_finding
from ._m303_m349_reconcile import m303_m349_intracom_reconcile_findings
from ._objective_estimation_advisory import _objective_estimation_exclusion_advisory_findings
from ._registry_helpers import assert_revision_content_integrity as _assert_revision_content_integrity
from ._registry_resources import authority_via_resources as _authority_via_resources
from ._required_binding_gate import (
    require_persisted_revision_required_bindings_resolved as _require_persisted_required_bindings_resolved,
)
from ._revision_persistence import emit_bucket_event as _emit_bucket_event
from ._verification_cross_period import (
    _CROSS_PERIOD_ACTIVITY_START_LEGAL_REFS as _CROSS_PERIOD_ACTIVITY_START_LEGAL_REFS,
)
from ._verification_cross_period import (
    _CROSS_PERIOD_DEPENDENCY_LEGAL_REFS as _CROSS_PERIOD_DEPENDENCY_LEGAL_REFS,
)
from ._verification_cross_period import (
    _IVA_COMPENSATION_CARRY_LEGAL_REF,
    _cross_period_clean_state_findings,
    _cross_period_clean_state_verdict_for_work_unit,
    _cross_period_expected_member_sets_from_profile,
    _modelo_202_incomplete_modality_finding,
    _require_cross_period_clean_state,
    _zero_value_previous_filing_binding_ids,
    derive_taxpayer_files_economic_activity,
)
from ._verification_cross_period import (
    _cross_period_clean_state_next_action as _cross_period_clean_state_next_action,
)
from ._verification_cross_period import (
    cross_period_expected_member_sets_from_profile as cross_period_expected_member_sets_from_profile,
)
from ._workflow_gate import build_revision_workflow_engine as _build_revision_workflow_engine
from ._workflow_gate import run_revision_workflow_gate as _run_revision_workflow_gate

if TYPE_CHECKING:
    from ...adapters.persistence.storage import SecureObjectWrite
    from ...domain.iva_compensation import IvaCompensationReconciliationDecision
    from ..calculations import IvaWalletDecisionRepository

from ._verification_predicates import (
    _BALANCE_CENT_TOLERANCE as _BALANCE_CENT_TOLERANCE,
)
from ._verification_predicates import (
    _M210_UNRESOLVED_RATE_REASONS as _M210_UNRESOLVED_RATE_REASONS,
)
from ._verification_predicates import (
    _M349_IMPORTE_RECTIFICACIONES_CASILLA as _M349_IMPORTE_RECTIFICACIONES_CASILLA,
)
from ._verification_predicates import (
    _M349_NUMERO_RECTIFICACIONES_CASILLA as _M349_NUMERO_RECTIFICACIONES_CASILLA,
)
from ._verification_predicates import (
    _PREDICATE_ADVISORY_WHEN_COMPUTED_DIVERGES as _PREDICATE_ADVISORY_WHEN_COMPUTED_DIVERGES,
)
from ._verification_predicates import (
    _PREDICATE_ADVISORY_WHEN_POSITIVE as _PREDICATE_ADVISORY_WHEN_POSITIVE,
)
from ._verification_predicates import (
    _PREDICATE_ADVISORY_WHEN_RATIO_GE as _PREDICATE_ADVISORY_WHEN_RATIO_GE,
)
from ._verification_predicates import (
    _PREDICATE_ALL_NONZERO as _PREDICATE_ALL_NONZERO,
)
from ._verification_predicates import (
    _PREDICATE_ANY_NONZERO as _PREDICATE_ANY_NONZERO,
)
from ._verification_predicates import (
    _PREDICATE_AT_MOST_ONE_POSITIVE as _PREDICATE_AT_MOST_ONE_POSITIVE,
)
from ._verification_predicates import (
    _PREDICATE_CAP_LE_WHEN_POSITIVE as _PREDICATE_CAP_LE_WHEN_POSITIVE,
)
from ._verification_predicates import (
    _PREDICATE_CASILLA_EQUALS_IMPLIES_DIVERGES as _PREDICATE_CASILLA_EQUALS_IMPLIES_DIVERGES,
)
from ._verification_predicates import (
    _PREDICATE_CASILLA_EQUALS_IMPLIES_NONZERO as _PREDICATE_CASILLA_EQUALS_IMPLIES_NONZERO,
)
from ._verification_predicates import (
    _PREDICATE_CASILLA_EQUALS_IMPLIES_PROFILE_FLAG as _PREDICATE_CASILLA_EQUALS_IMPLIES_PROFILE_FLAG,
)
from ._verification_predicates import (
    _PREDICATE_DEDUCCION_REQUIRES_ADQUISICION_BEFORE as _PREDICATE_DEDUCCION_REQUIRES_ADQUISICION_BEFORE,
)
from ._verification_predicates import (
    _PREDICATE_EQUALS as _PREDICATE_EQUALS,
)
from ._verification_predicates import (
    _PREDICATE_IMPLIES_ANY_NONZERO as _PREDICATE_IMPLIES_ANY_NONZERO,
)
from ._verification_predicates import (
    _PREDICATE_IMPLIES_NONZERO as _PREDICATE_IMPLIES_NONZERO,
)
from ._verification_predicates import (
    _PREDICATE_PROFILE_FIELD_REQUIRED as _PREDICATE_PROFILE_FIELD_REQUIRED,
)
from ._verification_predicates import (
    _PREDICATE_PROFILE_FLAG_ENABLED as _PREDICATE_PROFILE_FLAG_ENABLED,
)
from ._verification_predicates import (
    _PREDICATE_ROLL_FORWARD_BALANCES as _PREDICATE_ROLL_FORWARD_BALANCES,
)
from ._verification_predicates import (
    _evaluate_advisory_predicate_fires as _evaluate_advisory_predicate_fires,
)
from ._verification_predicates import (
    _evaluate_applicability_filter as _evaluate_applicability_filter,
)
from ._verification_predicates import (
    _evaluate_predicate_expression as _evaluate_predicate_expression,
)
from ._verification_predicates import (
    _evaluate_verification_predicates as _evaluate_verification_predicates,
)
from ._verification_predicates import (
    _m210_unresolved_outcome_findings as _m210_unresolved_outcome_findings,
)
from ._verification_predicates import (
    _parse_predicate_casilla_ids as _parse_predicate_casilla_ids,
)
from ._verification_predicates import (
    _parse_predicate_date as _parse_predicate_date,
)
from ._verification_predicates import (
    _parse_predicate_raw_tokens as _parse_predicate_raw_tokens,
)
from ._verification_predicates import (
    _resolve_advisory_message_default as _resolve_advisory_message_default,
)
from ._verification_predicates import (
    _resolve_predicate_next_action as _resolve_predicate_next_action,
)
from ._verification_predicates import (
    _roll_forward_balance_reconciles as _roll_forward_balance_reconciles,
)
from ._verification_predicates import (
    _validated_predicate_casilla_id as _validated_predicate_casilla_id,
)
from ._verification_predicates import (
    evaluate_advisory_predicate_fires as evaluate_advisory_predicate_fires,
)
from ._verification_predicates import (
    evaluate_predicate_expression as evaluate_predicate_expression,
)
from ._verification_predicates import (
    evaluate_verification_predicates as evaluate_verification_predicates,
)


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
        raise ModeloValidationError(f"ledger filing evidence requires non-empty observation {field_name}")
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


def _assert_evidence_covers_snapshot(snapshot: LedgerFilingSnapshot, evidence: LedgerFilingEvidence) -> None:
    """Guarantee the bundled evidence covers every fingerprinted contributor.

    The evidence and the fingerprint snapshot are projected from the same
    ``source_transaction_ids``; this invariant assertion makes a silent
    contributor omission impossible to ship — the evidence row set MUST equal the
    fingerprint row set.
    """
    snapshot_ids = {row.transaction_id for row in snapshot.rows}
    evidence_ids = {row.transaction_id for row in evidence.rows}
    if snapshot_ids != evidence_ids:
        missing = sorted(snapshot_ids - evidence_ids)
        extra = sorted(evidence_ids - snapshot_ids)
        raise ModeloError(
            f"ledger filing evidence does not cover the fingerprint snapshot: missing={missing} extra={extra}",
        )


#: Legal grounding for missing IVA evidence. Deducting input IVA requires the
#: original factura (LIVA art. 97, RD 1619/2012 art. 2). Output-IVA evidence
#: gaps stay advisory until the transaction model can distinguish every valid
#: issued-invoice support path without over-blocking.
_MISSING_EVIDENCE_LEGAL_REFS: tuple[str, ...] = (
    "ley-37-1992:art-97",
    "rd-1619-2012:art-2",
)


def _missing_evidence_findings(
    *,
    target: CalculationRevision,
    work_unit: WorkUnit,
    transaction_repository: TransactionCatalogueRepository | None,
) -> list[ModeloVerificationFinding]:
    """Build verification findings for evidence-less positive IVA rows.

    Loads the :class:`CalculationRevision` source transactions for the supplied
    :class:`WorkUnit` and
    projects each
    :class:`~cadrumo.application.aggregation.CalculationSourceDiagnostic`
    (reason ``missing_transaction_evidence``) into a
    :class:`ModeloVerificationFinding`. Deductible input-IVA and output-IVA gaps
    remain advisory on the verify path. A revision with no contributing
    transactions, or whose significant rows all carry evidence, yields no
    findings. Later filing/export finish lines may still refuse unsupported
    deductible IVA.
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
        is_deductible_gap = diagnostic.source_kind == MISSING_DEDUCTIBLE_VAT_EVIDENCE_SOURCE_KIND
        findings.append(
            ModeloVerificationFinding(
                kind=ModeloVerificationFindingKind.ADVISORY,
                severity=ModeloVerificationFindingSeverity.WARNING,
                message=diagnostic.message,
                next_action=(
                    f"Register the supplier invoice with `aeat app ledger evidence add PATH`, attach it with "
                    f"`aeat app ledger attach {diagnostic.binding_id} --purchase-invoice-evidence-id EVIDENCE_ID`, "
                    "then rerun verification."
                    if is_deductible_gap
                    else (
                        f"Advisory only: keep issued/sales invoice support for ledger row {diagnostic.binding_id}. "
                        "There is currently no dedicated public CLI path that mints issued-invoice evidence like "
                        "`aeat app ledger evidence add` does for purchase invoices. If you already have a secure "
                        "attachment id, link it with "
                        f"`aeat app ledger attach {diagnostic.binding_id} "
                        "--attachment-id ATTACHMENT_ID`, then rerun "
                        "verification."
                    )
                ),
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
    invoice_repository: InvoiceCatalogueRepository | None,
    iva_compensation_decision_repository: IvaWalletDecisionRepository | None,
    cross_period_expected_member_sets: Iterable[CrossPeriodExpectedMemberSet],
) -> tuple[list[ModeloVerificationFinding], list[CasillaId], list[CasillaId]]:
    findings, resolved_casilla_ids, missing_required_casilla_ids = _collect_revision_verification_findings(
        work_unit=work_unit,
        target=target,
        profile=workflow_profile,
        transaction_repository=transaction_repository,
        invoice_repository=invoice_repository,
    )
    incomplete_modality_finding = _modelo_202_incomplete_modality_finding(
        work_unit=work_unit,
        profile=workflow_profile,
    )
    if incomplete_modality_finding is not None:
        findings.append(incomplete_modality_finding)
    iva_compensation_decision = None
    try:
        iva_compensation_decision = _require_iva_compensation_revision_match(
            work_unit,
            target,
            repository=iva_compensation_decision_repository,
        )
    except ModeloIvaWalletReconciliationBlocked as exc:
        findings.append(_iva_wallet_error_verification_finding(exc))
    findings.extend(
        _cross_period_clean_state_findings(
            _cross_period_clean_state_verdict_for_work_unit(
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
            ),
            iva_compensation_decision=iva_compensation_decision,
            activity_start_date=workflow_profile.activity_start_date,
        ),
    )
    findings.extend(
        _missing_evidence_findings(
            target=target,
            work_unit=work_unit,
            transaction_repository=transaction_repository,
        ),
    )
    return findings, resolved_casilla_ids, missing_required_casilla_ids


def _existing_granting_verification_report(
    catalogue: VerificationReportCatalogue,
    calculation_revision_id: str,
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


def verify_modelo_revision(
    calculation_revision_id: str,
    *,
    actor: str,
    workflow_profile: TaxpayerProfile,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol | None = None,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol | None = None,
    filing_repository: ModeloRecordCatalogueRepositoryProtocol | None = None,
    transaction_repository: TransactionCatalogueRepository | None = None,
    invoice_repository: InvoiceCatalogueRepository | None = None,
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
        invoice_repository: Optional :class:`InvoiceCatalogueRepository` used
            to reconstruct legacy Modelo 369 OSS source resolution before the
            revision can be treated as filing-grade.
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
        The persisted :class:`VerificationReport`.

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
    cr_repo = calculation_repository or CalculationRevisionCatalogueRepository()
    wu_repo = work_unit_repository or WorkUnitCatalogueRepository()
    vr_repo = verification_repository or VerificationReportCatalogueRepository()
    fr_repo = filing_repository or ModeloRecordCatalogueRepository()
    obs_repo = calculation_observation_repository or CalculationObservationRepository()
    bv_repo = bucket_event_repository or BucketEventHistoryRepository()
    _secure_objects = bv_repo.secure_object_repository if isinstance(bv_repo, BucketEventHistoryRepository) else None
    run_repo = WorkflowRunRepository(objects=_secure_objects)

    revisions = cr_repo.load()
    target = revisions.get(calculation_revision_id)
    if target is None:
        raise CalculationRevisionNotFoundError(
            translated_message="application.modelo.errors.calculation_revision_not_found",
            context={"calculation_revision_id": calculation_revision_id},
        )
    if target.state is not CalculationRevisionState.BORRADOR:
        # Idempotent re-verify (single-subject-mutation-is-idempotent-guarded): a
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
            return existing
        raise CalculationRevisionStateError(
            f"calculation revision {calculation_revision_id!r} is in state "
            f"{target.state.value!r}; only DRAFT revisions can be verified",
        )

    _assert_revision_content_integrity(target)

    work_units = wu_repo.load()
    work_unit = work_units.get(target.work_unit_id)
    if work_unit is None:
        raise WorkUnitNotFoundError(
            f"calculation revision {calculation_revision_id!r} references missing work_unit_id={target.work_unit_id!r}",
        )
    from ._profile_readiness_gate import require_profile_ready_for_work_unit

    require_profile_ready_for_work_unit(work_unit)
    _require_persisted_required_bindings_resolved(
        work_unit=work_unit,
        revision=target,
        action="verify",
    )

    findings, resolved_casilla_ids, missing_required_casilla_ids = _collect_verification_gate_findings(
        work_unit=work_unit,
        target=target,
        workflow_profile=workflow_profile,
        observation_repository=obs_repo,
        filing_repository=fr_repo,
        calculation_repository=cr_repo,
        verification_repository=vr_repo,
        transaction_repository=transaction_repository,
        invoice_repository=invoice_repository,
        iva_compensation_decision_repository=iva_compensation_decision_repository,
        cross_period_expected_member_sets=cross_period_expected_member_sets,
    )
    findings.extend(
        m303_m349_intracom_reconcile_findings(
            work_unit=work_unit,
            target=target,
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
        ),
    )
    findings.extend(
        m210_agrupacion_renta_verification_findings(
            work_unit=work_unit,
            revision=target,
        ),
    )
    completeness, granted = _classify_verification_outcome(
        findings=findings,
        missing_required=missing_required_casilla_ids,
    )

    now = clock or _utc_now()
    report_id = derive_verification_report_id(
        calculation_revision_id=calculation_revision_id,
        completeness_status=completeness,
        findings=tuple(findings),
        verified_by=actor.strip(),
    )
    report = VerificationReport(
        verification_report_id=report_id,
        calculation_revision_id=calculation_revision_id,
        completeness_status=completeness,
        findings=tuple(findings),
        resolved_casilla_ids=tuple(resolved_casilla_ids),
        missing_required_casilla_ids=tuple(missing_required_casilla_ids),
        run_at=now,
        verified_by=actor.strip(),
        granted_verificado_completo=granted,
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
            run_repository=run_repo,
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
        repository=bv_repo,
        work_unit=work_unit,
        target=target,
        report_id=report_id,
        calculation_revision_id=calculation_revision_id,
        completeness=completeness,
        granted=granted,
        finding_count=len(findings),
        missing_required_count=len(missing_required_casilla_ids),
        actor=actor,
        occurred_at=now,
    )

    return report


def _repair_verified_revision_current_pointer(
    *,
    work_unit: WorkUnit,
    calculation_revision_id: str,
    verified_at: datetime,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol,
) -> None:
    work_units = work_unit_repository.load()
    latest = work_units.get(work_unit.work_unit_id)
    if latest is None:
        raise WorkUnitNotFoundError(f"work unit {work_unit.work_unit_id!r} disappeared during verification")
    if latest.current_calculation_revision_id == calculation_revision_id:
        return
    if latest.current_calculation_revision_id is not None:
        return
    work_unit_repository.save(
        upsert_work_unit(
            work_units,
            latest.model_copy(
                update={
                    "current_calculation_revision_id": calculation_revision_id,
                    "updated_at": verified_at,
                },
            ),
        ),
    )


def _build_participation_writes(
    *,
    verified: CalculationRevision,
    work_unit: WorkUnit,
    participation_index_repository: TransactionParticipationIndexRepository,
) -> tuple[SecureObjectWrite, ...]:
    """Build the per-transaction participation-index co-emission writes.

    For each ``source_transaction_id`` of the verified revision, load that
    transaction's existing
    :class:`~cadrumo.domain.modelos.TransactionRevisionParticipationIndex`, upsert
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
    _assert_evidence_covers_snapshot(filing_snapshot, filing_evidence)
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
    calculation_repository.save_with_secure_object_writes(updated_catalogue, participation_writes)


def _emit_verification_bucket_event(
    *,
    repository: BucketEventHistoryRepositoryProtocol,
    work_unit: WorkUnit,
    target: CalculationRevision,
    report_id: str,
    calculation_revision_id: str,
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
    invoice_repository: InvoiceCatalogueRepository | None,
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
    legal_refs = tuple(sorted({ref for binding in oss_bindings for ref in binding.legal_refs}))
    source_refs = tuple(sorted({ref for binding in oss_bindings for ref in binding.source_refs}))
    unrouted_issues = tuple(
        issue
        for issue in target.source_issues
        if issue.binding_source is _OSS_AGGREGATION_SOURCE and issue.reason == "unrouted_observation"
    )
    if unrouted_issues:
        unrouted_source_refs = ", ".join(issue.source_ref or "unidentified OSS source" for issue in unrouted_issues)
        return ModeloVerificationFinding(
            kind=ModeloVerificationFindingKind.BLOCKING_RULE,
            severity=ModeloVerificationFindingSeverity.BLOCKING,
            message=(
                "Modelo 369 has OSS/IOSS observations that no declared aggregation binding consumes; "
                f"unrouted source references: {unrouted_source_refs}"
            ),
            next_action=(
                "Correct the OSS/IOSS invoice classification or add its law-grounded registry binding, rerun "
                "`aeat app modelo work calculate`, then rerun verification."
            ),
            legal_refs=legal_refs or WORKFLOW_GATE_LEGAL_REFS,
            source_refs=source_refs,
        )
    if not target.source_resolution_assessed:
        legacy_resolution = OssIossLedgerSourceResolver(invoice_repository=invoice_repository).resolve(
            CalculationSourceContext(
                bucket_id=work_unit.bucket_id,
                modelo=str(work_unit.modelo),
                filing_year=work_unit.filing_year,
                period=work_unit.period,
                revision=snapshot.revision,
            ),
        )
        legacy_diagnostics = tuple(
            diagnostic
            for diagnostic in legacy_resolution.diagnostics
            if diagnostic.source_kind == _OSS_AGGREGATION_SOURCE.value
            and diagnostic.reason in {"unrouted_observation", "storage_degraded"}
        )
        if legacy_diagnostics:
            legacy_refs = ", ".join(diagnostic.source_ref or diagnostic.reason for diagnostic in legacy_diagnostics)
            return ModeloVerificationFinding(
                kind=ModeloVerificationFindingKind.BLOCKING_RULE,
                severity=ModeloVerificationFindingSeverity.BLOCKING,
                message=(
                    "Modelo 369 legacy OSS/IOSS source resolution cannot be confirmed; "
                    f"recalculate before verification (sources: {legacy_refs})"
                ),
                next_action=(
                    "Rerun `aeat app modelo work calculate` to persist current OSS/IOSS source resolution, "
                    "then rerun verification."
                ),
                legal_refs=legal_refs or WORKFLOW_GATE_LEGAL_REFS,
                source_refs=source_refs,
            )
        if any(ref.binding_source is _OSS_AGGREGATION_SOURCE for ref in target.source_provenance) and any(
            diagnostic.source_kind == _OSS_AGGREGATION_SOURCE.value and diagnostic.reason == "oss_no_live_source"
            for diagnostic in legacy_resolution.diagnostics
        ):
            return ModeloVerificationFinding(
                kind=ModeloVerificationFindingKind.BLOCKING_RULE,
                severity=ModeloVerificationFindingSeverity.BLOCKING,
                message=(
                    "Modelo 369 legacy OSS/IOSS source evidence is no longer available for verification; "
                    "recalculate before verification."
                ),
                next_action=(
                    "Restore or classify the OSS/IOSS issued invoice evidence, rerun "
                    "`aeat app modelo work calculate`, "
                    "then rerun verification."
                ),
                legal_refs=legal_refs or WORKFLOW_GATE_LEGAL_REFS,
                source_refs=source_refs,
            )
    if any(ref.binding_source is _OSS_AGGREGATION_SOURCE for ref in target.source_provenance):
        return None
    return ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.BLOCKING_RULE,
        severity=ModeloVerificationFindingSeverity.BLOCKING,
        message=(
            "Modelo 369 has unresolved OSS/IOSS aggregation sources: no OSS-tagged issued invoice evidence "
            "was persisted for a revision that declares ledger_oss_aggregation bindings."
        ),
        next_action=(
            "Record and classify the OSS/IOSS issued invoice evidence, rerun `aeat app modelo work calculate`, "
            "then rerun verification."
        ),
        legal_refs=legal_refs or WORKFLOW_GATE_LEGAL_REFS,
        source_refs=source_refs,
    )


def _collect_revision_verification_findings(
    *,
    work_unit: WorkUnit,
    target: CalculationRevision,
    profile: TaxpayerProfile,
    transaction_repository: TransactionCatalogueRepository | None,
    invoice_repository: InvoiceCatalogueRepository | None,
) -> tuple[list[ModeloVerificationFinding], list[CasillaId], list[CasillaId]]:
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

    from ...domain.calculations.registry import RegistrySnapshotError

    try:
        authority = _authority_via_resources()
        snapshot = authority.snapshot(
            work_unit.modelo,
            filing_year=work_unit.filing_year,
            period=work_unit.period.registry_token,
        )
    except (FileNotFoundError, RegistrySnapshotError):
        findings.append(
            ModeloVerificationFinding(
                kind=ModeloVerificationFindingKind.BLOCKING_RULE,
                severity=ModeloVerificationFindingSeverity.BLOCKING,
                message=tr(
                    "application.modelo.findings.registry_snapshot_unresolved",
                    modelo=str(work_unit.modelo),
                    filing_year=str(work_unit.filing_year),
                    period=work_unit.period.registry_token,
                ),
                next_action="aeat app registry verify",
                legal_refs=WORKFLOW_GATE_LEGAL_REFS,
            ),
        )
        return findings, resolved_casilla_ids, missing_required_casilla_ids

    revision_keys = set(target.input_values_by_casilla_id)
    for casilla in snapshot.revision.casillas:
        casilla_id = casilla.id
        if casilla.input_kind == InputKind.MANUAL and casilla.required:
            if _detail_row_template_casilla_is_satisfied(
                work_unit=work_unit,
                target=target,
                casilla=casilla,
            ):
                resolved_casilla_ids.append(casilla_id)
                continue
            if casilla_id in revision_keys:
                resolved_casilla_ids.append(casilla_id)
            else:
                missing_required_casilla_ids.append(casilla_id)
                findings.append(
                    _missing_required_casilla_finding(
                        casilla_id,
                        target.work_unit_id,
                        casilla_def=casilla,
                    ),
                )

    oss_source_finding = _m369_unresolved_oss_source_finding(
        work_unit=work_unit,
        target=target,
        snapshot=snapshot,
        invoice_repository=invoice_repository,
    )
    if oss_source_finding is not None:
        findings.append(oss_source_finding)

    predicate_profile = _profile_with_art109_period_evidence(
        work_unit=work_unit,
        profile=profile,
        transaction_repository=transaction_repository,
    )

    # Layer 2: cross-casilla predicate gate. target.input_values_by_casilla_id
    # carries the operator-entered raw strings (independent of the Decimal
    # casilla_values projection) for the text-reading operators
    # (casilla_equals_implies_nonzero categorical antecedent,
    # deduccion_requires_adquisicion_before date casillas); the other operators
    # ignore it.
    findings.extend(
        _evaluate_verification_predicates(
            snapshot.revision.verification_predicates,
            target.casilla_values,
            predicate_profile,
            target.input_values_by_casilla_id,
        ),
    )

    # Typed unresolved-outcome gate: the engine reports an unresolvable IRNR rate
    # beside the Decimal value channels (its casilla is omitted, not filled with a
    # sentinel). Convert each persisted outcome into a BLOCKING finding. The
    # consumer filters by reason, so the call is modelo-neutral: it no-ops for a
    # revision that carries no rate outcome. ``tipo_renta`` is left empty here so
    # the consumer reads it from the outcome's own captured context.
    findings.extend(
        _m210_unresolved_outcome_findings(
            target.unresolved_outcomes,
            profile=predicate_profile,
            snapshot=snapshot,
            year=work_unit.filing_year,
            tipo_renta="",
        ),
    )

    _append_revision_advisory_findings(
        findings,
        work_unit=work_unit,
        target=target,
        profile=profile,
        snapshot=snapshot,
    )

    return findings, resolved_casilla_ids, missing_required_casilla_ids


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
    work_unit_id: str,
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
        message=tr("application.modelo.findings.missing_required_casilla", casilla_id=casilla_id),
        next_action=(f"aeat app modelo work calculate {work_unit_id} --casilla {casilla_id}=VALUE"),
        legal_refs=legal_refs,
        source_refs=source_refs,
    )


missing_required_casilla_finding = _missing_required_casilla_finding


def _iva_wallet_blocking_verification_finding(
    decision: IvaCompensationReconciliationDecision,
) -> ModeloVerificationFinding:
    return ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.BLOCKING_RULE,
        severity=ModeloVerificationFindingSeverity.BLOCKING,
        message=_iva_wallet_blocked_message(decision),
        next_action=tr("application.modelo.findings.iva_wallet_next_action"),
        legal_refs=(_IVA_COMPENSATION_CARRY_LEGAL_REF,),
    )


iva_wallet_blocking_verification_finding = _iva_wallet_blocking_verification_finding


def _iva_wallet_error_verification_finding(error: ModeloIvaWalletReconciliationBlocked) -> ModeloVerificationFinding:
    return ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.BLOCKING_RULE,
        severity=ModeloVerificationFindingSeverity.BLOCKING,
        message=_translated_exception_message(error),
        next_action=tr("application.modelo.findings.iva_wallet_next_action"),
        legal_refs=(_IVA_COMPENSATION_CARRY_LEGAL_REF,),
    )


def _translated_exception_message(error: ModeloIvaWalletReconciliationBlocked) -> str:
    key = getattr(error, "translated_message", None)
    if isinstance(key, str) and key.strip() and key != "application.modelo.errors.iva_wallet_blocked":
        return tr(key)
    return str(error)


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
