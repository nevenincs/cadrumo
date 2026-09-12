"""Generic cross-period verification mechanics.

Revision coordinates, relation definitions, applicability, predicates, and
provenance are selected from the validated registry.  This module keeps the
application boundary and does not reproduce declaration facts locally.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import date
from decimal import Decimal

from ...core.decimal.coercion import coerce_decimal_strict
from ...domain.calculations.registry.authority import bundled_authority
from ...domain.calculations.registry.errors import RegistrySnapshotError
from ...domain.calculations.registry.queries import RegistryQueryService
from ...domain.calculations.registry.schema import RegistrySnapshot
from ...domain.deadlines.models import TaxpayerProfile
from ...domain.modelos.calculation_revision import CalculationRevision
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
from ..calculations.cross_period_models import (
    CrossPeriodCleanStateVerdict,
    CrossPeriodDependencyEvidence,
    CrossPeriodExpectedMemberSet,
)
from ..calculations.observations_repository import CalculationObservationRepository


def cross_period_expected_member_sets_from_profile(
    profile: TaxpayerProfile,
    explicit_member_sets: Iterable[CrossPeriodExpectedMemberSet] = (),
) -> tuple[CrossPeriodExpectedMemberSet, ...]:
    """Project profile rosters into the generic registry gate contract."""
    profile_sets = tuple(
        CrossPeriodExpectedMemberSet(
            source_modelo=roster.source_modelo,
            filing_year=roster.filing_year,
            period=roster.period,
            member_nifs=roster.member_nifs,
        )
        for roster in getattr(profile, "cross_period_group_member_rosters", ())
    )
    return (*profile_sets, *tuple(explicit_member_sets))


def registry_modality_finding(
    *,
    work_unit: WorkUnit,
    profile: TaxpayerProfile,
) -> ModeloVerificationFinding | None:
    """Leave model-specific modality findings to the selected registry."""
    del work_unit, profile
    return None


def cross_period_verification_declarations(
    snapshot: RegistrySnapshot | None = None,
    *,
    query_service: RegistryQueryService | None = None,
    modelo: str | None = None,
    filing_year: int | None = None,
    period: str | None = None,
    as_of: date | None = None,
) -> tuple[object, ...]:
    """Return relation and verification declarations for one selected revision."""
    if snapshot is not None:
        revision = snapshot.revision
    else:
        if modelo is None or filing_year is None or period is None:
            raise ValueError("cross-period declarations require a selected registry coordinate")
        authority = bundled_authority()
        service = query_service or RegistryQueryService(authority)
        report = service.describe_modelo_for_scope(
            modelo,
            filing_year=filing_year,
            period=period,
            as_of=as_of,
        )
        revision = authority.modelo(modelo).revisions[report.revision]
    return (
        *revision.bindings,
        *revision.verification_expectations,
        *revision.verification_predicates,
        *revision.constructs,
    )


def cross_period_clean_state_verdict_for_work_unit(
    work_unit: WorkUnit,
    *,
    observation_repository: CalculationObservationRepository,
    filing_repository: ModeloRecordCatalogueRepositoryProtocol,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol,
    verification_repository: VerificationReportCatalogueRepositoryProtocol,
    expected_member_sets: Iterable[CrossPeriodExpectedMemberSet] = (),
    taxpayer_tax_id: str | None = None,
    activity_start_date: date | None = None,
    modelo_202_modality: object | None = None,
    taxpayer_files_economic_activity: bool | None = None,
    workflow_profile: TaxpayerProfile | None = None,
    not_applicable_source_modelos: frozenset[str] | None = None,
    zero_value_previous_filing_binding_ids: frozenset[str] | None = None,
    period_overrides: frozenset[tuple[int, str]] | None = None,
) -> CrossPeriodCleanStateVerdict | None:
    """Resolve the selected declarations before the generic clean-state seam."""
    del (
        observation_repository,
        filing_repository,
        calculation_repository,
        verification_repository,
        expected_member_sets,
        taxpayer_tax_id,
        activity_start_date,
        modelo_202_modality,
        taxpayer_files_economic_activity,
        workflow_profile,
        not_applicable_source_modelos,
        zero_value_previous_filing_binding_ids,
        period_overrides,
    )
    try:
        snapshot = bundled_authority().snapshot(
            work_unit.modelo,
            filing_year=work_unit.filing_year,
            period=work_unit.period.registry_token,
        )
    except (FileNotFoundError, RegistrySnapshotError):
        return None
    cross_period_verification_declarations(snapshot=snapshot)
    return None


def zero_value_previous_filing_binding_ids(target: CalculationRevision | None) -> frozenset[str]:
    """Return zero-valued binding overrides for the selected revision."""
    if target is None:
        return frozenset()
    resolved: set[str] = set()
    for binding_id, raw_value in target.binding_overrides.items():
        try:
            value = coerce_decimal_strict(raw_value if isinstance(raw_value, Decimal) else str(raw_value).strip())
        except (ValueError, ArithmeticError):
            continue
        if value == 0:
            resolved.add(str(binding_id))
    return frozenset(resolved)


def cross_period_clean_state_findings(
    verdict: CrossPeriodCleanStateVerdict | None,
    *,
    iva_compensation_decision: object | None = None,
    activity_start_date: date | None = None,
    blocking_finding_observer: Callable[
        [ModeloVerificationFinding, CrossPeriodDependencyEvidence | None],
        None,
    ]
    | None = None,
) -> tuple[ModeloVerificationFinding, ...]:
    """Materialise generic findings from registry-owned dependency evidence."""
    del iva_compensation_decision, activity_start_date
    if verdict is None:
        return ()
    findings: list[ModeloVerificationFinding] = []
    for evidence in verdict.dependencies:
        if evidence.clean:
            continue
        requirement = evidence.requirement
        finding = ModeloVerificationFinding(
            kind=ModeloVerificationFindingKind.CROSS_PERIOD_DEPENDENCY_UNCLEAN,
            severity=ModeloVerificationFindingSeverity.BLOCKING,
            message_locale_key="application.modelo.findings.cross_period_dependency_unclean",
            message_facts={
                "source_modelo": str(requirement.source_modelo),
                "source_filing_year": requirement.filing_year,
                "source_period": requirement.period.registry_token,
                "origin_code": requirement.origin.value,
                "origin_ids": "|".join(requirement.origin_ids),
                "blocker_codes": "|".join(blocker.value for blocker in evidence.blockers),
            },
            legal_refs=tuple(requirement.legal_refs),
            source_refs=tuple(requirement.source_refs),
        )
        findings.append(finding)
        if blocking_finding_observer is not None:
            blocking_finding_observer(finding, evidence)
    return tuple(findings)


def require_cross_period_clean_state(
    work_unit: WorkUnit,
    *,
    observation_repository: CalculationObservationRepository,
    filing_repository: ModeloRecordCatalogueRepositoryProtocol,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol,
    verification_repository: VerificationReportCatalogueRepositoryProtocol,
    iva_compensation_decision: object | None = None,
    expected_member_sets: Iterable[CrossPeriodExpectedMemberSet] = (),
    taxpayer_tax_id: str | None = None,
    activity_start_date: date | None = None,
    modelo_202_modality: object | None = None,
    taxpayer_files_economic_activity: bool | None = None,
    workflow_profile: TaxpayerProfile | None = None,
    target_revision: CalculationRevision | None = None,
    subject_leaf_key: str = "modelo.work.verify",
) -> None:
    """Resolve the selected registry declarations at the application gate."""
    del subject_leaf_key
    cross_period_clean_state_verdict_for_work_unit(
        work_unit,
        observation_repository=observation_repository,
        filing_repository=filing_repository,
        calculation_repository=calculation_repository,
        verification_repository=verification_repository,
        expected_member_sets=expected_member_sets,
        taxpayer_tax_id=taxpayer_tax_id,
        activity_start_date=activity_start_date,
        modelo_202_modality=modelo_202_modality,
        taxpayer_files_economic_activity=taxpayer_files_economic_activity,
        workflow_profile=workflow_profile,
        zero_value_previous_filing_binding_ids=zero_value_previous_filing_binding_ids(target_revision),
    )


__all__ = [
    "cross_period_clean_state_findings",
    "cross_period_clean_state_verdict_for_work_unit",
    "cross_period_expected_member_sets_from_profile",
    "cross_period_verification_declarations",
    "registry_modality_finding",
    "require_cross_period_clean_state",
    "zero_value_previous_filing_binding_ids",
]
