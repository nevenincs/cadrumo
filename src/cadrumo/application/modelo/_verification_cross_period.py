"""Cross-period clean-state findings for modelo verification gates.

This module adapts :func:`~application.calculations.evaluate_cross_period_clean_state`
into :class:`~domain.modelos.ModeloVerificationFinding` rows. It can inspect
the target :class:`~domain.modelos.CalculationRevision` for explicit zero
previous-filing binding overrides before deciding whether a prior-year carry
requires upstream filing evidence.

The taxpayer-side inputs it consults - the declared activity start date, the
Modelo 202 modality, and whether economic activity is filed at all - are read
from the workflow's :class:`TaxpayerProfile`, the same record the deadline
engine uses to decide which obligations exist in the first place. Reading the
suppression signals from that one record is what keeps the verification gate
and the calendar from disagreeing about whether a prior period was ever due.
"""

from __future__ import annotations

import decimal as _decimal
import re as _re
from collections.abc import Callable, Iterable
from datetime import date
from decimal import Decimal

from cadrumo.domain.calculations.registry.applicability import derive_not_applicable_source_modelos
from cadrumo.domain.calculations.registry.applicability_modelo202 import Modelo202Modality, derive_modelo_202_modality

from ...core import ActionEvidenceProvenance, Modelo
from ...core.decimal import coerce_decimal_strict
from ...domain.calculations.registry.ids import (
    LegalRefId,
    SourceRefId,
)
from ...domain.deadlines import TaxpayerProfile
from ...domain.modelos import (
    CalculationRevision,
    CalculationRevisionCatalogueRepositoryProtocol,
    ModeloRecordCatalogueRepositoryProtocol,
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
    VerificationReportCatalogueRepositoryProtocol,
    WorkUnit,
)
from ..calculations import (
    M111_NO_RETENCIONES_PROFILE_PATH,
    CalculationObservationRepository,
    CrossPeriodCleanStateBlocker,
    CrossPeriodCleanStateVerdict,
    CrossPeriodDependencyEvidence,
    CrossPeriodDependencyRequirement,
    CrossPeriodExpectedMemberSet,
    evaluate_cross_period_clean_state,
    m111_no_retenciones_periods_for_bucket,
)
from ._action_errors import ModeloCrossPeriodCleanStateError
from ._preconditions import ModeloPreconditionFailure, build_modelo_precondition_failure
from ._registry_resources import authority_via_resources as _authority_via_resources


def _cross_period_expected_member_sets_from_profile(
    profile: TaxpayerProfile,
    explicit_member_sets: Iterable[CrossPeriodExpectedMemberSet] = (),
) -> tuple[CrossPeriodExpectedMemberSet, ...]:
    """Project durable profile rosters into the clean-state proof contract.

    Explicit caller-provided sets are appended last so they retain the
    existing override semantics inside ``evaluate_cross_period_clean_state``
    when both sources carry the same ``(modelo, year, period)`` key.
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


cross_period_expected_member_sets_from_profile = _cross_period_expected_member_sets_from_profile


_MODELO_202_INCN_PROFILE_FACT = "taxpayer_type.incn_prior_12_months"


def _modelo_202_incomplete_modality_finding(
    *,
    work_unit: WorkUnit,
    profile: TaxpayerProfile,
) -> ModeloVerificationFinding | None:
    """Return a blocking finding when an M202 revision has no filing-grade modality."""
    if str(work_unit.modelo) != Modelo.M202.value:
        return None
    verdict = derive_modelo_202_modality(profile)
    if verdict.modality is not Modelo202Modality.INCOMPLETE:
        return None
    return ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.BLOCKING_RULE,
        severity=ModeloVerificationFindingSeverity.BLOCKING,
        message_locale_key="application.modelo.findings.modelo_202_modality_incomplete",
        message_facts={"profile_fact_id": _MODELO_202_INCN_PROFILE_FACT},
        legal_refs=verdict.legal_refs,
    )


def _raise_if_modelo_202_modality_incomplete(
    *,
    work_unit: WorkUnit,
    profile: TaxpayerProfile | None,
    subject_leaf_key: str = "modelo.work.verify",
) -> None:
    if profile is None:
        return
    finding = _modelo_202_incomplete_modality_finding(work_unit=work_unit, profile=profile)
    if finding is None:
        return
    raise ModeloCrossPeriodCleanStateError(
        translated_message="application.modelo.errors.cross_period_clean_state_incomplete",
        context={
            "modelo": str(work_unit.modelo),
            "filing_year": work_unit.filing_year,
            "period": work_unit.period.registry_token,
            "missing_profile_fact": _MODELO_202_INCN_PROFILE_FACT,
            "modality": Modelo202Modality.INCOMPLETE.value,
        },
        precondition_failure=build_modelo_precondition_failure(
            subject_leaf_key=subject_leaf_key,
            condition_id=f"{subject_leaf_key}.m202.modality.complete",
            scenario_id=f"{subject_leaf_key}.m202.modality.incomplete",
            evidence_id=f"{subject_leaf_key}.m202.modality",
            evidence_values={
                "work_unit_id": work_unit.work_unit_id,
                "modelo": str(work_unit.modelo),
                "year": work_unit.filing_year,
                "period": work_unit.period.registry_token,
                "profile_fact_id": _MODELO_202_INCN_PROFILE_FACT,
                "modality_code": Modelo202Modality.INCOMPLETE.value,
            },
            provenance=ActionEvidenceProvenance.DOMAIN_EVALUATION,
        ),
    )


def _cross_period_clean_state_verdict_for_work_unit(
    work_unit: WorkUnit,
    *,
    observation_repository: CalculationObservationRepository,
    filing_repository: ModeloRecordCatalogueRepositoryProtocol,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol,
    verification_repository: VerificationReportCatalogueRepositoryProtocol,
    expected_member_sets: Iterable[CrossPeriodExpectedMemberSet] = (),
    taxpayer_tax_id: str | None = None,
    activity_start_date: date | None = None,
    modelo_202_modality: Modelo202Modality | None = None,
    taxpayer_files_economic_activity: bool | None = None,
    workflow_profile: TaxpayerProfile | None = None,
    not_applicable_source_modelos: frozenset[str] | None = None,
    zero_value_previous_filing_binding_ids: frozenset[str] | None = None,
    m111_no_retenciones_periods: frozenset[tuple[int, str]] | None = None,
) -> CrossPeriodCleanStateVerdict | None:
    """Evaluate the cross-period clean-state verdict for a work unit.

    ``activity_start_date`` is the operator-declared
    :attr:`TaxpayerProfile.activity_start_date` - the exact field the deadline
    engine consumes for pre-start obligation suppression. When supplied, a
    dependency whose period falls strictly before it is scoped out as
    no-prior-obligation.

    ``modelo_202_modality`` is the derived Modelo 202 pago-fraccionado modality.
    When it is ``ART_40_2_OPTIONAL`` and the recorded ``activity_start_date`` places
    the first IS year at or after the target year, the Modelo 202 cross-period
    dependency is scoped out as a first-year no-fractional-payment obligation;
    fail-closed otherwise.
    """
    from ...domain.calculations.registry.errors import RegistrySnapshotError

    try:
        snapshot = _authority_via_resources().snapshot(
            work_unit.modelo,
            filing_year=work_unit.filing_year,
            period=work_unit.period.registry_token,
        )
    except (FileNotFoundError, RegistrySnapshotError):
        return None
    if not_applicable_source_modelos is None and workflow_profile is not None:
        conditional_source_modelos = frozenset(
            classification.source_modelo
            for classification in snapshot.revision.dependency_classifications
            if classification.conditional_on_economic_activity
        )
        not_applicable_source_modelos = derive_not_applicable_source_modelos(
            workflow_profile,
            conditional_source_modelos,
        )
    return evaluate_cross_period_clean_state(
        snapshot,
        bucket_id=work_unit.bucket_id,
        observation_repository=observation_repository,
        filing_repository=filing_repository,
        calculation_repository=calculation_repository,
        verification_repository=verification_repository,
        expected_member_sets=expected_member_sets,
        taxpayer_tax_id=taxpayer_tax_id,
        activity_start_date=activity_start_date,
        modelo_202_modality=modelo_202_modality,
        taxpayer_files_economic_activity=taxpayer_files_economic_activity,
        not_applicable_source_modelos=not_applicable_source_modelos,
        zero_value_previous_filing_binding_ids=zero_value_previous_filing_binding_ids,
        m111_no_retenciones_periods=(
            m111_no_retenciones_periods
            if m111_no_retenciones_periods is not None
            else m111_no_retenciones_periods_for_bucket(work_unit.bucket_id)
        ),
    )


#: Blocker codes a genuine first filer would hit on a pre-activity dependency:
#: there is simply no prior filing or evidence because no obligation ever existed.
#: When these block AND no activity-start date is recorded, the gate prompts the
#: operator to record the date (fail-closed) rather than silently demanding
#: evidence of a filing the law never required.
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


#: Legal grounding for a cross-period dependency. A filing may fold in a prior
#: period's declared figure only once that prior declaration is real and
#: evidenced: LGT art. 120 (autoliquidaciones — the prior declaration AEAT may
#: verify) over art. 119 (declaración tributaria; pending compensación /
#: deducción balances). Surfaced on every cross-period finding so the operator
#: sees the legal basis for requiring the prior filing's evidence.
_CROSS_PERIOD_DEPENDENCY_LEGAL_REFS: tuple[LegalRefId, ...] = (
    "ley-58-2003:art-119",
    "ley-58-2003:art-120",
)

#: Additional grounding when the cross-period carry is an IVA compensación
#: balance: LIVA art. 99 governs the compensación del exceso de cuotas a deducir
#: en periodos sucesivos that the modelo-303 self-dependency carries forward.
_IVA_COMPENSATION_CARRY_LEGAL_REF: LegalRefId = "ley-37-1992:art-99"

#: Legal grounding for the first-filer / activity-start findings. Whether a prior
#: obligation existed turns on the start-of-activity censo declaration
#: (RGAT — RD 1065/2007 — art. 9, declaración de alta en el censo).
_CROSS_PERIOD_ACTIVITY_START_LEGAL_REFS: tuple[LegalRefId, ...] = ("rd-1065-2007:art-9",)
_M100_ZERO_VALUE_PREVIOUS_FILING_BINDING_RE = _re.compile(
    r"^renta-\d{4}-base-liquidable-negativa-general-anterior$",
)
_M100_ZERO_BIN_LEGAL_REFS: tuple[LegalRefId, ...] = ("ley-35-2006:art-48",)
_M111_NO_RETENCIONES_LEGAL_REFS: tuple[LegalRefId, ...] = (
    "rd-439-2007:art-108",
    "orden-eha-586-2011:art-1",
)


def _zero_value_previous_filing_binding_ids(target: CalculationRevision | None) -> frozenset[str]:
    """Return whitelisted previous-filing binding ids explicitly supplied as zero."""
    if target is None:
        return frozenset[str]()
    binding_ids: set[str] = set()
    for binding_id, raw_value in target.binding_overrides.items():
        if not _M100_ZERO_VALUE_PREVIOUS_FILING_BINDING_RE.fullmatch(str(binding_id)):
            continue
        try:
            # DECIMAL-TEXT-RATIONALE-BINDING-OVERRIDE-ZERO-TEST: the parse is a
            # zero PREDICATE over a persisted revision's binding overrides, and
            # only ``value == 0`` is read. The ambiguous Spanish thousands shape
            # cannot change that answer -- both readings of ``1.000`` are
            # non-zero -- and the override's own write boundary owns its grammar.
            value = coerce_decimal_strict(raw_value if isinstance(raw_value, Decimal) else str(raw_value).strip())
        except (_decimal.DecimalException, ValueError):
            continue
        if value == 0:
            binding_ids.add(str(binding_id))
    return frozenset(binding_ids)


def _cross_period_dependency_legal_refs(origin_ids: tuple[str, ...]) -> tuple[LegalRefId, ...]:
    """Return the legal grounding for one cross-period dependency finding.

    Every cross-period carry cites the prior-declaration basis
    (:data:`_CROSS_PERIOD_DEPENDENCY_LEGAL_REFS`); an IVA compensación carry
    (its origin binding/relation id names the compensación balance) additionally
    cites LIVA art. 99.
    """
    refs = list(_CROSS_PERIOD_DEPENDENCY_LEGAL_REFS)
    if any("compensacion" in origin_id for origin_id in origin_ids):
        refs.append(_IVA_COMPENSATION_CARRY_LEGAL_REF)
    return tuple(refs)


def _cross_period_requirement_legal_refs(requirement: CrossPeriodDependencyRequirement) -> tuple[LegalRefId, ...]:
    """Return generic cross-period refs plus the registry requirement refs."""
    return tuple(
        dict.fromkeys(
            (
                *_cross_period_dependency_legal_refs(requirement.origin_ids),
                *requirement.legal_refs,
            ),
        ),
    )


def _cross_period_requirement_source_refs(requirement: CrossPeriodDependencyRequirement) -> tuple[SourceRefId, ...]:
    """Return source refs carried by the registry requirement row."""
    return tuple(dict.fromkeys(requirement.source_refs))


def _cross_period_clean_state_findings(
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

    Emits a BLOCKING ``CROSS_PERIOD_DEPENDENCY_UNCLEAN`` finding for each unclean
    dependency. A source revision stamp that cannot be re-confirmed is a blocker,
    not a legacy advisory: current carry data must resolve against the
    law-determined revision before it can feed a downstream filing.

    Two additional outcomes are surfaced:

    * A dependency scoped out as no-prior-obligation pre-activity on an
      operator-declared (uncorroborated) date emits a NON-BLOCKING ``ADVISORY``
      (``WARNING``) so the suppression is operator-visible and never trusted
      silently, while keeping the grant path open.
    * When an evidence-missing dependency blocks AND ``activity_start_date`` is
      ``None`` (the profile records no activity-start date at all), a single
      BLOCKING finding prompts the operator to record the date so the gate fails
      closed instructively rather than silently demanding evidence of a filing the
      law may never have required.
    """
    if verdict is None:
        return ()
    findings: list[ModeloVerificationFinding] = []
    has_first_filer_candidate_block = False
    for evidence in verdict.dependencies:
        evidence_findings, evidence_has_first_filer_block = _cross_period_evidence_findings(
            verdict,
            evidence,
            iva_compensation_decision=iva_compensation_decision,
            blocking_finding_observer=blocking_finding_observer,
        )
        findings.extend(evidence_findings)
        has_first_filer_candidate_block = has_first_filer_candidate_block or evidence_has_first_filer_block
    if activity_start_date is None and has_first_filer_candidate_block:
        missing_activity_start_finding = _cross_period_missing_activity_start_finding(verdict)
        findings.append(missing_activity_start_finding)
        if blocking_finding_observer is not None:
            blocking_finding_observer(missing_activity_start_finding, None)
    if verdict.has_modelo_not_applicable_advisory:
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
    has_first_filer_candidate_block = False
    if not evidence.clean and not _iva_wallet_decision_covers_cross_period_dependency(
        verdict,
        evidence,
        iva_compensation_decision,
    ):
        has_first_filer_candidate_block = bool(set(evidence.blockers) & _FIRST_FILER_CANDIDATE_BLOCKERS)
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
                "origin_ids": _join_cross_period_ids(requirement.origin_ids),
                "blocker_codes": _join_cross_period_ids(tuple(blocker.value for blocker in evidence.blockers)),
            },
            legal_refs=_cross_period_requirement_legal_refs(requirement),
            source_refs=_cross_period_requirement_source_refs(requirement),
        )
        findings.append(finding)
        if blocking_finding_observer is not None:
            blocking_finding_observer(finding, evidence)
    if evidence.operator_declared_suppression_advisory:
        findings.append(_cross_period_operator_declared_suppression_advisory_finding(verdict, evidence))
    if evidence.non_official_local_chain_advisory:
        findings.append(_cross_period_non_official_local_chain_advisory_finding(verdict, evidence))
    if evidence.suppressed_first_year_fractional:
        findings.append(_cross_period_first_year_fractional_suppression_advisory_finding(verdict, evidence))
    if evidence.zero_value_previous_filing_advisory:
        findings.append(_cross_period_zero_value_previous_filing_advisory_finding(verdict, evidence))
    if evidence.m111_no_retenciones_no_obligation_advisory:
        findings.append(_cross_period_m111_no_retenciones_advisory_finding(verdict, evidence))
    return tuple(findings), has_first_filer_candidate_block


def _cross_period_operator_declared_suppression_advisory_finding(
    verdict: CrossPeriodCleanStateVerdict,
    evidence: CrossPeriodDependencyEvidence,
) -> ModeloVerificationFinding:
    """Build the NON-BLOCKING advisory for an operator-declared pre-activity suppression.

    A dependency was scoped out as
    no-prior-obligation because its period falls strictly before the
    operator-declared activity-start date. Censal facts are operator-supplied
    (the live Modelo 036 censo read was retired), so the date is never
    AEAT-corroborated and the suppression is surfaced as a non-blocking advisory -
    never presented as AEAT-authoritative, never trusted silently - mirroring the
    WARNING severity that keeps the grant path open.
    """
    requirement = evidence.requirement
    requirement_period = requirement.period.registry_token
    provenance = evidence.no_prior_obligation
    declared_date = provenance.activity_start_date.isoformat() if provenance is not None else "unknown"
    return ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.ADVISORY,
        severity=ModeloVerificationFindingSeverity.WARNING,
        message_locale_key="application.modelo.findings.cross_period_operator_declared_suppression",
        message_facts={
            "source_modelo": str(requirement.source_modelo),
            "source_filing_year": requirement.filing_year,
            "source_period": requirement_period,
            "origin_code": requirement.origin.value,
            "activity_start_date": declared_date,
        },
        legal_refs=_CROSS_PERIOD_ACTIVITY_START_LEGAL_REFS,
        source_refs=_cross_period_requirement_source_refs(requirement),
    )


#: LIS art. 40.2 (modalidad cuota) and art. 40.3 (modalidad base imponible) — the
#: legal grounding for the first-year Modelo 202 suppression and its modality split.
_M202_FIRST_YEAR_LEGAL_REFS: tuple[str, ...] = (
    "ley-27-2014:art-40",
    "ley-27-2014:art-40-3",
)


def _cross_period_first_year_fractional_suppression_advisory_finding(
    verdict: CrossPeriodCleanStateVerdict,
    evidence: CrossPeriodDependencyEvidence,
) -> ModeloVerificationFinding:
    """Build the NON-BLOCKING advisory for a first-year Modelo 202 modalidad-cuota suppression.

    The Modelo 202 cross-period
    dependency was scoped out because the taxpayer is a first-year Impuesto sobre
    Sociedades filer under modalidad cuota (LIS art. 40.2), which has no pago
    fraccionado obligation in the first IS year (no prior IS return provides the
    cuota basis). The assumption rests on the operator-declared INCN (driving the
    derived modality) and activity-start date, so the suppression is surfaced as a
    non-blocking advisory naming the operator's legal responsibility — in
    particular that an entity that elected modalidad base (art. 40.3) IS obligated
    and must file Modelo 202.
    """
    requirement = evidence.requirement
    requirement_period = requirement.period.registry_token
    provenance = evidence.no_prior_obligation
    declared_date = provenance.activity_start_date.isoformat() if provenance is not None else "unknown"
    return ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.ADVISORY,
        severity=ModeloVerificationFindingSeverity.WARNING,
        message_locale_key="application.modelo.findings.cross_period_first_year_fractional_suppression",
        message_facts={
            "source_modelo": str(requirement.source_modelo),
            "source_filing_year": requirement.filing_year,
            "source_period": requirement_period,
            "activity_start_date": declared_date,
        },
        legal_refs=_M202_FIRST_YEAR_LEGAL_REFS,
        source_refs=_cross_period_requirement_source_refs(requirement),
    )


def _cross_period_missing_activity_start_finding(
    verdict: CrossPeriodCleanStateVerdict,
) -> ModeloVerificationFinding:
    """Build the BLOCKING fail-closed finding when no activity-start date is recorded.

    A dependency blocks with an
    evidence-missing reason a genuine first filer would hit, but the profile
    records no ``activity_start_date`` at all, so the gate cannot decide whether
    the dependency is pre-activity (no prior obligation) or a genuinely missing
    filing. The gate fails CLOSED, prompting the operator to record the
    activity-start date, rather than silently opening.
    """
    return ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.CROSS_PERIOD_DEPENDENCY_UNCLEAN,
        severity=ModeloVerificationFindingSeverity.BLOCKING,
        message_locale_key="application.modelo.findings.cross_period_activity_start_missing",
        message_facts={
            "target_modelo": str(verdict.target_modelo),
            "target_filing_year": verdict.target_filing_year,
            "target_period": verdict.target_period.registry_token,
        },
        legal_refs=_CROSS_PERIOD_ACTIVITY_START_LEGAL_REFS,
    )


def _join_cross_period_ids(values: Iterable[str]) -> str:
    """Join exact stable identities without introducing presentation prose."""
    return "|".join(dict.fromkeys(values))


def _cross_period_modelo_not_applicable_advisory_finding(
    verdict: CrossPeriodCleanStateVerdict,
) -> ModeloVerificationFinding:
    """NON-BLOCKING summary advisory: dependencies on modelos the taxpayer does not file.

    Surfaces the not-applicable suppression so it is operator-visible (no-silent-under-declaration).
    """
    modelos = sorted(
        {item.requirement.source_modelo for item in verdict.dependencies if item.modelo_not_applicable_advisory}
    )
    legal_refs = tuple(
        dict.fromkeys(
            ref
            for item in verdict.dependencies
            if item.modelo_not_applicable_advisory
            for ref in _cross_period_requirement_legal_refs(item.requirement)
        ),
    )
    source_refs = tuple(
        dict.fromkeys(
            ref
            for item in verdict.dependencies
            if item.modelo_not_applicable_advisory
            for ref in _cross_period_requirement_source_refs(item.requirement)
        ),
    )
    return ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.ADVISORY,
        severity=ModeloVerificationFindingSeverity.WARNING,
        message_locale_key="application.modelo.findings.cross_period_modelo_not_applicable.message",
        message_facts={
            "source_modelos": "|".join(str(modelo) for modelo in modelos),
            "source_modelo_count": len(modelos),
        },
        legal_refs=legal_refs,
        source_refs=source_refs,
    )


def _cross_period_zero_value_previous_filing_advisory_finding(
    verdict: CrossPeriodCleanStateVerdict,
    evidence: CrossPeriodDependencyEvidence,
) -> ModeloVerificationFinding:
    """NON-BLOCKING advisory for an explicit zero prior-year carry."""
    requirement = evidence.requirement
    requirement_period = requirement.period.registry_token
    return ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.ADVISORY,
        severity=ModeloVerificationFindingSeverity.WARNING,
        message_locale_key="application.modelo.findings.cross_period_zero_value_previous_filing",
        message_facts={
            "source_modelo": str(requirement.source_modelo),
            "source_filing_year": requirement.filing_year,
            "source_period": requirement_period,
            "origin_ids": _join_cross_period_ids(requirement.origin_ids),
            "target_modelo": str(verdict.target_modelo),
            "target_filing_year": verdict.target_filing_year,
            "target_period": verdict.target_period.registry_token,
        },
        legal_refs=tuple(
            dict.fromkeys((*_M100_ZERO_BIN_LEGAL_REFS, *_cross_period_requirement_legal_refs(requirement))),
        ),
        source_refs=_cross_period_requirement_source_refs(requirement),
    )


def _cross_period_m111_no_retenciones_advisory_finding(
    verdict: CrossPeriodCleanStateVerdict,
    evidence: CrossPeriodDependencyEvidence,
) -> ModeloVerificationFinding:
    """NON-BLOCKING advisory for explicit M111 no-retenciones/no-obligation evidence."""
    requirement = evidence.requirement
    requirement_period = requirement.period.registry_token
    return ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.ADVISORY,
        severity=ModeloVerificationFindingSeverity.WARNING,
        message_locale_key="application.modelo.findings.cross_period_m111_no_retenciones",
        message_facts={
            "source_modelo": str(requirement.source_modelo),
            "source_filing_year": requirement.filing_year,
            "source_period": requirement_period,
            "origin_ids": _join_cross_period_ids(requirement.origin_ids),
            "target_modelo": str(verdict.target_modelo),
            "target_filing_year": verdict.target_filing_year,
            "target_period": verdict.target_period.registry_token,
            "profile_fact_id": M111_NO_RETENCIONES_PROFILE_PATH,
        },
        legal_refs=tuple(
            dict.fromkeys((*_M111_NO_RETENCIONES_LEGAL_REFS, *_cross_period_requirement_legal_refs(requirement))),
        ),
        source_refs=_cross_period_requirement_source_refs(requirement),
    )


def _cross_period_non_official_local_chain_advisory_finding(
    verdict: CrossPeriodCleanStateVerdict,
    evidence: CrossPeriodDependencyEvidence,
) -> ModeloVerificationFinding:
    """Build the NON-BLOCKING advisory for a same-year non-official (``app_filing``) local chain.

    Surfaces the non-official basis (``no-silent-under-declaration``); a cross-YEAR prior still blocks.
    """
    requirement = evidence.requirement
    requirement_period = requirement.period.registry_token
    return ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.ADVISORY,
        severity=ModeloVerificationFindingSeverity.WARNING,
        message_locale_key="application.modelo.findings.cross_period_non_official_local_chain.message",
        message_facts={
            "source_modelo": str(requirement.source_modelo),
            "source_filing_year": requirement.filing_year,
            "source_period": requirement_period,
            "origin_code": requirement.origin.value,
        },
        legal_refs=_cross_period_requirement_legal_refs(requirement),
        source_refs=_cross_period_requirement_source_refs(requirement),
    )


def _require_cross_period_clean_state(
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
    modelo_202_modality: Modelo202Modality | None = None,
    taxpayer_files_economic_activity: bool | None = None,
    workflow_profile: TaxpayerProfile | None = None,
    target_revision: CalculationRevision | None = None,
    subject_leaf_key: str = "modelo.work.verify",
) -> None:
    _raise_if_modelo_202_modality_incomplete(
        work_unit=work_unit,
        profile=workflow_profile,
        subject_leaf_key=subject_leaf_key,
    )
    verdict = _cross_period_clean_state_verdict_for_work_unit(
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
        zero_value_previous_filing_binding_ids=_zero_value_previous_filing_binding_ids(target_revision),
        m111_no_retenciones_periods=m111_no_retenciones_periods_for_bucket(work_unit.bucket_id),
    )
    failures_by_finding_id: dict[int, ModeloPreconditionFailure] = {}

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
        failures_by_finding_id[id(finding)] = build_modelo_precondition_failure(
            subject_leaf_key=subject_leaf_key,
            condition_id=f"{subject_leaf_key}.cross_period_dependency.clean",
            scenario_id=f"{subject_leaf_key}.cross_period_dependency.unclean",
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
        )

    findings = _cross_period_clean_state_findings(
        verdict,
        iva_compensation_decision=iva_compensation_decision,
        activity_start_date=activity_start_date,
        blocking_finding_observer=_observe_blocking_finding,
    )
    # Only BLOCKING findings gate the file/export path. NON-BLOCKING WARNING
    # advisories (e.g. indeterminate revision-stamp re-confirmation) surface
    # in the verification report but must never brick the file/export gate.
    blocking_findings = [f for f in findings if f.severity is ModeloVerificationFindingSeverity.BLOCKING]
    if not blocking_findings:
        return
    first = blocking_findings[0]
    raise ModeloCrossPeriodCleanStateError(
        translated_message="application.modelo.errors.cross_period_clean_state_incomplete",
        context={
            "modelo": work_unit.modelo,
            "filing_year": str(work_unit.filing_year),
            "period": work_unit.period.registry_token,
            "finding_count": str(len(blocking_findings)),
        },
        precondition_failure=failures_by_finding_id[id(first)],
    )


def _iva_wallet_decision_covers_cross_period_dependency(
    verdict: CrossPeriodCleanStateVerdict,
    evidence: CrossPeriodDependencyEvidence,
    decision: object | None,
) -> bool:
    """Return whether a persisted Modelo 303 wallet decision covers the dependency."""
    if decision is None:
        return False
    requirement = evidence.requirement
    if (
        verdict.target_modelo != Modelo.M303
        or requirement.source_modelo != Modelo.M303
        or not (
            set(requirement.origin_ids)
            & {
                "modelo-303-compensacion-pendiente-anteriores",
                "modelo-303-rel-self-compensacion-anteriores",
            }
        )
    ):
        return False
    if getattr(decision, "blocked", True):
        return False
    if getattr(decision, "target_year", None) != verdict.target_filing_year:
        return False
    if getattr(decision, "target_period", None) != verdict.target_period:
        return False
    selected_amount = getattr(decision, "selected_amount", None)
    if selected_amount is None:
        return False
    selected_authority = str(getattr(decision, "selected_authority", ""))
    source_kinds = {str(getattr(source, "source_kind", "")) for source in getattr(decision, "authority_sources", ())}
    if selected_authority in {"aeat_wallet", "taxpayer_override"}:
        return bool(source_kinds & {"aeat_wallet", "taxpayer_override"})
    return False


CROSS_PERIOD_ACTIVITY_START_LEGAL_REFS = _CROSS_PERIOD_ACTIVITY_START_LEGAL_REFS
CROSS_PERIOD_DEPENDENCY_LEGAL_REFS = _CROSS_PERIOD_DEPENDENCY_LEGAL_REFS
IVA_COMPENSATION_CARRY_LEGAL_REF = _IVA_COMPENSATION_CARRY_LEGAL_REF
cross_period_clean_state_findings = _cross_period_clean_state_findings
cross_period_clean_state_verdict_for_work_unit = _cross_period_clean_state_verdict_for_work_unit
modelo_202_incomplete_modality_finding = _modelo_202_incomplete_modality_finding
require_cross_period_clean_state = _require_cross_period_clean_state
zero_value_previous_filing_binding_ids = _zero_value_previous_filing_binding_ids
