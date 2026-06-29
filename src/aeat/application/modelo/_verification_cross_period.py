"""Cross-period clean-state findings for modelo verification gates.

This module adapts :func:`~aeat.application.calculations.evaluate_cross_period_clean_state`
into :class:`~aeat.domain.modelos.ModeloVerificationFinding` rows. It can inspect
the target :class:`~aeat.domain.modelos.CalculationRevision` for explicit zero
previous-filing binding overrides before deciding whether a prior-year carry
requires upstream filing evidence.
"""

from __future__ import annotations

import decimal as _decimal
import re as _re
from collections.abc import Iterable
from datetime import date
from decimal import Decimal

from ...core import Modelo
from ...core.i18n import tr
from ...domain.calculations.registry import (
    ApplicabilityVerdict,
    Modelo202Modality,
    derive_modelo_202_modality,
    derive_modelo_applicability,
)
from ...domain.deadlines import IrpfIncomeCategory, TaxpayerProfile
from ...domain.modelos._calculation_revision import CalculationRevision
from ...domain.modelos._errors import ModeloError
from ...domain.modelos._protocols import (
    CalculationRevisionCatalogueRepositoryProtocol,
    ModeloRecordCatalogueRepositoryProtocol,
    VerificationReportCatalogueRepositoryProtocol,
)
from ...domain.modelos._verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from ...domain.modelos._work_unit import WorkUnit
from ..calculations import (
    CalculationObservationRepository,
    CrossPeriodCleanStateBlocker,
    CrossPeriodCleanStateVerdict,
    CrossPeriodDependencyEvidence,
    CrossPeriodExpectedMemberSet,
    evaluate_cross_period_clean_state,
)
from ._action_errors import ModeloCrossPeriodCleanStateError
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


def derive_taxpayer_files_economic_activity(profile: TaxpayerProfile) -> bool | None:
    """Whether the taxpayer files actividad-económica pagos fraccionados (130/131).

    Reads the :class:`TaxpayerProfile` income-category declarations. ``True``
    when the profile declares actividad-económica income; ``False`` when it
    declares income categories that exclude it (a salaried/rental-only filer
    never files 130/131); ``None`` when income categories are undeclared
    (fail-closed: the 130/131 dependency stays enforced). LIRPF art. 99 /
    RIRPF art. 109.
    """
    if not profile.irpf_income_categories:
        return None
    return IrpfIncomeCategory.ACTIVIDAD_ECONOMICA in profile.irpf_income_categories


def derive_not_applicable_source_modelos(profile: TaxpayerProfile, modelos: Iterable[str]) -> frozenset[str] | None:
    """Return source modelos positively known not applicable for ``profile``.

    The clean-state gate is fail-closed: if applicability derivation raises or
    returns an incomplete/undetermined verdict for any queried modelo, callers
    receive ``None`` and suppress nothing. A positive ``NOT_APPLICABLE`` result
    is grounded in the same deadline/applicability rules that decide whether the
    :class:`TaxpayerProfile` files M130 vs M131.
    """
    not_applicable: set[str] = set()
    for modelo in sorted({str(modelo) for modelo in modelos}):
        try:
            applicability = derive_modelo_applicability(profile, modelo)
        except (ModeloError, TypeError, ValueError):
            return None
        if applicability.verdict is ApplicabilityVerdict.NOT_APPLICABLE:
            not_applicable.add(modelo)
        elif applicability.verdict not in {
            ApplicabilityVerdict.APPLICABLE,
            ApplicabilityVerdict.ATTRIBUTION_PASS_THROUGH,
        }:
            return None
    return frozenset(not_applicable)


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
        message=(
            "Modelo 202 modality is incomplete: profile fact "
            f"{_MODELO_202_INCN_PROFILE_FACT} (INCN prior 12 months) is required to choose "
            "LIS art. 40.2 vs art. 40.3 before verification, filing, or export."
        ),
        next_action=(
            f"Set {_MODELO_202_INCN_PROFILE_FACT} on the active taxpayer profile, then recalculate "
            "and rerun verification."
        ),
        legal_refs=verdict.legal_refs,
    )


def _raise_if_modelo_202_modality_incomplete(*, work_unit: WorkUnit, profile: TaxpayerProfile | None) -> None:
    if profile is None:
        return
    finding = _modelo_202_incomplete_modality_finding(work_unit=work_unit, profile=profile)
    if finding is None:
        return
    raise ModeloCrossPeriodCleanStateError(
        finding.message,
        translated_message="application.modelo.errors.cross_period_clean_state_incomplete",
        context={
            "modelo": str(work_unit.modelo),
            "filing_year": work_unit.filing_year,
            "period": work_unit.period.registry_token,
            "missing_profile_fact": _MODELO_202_INCN_PROFILE_FACT,
            "modality": Modelo202Modality.INCOMPLETE.value,
        },
        suggestion=finding.next_action,
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
) -> CrossPeriodCleanStateVerdict | None:
    """Evaluate the cross-period clean-state verdict for a work unit.

    ``activity_start_date`` is the operator-declared
    :attr:`TaxpayerProfile.activity_start_date` - the exact field the deadline
    engine consumes for pre-start obligation suppression. When supplied, a
    dependency whose period falls strictly before it is scoped out as
    no-prior-obligation (ADR 2026-06-13-first-filer-attestation-adr).

    ``modelo_202_modality`` is the derived Modelo 202 pago-fraccionado modality.
    When it is ``ART_40_2_OPTIONAL`` and the recorded ``activity_start_date`` places
    the first IS year at or after the target year, the Modelo 202 cross-period
    dependency is scoped out as a first-year no-fractional-payment obligation
    (ADR 2026-06-19-m202-first-period-attestation-adr); fail-closed otherwise.
    """
    from ...domain.calculations.registry import RegistrySnapshotError

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
_CROSS_PERIOD_DEPENDENCY_LEGAL_REFS: tuple[str, ...] = (
    "ley-58-2003:art-119",
    "ley-58-2003:art-120",
)

#: Additional grounding when the cross-period carry is an IVA compensación
#: balance: LIVA art. 99 governs the compensación del exceso de cuotas a deducir
#: en periodos sucesivos that the modelo-303 self-dependency carries forward.
_IVA_COMPENSATION_CARRY_LEGAL_REF: str = "ley-37-1992:art-99"

#: Legal grounding for the first-filer / activity-start findings. Whether a prior
#: obligation existed turns on the start-of-activity censo declaration
#: (RGAT — RD 1065/2007 — art. 9, declaración de alta en el censo).
_CROSS_PERIOD_ACTIVITY_START_LEGAL_REFS: tuple[str, ...] = ("rd-1065-2007:art-9",)
_M100_ZERO_VALUE_PREVIOUS_FILING_BINDING_RE = _re.compile(
    r"^renta-\d{4}-base-liquidable-negativa-general-anterior$",
)
_M100_ZERO_BIN_LEGAL_REFS: tuple[str, ...] = ("ley-35-2006:art-48",)


def _zero_value_previous_filing_binding_ids(target: CalculationRevision | None) -> frozenset[str]:
    """Return whitelisted previous-filing binding ids explicitly supplied as zero."""
    if target is None:
        return frozenset()
    binding_ids: set[str] = set()
    for binding_id, raw_value in target.binding_overrides.items():
        if not _M100_ZERO_VALUE_PREVIOUS_FILING_BINDING_RE.fullmatch(str(binding_id)):
            continue
        try:
            value = Decimal(str(raw_value).strip())
        except (_decimal.DecimalException, ValueError):
            continue
        if value == 0:
            binding_ids.add(str(binding_id))
    return frozenset(binding_ids)


def _cross_period_dependency_legal_refs(origin_ids: tuple[str, ...]) -> tuple[str, ...]:
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


def _cross_period_clean_state_findings(
    verdict: CrossPeriodCleanStateVerdict | None,
    *,
    iva_compensation_decision: object | None = None,
    activity_start_date: date | None = None,
) -> tuple[ModeloVerificationFinding, ...]:
    """Return verification findings for a cross-period clean-state verdict.

    Emits a BLOCKING ``CROSS_PERIOD_DEPENDENCY_UNCLEAN`` finding for each unclean
    dependency, plus a NON-BLOCKING ``ADVISORY`` (``WARNING`` severity) finding for
    each dependency that carried an unstamped or indeterminate revision stamp
    (``unstamped_revision_advisory``). The advisory is surfaced even when the
    dependency is otherwise ``clean`` — ADR 2026-06-10-period-revision-resolution-adr,
    Ruling 3 / R2 mandates that an unstamped carry must never degrade
    silently. The WARNING severity keeps the grant path open (see
    :func:`_classify_verification_outcome`) while making the carry operator-visible.

    ADR 2026-06-13-first-filer-attestation-adr adds two outcomes:

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
        if not evidence.clean:
            if _iva_wallet_decision_covers_cross_period_dependency(verdict, evidence, iva_compensation_decision):
                pass
            else:
                if set(evidence.blockers) & _FIRST_FILER_CANDIDATE_BLOCKERS:
                    has_first_filer_candidate_block = True
                requirement = evidence.requirement
                requirement_period = requirement.period.registry_token
                blocker_text = _summarize_cross_period_ids(tuple(blocker.value for blocker in evidence.blockers))
                origin_text = _summarize_cross_period_ids(requirement.origin_ids)
                findings.append(
                    ModeloVerificationFinding(
                        kind=ModeloVerificationFindingKind.CROSS_PERIOD_DEPENDENCY_UNCLEAN,
                        severity=ModeloVerificationFindingSeverity.BLOCKING,
                        message=(
                            "cross-period dependency is not clean: "
                            f"modelo={requirement.source_modelo} year={requirement.filing_year} "
                            f"period={requirement_period} origin={requirement.origin.value} "
                            f"origin_ids={origin_text} blockers={blocker_text}"
                        ),
                        next_action=_cross_period_clean_state_next_action(verdict, evidence),
                        legal_refs=_cross_period_dependency_legal_refs(requirement.origin_ids),
                    ),
                )
        if evidence.unstamped_revision_advisory:
            findings.append(_cross_period_unstamped_revision_advisory_finding(verdict, evidence))
        if evidence.operator_declared_suppression_advisory:
            findings.append(_cross_period_operator_declared_suppression_advisory_finding(verdict, evidence))
        if evidence.non_official_local_chain_advisory:
            findings.append(_cross_period_non_official_local_chain_advisory_finding(verdict, evidence))
        if evidence.suppressed_first_year_fractional:
            findings.append(_cross_period_first_year_fractional_suppression_advisory_finding(verdict, evidence))
        if evidence.zero_value_previous_filing_advisory:
            findings.append(_cross_period_zero_value_previous_filing_advisory_finding(verdict, evidence))
    if activity_start_date is None and has_first_filer_candidate_block:
        findings.append(_cross_period_missing_activity_start_finding(verdict))
    if verdict.has_modelo_not_applicable_advisory:
        findings.append(_cross_period_modelo_not_applicable_advisory_finding(verdict))
    return tuple(findings)


def _cross_period_operator_declared_suppression_advisory_finding(
    verdict: CrossPeriodCleanStateVerdict,
    evidence: CrossPeriodDependencyEvidence,
) -> ModeloVerificationFinding:
    """Build the NON-BLOCKING advisory for an operator-declared pre-activity suppression.

    ADR 2026-06-13-first-filer-attestation-adr (operator-declared now,
    censo-corroborated when the live censo surface is fixed): a dependency was
    scoped out as no-prior-obligation because its period falls strictly before the
    operator-declared activity-start date. The date has NOT been corroborated
    against an AEAT censo snapshot, so the suppression is surfaced as a
    non-blocking advisory - never presented as AEAT-authoritative, never trusted
    silently - mirroring the WARNING severity that keeps the grant path open.
    """
    requirement = evidence.requirement
    requirement_period = requirement.period.registry_token
    provenance = evidence.no_prior_obligation
    declared_date = provenance.activity_start_date.isoformat() if provenance is not None else "unknown"
    return ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.ADVISORY,
        severity=ModeloVerificationFindingSeverity.WARNING,
        message=(
            "cross-period dependency scoped out as no-prior-obligation (pre-activity): "
            f"modelo={requirement.source_modelo} year={requirement.filing_year} "
            f"period={requirement_period} origin={requirement.origin.value}. The period falls "
            f"strictly before the operator-declared activity-start date {declared_date}, which has "
            "not yet been corroborated against an AEAT censo snapshot."
        ),
        next_action=(
            "Confirm the recorded activity-start date is correct. Once the live AEAT censo read is "
            "available, the date will be corroborated and this advisory cleared."
        ),
        legal_refs=_CROSS_PERIOD_ACTIVITY_START_LEGAL_REFS,
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

    ADR 2026-06-19-m202-first-period-attestation-adr: the Modelo 202 cross-period
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
        message=(
            "Modelo 202 cross-period dependency scoped out as a first-year no-fractional-payment "
            f"obligation (modelo={requirement.source_modelo} year={requirement.filing_year} "
            f"period={requirement_period}): a first-year IS filer under modalidad cuota "
            f"(LIS art. 40.2) has no Modelo 202 obligation, as no prior IS return (activity-start "
            f"{declared_date}) provides the cuota basis. If modalidad base (art. 40.3) was elected, "
            "the entity IS obligated — the operator confirms the modality (see next action)."
        ),
        next_action=(
            "Confirm the entity files Modelo 202 under modalidad cuota (LIS art. 40.2) and that this "
            "is its first Impuesto sobre Sociedades year. If it elected modalidad base (art. 40.3) or "
            "a prior IS return exists, capture or import the prior Modelo 200/202 AEAT evidence and "
            "rerun verification."
        ),
        legal_refs=_M202_FIRST_YEAR_LEGAL_REFS,
    )


def _cross_period_missing_activity_start_finding(
    verdict: CrossPeriodCleanStateVerdict,
) -> ModeloVerificationFinding:
    """Build the BLOCKING fail-closed finding when no activity-start date is recorded.

    ADR 2026-06-13-first-filer-attestation-adr: a dependency blocks with an
    evidence-missing reason a genuine first filer would hit, but the profile
    records no ``activity_start_date`` at all, so the gate cannot decide whether
    the dependency is pre-activity (no prior obligation) or a genuinely missing
    filing. The gate fails CLOSED, prompting the operator to record the
    activity-start date, rather than silently opening.
    """
    return ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.CROSS_PERIOD_DEPENDENCY_UNCLEAN,
        severity=ModeloVerificationFindingSeverity.BLOCKING,
        message=(
            "a cross-period dependency is missing its prior filing or evidence and the profile records "
            f"no activity-start date for modelo={verdict.target_modelo} year={verdict.target_filing_year} "
            f"period={verdict.target_period.registry_token}. If this is the first period of economic "
            "activity, no prior obligation existed; record the activity-start date so the pre-activity "
            "dependency can be scoped out. Otherwise capture the missing AEAT evidence."
        ),
        next_action=(
            "Record the operator-declared activity-start date on the taxpayer profile "
            "(`aeat config profile edit`), then rerun verification. If a prior obligation genuinely "
            "existed, capture or import its AEAT justificante/CSV/live evidence instead."
        ),
        legal_refs=_CROSS_PERIOD_ACTIVITY_START_LEGAL_REFS,
    )


def _cross_period_unstamped_revision_advisory_finding(
    verdict: CrossPeriodCleanStateVerdict,
    evidence: CrossPeriodDependencyEvidence,
) -> ModeloVerificationFinding:
    """Build the NON-BLOCKING revision-stamp advisory finding for one dependency.

    ADR 2026-06-10-period-revision-resolution-adr, Ruling 3 / R2: a prior filing
    whose persisted observation has no revision stamp — or whose
    stamp could not be re-confirmed because the source context will not resolve
    (indeterminate) — carries, but the operator MUST be told so the value is not
    accepted silently. The remediation is to re-file the source period so a
    stamped observation is captured.
    """
    requirement = evidence.requirement
    requirement_period = requirement.period.registry_token
    re_file_capture = (
        "aeat app live filed pull-sources "
        f"--modelo {requirement.source_modelo} "
        f"--year {requirement.filing_year} "
        f"--period {requirement_period}"
    )
    return ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.ADVISORY,
        severity=ModeloVerificationFindingSeverity.WARNING,
        message=(
            "cross-period carry used a prior filing with no re-confirmable registry "
            f"revision stamp: modelo={requirement.source_modelo} year={requirement.filing_year} "
            f"period={requirement_period} origin={requirement.origin.value}. The carried value "
            "was accepted but its source revision could not be re-confirmed against the "
            "law-determined revision (unstamped or indeterminate record)."
        ),
        next_action=(
            f"Re-file the source period to capture a revision-stamped observation: run `{re_file_capture}`, "
            "then rerun verification so the carry is re-confirmed against the law-determined revision."
        ),
        legal_refs=_cross_period_dependency_legal_refs(requirement.origin_ids),
    )


def _summarize_cross_period_ids(
    values: Iterable[str],
    *,
    limit: int = 2,
    max_chars: int = 120,
) -> str:
    items = tuple(dict.fromkeys(values))
    text = ", ".join(items) if len(items) <= limit else ", ".join((*items[:limit], f"+{len(items) - limit} more"))
    if len(text) <= max_chars:
        return text
    return f"{text[: max_chars - 4]}..."


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
            for ref in _cross_period_dependency_legal_refs(item.requirement.origin_ids)
        ),
    )
    return ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.ADVISORY,
        severity=ModeloVerificationFindingSeverity.WARNING,
        message=(
            "cross-period dependencies on source modelos the taxpayer does not file were scoped out as "
            f"not-applicable: {', '.join(modelos)}. For suffered retenciones, enter the income-certificate "
            "amount with the corresponding --binding KEY=VALUE source, not --casilla; for mutually "
            "exclusive pagos fraccionados, confirm the activity-estimation regime on the profile."
        ),
        next_action=(
            "Use the bindings list --missing command to identify the retenciones binding, supply the "
            "certificate amount with --binding KEY=VALUE where applicable, and confirm the profile's IRPF "
            "estimation regime if a mutually exclusive pago-fraccionado modelo was scoped out."
        ),
        legal_refs=legal_refs,
    )


def _cross_period_zero_value_previous_filing_advisory_finding(
    verdict: CrossPeriodCleanStateVerdict,
    evidence: CrossPeriodDependencyEvidence,
) -> ModeloVerificationFinding:
    """NON-BLOCKING advisory for an explicit zero prior-year carry."""
    requirement = evidence.requirement
    requirement_period = requirement.period.registry_token
    origin_text = _summarize_cross_period_ids(requirement.origin_ids)
    return ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.ADVISORY,
        severity=ModeloVerificationFindingSeverity.WARNING,
        message=(
            "cross-period previous-filing carry treated as zero by explicit operator input: "
            f"modelo={requirement.source_modelo} year={requirement.filing_year} "
            f"period={requirement_period} origin_ids={origin_text} for target modelo={verdict.target_modelo} "
            f"year={verdict.target_filing_year} period={verdict.target_period.registry_token}. No prior filing "
            "evidence is required because the taxpayer is not applying a positive prior-year negative-base balance."
        ),
        next_action=(
            "If a prior-year negative general base balance exists and is being applied, replace the zero "
            "with the carried amount and capture/import the prior Modelo 100 AEAT evidence before filing."
        ),
        legal_refs=(*_M100_ZERO_BIN_LEGAL_REFS, *_cross_period_dependency_legal_refs(requirement.origin_ids)),
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
        message=tr(
            "application.modelo.findings.cross_period_non_official_local_chain.message",
            source_modelo=requirement.source_modelo,
            filing_year=requirement.filing_year,
            period=requirement_period,
            origin=requirement.origin.value,
        ),
        next_action=tr("application.modelo.findings.cross_period_non_official_local_chain.next_action"),
        legal_refs=_cross_period_dependency_legal_refs(requirement.origin_ids),
    )


def _cross_period_clean_state_next_action(
    verdict: CrossPeriodCleanStateVerdict,
    evidence: CrossPeriodDependencyEvidence,
) -> str:
    requirement = evidence.requirement
    requirement_period = requirement.period.registry_token
    target_period = verdict.target_period.registry_token
    blockers = set(evidence.blockers)
    target_capture = (
        "aeat app live filed pull-sources "
        f"--modelo {verdict.target_modelo} "
        f"--year {verdict.target_filing_year} "
        f"--period {target_period}"
    )
    source_hint = (
        f"source modelo={requirement.source_modelo} year={requirement.filing_year} period={requirement_period}"
    )
    source_capture = (
        "aeat app live filed pull-sources "
        f"--modelo {requirement.source_modelo} "
        f"--year {requirement.filing_year} "
        f"--period {requirement_period}"
    )
    source_justificante_capture = (
        "aeat app live justificante pull "
        f"--modelo {requirement.source_modelo} "
        f"--year {requirement.filing_year} "
        f"--period {requirement_period}"
    )
    import_official_record = (
        "aeat app modelo filing-record import WORK_UNIT_ID "
        "--evidence-kind aeat_justificante_pdf --evidence-id CSV --set CASILLA=VALUE"
    )
    if CrossPeriodCleanStateBlocker.REGISTRY_REVISION_DIVERGENCE in blockers:
        # ADR 2026-06-10-period-revision-resolution-adr, Ruling 3 / R2: the prior
        # filing's stamped revision is no longer the law-determined revision for its
        # source context. Re-file and re-stamp the source period under the correct
        # revision rather than carrying a stale-norm value forward.
        return (
            f"The prior filing for {source_hint} was captured under a registry revision that is no longer "
            "the law-determined revision for that period; its values may follow superseded rules. Re-file and "
            f"re-capture the source period so it is re-stamped under the current revision: run `{source_capture}`, "
            "then rerun verification."
        )
    if CrossPeriodCleanStateBlocker.MISSING_EXPECTED_GROUP_MEMBER_ROSTER in blockers:
        return (
            "Configure the expected grupo member roster for "
            f"{source_hint}, then run `{target_capture}` and rerun verification."
        )
    if CrossPeriodCleanStateBlocker.INCOMPLETE_GROUP_MEMBER_COVERAGE in blockers:
        missing = ", ".join(evidence.missing_member_nifs)
        member_detail = f" Missing members: {missing}." if missing else ""
        return f"Capture every expected grupo member filing for {source_hint}.{member_detail} Run `{target_capture}`."
    if CrossPeriodCleanStateBlocker.UNEXPECTED_GROUP_MEMBER_SOURCE in blockers:
        unexpected = ", ".join(evidence.unexpected_member_nifs)
        return (
            f"Review the grupo roster for {source_hint}; unexpected captured members: "
            f"{unexpected}. Then rerun verification."
        )
    if CrossPeriodCleanStateBlocker.OBSERVATION_REVISION_VALUE_DIVERGENCE in blockers:
        return (
            "Reconcile the captured filed observation against the local calculation with "
            "`aeat app registry verify-filed-state --observation PATH`, then refresh the upstream filing evidence."
        )
    if CrossPeriodCleanStateBlocker.OPERATOR_MANUAL_SOURCE in blockers:
        return f"Use AEAT evidence for upstream values in {source_hint}. Run `{target_capture}`."
    if blockers & {
        CrossPeriodCleanStateBlocker.MISSING_OBSERVATION,
        CrossPeriodCleanStateBlocker.MISSING_OBSERVED_CASILLA,
        CrossPeriodCleanStateBlocker.MISSING_CURRENT_FILING_RECORD,
        CrossPeriodCleanStateBlocker.DUPLICATE_CURRENT_FILING_RECORD,
        CrossPeriodCleanStateBlocker.SUPERSEDED_DEPENDENCY,
        CrossPeriodCleanStateBlocker.MISSING_AEAT_ACCEPTANCE,
        CrossPeriodCleanStateBlocker.MISSING_EXTERNAL_EVIDENCE,
        CrossPeriodCleanStateBlocker.MISSING_EXTERNAL_EVIDENCE_RECORD,
        CrossPeriodCleanStateBlocker.MISMATCHED_EXTERNAL_EVIDENCE_RECORD,
        CrossPeriodCleanStateBlocker.MISSING_JUSTIFICANTE_VERIFICATION,
        CrossPeriodCleanStateBlocker.LOCAL_FILING_MISSING_EXTERNAL_EVIDENCE,
    }:
        return (
            f"Capture/import AEAT evidence for {source_hint}. Run `{target_capture}`, "
            f"`{source_justificante_capture}`, `{import_official_record}`, or "
            "`aeat app modelo reconcile file WORK_UNIT_ID --file PATH`; rerun verification."
        )
    if blockers & {
        CrossPeriodCleanStateBlocker.MISSING_CALCULATION_REVISION,
        CrossPeriodCleanStateBlocker.UNFILED_CALCULATION_REVISION,
        CrossPeriodCleanStateBlocker.MISSING_COMPLETE_VERIFICATION_REPORT,
    }:
        return (
            f"Recalculate and verify the upstream work unit for {source_hint}, then attach AEAT evidence "
            "and rerun the target verification."
        )
    return (
        "Import or capture the upstream justificante/CSV/live evidence, reconcile it with the local calculation, "
        "and rerun verification."
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
) -> None:
    _raise_if_modelo_202_modality_incomplete(work_unit=work_unit, profile=workflow_profile)
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
    )
    findings = _cross_period_clean_state_findings(
        verdict,
        iva_compensation_decision=iva_compensation_decision,
        activity_start_date=activity_start_date,
    )
    # Only BLOCKING findings gate the file/export path. NON-BLOCKING WARNING
    # advisories (e.g. the unstamped/indeterminate revision-stamp advisory) surface
    # in the verification report but must never brick the file/export gate —
    # ADR 2026-06-10-period-revision-resolution-adr, Ruling 3 / R2.
    blocking_findings = [f for f in findings if f.severity is ModeloVerificationFindingSeverity.BLOCKING]
    if not blocking_findings:
        return
    first = blocking_findings[0]
    raise ModeloCrossPeriodCleanStateError(
        first.message,
        translated_message="application.modelo.errors.cross_period_clean_state_incomplete",
        context={
            "modelo": work_unit.modelo,
            "filing_year": str(work_unit.filing_year),
            "period": work_unit.period.registry_token,
            "finding_count": str(len(blocking_findings)),
        },
        suggestion=first.next_action,
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
