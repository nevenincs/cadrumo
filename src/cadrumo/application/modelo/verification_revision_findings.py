"""Compose one revision’s registry, applicability, provenance, and advisory findings."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from ...core.aggregation import BindingSourceKind
from ...core.casilla_id import CasillaId
from ...core.operator_action_enums import ActionEvidenceProvenance
from ...domain.calculations.registry.schema import RegistrySnapshot
from ...domain.deadlines.models import TaxpayerProfile
from ...domain.modelos.calculation_revision import (
    CalculationRevision,
)
from ...domain.modelos.modelo_fact_context import ModeloFactResolutionContext
from ...domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from ...domain.modelos.work_unit import WorkUnit
from ...domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
from ..user_profile.projections import record_to_path_values
from ._art109_activity_income import derive_art109_activity_income_coverage_for_work_unit as _derive_art109_coverage
from ._attribution_received_advisory import _attribution_received_omission_advisory_findings
from ._autonomic_deduccion_advisory import madrid_nacimiento_adopcion_advisory_finding_for_work_unit
from ._m210_convenio_lob_advisory import _m210_convenio_lob_advisory_finding
from ._objective_estimation_advisory import _objective_estimation_exclusion_advisory_findings
from .action_errors import (
    WORKFLOW_GATE_LEGAL_REFS,
)
from .art20_advisory import art20_reduccion_advisory_finding
from .art52_advisory import art52_reduccion_advisory_finding
from .dt12_advisory import dt12_reduccion_advisory_finding
from .dt12_antiquity_advisory import dt12_antiquity_advisory_finding
from .preconditions import ModeloPreconditionFailure
from .verification_finding_contracts import (
    REGISTRY_SNAPSHOT_GRADE_INSUFFICIENT_SCENARIO,
    REGISTRY_SNAPSHOT_UNAVAILABLE_SCENARIO,
)
from .verification_iva_evidence import (
    append_iva_compensation_annual_source_evidence_finding,
    append_iva_selected_scope_evidence_finding,
)
from .verification_oss_evidence import m369_unresolved_oss_source_finding
from .verification_preconditions import (
    build_verification_precondition_failure,
)
from .verification_predicates import (
    evaluate_verification_predicates,
)
from .verification_report_facts import m210_unresolved_outcome_findings
from .verification_required_fields import append_required_casilla_findings, perceptor_clave_scope
from .withholding_detail_gate import append_withholding_detail_findings

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from ...domain.invoices.protocols import InvoiceCatalogueRepositoryProtocol
    from .work_profile import ModeloWorkProfile


def append_revision_advisory_findings(
    findings: list[ModeloVerificationFinding],
    *,
    work_unit: WorkUnit,
    target: CalculationRevision,
    profile: TaxpayerProfile,
    snapshot: RegistrySnapshot,
    operation: PinnedAuthorityOperation,
    work_profile: ModeloWorkProfile | None,
) -> None:
    """Append the selected revision’s model advisories without changing grant semantics.

    Parameter types: ``target`` (:class:`~cadrumo.domain.modelos.calculation_revision.CalculationRevision`),
    ``snapshot`` (:class:`~cadrumo.domain.calculations.registry.schema.RegistrySnapshot`), ``profile``
    (:class:`~cadrumo.domain.deadlines.models.TaxpayerProfile`).
    """
    fact_coordinate = date(work_unit.filing_year, 12, 31)
    modelo_fact_context = ModeloFactResolutionContext(
        authority=operation,
        filing_period=fact_coordinate,
        devengo_date=fact_coordinate,
    )
    for finding in (
        dt12_reduccion_advisory_finding(
            snapshot.revision,
            target.casilla_values,
            operation=operation,
        ),
        art20_reduccion_advisory_finding(
            snapshot.revision,
            target.casilla_values,
            context=modelo_fact_context,
        ),
        art52_reduccion_advisory_finding(
            snapshot.revision,
            target.casilla_values,
            operation=operation,
            modelo=str(work_unit.modelo),
        ),
        dt12_antiquity_advisory_finding(
            snapshot.revision,
            target.casilla_values,
            operation=operation,
            modelo=str(work_unit.modelo),
        ),
        madrid_nacimiento_adopcion_advisory_finding_for_work_unit(
            snapshot,
            target.casilla_values,
            work_unit=work_unit,
            operation=operation,
            profile=work_profile,
        ),
        _m210_convenio_lob_advisory_finding(
            snapshot,
            profile,
            target.input_values_by_casilla_id,
            devengo_date=fact_coordinate,
        ),
    ):
        if finding is not None:
            findings.append(finding)
    findings.extend(_objective_estimation_exclusion_advisory_findings(work_unit=work_unit, profile=profile))
    findings.extend(
        _attribution_received_omission_advisory_findings(
            work_unit=work_unit,
            snapshot=snapshot,
            casilla_values=target.casilla_values,
            profile_decode_context=operation.profile_decode_context(),
            profile_record=work_profile.record if work_profile is not None else None,
        )
    )


def resolve_verification_snapshot(
    *,
    work_unit: WorkUnit,
    target: CalculationRevision,
    findings: list[ModeloVerificationFinding],
    failures_by_finding_id: dict[int, ModeloPreconditionFailure],
    operation: PinnedAuthorityOperation,
) -> RegistrySnapshot | None:
    """Read the selected authority or retain its exact blocking refusal and precondition.

    Parameter types: ``target`` (:class:`~cadrumo.domain.modelos.calculation_revision.CalculationRevision`).
    """
    from ...domain.calculations.registry.errors import (
        RegistrySnapshotError,
        RegistryValidationError,
    )

    try:
        return operation.snapshot(
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
            scenario_id=REGISTRY_SNAPSHOT_GRADE_INSUFFICIENT_SCENARIO,
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
            scenario_id=REGISTRY_SNAPSHOT_UNAVAILABLE_SCENARIO,
            evidence_id="modelo.work.verify.registry_snapshot",
            evidence_values={
                "modelo": str(work_unit.modelo),
                "year": work_unit.filing_year,
                "period": work_unit.period.registry_token,
            },
            provenance=ActionEvidenceProvenance.REGISTRY_RECORD,
        )
        return None


def append_oss_verification_finding(
    *,
    work_unit: WorkUnit,
    target: CalculationRevision,
    snapshot: RegistrySnapshot,
    findings: list[ModeloVerificationFinding],
    failures_by_finding_id: dict[int, ModeloPreconditionFailure],
) -> None:
    """Append unresolved OSS source evidence to the current revision findings.

    Parameter types: ``target`` (:class:`~cadrumo.domain.modelos.calculation_revision.CalculationRevision`),
    ``snapshot`` (:class:`~cadrumo.domain.calculations.registry.schema.RegistrySnapshot`).
    """
    oss_source_finding = m369_unresolved_oss_source_finding(
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
        if issue.binding_source is BindingSourceKind.LEDGER_OSS_AGGREGATION and issue.reason == "unrouted_observation"
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


def append_registry_predicate_findings(
    *,
    work_unit: WorkUnit,
    target: CalculationRevision,
    snapshot: RegistrySnapshot,
    predicate_profile: TaxpayerProfile,
    findings: list[ModeloVerificationFinding],
    failures_by_finding_id: dict[int, ModeloPreconditionFailure],
) -> None:
    """Append registry predicates with their exact blocking preconditions.

    Parameter types: ``target`` (:class:`~cadrumo.domain.modelos.calculation_revision.CalculationRevision`),
    ``snapshot`` (:class:`~cadrumo.domain.calculations.registry.schema.RegistrySnapshot`), ``predicate_profile``
    (:class:`~cadrumo.domain.deadlines.models.TaxpayerProfile`).
    """
    findings.extend(
        evaluate_verification_predicates(
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


def append_unresolved_outcome_findings(
    *,
    work_unit: WorkUnit,
    target: CalculationRevision,
    snapshot: RegistrySnapshot,
    predicate_profile: TaxpayerProfile,
    findings: list[ModeloVerificationFinding],
    failures_by_finding_id: dict[int, ModeloPreconditionFailure],
) -> None:
    """Append unresolved calculation outcomes and their required operator preconditions.

    Parameter types: ``target`` (:class:`~cadrumo.domain.modelos.calculation_revision.CalculationRevision`),
    ``snapshot`` (:class:`~cadrumo.domain.calculations.registry.schema.RegistrySnapshot`), ``predicate_profile``
    (:class:`~cadrumo.domain.deadlines.models.TaxpayerProfile`).
    """
    findings.extend(
        m210_unresolved_outcome_findings(
            target.unresolved_outcomes,
            profile=predicate_profile,
            snapshot=snapshot,
            year=work_unit.filing_year,
            devengo_date=date(work_unit.filing_year, 12, 31),
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


def collect_revision_verification_findings(
    *,
    work_unit: WorkUnit,
    target: CalculationRevision,
    profile: TaxpayerProfile,
    transaction_repository: TransactionCatalogueRepositoryProtocol,
    invoice_repository: InvoiceCatalogueRepositoryProtocol,
    operation: PinnedAuthorityOperation,
    work_profile: ModeloWorkProfile | None,
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

    Parameter types: ``target`` (:class:`~cadrumo.domain.modelos.calculation_revision.CalculationRevision`), ``profile``
    (:class:`~cadrumo.domain.deadlines.models.TaxpayerProfile`).
    """
    findings: list[ModeloVerificationFinding] = []
    resolved_casilla_ids: list[CasillaId] = []
    missing_required_casilla_ids: list[CasillaId] = []
    failures_by_finding_id: dict[int, ModeloPreconditionFailure] = {}
    snapshot = resolve_verification_snapshot(
        work_unit=work_unit,
        target=target,
        findings=findings,
        failures_by_finding_id=failures_by_finding_id,
        operation=operation,
    )
    if snapshot is None:
        return findings, resolved_casilla_ids, missing_required_casilla_ids, failures_by_finding_id

    append_required_casilla_findings(
        work_unit=work_unit,
        target=target,
        snapshot=snapshot,
        findings=findings,
        resolved_casilla_ids=resolved_casilla_ids,
        missing_required_casilla_ids=missing_required_casilla_ids,
        failures_by_finding_id=failures_by_finding_id,
        clave_scope=perceptor_clave_scope(work_unit, operation=operation),
    )
    append_iva_selected_scope_evidence_finding(
        work_unit=work_unit,
        target=target,
        transaction_repository=transaction_repository,
        findings=findings,
        failures_by_finding_id=failures_by_finding_id,
    )
    append_iva_compensation_annual_source_evidence_finding(
        work_unit=work_unit,
        target=target,
        findings=findings,
        failures_by_finding_id=failures_by_finding_id,
    )
    append_oss_verification_finding(
        work_unit=work_unit,
        target=target,
        snapshot=snapshot,
        findings=findings,
        failures_by_finding_id=failures_by_finding_id,
    )
    append_withholding_detail_findings(
        work_unit=work_unit,
        target=target,
        snapshot=snapshot,
        invoice_repository=invoice_repository,
        transaction_repository=transaction_repository,
        profile_path_values=record_to_path_values(work_profile.record) if work_profile is not None else None,
        operation=operation,
        findings=findings,
        failures_by_finding_id=failures_by_finding_id,
    )
    predicate_profile = profile_with_art109_period_evidence(
        work_unit=work_unit,
        profile=profile,
        transaction_repository=transaction_repository,
    )
    append_registry_predicate_findings(
        work_unit=work_unit,
        target=target,
        snapshot=snapshot,
        predicate_profile=predicate_profile,
        findings=findings,
        failures_by_finding_id=failures_by_finding_id,
    )
    append_unresolved_outcome_findings(
        work_unit=work_unit,
        target=target,
        snapshot=snapshot,
        predicate_profile=predicate_profile,
        findings=findings,
        failures_by_finding_id=failures_by_finding_id,
    )
    append_revision_advisory_findings(
        findings,
        work_unit=work_unit,
        target=target,
        profile=profile,
        snapshot=snapshot,
        operation=operation,
        work_profile=work_profile,
    )
    return findings, resolved_casilla_ids, missing_required_casilla_ids, failures_by_finding_id


def profile_with_art109_period_evidence(
    *,
    work_unit: WorkUnit,
    profile: TaxpayerProfile,
    transaction_repository: TransactionCatalogueRepositoryProtocol,
) -> TaxpayerProfile:
    """Add the work unit’s grounded period-income evidence to the retained profile.

    Parameter types: ``profile`` (:class:`~cadrumo.domain.deadlines.models.TaxpayerProfile`).
    """
    coverage = _derive_art109_coverage(
        work_unit,
        transaction_repository=transaction_repository,
    )
    if not coverage.is_proven or coverage.meets_threshold is None:
        return profile
    return profile.model_copy(
        update={"art109_activity_income_withholding_ge_70pct": coverage.meets_threshold},
    )
