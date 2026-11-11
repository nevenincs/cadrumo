"""Generic cross-period verification mechanics.

Revision coordinates, relation definitions, applicability, predicates, and
provenance are selected from the validated registry.  This module keeps the
application boundary and does not reproduce declaration facts locally.

Core types:
:class:`~cadrumo.domain.calculations.registry.schema.RegistrySnapshot`.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Final, Literal

from cadrumo.application.calculations.observations_repository import CalculationObservationRepositoryProtocol

from ...core.authority_grade import RegistryAuthorityGrade
from ...core.decimal.coercion import coerce_decimal_strict
from ...core.operator_action_enums import ActionEvidenceProvenance
from ...domain.calculations.registry.applicability import derive_modelo_applicability
from ...domain.calculations.registry.applicability_modelo202 import Modelo202Modality
from ...domain.calculations.registry.applicability_models import ApplicabilityVerdict
from ...domain.calculations.registry.authority import bundled_indexed_authority
from ...domain.calculations.registry.errors import RegistrySnapshotError, RegistryValidationError
from ...domain.calculations.registry.form_codes import form_for_role
from ...domain.calculations.registry.ids import LegalRefId, SourceRefId
from ...domain.calculations.registry.schema import RegistrySnapshot
from ...domain.deadlines.models import TaxpayerProfile
from ...domain.justificante.protocols import JustificanteRepositoryProtocol
from ...domain.modelos.calculation_revision import CalculationRevision, CalculationRevisionCatalogue
from ...domain.modelos.filing_record import ModeloRecordCatalogue
from ...domain.modelos.protocols import (
    CalculationRevisionCatalogueRepositoryProtocol,
    ModeloRecordCatalogueRepositoryProtocol,
    VerificationReportCatalogueRepositoryProtocol,
)
from ...domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
    VerificationReportCatalogue,
)
from ...domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue
from ...domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol
from ..calculations.cross_period_clean_state import evaluate_cross_period_clean_state
from ..calculations.cross_period_models import (
    CrossPeriodCleanStateBlocker,
    CrossPeriodCleanStateVerdict,
    CrossPeriodDependencyEvidence,
    CrossPeriodDependencyOrigin,
    CrossPeriodDependencyRequirement,
    CrossPeriodExpectedMemberSet,
    OperatorAttestedValue,
)
from ..calculations.m111_no_retenciones import m111_no_retenciones_periods_from_profile_values
from ..user_profile.projections import profile_path_values_for_bucket
from .action_errors import ModeloCrossPeriodCleanStateError
from .preconditions import (
    ModeloPreconditionFailure,
    build_modelo_precondition_failure,
    build_modelo_precondition_failure_for_scenario,
)
from .reconciliation_sources import ReconciliationSourceNeed, source_declaration_need

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation


def cross_period_expected_member_sets_from_profile(
    profile: TaxpayerProfile,
    explicit_member_sets: Iterable[CrossPeriodExpectedMemberSet] = (),
) -> tuple[CrossPeriodExpectedMemberSet, ...]:
    """Project profile rosters into the generic registry gate contract.

    Core types:
    :class:`~cadrumo.domain.deadlines.models.TaxpayerProfile`.
    """
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
    """Leave model-specific modality findings to the selected registry.

    Core types:
    :class:`~cadrumo.domain.deadlines.models.TaxpayerProfile`.
    """
    del work_unit, profile
    return None


def cross_period_clean_state_verdict_for_work_unit(
    work_unit: WorkUnit,
    *,
    observation_repository: CalculationObservationRepositoryProtocol,
    filing_repository: ModeloRecordCatalogueRepositoryProtocol,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol,
    verification_repository: VerificationReportCatalogueRepositoryProtocol,
    justificante_repository: JustificanteRepositoryProtocol,
    calculation_catalogue: CalculationRevisionCatalogue | None = None,
    filing_catalogue: ModeloRecordCatalogue | None = None,
    verification_catalogue: VerificationReportCatalogue | None = None,
    expected_member_sets: Iterable[CrossPeriodExpectedMemberSet] = (),
    taxpayer_tax_id: str | None = None,
    activity_start_date: date | None = None,
    modelo_202_modality: Modelo202Modality | None = None,
    taxpayer_files_economic_activity: bool | None = None,
    workflow_profile: TaxpayerProfile | None = None,
    not_applicable_source_modelos: frozenset[str] | None = None,
    zero_value_previous_filing_binding_ids: frozenset[str] | None = None,
    m111_no_retenciones_periods: frozenset[tuple[int, str]] | None = None,
    operator_value_attestations: Mapping[str, OperatorAttestedValue] | None = None,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol | None = None,
    operation: PinnedAuthorityOperation | None = None,
) -> CrossPeriodCleanStateVerdict | None:
    """Evaluate the registry-declared cross-period dependencies of one work unit.

    Returns ``None`` only when the work unit's coordinate selects no registry
    revision; every selected revision is evaluated against the stored prior
    filings, observations, and justificantes. When the caller supplies no
    ``not_applicable_source_modelos`` but does supply ``workflow_profile``, the
    revision's economic-activity-conditional sources the profile positively
    excludes (Modelo 130 or 131, RIRPF art. 110) are scoped out.

    Core types:
    :class:`~cadrumo.domain.deadlines.models.TaxpayerProfile`.
    """
    if operation is None:
        with bundled_indexed_authority().operation() as indexed_operation:
            return cross_period_clean_state_verdict_for_work_unit(
                work_unit,
                observation_repository=observation_repository,
                filing_repository=filing_repository,
                calculation_repository=calculation_repository,
                verification_repository=verification_repository,
                justificante_repository=justificante_repository,
                calculation_catalogue=calculation_catalogue,
                filing_catalogue=filing_catalogue,
                verification_catalogue=verification_catalogue,
                expected_member_sets=expected_member_sets,
                taxpayer_tax_id=taxpayer_tax_id,
                activity_start_date=activity_start_date,
                modelo_202_modality=modelo_202_modality,
                taxpayer_files_economic_activity=taxpayer_files_economic_activity,
                not_applicable_source_modelos=not_applicable_source_modelos,
                workflow_profile=workflow_profile,
                zero_value_previous_filing_binding_ids=zero_value_previous_filing_binding_ids,
                m111_no_retenciones_periods=m111_no_retenciones_periods,
                operator_value_attestations=operator_value_attestations,
                work_unit_repository=work_unit_repository,
                operation=indexed_operation,
            )
    try:
        snapshot = operation.snapshot(
            work_unit.modelo,
            filing_year=work_unit.filing_year,
            period=work_unit.period.registry_token,
            grade=RegistryAuthorityGrade.CALCULATION,
        )
    except (FileNotFoundError, RegistrySnapshotError):
        return None
    if not_applicable_source_modelos is None and workflow_profile is not None:
        not_applicable_source_modelos = _not_applicable_conditional_source_modelos(
            snapshot,
            workflow_profile,
            operation=operation,
        )
    if m111_no_retenciones_periods is None:
        # Only the taxpayer's explicit attestation scopes a Modelo 111 period
        # out; a missing profile attests nothing.
        m111_no_retenciones_periods = m111_no_retenciones_periods_from_profile_values(
            profile_path_values_for_bucket(work_unit.bucket_id),
        )
    return evaluate_cross_period_clean_state(
        snapshot,
        operation=operation,
        bucket_id=work_unit.bucket_id,
        observation_repository=observation_repository,
        filing_repository=filing_repository,
        calculation_repository=calculation_repository,
        verification_repository=verification_repository,
        justificante_repository=justificante_repository,
        calculation_catalogue=calculation_catalogue,
        filing_catalogue=filing_catalogue,
        verification_catalogue=verification_catalogue,
        expected_member_sets=expected_member_sets,
        taxpayer_tax_id=taxpayer_tax_id,
        activity_start_date=activity_start_date,
        modelo_202_modality=modelo_202_modality,
        taxpayer_files_economic_activity=taxpayer_files_economic_activity,
        not_applicable_source_modelos=not_applicable_source_modelos,
        zero_value_previous_filing_binding_ids=zero_value_previous_filing_binding_ids,
        m111_no_retenciones_periods=m111_no_retenciones_periods,
        operator_value_attestations=operator_value_attestations,
        work_catalogue=(
            work_unit_repository.load()
            if operator_value_attestations is not None
            and len(operator_value_attestations) > 0
            and work_unit_repository is not None
            else None
        ),
    )


def _not_applicable_conditional_source_modelos(
    snapshot: RegistrySnapshot,
    profile: TaxpayerProfile,
    *,
    operation: PinnedAuthorityOperation,
) -> frozenset[str] | None:
    """Return the conditional sources the profile positively excludes, or ``None``.

    Fail-closed: an applicability derivation that raises, or that is not a
    positive applies / does-not-apply verdict for any candidate, suppresses
    nothing.
    """
    candidates = sorted(
        {
            classification.source_modelo
            for classification in snapshot.revision.dependency_classifications
            if classification.conditional_on_economic_activity
        },
    )
    not_applicable: set[str] = set()
    for modelo in candidates:
        try:
            applicability = derive_modelo_applicability(profile, modelo, operation=operation)
        except (TypeError, ValueError, RegistryValidationError):
            return None
        if applicability.verdict is ApplicabilityVerdict.NOT_APPLICABLE:
            not_applicable.add(modelo)
        elif applicability.verdict not in {
            ApplicabilityVerdict.APPLICABLE,
            ApplicabilityVerdict.ATTRIBUTION_PASS_THROUGH,
        }:
            return None
    return frozenset(not_applicable)


def zero_value_previous_filing_binding_ids(target: CalculationRevision | None) -> frozenset[str]:
    """Return zero-valued binding overrides for the selected revision.

    Core types:
    :class:`~cadrumo.domain.modelos.calculation_revision.CalculationRevision`.
    """
    if target is None:
        return frozenset[str]()
    resolved: set[str] = set()
    for binding_id, raw_value in target.binding_overrides.items():
        try:
            value = coerce_decimal_strict(raw_value if isinstance(raw_value, Decimal) else raw_value.strip())
        except (ValueError, ArithmeticError):
            continue
        if value == 0:
            resolved.add(binding_id)
    return frozenset(resolved)


def operator_value_attestations(target: CalculationRevision | None) -> dict[str, OperatorAttestedValue]:
    """Return the figures the operator stated for earlier filings the product cannot hold.

    Only the target's operator layer is read: a value attestation is the
    operator's own statement, so a value a source tier merged into the
    revision's replay map can never stand for one. A revision with no layer, or
    a layer that attests nothing, yields none.

    Core types:
    :class:`~cadrumo.domain.modelos.calculation_revision.CalculationRevision`.
    """
    layer = None if target is None else target.operator_layer
    if layer is None:
        return {}
    return {
        binding_id: OperatorAttestedValue(
            binding_id=binding_id,
            value=layer.binding_overrides[binding_id],
            sources=attestation.sources,
        )
        for binding_id, attestation in layer.value_attestations.items()
    }


#: Evidence-missing blockers a genuine first filer hits on a pre-activity
#: dependency: no prior filing exists because no obligation ever did. When one
#: blocks and no activity-start date is recorded, the gate asks for the date.
_FIRST_FILER_CANDIDATE_BLOCKERS: frozenset[CrossPeriodCleanStateBlocker] = frozenset(
    {
        CrossPeriodCleanStateBlocker.MISSING_OBSERVATION,
        CrossPeriodCleanStateBlocker.MISSING_OBSERVED_CASILLA,
        CrossPeriodCleanStateBlocker.MISSING_CURRENT_FILING_RECORD,
        CrossPeriodCleanStateBlocker.MISSING_EXTERNAL_EVIDENCE,
        CrossPeriodCleanStateBlocker.LOCAL_FILING_MISSING_EXTERNAL_EVIDENCE,
        CrossPeriodCleanStateBlocker.MISSING_AEAT_ACCEPTANCE,
        CrossPeriodCleanStateBlocker.MISSING_CALCULATION_REVISION,
    },
)

#: A filing may fold in a prior period's figure only once that prior
#: declaration is real and evidenced: LGT art. 119 (declaración tributaria) and
#: art. 120 (autoliquidaciones).
_CROSS_PERIOD_DEPENDENCY_LEGAL_REFS: tuple[LegalRefId, ...] = (
    "ley-58-2003:art-119",
    "ley-58-2003:art-120",
)

#: An IVA compensación carry is additionally governed by LIVA art. 99.
IVA_COMPENSATION_CARRY_LEGAL_REF: LegalRefId = "ley-37-1992:art-99"

#: Whether a prior obligation existed turns on the censo alta (RGAT art. 9).
_CROSS_PERIOD_ACTIVITY_START_LEGAL_REFS: tuple[LegalRefId, ...] = ("rd-1065-2007:art-9",)

#: LIRPF art. 48: a negative general base carried from a prior year.
_ZERO_VALUE_PREVIOUS_FILING_LEGAL_REFS: tuple[LegalRefId, ...] = ("ley-35-2006:art-48",)

#: RIRPF art. 108 and Orden EHA/586/2011 art. 1: the Modelo 111 period without retenciones.
_M111_NO_RETENCIONES_LEGAL_REFS: tuple[LegalRefId, ...] = (
    "rd-439-2007:art-108",
    "orden-eha-586-2011:art-1",
)

#: LIS art. 40.2 (modalidad cuota) and art. 40.3 (modalidad base imponible).
_M202_FIRST_YEAR_LEGAL_REFS: tuple[LegalRefId, ...] = (
    "ley-27-2014:art-40",
    "ley-27-2014:art-40-3",
)

_IVA_WALLET_CROSS_PERIOD_ORIGIN_IDS: frozenset[str] = frozenset({"modelo-303-compensacion-pendiente-anteriores"})


def _cross_period_dependency_legal_refs(origin_ids: tuple[str, ...]) -> tuple[LegalRefId, ...]:
    """Return the prior-declaration basis, plus LIVA art. 99 for a compensación carry."""
    refs = list(_CROSS_PERIOD_DEPENDENCY_LEGAL_REFS)
    if any("compensacion" in origin_id for origin_id in origin_ids):
        refs.append(IVA_COMPENSATION_CARRY_LEGAL_REF)
    return tuple(refs)


def _cross_period_requirement_legal_refs(requirement: CrossPeriodDependencyRequirement) -> tuple[LegalRefId, ...]:
    """Return generic cross-period refs plus the registry requirement refs."""
    return tuple(dict.fromkeys((*_cross_period_dependency_legal_refs(requirement.origin_ids), *requirement.legal_refs)))


def _cross_period_requirement_source_refs(requirement: CrossPeriodDependencyRequirement) -> tuple[SourceRefId, ...]:
    """Return source refs carried by the registry requirement row."""
    return tuple(dict.fromkeys(requirement.source_refs))


def _join_cross_period_ids(values: Iterable[str]) -> str:
    """Join exact stable identities without introducing presentation prose."""
    return "|".join(dict.fromkeys(values))


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
    """Return verification findings for a cross-period clean-state verdict.

    Every unclean dependency yields a BLOCKING finding. Suppressions and
    non-official bases stay visible as NON-BLOCKING advisories. When an
    evidence-missing dependency blocks and the profile records no activity-start
    date, one more BLOCKING finding asks for the date, because the gate cannot
    otherwise tell a first filer from a genuinely missing prior filing.
    """
    if verdict is None:
        return ()
    findings: list[ModeloVerificationFinding] = []
    has_first_filer_candidate_block = False
    for evidence in verdict.dependencies:
        evidence_findings, evidence_blocks_first_filer = _cross_period_evidence_findings(
            verdict,
            evidence,
            iva_compensation_decision=iva_compensation_decision,
            blocking_finding_observer=blocking_finding_observer,
        )
        findings.extend(evidence_findings)
        has_first_filer_candidate_block = has_first_filer_candidate_block or evidence_blocks_first_filer
    if activity_start_date is None and has_first_filer_candidate_block:
        missing_activity_start = _cross_period_missing_activity_start_finding(verdict)
        findings.append(missing_activity_start)
        if blocking_finding_observer is not None:
            blocking_finding_observer(missing_activity_start, None)
    if any(item.modelo_not_applicable_advisory for item in verdict.dependencies):
        findings.append(_cross_period_modelo_not_applicable_advisory_finding(verdict))
    return tuple(findings)


def _cross_period_evidence_findings(
    verdict: CrossPeriodCleanStateVerdict,
    evidence: CrossPeriodDependencyEvidence,
    *,
    iva_compensation_decision: object | None,
    blocking_finding_observer: Callable[
        [ModeloVerificationFinding, CrossPeriodDependencyEvidence | None],
        None,
    ]
    | None,
) -> tuple[tuple[ModeloVerificationFinding, ...], bool]:
    findings: list[ModeloVerificationFinding] = []
    blocks_first_filer = False
    if not evidence.clean and not _iva_wallet_decision_covers_cross_period_dependency(
        verdict,
        evidence,
        iva_compensation_decision,
    ):
        blocks_first_filer = bool(set(evidence.blockers) & _FIRST_FILER_CANDIDATE_BLOCKERS)
        finding = _cross_period_unclean_finding(evidence)
        findings.append(finding)
        if blocking_finding_observer is not None:
            blocking_finding_observer(finding, evidence)
    if evidence.operator_attestation_conflict:
        finding = _cross_period_attestation_conflict_finding(verdict, evidence)
        findings.append(finding)
        if blocking_finding_observer is not None:
            blocking_finding_observer(finding, evidence)
    findings.extend(_cross_period_evidence_advisories(verdict, evidence))
    return tuple(findings), blocks_first_filer


def _cross_period_unclean_finding(evidence: CrossPeriodDependencyEvidence) -> ModeloVerificationFinding:
    requirement = evidence.requirement
    return ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.CROSS_PERIOD_DEPENDENCY_UNCLEAN,
        severity=ModeloVerificationFindingSeverity.BLOCKING,
        message_locale_key=(
            "application.modelo.findings.cross_period_dependency_unclean_attestable"
            if evidence.attestation_admitted
            else "application.modelo.findings.cross_period_dependency_unclean"
        ),
        message_facts={
            "source_modelo": requirement.source_modelo,
            "source_filing_year": requirement.filing_year,
            "source_period": requirement.period.registry_token,
            "origin_code": requirement.origin.value,
            "origin_ids": _join_cross_period_ids(requirement.origin_ids),
            "blocker_codes": _join_cross_period_ids(blocker.value for blocker in evidence.blockers),
        },
        legal_refs=_cross_period_requirement_legal_refs(requirement),
        source_refs=_cross_period_requirement_source_refs(requirement),
    )


def _cross_period_evidence_advisories(
    verdict: CrossPeriodCleanStateVerdict,
    evidence: CrossPeriodDependencyEvidence,
) -> tuple[ModeloVerificationFinding, ...]:
    findings: list[ModeloVerificationFinding] = []
    if evidence.operator_declared_suppression_advisory:
        findings.append(_cross_period_operator_declared_suppression_advisory_finding(evidence))
    if evidence.non_official_local_chain_advisory:
        findings.append(_cross_period_non_official_local_chain_advisory_finding(evidence))
    if evidence.suppressed_first_year_fractional:
        findings.append(_cross_period_first_year_fractional_suppression_advisory_finding(evidence))
    if evidence.zero_value_previous_filing_advisory:
        findings.append(
            _cross_period_target_advisory_finding(verdict, evidence, advisory="zero_value_previous_filing"),
        )
    if evidence.m111_no_retenciones_no_obligation_advisory:
        findings.append(
            _cross_period_target_advisory_finding(verdict, evidence, advisory="m111_no_retenciones"),
        )
    if evidence.operator_attested_absent_upstream_advisory:
        findings.append(_cross_period_operator_attested_advisory_finding(verdict, evidence))
    return tuple(findings)


def _declared_activity_start(evidence: CrossPeriodDependencyEvidence) -> str:
    provenance = evidence.no_prior_obligation
    return provenance.activity_start_date.isoformat() if provenance is not None else "unknown"


def _cross_period_operator_declared_suppression_advisory_finding(
    evidence: CrossPeriodDependencyEvidence,
) -> ModeloVerificationFinding:
    """Disclose a pre-activity suppression that rests on an operator-declared date."""
    requirement = evidence.requirement
    return ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.ADVISORY,
        severity=ModeloVerificationFindingSeverity.WARNING,
        message_locale_key="application.modelo.findings.cross_period_operator_declared_suppression",
        message_facts={
            "source_modelo": requirement.source_modelo,
            "source_filing_year": requirement.filing_year,
            "source_period": requirement.period.registry_token,
            "origin_code": requirement.origin.value,
            "activity_start_date": _declared_activity_start(evidence),
        },
        legal_refs=_CROSS_PERIOD_ACTIVITY_START_LEGAL_REFS,
        source_refs=_cross_period_requirement_source_refs(requirement),
    )


def _cross_period_first_year_fractional_suppression_advisory_finding(
    evidence: CrossPeriodDependencyEvidence,
) -> ModeloVerificationFinding:
    """Disclose a first-year Modelo 202 modalidad-cuota suppression."""
    requirement = evidence.requirement
    return ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.ADVISORY,
        severity=ModeloVerificationFindingSeverity.WARNING,
        message_locale_key="application.modelo.findings.cross_period_first_year_fractional_suppression",
        message_facts={
            "source_modelo": requirement.source_modelo,
            "source_filing_year": requirement.filing_year,
            "source_period": requirement.period.registry_token,
            "activity_start_date": _declared_activity_start(evidence),
        },
        legal_refs=_M202_FIRST_YEAR_LEGAL_REFS,
        source_refs=_cross_period_requirement_source_refs(requirement),
    )


def _cross_period_target_advisory_finding(
    verdict: CrossPeriodCleanStateVerdict,
    evidence: CrossPeriodDependencyEvidence,
    *,
    advisory: Literal["zero_value_previous_filing", "m111_no_retenciones"],
) -> ModeloVerificationFinding:
    """Disclose a dependency admitted on explicit no-carry evidence for the target."""
    requirement = evidence.requirement
    facts: dict[str, str | int] = {
        "source_modelo": requirement.source_modelo,
        "source_filing_year": requirement.filing_year,
        "source_period": requirement.period.registry_token,
        "origin_ids": _join_cross_period_ids(requirement.origin_ids),
        "target_modelo": verdict.target_modelo,
        "target_filing_year": verdict.target_filing_year,
        "target_period": verdict.target_period.registry_token,
    }
    source_refs = _cross_period_requirement_source_refs(requirement)
    if advisory == "zero_value_previous_filing":
        return ModeloVerificationFinding(
            kind=ModeloVerificationFindingKind.ADVISORY,
            severity=ModeloVerificationFindingSeverity.WARNING,
            message_locale_key="application.modelo.findings.cross_period_zero_value_previous_filing",
            message_facts=facts,
            legal_refs=_merged_legal_refs(_ZERO_VALUE_PREVIOUS_FILING_LEGAL_REFS, requirement),
            source_refs=source_refs,
        )
    return ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.ADVISORY,
        severity=ModeloVerificationFindingSeverity.WARNING,
        message_locale_key="application.modelo.findings.cross_period_m111_no_retenciones",
        message_facts=facts,
        legal_refs=_merged_legal_refs(_M111_NO_RETENCIONES_LEGAL_REFS, requirement),
        source_refs=source_refs,
    )


def _cross_period_attestation_conflict_finding(
    verdict: CrossPeriodCleanStateVerdict,
    evidence: CrossPeriodDependencyEvidence,
) -> ModeloVerificationFinding:
    """Block on a stated figure that the source now held here contradicts; the source decides."""
    requirement = evidence.requirement
    stated = evidence.operator_attestation_conflict
    return ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.CROSS_PERIOD_DEPENDENCY_UNCLEAN,
        severity=ModeloVerificationFindingSeverity.BLOCKING,
        message_locale_key="application.modelo.findings.cross_period_dependency_attestation_conflict",
        message_facts={
            "source_modelo": requirement.source_modelo,
            "source_filing_year": requirement.filing_year,
            "source_period": requirement.period.registry_token,
            "binding_id": _join_cross_period_ids(item.binding_id for item in stated),
            "value": "|".join(item.value for item in stated),
            "target_modelo": verdict.target_modelo,
            "target_filing_year": verdict.target_filing_year,
            "target_period": verdict.target_period.registry_token,
        },
        legal_refs=_cross_period_requirement_legal_refs(requirement),
        source_refs=_cross_period_requirement_source_refs(requirement),
    )


def _cross_period_operator_attested_advisory_finding(
    verdict: CrossPeriodCleanStateVerdict,
    evidence: CrossPeriodDependencyEvidence,
) -> ModeloVerificationFinding:
    """Disclose a dependency admitted on the operator's stated figure for a year the product cannot hold."""
    requirement = evidence.requirement
    attested = evidence.operator_attested_absent_upstream
    return ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.ADVISORY,
        severity=ModeloVerificationFindingSeverity.WARNING,
        message_locale_key="application.modelo.findings.cross_period_dependency_operator_attested",
        message_facts={
            "source_modelo": requirement.source_modelo,
            "source_filing_year": requirement.filing_year,
            "source_period": requirement.period.registry_token,
            "binding_id": _join_cross_period_ids(item.binding_id for item in attested),
            "value": "|".join(item.value for item in attested),
            "target_modelo": verdict.target_modelo,
            "target_filing_year": verdict.target_filing_year,
            "target_period": verdict.target_period.registry_token,
        },
        legal_refs=_cross_period_requirement_legal_refs(requirement),
        source_refs=_cross_period_requirement_source_refs(requirement),
    )


def _merged_legal_refs(
    advisory_refs: tuple[LegalRefId, ...],
    requirement: CrossPeriodDependencyRequirement,
) -> tuple[LegalRefId, ...]:
    return tuple(dict.fromkeys((*advisory_refs, *_cross_period_requirement_legal_refs(requirement))))


def _cross_period_missing_activity_start_finding(verdict: CrossPeriodCleanStateVerdict) -> ModeloVerificationFinding:
    """Ask for the activity-start date before a first filer can be told from a missing filing."""
    return ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.CROSS_PERIOD_DEPENDENCY_UNCLEAN,
        severity=ModeloVerificationFindingSeverity.BLOCKING,
        message_locale_key="application.modelo.findings.cross_period_activity_start_missing",
        message_facts={
            "target_modelo": verdict.target_modelo,
            "target_filing_year": verdict.target_filing_year,
            "target_period": verdict.target_period.registry_token,
        },
        legal_refs=_CROSS_PERIOD_ACTIVITY_START_LEGAL_REFS,
    )


def _cross_period_modelo_not_applicable_advisory_finding(
    verdict: CrossPeriodCleanStateVerdict,
) -> ModeloVerificationFinding:
    """Summarise dependencies on modelos this taxpayer does not file."""
    suppressed = tuple(item for item in verdict.dependencies if item.modelo_not_applicable_advisory)
    modelos = sorted({item.requirement.source_modelo for item in suppressed})
    return ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.ADVISORY,
        severity=ModeloVerificationFindingSeverity.WARNING,
        message_locale_key="application.modelo.findings.cross_period_modelo_not_applicable.message",
        message_facts={
            "source_modelos": "|".join(modelos),
            "source_modelo_count": len(modelos),
        },
        legal_refs=tuple(
            dict.fromkeys(ref for item in suppressed for ref in _cross_period_requirement_legal_refs(item.requirement)),
        ),
        source_refs=tuple(
            dict.fromkeys(
                ref for item in suppressed for ref in _cross_period_requirement_source_refs(item.requirement)
            ),
        ),
    )


def _cross_period_non_official_local_chain_advisory_finding(
    evidence: CrossPeriodDependencyEvidence,
) -> ModeloVerificationFinding:
    """Disclose a same-year dependency admitted on a non-official local chain."""
    requirement = evidence.requirement
    return ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.ADVISORY,
        severity=ModeloVerificationFindingSeverity.WARNING,
        message_locale_key="application.modelo.findings.cross_period_non_official_local_chain.message",
        message_facts={
            "source_modelo": requirement.source_modelo,
            "source_filing_year": requirement.filing_year,
            "source_period": requirement.period.registry_token,
            "origin_code": requirement.origin.value,
        },
        legal_refs=_cross_period_requirement_legal_refs(requirement),
        source_refs=_cross_period_requirement_source_refs(requirement),
    )


def _iva_wallet_decision_covers_cross_period_dependency(
    verdict: CrossPeriodCleanStateVerdict,
    evidence: CrossPeriodDependencyEvidence,
    decision: object | None,
) -> bool:
    """Return whether a persisted Modelo 303 wallet decision covers the compensación carry."""
    if decision is None:
        return False
    requirement = evidence.requirement
    if not (
        verdict.target_modelo == form_for_role("iva.periodic")
        and requirement.source_modelo == form_for_role("iva.periodic")
        and set(requirement.origin_ids) & _IVA_WALLET_CROSS_PERIOD_ORIGIN_IDS
    ):
        return False
    if getattr(decision, "blocked", True):
        return False
    if getattr(decision, "target_year", None) != verdict.target_filing_year:
        return False
    if getattr(decision, "target_period", None) != verdict.target_period:
        return False
    if getattr(decision, "selected_amount", None) is None:
        return False
    return _wallet_decision_has_supported_authority(decision)


_STANDING_ROUTED_BLOCKERS: Final[frozenset[CrossPeriodCleanStateBlocker]] = frozenset(
    {
        CrossPeriodCleanStateBlocker.MISSING_OBSERVATION,
        CrossPeriodCleanStateBlocker.MISSING_CURRENT_FILING_RECORD,
        CrossPeriodCleanStateBlocker.SUPERSEDED_DEPENDENCY,
        CrossPeriodCleanStateBlocker.UNFILED_CALCULATION_REVISION,
        CrossPeriodCleanStateBlocker.MISSING_COMPLETE_VERIFICATION_REPORT,
    }
)
"""Blockers the source declaration's own work settles, so its standing names the door."""

_FILED_CAPTURE_BLOCKERS: Final[frozenset[CrossPeriodCleanStateBlocker]] = frozenset(
    {
        CrossPeriodCleanStateBlocker.MISSING_OBSERVED_CASILLA,
        CrossPeriodCleanStateBlocker.MISSING_EXTERNAL_EVIDENCE,
        CrossPeriodCleanStateBlocker.LOCAL_FILING_MISSING_EXTERNAL_EVIDENCE,
        CrossPeriodCleanStateBlocker.MISSING_AEAT_ACCEPTANCE,
        CrossPeriodCleanStateBlocker.MISSING_EXTERNAL_EVIDENCE_RECORD,
        CrossPeriodCleanStateBlocker.MISSING_JUSTIFICANTE_VERIFICATION,
    }
)
"""Blockers of a filed source that only its capture from the AEAT settles: its values or its official evidence."""

_UNROUTED_SCENARIO: Final[str] = "unclean"
_ATTEST_PRIOR_VALUE_SCENARIO: Final[str] = "attest_prior_value"
_FILED_CAPTURE_SCENARIO: Final[str] = "filed_evidence_missing"

type CrossPeriodDoor = tuple[str, dict[str, str | int] | None]
"""The ``cross_period_dependency`` scenario suffix and the facts its action binds, ``None`` when door-less."""


def cross_period_door_operator_arguments(scenario: str) -> tuple[str, ...]:
    """The arguments of a door's action only the operator supplies: the figure a statement states."""
    return ("value",) if scenario == _ATTEST_PRIOR_VALUE_SCENARIO else ()


def cross_period_door(
    evidence: CrossPeriodDependencyEvidence,
    *,
    bucket_id: str,
    work_catalogue: WorkUnitCatalogue,
    calculation_catalogue: CalculationRevisionCatalogue,
    operation: PinnedAuthorityOperation,
    target: WorkUnit | None = None,
) -> CrossPeriodDoor:
    """The door the first blocker of an unclean source names.

    A blocker the source declaration's own work settles routes by where that
    declaration stands: create, calculate, verify or file it. Creating is
    offered only for a declaration the registry admits for that period and
    whose values are not already observed. A filed source whose values or
    official evidence are missing is captured from the AEAT, and so is a
    source whose value only the filer stated, unless its declaration is held
    here. A member fan-in source, or any other blocker, names no command, as
    none settles it.

    A previous-filing source whose year the support envelope refuses cannot be
    created, filed or captured here, so no return can ever prove it. The door
    for it, when the ``target`` declaration is known, is the operator stating
    the figure for the binding that still lacks that statement.
    """
    requirement = evidence.requirement
    if not evidence.blockers or requirement.requires_member_fan_in:
        return _UNROUTED_SCENARIO, None
    if target is not None and _outside_envelope_previous_filing(requirement):
        return _ATTEST_PRIOR_VALUE_SCENARIO, {
            "work_unit_id": target.work_unit_id,
            "modelo": str(target.modelo),
            "year": target.filing_year,
            "period": target.period.registry_token,
            "binding_id": requirement.origin_ids[0],
        }
    first = evidence.blockers[0]
    if first in _STANDING_ROUTED_BLOCKERS or first is CrossPeriodCleanStateBlocker.OPERATOR_MANUAL_SOURCE:
        need = source_declaration_need(
            requirement.source_modelo,
            requirement.period,
            bucket_id=bucket_id,
            work_catalogue=work_catalogue,
            calculation_catalogue=calculation_catalogue,
        )
        door = _standing_door(evidence, first, need, operation=operation)
        if door is not None:
            return door
    if first in _FILED_CAPTURE_BLOCKERS or first is CrossPeriodCleanStateBlocker.MISSING_OBSERVATION:
        return _filed_capture_door(requirement)
    return _UNROUTED_SCENARIO, None


def _outside_envelope_previous_filing(requirement: CrossPeriodDependencyRequirement) -> bool:
    """Whether the requirement reads a previous filing the pinned support envelope refuses."""
    return (
        requirement.origin is CrossPeriodDependencyOrigin.PREVIOUS_FILING_BINDING
        and requirement.source_outside_envelope
    )


def _standing_door(
    evidence: CrossPeriodDependencyEvidence,
    first: CrossPeriodCleanStateBlocker,
    need: ReconciliationSourceNeed | None,
    *,
    operation: PinnedAuthorityOperation,
) -> CrossPeriodDoor | None:
    """The door where the source declaration stands, ``None`` to fall through.

    A value only the filer stated moves on by where its declaration stands when
    it is held here; one filed elsewhere, such as the prior-year Renta a
    first-quarter pago fraccionado reads, is captured from the AEAT.
    """
    if first is CrossPeriodCleanStateBlocker.OPERATOR_MANUAL_SOURCE:
        if need is not None and need.unit is not None:
            return need.door()
        return _filed_capture_door(evidence.requirement)
    if need is None:
        return None
    if need.unit is not None or _declaration_creatable(evidence, operation=operation):
        return need.door()
    return _UNROUTED_SCENARIO, None


def _filed_capture_door(requirement: CrossPeriodDependencyRequirement) -> CrossPeriodDoor:
    """Capture the filed source declaration from the AEAT."""
    return _FILED_CAPTURE_SCENARIO, {
        "modelos": requirement.source_modelo,
        "period": requirement.period.registry_token,
        "year": requirement.filing_year,
    }


def _declaration_creatable(evidence: CrossPeriodDependencyEvidence, *, operation: PinnedAuthorityOperation) -> bool:
    """Whether creating the source declaration is the way on.

    Not when its values are already observed, as they came from a filing, nor
    when the registry refuses that modelo and period, such as a year outside
    the support envelope.
    """
    if evidence.observation_source_kind is not None:
        return False
    requirement = evidence.requirement
    try:
        operation.snapshot(
            requirement.source_modelo,
            filing_year=requirement.filing_year,
            period=requirement.period.registry_token,
            grade=RegistryAuthorityGrade.APPLICABILITY,
        )
    except RegistrySnapshotError:
        return False
    return True


def cross_period_door_reader(
    *,
    bucket_id: str,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol | None,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol,
    calculation_catalogue: CalculationRevisionCatalogue | None,
    operation: PinnedAuthorityOperation | None,
    target: WorkUnit | None = None,
) -> Callable[[CrossPeriodDependencyEvidence], CrossPeriodDoor]:
    """Route unclean sources by :func:`cross_period_door`, reading the catalogues once and only when one is unclean.

    Without the work-unit catalogue or a pinned operation no standing can be
    read, so every source stays door-less rather than being sent to a wrong
    command.
    """
    catalogues: list[tuple[WorkUnitCatalogue, CalculationRevisionCatalogue]] = []

    def door(evidence: CrossPeriodDependencyEvidence) -> CrossPeriodDoor:
        if work_unit_repository is None or operation is None:
            return _UNROUTED_SCENARIO, None
        if not catalogues:
            revisions = (
                calculation_repository.load(operation=operation)
                if calculation_catalogue is None
                else calculation_catalogue
            )
            catalogues.append((work_unit_repository.load(), revisions))
        work_catalogue, revisions = catalogues[0]
        return cross_period_door(
            evidence,
            bucket_id=bucket_id,
            work_catalogue=work_catalogue,
            calculation_catalogue=revisions,
            operation=operation,
            target=target,
        )

    return door


def require_cross_period_clean_state(
    work_unit: WorkUnit,
    *,
    observation_repository: CalculationObservationRepositoryProtocol,
    filing_repository: ModeloRecordCatalogueRepositoryProtocol,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol,
    verification_repository: VerificationReportCatalogueRepositoryProtocol,
    justificante_repository: JustificanteRepositoryProtocol,
    calculation_catalogue: CalculationRevisionCatalogue | None = None,
    filing_catalogue: ModeloRecordCatalogue | None = None,
    verification_catalogue: VerificationReportCatalogue | None = None,
    iva_compensation_decision: object | None = None,
    expected_member_sets: Iterable[CrossPeriodExpectedMemberSet] = (),
    taxpayer_tax_id: str | None = None,
    activity_start_date: date | None = None,
    modelo_202_modality: Modelo202Modality | None = None,
    taxpayer_files_economic_activity: bool | None = None,
    workflow_profile: TaxpayerProfile | None = None,
    target_revision: CalculationRevision | None = None,
    subject_leaf_key: str = "modelo.work.verify",
    operation: PinnedAuthorityOperation | None = None,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol | None = None,
) -> None:
    """Refuse the action while a registry-declared prior period is not cleanly evidenced.

    Core types:
    :class:`~cadrumo.domain.modelos.calculation_revision.CalculationRevision`,
    :class:`~cadrumo.domain.deadlines.models.TaxpayerProfile`.
    """
    verdict = cross_period_clean_state_verdict_for_work_unit(
        work_unit,
        observation_repository=observation_repository,
        filing_repository=filing_repository,
        calculation_repository=calculation_repository,
        verification_repository=verification_repository,
        justificante_repository=justificante_repository,
        calculation_catalogue=calculation_catalogue,
        filing_catalogue=filing_catalogue,
        verification_catalogue=verification_catalogue,
        expected_member_sets=expected_member_sets,
        taxpayer_tax_id=taxpayer_tax_id,
        activity_start_date=activity_start_date,
        modelo_202_modality=modelo_202_modality,
        taxpayer_files_economic_activity=taxpayer_files_economic_activity,
        workflow_profile=workflow_profile,
        zero_value_previous_filing_binding_ids=zero_value_previous_filing_binding_ids(target_revision),
        operator_value_attestations=operator_value_attestations(target_revision),
        work_unit_repository=work_unit_repository,
        operation=operation,
    )
    failures_by_finding_id: dict[int, ModeloPreconditionFailure] = {}
    door_of = cross_period_door_reader(
        bucket_id=work_unit.bucket_id,
        work_unit_repository=work_unit_repository,
        calculation_repository=calculation_repository,
        calculation_catalogue=calculation_catalogue,
        operation=operation,
        target=work_unit,
    )

    def _observe_blocking_finding(
        finding: ModeloVerificationFinding,
        evidence: CrossPeriodDependencyEvidence | None,
    ) -> None:
        if evidence is None:
            failures_by_finding_id[id(finding)] = build_modelo_precondition_failure(
                subject_leaf_key=subject_leaf_key,
                condition_id=f"{subject_leaf_key}.activity_start_date.present",
                scenario_id=f"{subject_leaf_key}.activity_start_date.missing_for_first_filer_adjudication",
                evidence_id=f"{subject_leaf_key}.activity_start_date",
                evidence_values={
                    "work_unit_id": work_unit.work_unit_id,
                    "modelo": str(work_unit.modelo),
                    "year": work_unit.filing_year,
                    "period": work_unit.period.registry_token,
                    "dependency_count": len(verdict.dependencies) if verdict is not None else 0,
                },
                provenance=ActionEvidenceProvenance.APPLICATION_STATE,
            )
            return
        requirement = evidence.requirement
        scenario, action_argument_values = door_of(evidence)
        failures_by_finding_id[id(finding)] = build_modelo_precondition_failure_for_scenario(
            subject_leaf_key=subject_leaf_key,
            scenario_id=f"{subject_leaf_key}.cross_period_dependency.{scenario}",
            evidence_id=f"{subject_leaf_key}.cross_period_dependency",
            evidence_values={
                "work_unit_id": work_unit.work_unit_id,
                "source_modelo": requirement.source_modelo,
                "year": requirement.filing_year,
                "period": requirement.period.registry_token,
                "origin_code": requirement.origin.value,
                "origin_ids": "|".join(requirement.origin_ids),
                "blocker_codes": "|".join(blocker.value for blocker in evidence.blockers),
            },
            provenance=ActionEvidenceProvenance.DOMAIN_EVALUATION,
            action_argument_values=action_argument_values,
            missing_action_arguments=cross_period_door_operator_arguments(scenario),
        )

    findings = cross_period_clean_state_findings(
        verdict,
        iva_compensation_decision=iva_compensation_decision,
        activity_start_date=activity_start_date,
        blocking_finding_observer=_observe_blocking_finding,
    )
    blocking = [finding for finding in findings if finding.severity is ModeloVerificationFindingSeverity.BLOCKING]
    if not blocking:
        return
    raise ModeloCrossPeriodCleanStateError(
        translated_message="application.modelo.errors.cross_period_clean_state_incomplete",
        context={
            "modelo": str(work_unit.modelo),
            "filing_year": str(work_unit.filing_year),
            "period": work_unit.period.registry_token,
            "finding_count": str(len(blocking)),
        },
        precondition_failure=failures_by_finding_id[id(blocking[0])],
    )


__all__ = [
    "IVA_COMPENSATION_CARRY_LEGAL_REF",
    "CrossPeriodDoor",
    "cross_period_clean_state_findings",
    "cross_period_clean_state_verdict_for_work_unit",
    "cross_period_door",
    "cross_period_door_operator_arguments",
    "cross_period_door_reader",
    "cross_period_expected_member_sets_from_profile",
    "operator_value_attestations",
    "registry_modality_finding",
    "require_cross_period_clean_state",
    "zero_value_previous_filing_binding_ids",
]


def _wallet_decision_has_supported_authority(decision: object) -> bool:
    """Require both selected and source authority for an admitted carry decision."""
    selected_authority = str(getattr(decision, "selected_authority", ""))
    source_kinds = {str(getattr(source, "source_kind", "")) for source in getattr(decision, "authority_sources", ())}
    return selected_authority in {"aeat_wallet", "taxpayer_override"} and bool(
        source_kinds & {"aeat_wallet", "taxpayer_override"}
    )
