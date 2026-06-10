"""Verification actions and predicates for modelo filings.

Use of :class:`BucketEventHistoryRepository`, :class:`CalculationRevision`, :class:`CasillaObservation`,
:class:`RegistrySnapshot`, :class:`TaxpayerProfile`, and :class:`TransactionCatalogueRepository` for compliance.
"""

from __future__ import annotations

import decimal as _decimal
import re as _re
from collections.abc import Iterable, Mapping
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING

from ...core import Modelo
from ...core.config import Settings
from ...core.i18n import tr
from ...core.time import now as _utc_now
from ...domain.buckets import BucketEventHistoryRepository, BucketEventObjectType, BucketEventType
from ...domain.buckets._protocols import BucketEventHistoryRepositoryProtocol
from ...domain.calculations.registry import (
    M210_RATE_SENTINELS,
    CasillaDefinition,
    CasillaObservation,
    InputKind,
    RegistrySnapshot,
    VerificationPredicateDefinition,
)
from ...domain.deadlines import FiscalResidency, TaxpayerProfile
from ...domain.modelos._calculation_repository import (
    CalculationRevisionCatalogueRepository,
    upsert_calculation_revision,
)
from ...domain.modelos._calculation_revision import (
    CalculationRevision,
    CalculationRevisionCatalogue,
    CalculationRevisionState,
)
from ...domain.modelos._errors import ModeloError
from ...domain.modelos._filing_repository import ModeloRecordCatalogueRepository
from ...domain.modelos._ledger_filing_snapshot import (
    LedgerFilingEvidence,
    LedgerFilingSnapshot,
    ManualFactBasisEntry,
)
from ...domain.modelos._protocols import (
    CalculationRevisionCatalogueRepositoryProtocol,
    ModeloRecordCatalogueRepositoryProtocol,
    VerificationReportCatalogueRepositoryProtocol,
    WorkUnitCatalogueRepositoryProtocol,
)
from ...domain.modelos._repository import WorkUnitCatalogueRepository
from ...domain.modelos._verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
    VerificationCompletenessStatus,
    VerificationReport,
    derive_verification_report_id,
)
from ...domain.modelos._verification_repository import (
    VerificationReportCatalogueRepository,
    upsert_verification_report,
)
from ...domain.modelos._work_unit import WorkUnit
from ...domain.transactions import TransactionCatalogueRepository
from ..aggregation._ledger_filing_snapshot import (
    compute_ledger_filing_evidence,
    compute_ledger_filing_snapshot,
)
from ..calculations import (
    CalculationObservationRepository,
    CrossPeriodCleanStateBlocker,
    CrossPeriodCleanStateVerdict,
    CrossPeriodDependencyEvidence,
    CrossPeriodExpectedMemberSet,
    evaluate_cross_period_clean_state,
)
from ..workflow import WorkflowEngine, WorkflowPurpose, WorkflowRunRepository
from ._action_errors import (
    CalculationRevisionNotFoundError,
    CalculationRevisionStateError,
    ModeloApplicabilityFilterError,
    ModeloCrossPeriodCleanStateError,
    WorkUnitNotFoundError,
)
from ._calculation_actions import _iva_wallet_blocked_message
from ._iva_wallet_gate import (
    ModeloIvaWalletReconciliationBlocked,
)
from ._iva_wallet_gate import (
    require_persisted_iva_compensation_decision_matches_revision as _require_iva_compensation_revision_match,
)
from ._m210_rate import resolve_m210_rate as _resolve_m210_rate
from ._registry_helpers import assert_revision_content_integrity as _assert_revision_content_integrity
from ._registry_resources import authority_via_resources as _authority_via_resources
from ._revision_persistence import emit_bucket_event as _emit_bucket_event
from ._workflow_gate import build_revision_workflow_engine as _build_revision_workflow_engine
from ._workflow_gate import run_revision_workflow_gate as _run_revision_workflow_gate

if TYPE_CHECKING:
    from ..calculations._observations_repository import IvaWalletDecisionRepository

_PREDICATE_ALL_NONZERO = _re.compile(r"^all_nonzero\(\[(?P<ids>[^\]]*)\]\)$")
_PREDICATE_ANY_NONZERO = _re.compile(r"^any_nonzero\(\[(?P<ids>[^\]]*)\]\)$")
_PREDICATE_CAP_LE_WHEN_POSITIVE = _re.compile(r"^cap_le_when_positive\(\[(?P<ids>[^\]]*)\]\)$")
# implies_nonzero(["antecedent_id", "consequent_id"]) — material implication
# with a strictly-positive antecedent test: predicate holds iff antecedent
# is <= 0 OR consequent is non-zero. Authored for AEAT cuota-mínima
# invariants of the shape "cuando C01 sea positivo, C07 debe ser distinta
# de cero" (M131 EO cuota mínima, M130/M303 régimen simplificado analogues).
_PREDICATE_IMPLIES_NONZERO = _re.compile(r"^implies_nonzero\(\[(?P<ids>[^\]]*)\]\)$")
# profile_field_required("field_name", "applicability_filter") —
# profile-state-aware conditional non-zero requirement; sibling of
# implies_nonzero per the dsl-conditional-predicate ADR. The
# applicability filter is dispatched via _evaluate_applicability_filter
# against the TaxpayerProfile threaded through the verification pipeline.
# First use site: M210 representante-fiscal gate per
# m210-irnr-full-engine ADR §D2.5 (TRLIRNR Art 10).
_PREDICATE_PROFILE_FIELD_REQUIRED = _re.compile(r'^profile_field_required\("(?P<field>[^"]+)", "(?P<filter>[^"]+)"\)$')

# Per-predicate next_action dispatch. Predicates listed here emit their
# dedicated next_action prose via a direct tr() call (so the locale
# scaffold AST scanner can pick up the literal key); predicates absent
# from this dispatch fall back to the generic cross-casilla template.


def _resolve_predicate_next_action(predicate_id: str) -> str | None:
    if predicate_id == "m210-representante-fiscal-required":
        return tr("application.modelo.findings.representante_fiscal_required.next_action")
    return None


# advisory_when_ratio_ge(["numerator_id", "denominator_id", "threshold"]) —
# fires a WARNING-severity ADVISORY finding when numerator/denominator >= threshold
# and denominator > 0. Used for Art. 110.3.b RIRPF M130 high-retention exemption.
_PREDICATE_ADVISORY_WHEN_RATIO_GE = _re.compile(
    r'^advisory_when_ratio_ge\(\["(?P<num>[^"]+)",\s*"(?P<den>[^"]+)",\s*"(?P<thr>[^"]+)"\]\)$'
)


def _parse_predicate_casilla_ids(ids_fragment: str) -> list[str]:
    """Parse the comma-separated quoted-id list from a predicate expression."""
    ids: list[str] = []
    for token in ids_fragment.split(","):
        token = token.strip().strip('"').strip("'")
        if token:
            ids.append(token)
    return ids


def _evaluate_applicability_filter(filter_name: str, profile: TaxpayerProfile) -> bool:
    """Return True iff the profile state matches the named applicability filter.

    Used by ``profile_field_required`` predicates to gate whether the
    field-presence requirement applies to a given profile. Adding a
    new filter is a deliberate authoring decision: the dispatch table
    here is the single source of truth, and an unknown filter name
    raises ``ValueError`` rather than silently passing (mirrors the
    KNOWN_VERIFICATION_PREDICATE_OPERATORS gate).
    """
    if filter_name == "non_resident_irnr_non_eea":
        # TRLIRNR Art 10 letter applies only to non-EU residents.
        # Phase 1 uses the broader ue_eee_status per m210-irnr-full-engine
        # ADR §D2.5 escape hatch: EEA residents are exempt because of the
        # bilateral mutual-assistance regime.
        return profile.fiscal_residency is FiscalResidency.NON_RESIDENT_IRNR and not profile.ue_eee_status
    raise ModeloApplicabilityFilterError(f"Unknown applicability filter: {filter_name!r}")


def _evaluate_predicate_expression(
    expression: str,
    casilla_values: Mapping[str, Decimal],
    profile: TaxpayerProfile,
) -> bool:
    """Return True when the predicate holds, False when it is violated.

    Supports the DSL operators registered in
    :data:`aeat.domain.calculations.registry._schema.KNOWN_VERIFICATION_PREDICATE_OPERATORS`:

    - ``all_nonzero(["id1", "id2", ...])`` — all ids must have a non-zero value.
    - ``any_nonzero(["id1", "id2", ...])`` — at least one id must have a non-zero value.
    - ``cap_le_when_positive(["limited_id", "ceiling_id"])`` — when the ceiling
      casilla is strictly positive, the limited casilla MUST NOT exceed it.
    - ``implies_nonzero(["antecedent_id", "consequent_id"])`` — material
      implication with strictly-positive antecedent: predicate holds iff
      antecedent <= 0 OR consequent != 0.
    - ``profile_field_required("field_name", "applicability_filter")`` —
      profile-state-aware conditional non-zero requirement; sibling of
      ``implies_nonzero`` per the dsl-conditional-predicate ADR.

    An expression that does not match any registered pattern is treated as
    holding (i.e. unknown predicates do not block the operator). The
    authoring-time validator in
    :mod:`aeat.domain.calculations.registry._validate_surfaces` is the gate
    against typos reaching this branch.
    """
    expr = expression.strip()

    m = _PREDICATE_ALL_NONZERO.match(expr)
    if m:
        ids = _parse_predicate_casilla_ids(m.group("ids"))
        return all(casilla_values.get(cid, Decimal(0)) != Decimal(0) for cid in ids)

    m = _PREDICATE_ANY_NONZERO.match(expr)
    if m:
        ids = _parse_predicate_casilla_ids(m.group("ids"))
        return any(casilla_values.get(cid, Decimal(0)) != Decimal(0) for cid in ids)

    m = _PREDICATE_CAP_LE_WHEN_POSITIVE.match(expr)
    if m:
        # cap_le_when_positive(["limited_id", "ceiling_id"]) — when the
        # ceiling casilla is strictly positive, the limited casilla value
        # MUST NOT exceed the ceiling, enforcing AEAT cap rules like
        # Modelo 131 C11 ≤ C10 (and Modelo 130 C15 ≤ C14) "en ningún
        # caso podrá figurar... un importe superior a la cantidad positiva
        # consignada".
        ids = _parse_predicate_casilla_ids(m.group("ids"))
        if len(ids) != 2:
            return True
        limited_id, ceiling_id = ids[0], ids[1]
        ceiling = casilla_values.get(ceiling_id, Decimal(0))
        if ceiling <= Decimal(0):
            return True
        limited = casilla_values.get(limited_id, Decimal(0))
        return limited <= ceiling

    m = _PREDICATE_IMPLIES_NONZERO.match(expr)
    if m:
        # implies_nonzero(["antecedent_id", "consequent_id"]) — material
        # implication "antecedent strictly positive → consequent non-zero".
        # Predicate holds (returns True) when:
        #   - the expression is malformed (defensive — same shape as
        #     cap_le_when_positive),
        #   - the antecedent is <= 0 (implication trivially holds with
        #     non-positive antecedent — mirrors AEAT phrasing "cuando C01
        #     sea positivo"),
        #   - or the consequent is non-zero.
        # The violation case (returns False) is "antecedent strictly
        # positive AND consequent == 0". A missing consequent reads as
        # Decimal(0) via the .get default — same convention as the other
        # operators.
        ids = _parse_predicate_casilla_ids(m.group("ids"))
        if len(ids) != 2:
            return True
        antecedent_id, consequent_id = ids[0], ids[1]
        antecedent = casilla_values.get(antecedent_id, Decimal(0))
        if antecedent <= Decimal(0):
            return True
        consequent = casilla_values.get(consequent_id, Decimal(0))
        return consequent != Decimal(0)

    m = _PREDICATE_PROFILE_FIELD_REQUIRED.match(expr)
    if m:
        field_name = m.group("field")
        filter_name = m.group("filter")
        # Applicability dispatch: filter_name -> profile-predicate function.
        # An unknown filter raises ValueError (single source of truth in the
        # dispatch table) rather than silently passing the predicate.
        if not _evaluate_applicability_filter(filter_name, profile):
            return True  # rule doesn't apply; predicate trivially holds
        field_value = getattr(profile, field_name, None)
        return not (field_value is None or (isinstance(field_value, str) and not field_value.strip()))

    return True


def _rewrite_m210_sentinels(
    observations: tuple[CasillaObservation, ...],
    *,
    profile: TaxpayerProfile,
    snapshot: RegistrySnapshot,
    year: int,
    tipo_renta: str,
) -> tuple[tuple[CasillaObservation, ...], list[ModeloVerificationFinding]]:
    """Sweep engine observations for M210 rate sentinels and rewrite them.

    The ``m210_resolve_rate`` formula op emits one of the
    ``M210_RATE_SENTINELS`` Decimals (``-1``, ``-2``, ``-3``) when the
    rate cannot be deterministically resolved from registry parameters
    at evaluation time. The verification sweep here:

    1. Finds every observation whose ``value`` matches a sentinel.
    2. Re-invokes :func:`_resolve_m210_rate` to compute the
       authoritative ``(rate, finding)`` pair from the profile +
       snapshot.
    3. Replaces the sentinel observation with one carrying the
       resolved rate (or ``Decimal(0)`` when the helper returns
       ``rate is None``, which is the safe operator-facing default
       for a rate the registry could not determine).
    4. Aggregates every emitted finding into the returned list.

    A pure function over the inputs; no state mutation. The non-
    sentinel observations pass through unchanged. The ``tipo_renta``
    argument is the text input the operator declared for the M210
    work unit; it is the discriminator the formula op consumed
    upstream and is therefore the discriminator the resolution
    helper must consume here.
    """
    findings: list[ModeloVerificationFinding] = []
    rewritten: list[CasillaObservation] = []
    for obs in observations:
        if obs.value not in M210_RATE_SENTINELS:
            rewritten.append(obs)
            continue
        rate, obs_findings = _resolve_m210_rate(profile, tipo_renta, year, snapshot)
        findings.extend(obs_findings)
        new_value = rate if rate is not None else Decimal(0)
        rewritten.append(obs.model_copy(update={"value": new_value}))
    return tuple(rewritten), findings


def _evaluate_advisory_predicate_fires(
    expression: str,
    casilla_values: Mapping[str, Decimal],
) -> bool:
    """Return True when an advisory predicate's condition is met (i.e. advisory should fire).

    Supports:

    - ``advisory_when_ratio_ge(["num_id", "den_id", "threshold"])`` — fires when
      num/den >= threshold and den > 0. Art. 110.3.b RIRPF: exempt from M130
      when retenciones_acumuladas / rendimientos_brutos >= 0.70.
    - ``implies_nonzero(["antecedent_id", "consequent_id"])`` — fires when the
      material implication is violated, i.e. the antecedent is strictly positive
      but the consequent is zero. As an ADVISORY this surfaces a non-blocking
      operator alert for the same shape the BLOCKING_RULE variant refuses: e.g.
      a positive resultado contable with an undetermined (zero) base imponible,
      a likely silent under-declaration that a positive-result entity should
      confirm (legitimate zero-base via BIN compensation remains permissible,
      hence advisory rather than blocking).
    """
    expr = expression.strip()
    m = _PREDICATE_ADVISORY_WHEN_RATIO_GE.match(expr)
    if m:
        num_id = m.group("num")
        den_id = m.group("den")
        thr_str = m.group("thr")
        den = casilla_values.get(den_id, Decimal(0))
        if den <= Decimal(0):
            return False
        num = casilla_values.get(num_id, Decimal(0))
        try:
            threshold = Decimal(thr_str)
        except _decimal.InvalidOperation:
            return False
        return (num / den) >= threshold
    m = _PREDICATE_IMPLIES_NONZERO.match(expr)
    if m:
        ids = _parse_predicate_casilla_ids(m.group("ids"))
        if len(ids) != 2:
            return False
        antecedent = casilla_values.get(ids[0], Decimal(0))
        consequent = casilla_values.get(ids[1], Decimal(0))
        return antecedent > Decimal(0) and consequent == Decimal(0)
    return False


def _evaluate_verification_predicates(
    predicates: tuple[VerificationPredicateDefinition, ...],
    casilla_values: Mapping[str, Decimal],
    profile: TaxpayerProfile,
) -> list[ModeloVerificationFinding]:
    """Evaluate Layer 2 cross-casilla predicates; return findings for violations or advisories.

    ``profile`` is threaded through to support profile-state-aware
    predicate operators such as ``profile_field_required`` (m210
    representante-fiscal gate per ADR §D2.5). Casilla-only operators
    ignore the parameter.
    """
    if not predicates:
        return []

    findings: list[ModeloVerificationFinding] = []
    for predicate in predicates:
        if predicate.finding_kind == "ADVISORY":
            # ADVISORY predicates fire a WARNING finding when their condition IS met
            # (affirmative logic — opposite of BLOCKING_RULE predicates).
            if _evaluate_advisory_predicate_fires(predicate.expression, casilla_values):
                advisory_key = f"application.modelo.findings.{predicate.predicate_id.replace('-', '_')}"
                findings.append(
                    ModeloVerificationFinding(
                        kind=ModeloVerificationFindingKind.ADVISORY,
                        severity=ModeloVerificationFindingSeverity.WARNING,
                        message=tr(advisory_key),
                        legal_refs=tuple(str(r) for r in predicate.legal_refs),
                    )
                )
        else:
            if not _evaluate_predicate_expression(predicate.expression, casilla_values, profile):
                next_action = _resolve_predicate_next_action(predicate.predicate_id)
                if next_action is None:
                    next_action = tr(
                        "application.modelo.findings.cross_casilla_invariant_next_action",
                        predicate_id=predicate.predicate_id,
                    )
                findings.append(
                    ModeloVerificationFinding(
                        kind=ModeloVerificationFindingKind.BLOCKING_RULE,
                        severity=ModeloVerificationFindingSeverity.BLOCKING,
                        message=tr(
                            "application.modelo.findings.cross_casilla_invariant_violated",
                            predicate_id=predicate.predicate_id,
                            expression=predicate.expression,
                        ),
                        next_action=next_action,
                        legal_refs=tuple(str(r) for r in predicate.legal_refs),
                    )
                )
    return findings


def _manual_fact_basis_entries(inputs_snapshot: Mapping[str, str]) -> tuple[ManualFactBasisEntry, ...]:
    """Project a revision's operator casilla inputs into manual fact-basis entries.

    The ``inputs_snapshot`` holds the caller-supplied (operator-entered) casilla
    values that are not ledger-derived; each non-empty entry is part of the fact
    basis a filing artefact must explain. Blank values are skipped (they carry no
    fact).
    """
    return tuple(
        ManualFactBasisEntry(casilla=casilla, value=value)
        for casilla, value in sorted(inputs_snapshot.items())
        if value.strip()
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


def _cross_period_clean_state_verdict_for_work_unit(
    work_unit: WorkUnit,
    *,
    observation_repository: CalculationObservationRepository,
    filing_repository: ModeloRecordCatalogueRepositoryProtocol,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol,
    verification_repository: VerificationReportCatalogueRepositoryProtocol,
    expected_member_sets: Iterable[CrossPeriodExpectedMemberSet] = (),
) -> CrossPeriodCleanStateVerdict | None:
    from ...domain.calculations.registry import RegistrySnapshotError

    try:
        snapshot = _authority_via_resources().snapshot(
            work_unit.modelo,
            filing_year=work_unit.filing_year,
            period=work_unit.period,
        )
    except (FileNotFoundError, RegistrySnapshotError):
        return None
    return evaluate_cross_period_clean_state(
        snapshot,
        bucket_id=work_unit.bucket_id,
        observation_repository=observation_repository,
        filing_repository=filing_repository,
        calculation_repository=calculation_repository,
        verification_repository=verification_repository,
        expected_member_sets=expected_member_sets,
    )


def _cross_period_clean_state_findings(
    verdict: CrossPeriodCleanStateVerdict | None,
    *,
    iva_compensation_decision: object | None = None,
) -> tuple[ModeloVerificationFinding, ...]:
    if verdict is None or verdict.clean:
        return ()
    findings: list[ModeloVerificationFinding] = []
    for evidence in verdict.dependencies:
        if evidence.clean:
            continue
        if _iva_wallet_decision_covers_cross_period_dependency(verdict, evidence, iva_compensation_decision):
            continue
        requirement = evidence.requirement
        blocker_text = _summarize_cross_period_ids(tuple(blocker.value for blocker in evidence.blockers))
        origin_text = _summarize_cross_period_ids(requirement.origin_ids)
        findings.append(
            ModeloVerificationFinding(
                kind=ModeloVerificationFindingKind.CROSS_PERIOD_DEPENDENCY_UNCLEAN,
                severity=ModeloVerificationFindingSeverity.BLOCKING,
                message=(
                    "cross-period dependency is not clean: "
                    f"modelo={requirement.source_modelo} year={requirement.filing_year} "
                    f"period={requirement.period} origin={requirement.origin.value} "
                    f"origin_ids={origin_text} blockers={blocker_text}"
                ),
                next_action=_cross_period_clean_state_next_action(verdict, evidence),
            )
        )
    return tuple(findings)


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


def _cross_period_clean_state_next_action(
    verdict: CrossPeriodCleanStateVerdict,
    evidence: CrossPeriodDependencyEvidence,
) -> str:
    requirement = evidence.requirement
    blockers = set(evidence.blockers)
    target_capture = (
        "aeat app live filed capture-sources "
        f"--modelo {verdict.target_modelo} "
        f"--year {verdict.target_filing_year} "
        f"--period {verdict.target_period}"
    )
    source_hint = (
        f"source modelo={requirement.source_modelo} year={requirement.filing_year} period={requirement.period}"
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
        CrossPeriodCleanStateBlocker.MISSING_JUSTIFICANTE_VERIFICATION,
        CrossPeriodCleanStateBlocker.LOCAL_FILING_MISSING_EXTERNAL_EVIDENCE,
    }:
        return (
            f"Capture or import AEAT justificante evidence for {source_hint}. "
            f"Run `{target_capture}` or `aeat app modelo reconcile-from-justificante PATH WORK_UNIT_ID`, "
            "then rerun verification."
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
) -> None:
    verdict = _cross_period_clean_state_verdict_for_work_unit(
        work_unit,
        observation_repository=observation_repository,
        filing_repository=filing_repository,
        calculation_repository=calculation_repository,
        verification_repository=verification_repository,
        expected_member_sets=expected_member_sets,
    )
    findings = _cross_period_clean_state_findings(
        verdict,
        iva_compensation_decision=iva_compensation_decision,
    )
    if not findings:
        return
    first = findings[0]
    raise ModeloCrossPeriodCleanStateError(
        first.message,
        translated_message="application.modelo.errors.cross_period_clean_state_incomplete",
        context={
            "modelo": work_unit.modelo,
            "filing_year": str(work_unit.filing_year),
            "period": work_unit.period,
            "finding_count": str(len(findings)),
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
    if getattr(decision, "selected_amount", None) is None:
        return False
    selected_authority = str(getattr(decision, "selected_authority", ""))
    if selected_authority not in {"aeat_wallet", "taxpayer_override"}:
        return False
    source_kinds = {str(getattr(source, "source_kind", "")) for source in getattr(decision, "authority_sources", ())}
    return bool(source_kinds & {"aeat_wallet", "taxpayer_override"})


def verify_modelo_revision(
    calculation_revision_id: str,
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
    cross_period_expected_member_sets: Iterable[CrossPeriodExpectedMemberSet] = (),
    workflow_engine: WorkflowEngine | None = None,
    workflow_runs_dir: Path | None = None,
    settings: Settings | None = None,
    clock: datetime | None = None,
) -> VerificationReport:
    """Evaluate a draft revision against registry, clean-state, provenance, and workflow gates.

    Returns a :class:`VerificationReport`. Uses :class:`TaxpayerProfile` and
    :class:`TransactionCatalogueRepository` for compliance checks.
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
        raise CalculationRevisionStateError(
            f"calculation revision {calculation_revision_id!r} is in state "
            f"{target.state.value!r}; only DRAFT revisions can be verified"
        )

    _assert_revision_content_integrity(target)

    work_units = wu_repo.load()
    work_unit = work_units.get(target.work_unit_id)
    if work_unit is None:
        raise WorkUnitNotFoundError(
            f"calculation revision {calculation_revision_id!r} references missing work_unit_id={target.work_unit_id!r}"
        )

    findings, resolved_casillas, missing_required = _collect_revision_verification_findings(
        work_unit=work_unit,
        target=target,
        profile=workflow_profile,
    )
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
                observation_repository=obs_repo,
                filing_repository=fr_repo,
                calculation_repository=cr_repo,
                verification_repository=vr_repo,
                expected_member_sets=_cross_period_expected_member_sets_from_profile(
                    workflow_profile,
                    cross_period_expected_member_sets,
                ),
            ),
            iva_compensation_decision=iva_compensation_decision,
        )
    )
    completeness, granted = _classify_verification_outcome(
        findings=findings,
        missing_required=missing_required,
    )

    now = clock or _utc_now()
    report_id = derive_verification_report_id(
        calculation_revision_id=calculation_revision_id,
        run_at=now,
        verified_by=actor.strip(),
    )
    report = VerificationReport(
        verification_report_id=report_id,
        calculation_revision_id=calculation_revision_id,
        completeness_status=completeness,
        findings=tuple(findings),
        resolved_casillas=tuple(resolved_casillas),
        missing_required_casillas=tuple(missing_required),
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
        missing_required_count=len(missing_required),
        actor=actor,
        occurred_at=now,
    )

    return report


def _persist_verified_revision_evidence(
    *,
    target: CalculationRevision,
    actor: str,
    now: datetime,
    revisions: CalculationRevisionCatalogue,
    work_unit: WorkUnit,
    transaction_repository: TransactionCatalogueRepository | None,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol,
) -> None:
    tx_repo = transaction_repository or TransactionCatalogueRepository(bucket_id=work_unit.bucket_id)
    catalogue = tx_repo.load()
    filing_snapshot = compute_ledger_filing_snapshot(
        source_transaction_ids=target.source_transaction_ids,
        catalogue=catalogue,
        captured_at=now,
    )
    filing_evidence = compute_ledger_filing_evidence(
        source_transaction_ids=target.source_transaction_ids,
        catalogue=catalogue,
        snapshot_fingerprint=filing_snapshot.snapshot_fingerprint,
        captured_at=now,
        manual_entries=_manual_fact_basis_entries(target.inputs_snapshot),
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
        }
    )
    calculation_repository.save(upsert_calculation_revision(revisions, verified))


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
            "period": work_unit.period,
            "completeness_status": completeness.value,
            "finding_count": str(finding_count),
            "missing_required_count": str(missing_required_count),
        },
    )


def _collect_revision_verification_findings(
    *,
    work_unit: WorkUnit,
    target: CalculationRevision,
    profile: TaxpayerProfile,
) -> tuple[list[ModeloVerificationFinding], list[str], list[str]]:
    """Build the verification finding list for one calculation revision.

    Returns ``(findings, resolved_casillas, missing_required)``. A
    revision whose ``(modelo, year, period)`` triple does not resolve
    against the registry yields a single BLOCKING_RULE finding and
    empty resolved/missing lists — there is no per-casilla check to
    perform without a registry snapshot.

    With a snapshot present, the operator-supplied
    ``inputs_snapshot`` keys are compared against the registry's
    required-input casilla set. Each missing required casilla
    produces a MISSING_REQUIRED_CASILLA finding plus an entry in the
    missing-required list; each present required casilla lands in
    the resolved-casillas list.
    """
    findings: list[ModeloVerificationFinding] = []
    resolved_casillas: list[str] = []
    missing_required: list[str] = []

    from ...domain.calculations.registry import RegistrySnapshotError

    try:
        authority = _authority_via_resources()
        snapshot = authority.snapshot(
            work_unit.modelo,
            filing_year=work_unit.filing_year,
            period=work_unit.period,
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
                    period=str(work_unit.period),
                ),
                next_action="aeat app registry verify",
            )
        )
        return findings, resolved_casillas, missing_required

    revision_keys = set(target.inputs_snapshot)
    for casilla in snapshot.revision.casillas:
        casilla_id = str(casilla.id)
        if casilla.input_kind == InputKind.MANUAL and casilla.required:
            if casilla_id in revision_keys:
                resolved_casillas.append(casilla_id)
            else:
                missing_required.append(casilla_id)
                findings.append(
                    _missing_required_casilla_finding(
                        casilla_id,
                        target.work_unit_id,
                        casilla_def=casilla,
                    )
                )

    # Layer 2: cross-casilla predicate gate.
    findings.extend(
        _evaluate_verification_predicates(
            snapshot.revision.verification_predicates,
            target.casilla_values,
            profile,
        )
    )

    # Advisory: DT 12ª LIRPF — warn when a large trabajo income (0003 > 20 000)
    # is present but the trabajo reducción slot (0011) is zero / absent.
    # This heuristic surfaces the DT_12A_REDUCCION_POSSIBLE advisory so
    # retirees do not silently lose the 40% reducción for pre-2007 aportaciones.
    dt12_finding = _dt12_reduccion_advisory_finding(snapshot.revision, target.casilla_values)
    if dt12_finding is not None:
        findings.append(dt12_finding)

    return findings, resolved_casillas, missing_required


_DT12_TRABAJO_INGRESO_ROLE = "irpf_rendimiento_trabajo_importe_integro_dinerario"
_DT12_TRABAJO_REDUCCION_ROLE = "irpf_rendimiento_trabajo_reduccion"
#: Heuristic threshold above which DT 12ª advisory fires (large lump-sum pension).
_DT12_LARGE_TRABAJO_THRESHOLD = Decimal("20000")


def _dt12_reduccion_advisory_finding(
    revision: object,
    casilla_values: Mapping[str, Decimal],
) -> ModeloVerificationFinding | None:
    """Return a DT_12A_REDUCCION_POSSIBLE WARNING when large trabajo income is present but no reducción is declared.

    The check is advisory only (WARNING severity); it does not block VERIFICADO_COMPLETO.
    Heuristic: casilla with semantic_role ``irpf_rendimiento_trabajo_importe_integro_dinerario``
    value > 20 000 AND casilla with role ``irpf_rendimiento_trabajo_reduccion`` is zero/absent.
    Returns ``None`` when the advisory does not apply or when the snapshot revision
    does not carry the required semantic roles (non-M100 modelos).
    """
    ingreso_id: str | None = None
    reduccion_id: str | None = None
    for casilla in getattr(revision, "casillas", ()):
        role = getattr(casilla, "semantic_role", None)
        if role == _DT12_TRABAJO_INGRESO_ROLE:
            ingreso_id = str(casilla.id)
        elif role == _DT12_TRABAJO_REDUCCION_ROLE:
            reduccion_id = str(casilla.id)

    if ingreso_id is None or reduccion_id is None:
        return None

    ingreso_value = casilla_values.get(ingreso_id, Decimal(0))
    reduccion_value = casilla_values.get(reduccion_id, Decimal(0))

    if ingreso_value > _DT12_LARGE_TRABAJO_THRESHOLD and reduccion_value == Decimal(0):
        return ModeloVerificationFinding(
            kind=ModeloVerificationFindingKind.BLOCKING_RULE,
            severity=ModeloVerificationFindingSeverity.WARNING,
            casilla_id=reduccion_id,
            message=tr(
                "application.modelo.findings.dt12a_reduccion_possible",
                ingreso_id=ingreso_id,
                ingreso_value=str(ingreso_value),
                reduccion_id=reduccion_id,
            ),
            next_action=tr("application.modelo.findings.dt12a_reduccion_next_action"),
            legal_refs=("ley-35-2006:dt-12",),
        )
    return None


def _missing_required_casilla_finding(
    casilla_id: str,
    work_unit_id: str,
    *,
    casilla_def: CasillaDefinition | None = None,
) -> ModeloVerificationFinding:
    legal_refs: tuple[str, ...] = tuple(str(r) for r in casilla_def.legal_refs) if casilla_def is not None else ()
    source_refs: tuple[str, ...] = tuple(str(r) for r in casilla_def.source_refs) if casilla_def is not None else ()
    return ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.MISSING_REQUIRED_CASILLA,
        severity=ModeloVerificationFindingSeverity.BLOCKING,
        casilla_id=casilla_id,
        message=tr("application.modelo.findings.missing_required_casilla", casilla_id=casilla_id),
        next_action=(f"aeat app modelo work calculate {work_unit_id} --casilla {casilla_id}=VALUE"),
        legal_refs=legal_refs,
        source_refs=source_refs,
    )


def _iva_wallet_blocking_verification_finding(decision: object) -> ModeloVerificationFinding:
    return ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.BLOCKING_RULE,
        severity=ModeloVerificationFindingSeverity.BLOCKING,
        message=_iva_wallet_blocked_message(decision),
        next_action=tr("application.modelo.findings.iva_wallet_next_action"),
    )


def _iva_wallet_error_verification_finding(error: ModeloIvaWalletReconciliationBlocked) -> ModeloVerificationFinding:
    return ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.BLOCKING_RULE,
        severity=ModeloVerificationFindingSeverity.BLOCKING,
        message=_translated_exception_message(error),
        next_action=tr("application.modelo.findings.iva_wallet_next_action"),
    )


def _translated_exception_message(error: ModeloIvaWalletReconciliationBlocked) -> str:
    key = getattr(error, "translated_message", None)
    if isinstance(key, str) and key.strip() and key != "application.modelo.errors.iva_wallet_blocked":
        return tr(key)
    return str(error)


def _classify_verification_outcome(
    *,
    findings: list[ModeloVerificationFinding],
    missing_required: list[str],
) -> tuple[VerificationCompletenessStatus, bool]:
    """Compute the completeness status + granted flag from finding shape.

    With no BLOCKING finding, the report is COMPLETE and the
    verified-complete transition is granted. With at least one
    BLOCKING_RULE finding, the report is BLOCKED. With BLOCKING
    findings that are exclusively MISSING_REQUIRED_CASILLA, the
    report is INCOMPLETE so the operator sees that completing the
    inputs unblocks the transition.
    """
    has_blocking = any(f.severity is ModeloVerificationFindingSeverity.BLOCKING for f in findings)
    if not has_blocking:
        return VerificationCompletenessStatus.COMPLETE, True
    has_blocking_rule = any(f.kind is ModeloVerificationFindingKind.BLOCKING_RULE for f in findings)
    if missing_required and not has_blocking_rule:
        return VerificationCompletenessStatus.INCOMPLETE, False
    return VerificationCompletenessStatus.BLOCKED, False
