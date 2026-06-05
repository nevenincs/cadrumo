"""Modelo work-unit lifecycle actions.

Each action loads the catalogue, applies a single mutation in
memory (or returns a read view), and writes the catalogue back.
The catalogue is content-addressed by ``work_unit_id`` so
deterministic derivation lets ``create_work_unit`` be idempotent:
calling it twice with the same four-axis key returns the same
record without producing a duplicate.

The action signatures take an explicit ``bucket_id`` so the
service layer is unit-testable without a workflow-state fixture.

Actions obtain a :class:`RegistrySnapshot` for the target revision from a
:class:`ValidatedRegistryAuthority`, then feed :class:`ModeloRevision` data
into the formula engine to produce or amend a calculation revision. Invoice
evidence is loaded from an :class:`InvoiceCatalogueRepository` when the
revision's source mesh includes invoice-backed bindings, and the
:class:`TransactionCatalogue` is consumed by the ledger aggregation step.
Ledger transactions are loaded via :class:`TransactionCatalogueRepository`.
Every mutating action emits a typed event to :class:`BucketEventHistoryRepository`.
The deadline window is derived from a :class:`TaxpayerProfile` when the
modelo has an obligation schedule.
"""

from __future__ import annotations

import asyncio
import decimal as _decimal
import re as _re
from collections.abc import Iterable, Mapping
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING

from ...core.config import Settings
from ...core.i18n import tr
from ...core.time import now as _utc_now
from ...domain.buckets import (
    BucketEventHistoryRepository,
    BucketEventObjectType,
    BucketEventType,
)
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
    CalculationRevisionAmendmentKind,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ...domain.modelos._errors import ModeloError
from ...domain.modelos._filing_record import (
    ExternalEvidence,
    ExternalEvidenceKind,
    ModeloRecord,
    ModeloRecordStatus,
    derive_filing_record_id,
)
from ...domain.modelos._filing_repository import (
    ModeloRecordCatalogueRepository,
    upsert_filing_record,
)
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
from ...domain.modelos._repository import (
    WorkUnitCatalogueRepository,
    upsert_work_unit,
)
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
from ...domain.modelos._work_unit import (
    WorkUnit,
    WorkUnitState,
)
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
from ..workflow import (
    WorkflowEngine,
    WorkflowPurpose,
    WorkflowResult,
    WorkflowRunRepository,
    WorkflowStage,
)
from ..workflow import (
    WorkflowInputMismatchError as WorkflowInputMismatchError,
)
from . import _iva_wallet_gate
from ._action_errors import (
    AmendmentEvidenceMissingError,
    AmendmentOverrideCasillaError,
    AmendmentTargetStateError,
    AmendmentVerificationRefusedError,
    CalculationRegistryUnavailableError,
    CalculationRevisionNotFoundError,
    CalculationRevisionStateError,
    CasillaProvenanceMissingError,
    ExternalModeloImportError,
    ModeloAggregationBindingError,
    ModeloApplicabilityFilterError,
    ModeloCrossPeriodCleanStateError,
    ModeloRecordNotFoundError,
    ModeloWorkflowGateError,
    StoredCalculationDriftError,
    VerificationReportNotFoundError,
    WorkUnitAlreadyDiscardedError,
    WorkUnitMutationRefusedError,
    WorkUnitNotFoundError,
)
from ._calculation_actions import (
    _IVA_LEDGER_EXEMPT_REGIMES as _IVA_LEDGER_EXEMPT_REGIMES,
)
from ._calculation_actions import (
    _iva_wallet_blocked_message as _iva_wallet_blocked_message,
)
from ._calculation_actions import (
    _raise_if_ledger_preflight_blocks_calculation as _raise_if_ledger_preflight_blocks_calculation,
)
from ._calculation_actions import (
    _reject_caller_overrides_of_source_bindings as _reject_caller_overrides_of_source_bindings,
)
from ._calculation_actions import (
    calculate_modelo_revision as calculate_modelo_revision,
)
from ._calculation_actions import (
    calculate_modelo_revision_from_bucket_aggregation as calculate_modelo_revision_from_bucket_aggregation,
)
from ._calculation_actions import (
    get_calculation_revision as get_calculation_revision,
)
from ._calculation_actions import (
    list_calculation_revisions as list_calculation_revisions,
)
from ._calculation_actions import (
    mark_revision_verificado_completo as mark_revision_verificado_completo,
)
from ._calculation_helpers import (
    amendment_observations as _amendment_observations,
)
from ._calculation_helpers import (
    external_filing_observations as _external_filing_observations,
)
from ._calculation_helpers import (
    resolve_registry_snapshot_for_work_unit as _resolve_registry_snapshot_for_work_unit,
)
from ._m210_rate import resolve_m210_rate as _resolve_m210_rate
from ._registry_helpers import (
    assert_revision_content_integrity as _assert_revision_content_integrity,
)
from ._registry_helpers import (
    reject_incomplete_amendment_casillas as _reject_incomplete_amendment_casillas,
)
from ._registry_helpers import (
    reject_unknown_import_casillas as _reject_unknown_import_casillas,
)
from ._registry_helpers import (
    reject_unknown_override_casillas as _reject_unknown_override_casillas,
)
from ._registry_resources import (
    authority_via_resources as _authority_via_resources,
)
from ._revision_persistence import (
    emit_bucket_event as _emit_bucket_event,
)
from ._revision_persistence import (
    persist_filed_revision,
)
from ._work_lifecycle import (
    create_work_unit as create_work_unit,
)
from ._work_lifecycle import (
    discard_work_unit as discard_work_unit,
)
from ._work_lifecycle import (
    get_work_unit as get_work_unit,
)
from ._work_lifecycle import (
    list_work_units as list_work_units,
)
from ._work_lifecycle import (
    rename_work_unit as rename_work_unit,
)
from ._workflow_gate import (
    _RevisionInputsProvider as _RevisionInputsProvider,
)
from ._workflow_gate import (
    build_revision_workflow_engine as _build_revision_workflow_engine,
)
from ._workflow_gate import (
    workflow_period_for_work_unit,
)

if TYPE_CHECKING:
    from ..calculations._observations_repository import IvaWalletDecisionRepository

ModeloIvaWalletReconciliationBlocked = _iva_wallet_gate.ModeloIvaWalletReconciliationBlocked
ModeloIvaWalletReconciliationBlockedError = _iva_wallet_gate.ModeloIvaWalletReconciliationBlockedError
_apply_iva_compensation_decision_binding = _iva_wallet_gate.apply_iva_compensation_decision_binding
_require_iva_compensation_revision_match = _iva_wallet_gate.require_persisted_iva_compensation_decision_matches_revision
_require_persisted_iva_compensation_decision_matches_revision = _require_iva_compensation_revision_match
_taxpayer_nif_for_bucket = _iva_wallet_gate.taxpayer_nif_for_bucket
iva_wallet_blocked_message = _iva_wallet_gate.iva_wallet_blocked_message
resolve_iva_compensation_decision_for_calculation = _iva_wallet_gate.resolve_iva_compensation_decision_for_calculation

def _run_revision_workflow_gate(
    *,
    engine: WorkflowEngine,
    profile: TaxpayerProfile,
    work_unit: WorkUnit,
    today: date,
    runs_dir: Path | None,
    run_repository: WorkflowRunRepository,
    resumed_from: str | None = None,
    purpose: WorkflowPurpose = WorkflowPurpose.FILE,
) -> WorkflowResult:
    result = asyncio.run(
        engine.run_for_period(
            profile,
            work_unit.modelo,
            workflow_period_for_work_unit(work_unit),
            today=today,
            resumed_from=resumed_from,
            purpose=purpose,
        )
    )
    run_repository.save(result, runs_dir=runs_dir)
    if result.final_stage is WorkflowStage.ABORTED:
        raise ModeloWorkflowGateError(result)
    return result


# ---------------------------------------------------------------------------
# Calculation revision lifecycle: calculate / verify / mark-verified / file
# ---------------------------------------------------------------------------



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


def _assert_evidence_covers_snapshot(
    snapshot: LedgerFilingSnapshot, evidence: LedgerFilingEvidence
) -> None:
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
            "ledger filing evidence does not cover the fingerprint snapshot: "
            f"missing={missing} extra={extra}",
        )


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
    text = (
        ", ".join(items)
        if len(items) <= limit
        else ", ".join((*items[:limit], f"+{len(items) - limit} more"))
    )
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
        f"source modelo={requirement.source_modelo} "
        f"year={requirement.filing_year} "
        f"period={requirement.period}"
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
    evidence,
    decision: object | None,
) -> bool:
    """Return whether a persisted Modelo 303 wallet decision covers the dependency."""
    if decision is None:
        return False
    requirement = evidence.requirement
    if (
        verdict.target_modelo != "303"
        or requirement.source_modelo != "303"
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
    """Evaluate a draft revision against the four-layer verified-complete gate.

    ``workflow_profile`` is the :class:`TaxpayerProfile` used to drive the
    workflow engine and filing deadline checks. The ``transaction_repository``
    is a :class:`TransactionCatalogueRepository` used to query ledger entries.

    The gate is described fully in the package docstring
    (:mod:`aeat.application.modelo`). This function is the implementation
    entry point.

    Pipeline:

    1. **State machine** -- load the revision; it must be in ``BORRADOR``
       (DRAFT) state. Any other state raises
       :exc:`CalculationRevisionStateError`.
    2. **Registry snapshot** -- resolve the snapshot for the parent work
       unit's ``(modelo, filing_year, period)``. On failure, emit a
       BLOCKING finding and refuse the transition immediately.
    3. **Layer 1 — required-input gate** -- for each casilla declared
       ``required = true`` and ``input_kind = "manual"`` in the registry,
       check that the revision's ``casilla_values`` contains a value.
       Missing entries produce
       :attr:`~aeat.domain.modelos._verification_report.ModeloVerificationFindingKind.MISSING_REQUIRED_CASILLA`
       findings and set ``completeness_status`` to ``INCOMPLETE``.
    4. **Layer 2 — cross-casilla predicate gate** -- evaluate each
       :class:`~aeat.domain.calculations.registry.VerificationPredicateDefinition`
       from the snapshot against the stored ``casilla_values``.  A failing
       predicate produces a
       :attr:`~aeat.domain.modelos._verification_report.ModeloVerificationFindingKind.BLOCKING_RULE`
       finding.
    5. **Provenance re-validation** -- call
       :func:`_assert_revision_content_integrity` to re-derive the SHA-256
       content address and check that each ``CasillaObservation.value``
       matches ``casilla_values`` for the same casilla.  Either mismatch
       raises :exc:`StoredCalculationDriftError`.
    6. **Workflow engine gate** -- when layers 1-3 produce zero blocking
       findings, run the WorkflowEngine-owned preflight with
       ``WorkflowPurpose.VERIFY`` before mutating state.  This gate
       validates the draft against the registry but is independent of the
       AEAT filing calendar.
    7. **Persist** -- write the :class:`~aeat.domain.modelos._verification_report.ModeloVerificationReport`
       to the verification-report catalogue.  Failed attempts are persisted
       so the audit trail records why the transition was refused.

    Args:
        calculation_revision_id: The id of the draft revision to verify.
        actor: Operator identifier stamped as ``verified_by``.
        workflow_profile: The taxpayer profile used to evaluate workflow gate
            conditions.
        work_unit_repository: Optional work-unit catalogue repository override.
        calculation_repository: Optional calculation-revision catalogue
            repository override.
        filing_repository: Optional filing-record catalogue repository override
            used by the cross-period clean-state proof.
        transaction_repository: Optional transaction catalogue repository
            override consulted by the snapshot resolver and ledger-backed
            binding checks.
        verification_repository: Optional verification-report catalogue
            repository override.
        bucket_event_repository: Optional bucket-event history repository
            override.
        iva_compensation_decision_repository: Optional IVA wallet decision
            repository override.
        calculation_observation_repository: Optional calculation-observation
            repository override used by the cross-period clean-state proof.
        cross_period_expected_member_sets: Optional expected grupo member
            rosters used by the cross-period clean-state proof.
        workflow_engine: Optional workflow engine override for the preflight gate.
        workflow_runs_dir: Optional workflow runs directory override.
        settings: Optional settings override.
        clock: Optional UTC timestamp override.

    Returns:
        The persisted :class:`VerificationReport` for the revision.

    Raises:
        CalculationRevisionNotFoundError: When the revision id is absent.
        CalculationRevisionStateError: When the revision is not in BORRADOR
            state.  Re-verifying a verified-complete or filed revision is
            rejected; the operator must produce a fresh calculation revision
            (which lands as a new draft).
        WorkUnitNotFoundError: When the revision's parent work unit cannot
            be loaded.
    """
    cr_repo = calculation_repository or CalculationRevisionCatalogueRepository()
    wu_repo = work_unit_repository or WorkUnitCatalogueRepository()
    vr_repo = verification_repository or VerificationReportCatalogueRepository()
    fr_repo = filing_repository or ModeloRecordCatalogueRepository()
    obs_repo = calculation_observation_repository or CalculationObservationRepository()
    bv_repo = bucket_event_repository or BucketEventHistoryRepository()
    run_repo = WorkflowRunRepository(objects=bv_repo.secure_object_repository)

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
                expected_member_sets=cross_period_expected_member_sets,
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
        # Back the verified revision with an immutable content-addressed ledger
        # snapshot over its contributing rows (modelo-filing-ledger-snapshot ADR).
        # Uniform for every modelo: a non-ledger revision has no
        # source_transaction_ids and gets a valid empty snapshot.
        tx_repo = transaction_repository or TransactionCatalogueRepository(bucket_id=work_unit.bucket_id)
        catalogue = tx_repo.load()
        filing_snapshot = compute_ledger_filing_snapshot(
            source_transaction_ids=target.source_transaction_ids,
            catalogue=catalogue,
            captured_at=now,
        )
        # Bundle the fact basis behind the revision (modelo-export-evidence-parity
        # ADR): the typed contributing-row evidence + the operator manual inputs,
        # pegged to the snapshot fingerprint. Reuses the single catalogue load.
        filing_evidence = compute_ledger_filing_evidence(
            source_transaction_ids=target.source_transaction_ids,
            catalogue=catalogue,
            snapshot_fingerprint=filing_snapshot.snapshot_fingerprint,
            captured_at=now,
            manual_entries=_manual_fact_basis_entries(target.inputs_snapshot),
        )
        # No-silent-omission guard: every fingerprinted contributor must appear in
        # the bundled evidence.
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
        cr_repo.save(upsert_calculation_revision(revisions, verified))

    _emit_bucket_event(
        repository=bv_repo,
        bucket_id=work_unit.bucket_id,
        event_type=(
            BucketEventType.MODELO_VERIFICATION_PASSED if granted else BucketEventType.MODELO_VERIFICATION_REFUSED
        ),
        occurred_at=now,
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
            "finding_count": str(len(findings)),
            "missing_required_count": str(len(missing_required)),
        },
    )

    return report


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



def file_modelo_revision(
    calculation_revision_id: str,
    *,
    actor: str,
    workflow_profile: TaxpayerProfile,
    notes: str | None = None,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol | None = None,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol | None = None,
    filing_repository: ModeloRecordCatalogueRepositoryProtocol | None = None,
    verification_repository: VerificationReportCatalogueRepositoryProtocol | None = None,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol | None = None,
    iva_compensation_decision_repository: IvaWalletDecisionRepository | None = None,
    calculation_observation_repository: CalculationObservationRepository | None = None,
    cross_period_expected_member_sets: Iterable[CrossPeriodExpectedMemberSet] = (),
    workflow_engine: WorkflowEngine | None = None,
    workflow_runs_dir: Path | None = None,
    settings: Settings | None = None,
    clock: datetime | None = None,
) -> ModeloRecord:
    """File a verified-complete revision as the current filed answer.

    State transitions performed atomically (from the caller's
    perspective — each repository save is sequenced):

    1. Verify the revision is in ``VERIFICADO_COMPLETO`` state.
    2. Run the workflow gate for the revision's modelo and period.
    3. Look up any existing current filing record for the same
       (bucket, modelo, year, period) tuple.
    4. If a prior current filing exists:
        * mark the prior filing record ``SUPERSEDED`` with
          ``superseded_at`` and ``superseded_by_filing_record_id``;
        * transition the prior filed calculation revision from
          ``FILED`` to ``FILED_SUPERSEDED``.
    5. Create the new filing record with status ``CURRENT``.
    6. Transition the target calculation revision from
       ``VERIFICADO_COMPLETO`` to ``FILED``.
    7. Advance the work unit's ``filed_calculation_revision_id``
       and ``current_filing_record_id`` pointers.

    Args:
        calculation_revision_id: The id of the verified-complete revision
            to file.
        actor: Operator identifier recorded in the filing record and audit
            trail.
        workflow_profile: The :class:`TaxpayerProfile` used to evaluate workflow
            gate conditions.
        notes: Optional operator-supplied filing notes.
        work_unit_repository: Optional work-unit catalogue repository override.
        calculation_repository: Optional calculation-revision catalogue
            repository override.
        filing_repository: Optional filing-record catalogue repository
            override.
        verification_repository: Optional verification-report catalogue
            repository override used by the cross-period clean-state proof.
        bucket_event_repository: Optional bucket-event history repository
            override.
        iva_compensation_decision_repository: Optional IVA wallet decision
            repository override.
        calculation_observation_repository: Optional calculation-observation
            repository override used by the cross-period clean-state proof.
        cross_period_expected_member_sets: Optional expected grupo member
            rosters used by the cross-period clean-state proof.
        workflow_engine: Optional workflow engine override for the preflight
            gate.
        workflow_runs_dir: Optional workflow runs directory override.
        settings: Optional settings override.
        clock: Optional UTC timestamp override.

    Returns:
        The newly created :class:`ModeloRecord` in ``CURRENT`` status.

    Raises:
        CalculationRevisionNotFoundError: When the revision id is
            absent.
        CalculationRevisionStateError: When the revision is not in
            ``VERIFICADO_COMPLETO`` state.
        WorkUnitNotFoundError: When the revision's parent work
            unit cannot be loaded.
    """
    wu_repo = work_unit_repository or WorkUnitCatalogueRepository()
    cr_repo = calculation_repository or CalculationRevisionCatalogueRepository()
    fr_repo = filing_repository or ModeloRecordCatalogueRepository()
    vr_repo = verification_repository or VerificationReportCatalogueRepository()
    obs_repo = calculation_observation_repository or CalculationObservationRepository()
    bv_repo = bucket_event_repository or BucketEventHistoryRepository()
    run_repo = WorkflowRunRepository(objects=bv_repo.secure_object_repository)

    revisions = cr_repo.load()
    target = revisions.get(calculation_revision_id)
    if target is None:
        raise CalculationRevisionNotFoundError(
            translated_message="application.modelo.errors.calculation_revision_not_found",
            context={"calculation_revision_id": calculation_revision_id},
        )
    if target.state is not CalculationRevisionState.VERIFICADO_COMPLETO:
        raise CalculationRevisionStateError(
            f"calculation revision {calculation_revision_id!r} is in state "
            f"{target.state.value!r}; only VERIFICADO_COMPLETO revisions can be filed"
        )

    work_units = wu_repo.load()
    work_unit = work_units.get(target.work_unit_id)
    if work_unit is None:
        raise WorkUnitNotFoundError(
            f"calculation revision {calculation_revision_id!r} references missing work_unit_id={target.work_unit_id!r}"
        )
    iva_compensation_decision = _require_iva_compensation_revision_match(
        work_unit,
        target,
        repository=iva_compensation_decision_repository,
    )
    _require_cross_period_clean_state(
        work_unit,
        observation_repository=obs_repo,
        filing_repository=fr_repo,
        calculation_repository=cr_repo,
        verification_repository=vr_repo,
        iva_compensation_decision=iva_compensation_decision,
        expected_member_sets=cross_period_expected_member_sets,
    )

    now = clock or _utc_now()
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
    )

    return persist_filed_revision(
        target=target,
        work_unit=work_unit,
        work_units=work_units,
        notes=notes,
        actor=actor,
        now=now,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        work_unit_repository=wu_repo,
        bucket_event_repository=bv_repo,
    )


def list_filing_records(
    *,
    bucket_id: str | None = None,
    include_superseded: bool = False,
    filing_repository: ModeloRecordCatalogueRepositoryProtocol | None = None,
) -> tuple[ModeloRecord, ...]:
    """List :class:`ModeloRecord` filing records, optionally filtered to a bucket.

    Superseded records are excluded unless ``include_superseded``
    is true. Results are sorted by ``(bucket_id, filing_year,
    modelo, period, filed_at)``.
    """
    fr_repo = filing_repository or ModeloRecordCatalogueRepository()
    catalogue = fr_repo.load()
    records = tuple(
        record
        for record in catalogue.values()
        if (bucket_id is None or record.bucket_id == bucket_id)
        and (include_superseded or record.status is ModeloRecordStatus.VIGENTE)
    )
    return tuple(
        sorted(
            records,
            key=lambda r: (r.bucket_id, r.filing_year, str(r.modelo), r.period, r.filed_at),
        )
    )


def get_filing_record(
    filing_record_id: str,
    *,
    filing_repository: ModeloRecordCatalogueRepositoryProtocol | None = None,
) -> ModeloRecord:
    """Return the :class:`ModeloRecord` for the given id, or raise."""
    fr_repo = filing_repository or ModeloRecordCatalogueRepository()
    catalogue = fr_repo.load()
    record = catalogue.get(filing_record_id)
    if record is None:
        raise ModeloRecordNotFoundError(
            translated_message="application.modelo.errors.filing_record_not_found",
            context={"filing_record_id": filing_record_id},
        )
    return record


def list_verification_reports(
    *,
    calculation_revision_id: str | None = None,
    verification_repository: VerificationReportCatalogueRepositoryProtocol | None = None,
) -> tuple[VerificationReport, ...]:
    """List :class:`VerificationReport` records, optionally filtered to one calculation revision.

    Results are sorted by ``(calculation_revision_id, run_at)``.
    """
    vr_repo = verification_repository or VerificationReportCatalogueRepository()
    catalogue = vr_repo.load()
    reports = tuple(
        r
        for r in catalogue.values()
        if calculation_revision_id is None or r.calculation_revision_id == calculation_revision_id
    )
    return tuple(sorted(reports, key=lambda r: (r.calculation_revision_id, r.run_at)))


def get_verification_report(
    verification_report_id: str,
    *,
    verification_repository: VerificationReportCatalogueRepositoryProtocol | None = None,
) -> VerificationReport:
    """Return one :class:`VerificationReport` by id, or raise."""
    vr_repo = verification_repository or VerificationReportCatalogueRepository()
    catalogue = vr_repo.load()
    report = catalogue.get(verification_report_id)
    if report is None:
        raise VerificationReportNotFoundError(
            translated_message="application.modelo.errors.verification_report_not_found",
            context={"verification_report_id": verification_report_id},
        )
    return report


def amend_modelo_revision(
    *,
    from_filing_record_id: str,
    overrides: Mapping[str, Decimal],
    amendment_kind: CalculationRevisionAmendmentKind,
    reason: str,
    actor: str,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol | None = None,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol | None = None,
    filing_repository: ModeloRecordCatalogueRepositoryProtocol | None = None,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol | None = None,
    clock: datetime | None = None,
) -> ModeloRecord:
    """Build and file an amendment over an externally-filed return.

    Pipeline:

    1. Load the baseline filing record (must exist, must be CURRENT,
       must carry ``external_evidence``). The evidence gate ensures
       the amendment runs against AEAT-attested imported data, not a
       fabricated local original.
    2. Load the baseline calculation revision; merge its
       ``casilla_values`` with the operator-supplied ``overrides``
       to produce the corrected casilla map.
    3. Persist a new ``DRAFT`` calculation revision carrying
       ``amendment_kind``, ``amends_filing_record_id``, and the
       operator-supplied ``reason``.
    4. Transition it through ``VERIFICADO_COMPLETO`` (the verification
       contract for amendments is identity-equivalent to the
       calculate path because the registry-snapshot resolver still
       applies; here we mark it verified-complete directly because
       the operator opts in by invoking the amend verb).
    5. Build a new filing record with
       ``amends_filing_record_id = baseline.filing_record_id`` and
       status CURRENT; supersede the baseline record.
    6. Emit a ``modelo.amended`` bucket event linking the new
       filing record to the baseline.

    Args:
        from_filing_record_id: The id of the baseline filing record to amend.
            Must be CURRENT and carry ``external_evidence``.
        overrides: Casilla-id to Decimal mapping of corrected values to merge
            over the baseline revision's casilla map.
        amendment_kind: Whether the amendment is ``COMPLEMENTARIA`` or
            ``SUSTITUTIVA``.
        reason: Operator-supplied explanation for the amendment, recorded in
            the revision and bucket event.
        actor: Operator identifier recorded in the audit trail.
        work_unit_repository: Optional work-unit catalogue repository override.
        calculation_repository: Optional calculation-revision catalogue
            repository override.
        filing_repository: Optional filing-record catalogue repository override.
        bucket_event_repository: Optional bucket-event history repository
            override.
        clock: Optional UTC timestamp override.

    Returns:
        The newly created :class:`ModeloRecord` in ``CURRENT`` status for the
        amendment.

    Raises:
        ModeloRecordNotFoundError: When ``from_filing_record_id`` is
            absent from the catalogue.
        AmendmentEvidenceMissingError: When the baseline record does
            not carry ``external_evidence``.
        AmendmentTargetStateError: When the baseline record is not
            in ``CURRENT`` status.
        WorkUnitNotFoundError: When the work unit referenced by the
            baseline record cannot be loaded.
        CalculationRevisionNotFoundError: When the baseline calculation
            revision referenced by the filing record is absent.
        CalculationRevisionStateError: When the amendment overrides
            produce a duplicate revision id already present in the catalogue.
    """
    wu_repo = work_unit_repository or WorkUnitCatalogueRepository()
    cr_repo = calculation_repository or CalculationRevisionCatalogueRepository()
    fr_repo = filing_repository or ModeloRecordCatalogueRepository()
    bv_repo = bucket_event_repository or BucketEventHistoryRepository()

    filing_catalogue = fr_repo.load()
    baseline = filing_catalogue.get(from_filing_record_id)
    if baseline is None:
        raise ModeloRecordNotFoundError(
            translated_message="application.modelo.errors.filing_record_not_found",
            context={"filing_record_id": from_filing_record_id},
        )
    if baseline.external_evidence is None:
        raise AmendmentEvidenceMissingError(
            f"filing record {from_filing_record_id!r} has no external_evidence; the "
            f"modelo amend path requires an imported AEAT-attested baseline. Use the "
            f"standard re-file path (calculate → verify → file) for locally-filed returns."
        )
    if baseline.status is not ModeloRecordStatus.VIGENTE:
        raise AmendmentTargetStateError(
            f"filing record {from_filing_record_id!r} is in status {baseline.status.value!r}; "
            f"only CURRENT filings can be amended"
        )

    work_units = wu_repo.load()
    work_unit = work_units.get(baseline.work_unit_id)
    if work_unit is None:
        raise WorkUnitNotFoundError(
            f"filing record {from_filing_record_id!r} references missing work_unit_id={baseline.work_unit_id!r}"
        )

    revisions = cr_repo.load()
    baseline_revision = revisions.get(baseline.calculation_revision_id)
    if baseline_revision is None:
        raise CalculationRevisionNotFoundError(
            f"baseline calculation revision {baseline.calculation_revision_id!r} is missing from the catalogue"
        )

    _reject_unknown_override_casillas(
        modelo=baseline.modelo,
        filing_year=baseline.filing_year,
        period=baseline.period,
        overrides=overrides,
    )

    now = clock or _utc_now()
    corrected_values: dict[str, Decimal] = dict(baseline_revision.casilla_values)
    corrected_values.update(overrides)

    new_revision_id = derive_calculation_revision_id(
        work_unit_id=baseline.work_unit_id,
        inputs_snapshot=baseline_revision.inputs_snapshot,
        binding_overrides=baseline_revision.binding_overrides,
        casilla_values=corrected_values,
        source_transaction_ids=baseline_revision.source_transaction_ids,
        borrador_snapshot_id=baseline_revision.borrador_snapshot_id,
        bindings_sourced_from_borrador=baseline_revision.bindings_sourced_from_borrador,
    )
    if new_revision_id in revisions:
        raise CalculationRevisionStateError(
            f"amendment overrides produce calculation_revision_id {new_revision_id!r} "
            f"that already exists in the catalogue; no-op overrides cannot be filed as amendments"
        )

    # Carry regulatory grounding onto the amendment: build typed
    # CasillaObservation rows for the corrected casilla map so the
    # persisted amendment revision and its CLI emit preserve
    # legal_refs / source_refs (and baseline formula provenance for
    # non-overridden casillas) instead of an empty observations tuple.
    amendment_observations = _amendment_observations(
        corrected_values=corrected_values,
        overrides=overrides,
        baseline_revision=baseline_revision,
        snapshot=_resolve_registry_snapshot_for_work_unit(work_unit),
    )

    amendment_draft = CalculationRevision(
        calculation_revision_id=new_revision_id,
        work_unit_id=baseline.work_unit_id,
        state=CalculationRevisionState.BORRADOR,
        inputs_snapshot=baseline_revision.inputs_snapshot,
        binding_overrides=baseline_revision.binding_overrides,
        source_transaction_ids=baseline_revision.source_transaction_ids,
        borrador_snapshot_id=baseline_revision.borrador_snapshot_id,
        bindings_sourced_from_borrador=baseline_revision.bindings_sourced_from_borrador,
        casilla_values=corrected_values,
        observations=amendment_observations,
        created_at=now,
        updated_at=now,
        amendment_kind=amendment_kind,
        amends_filing_record_id=baseline.filing_record_id,
        amendment_reason=reason.strip(),
    )
    revisions = upsert_calculation_revision(revisions, amendment_draft)

    # Verify the corrected casilla map against the registry's
    # required-manual-input contract before transitioning. The amend
    # path mirrors the standard verify gate so a complementaria
    # cannot be filed with a missing required casilla.
    _reject_incomplete_amendment_casillas(
        modelo=baseline.modelo,
        filing_year=baseline.filing_year,
        period=baseline.period,
        casilla_values=corrected_values,
    )

    # Transition draft → verified-complete (operator opts in by calling amend).
    verified_amendment = amendment_draft.model_copy(
        update={
            "state": CalculationRevisionState.VERIFICADO_COMPLETO,
            "verified_at": now,
            "verified_by": actor.strip(),
            "updated_at": now,
        }
    )
    revisions = upsert_calculation_revision(revisions, verified_amendment)

    new_filing_id = derive_filing_record_id(
        work_unit_id=baseline.work_unit_id,
        calculation_revision_id=new_revision_id,
        filed_at=now,
        filed_by=actor.strip(),
    )

    new_filing = ModeloRecord(
        filing_record_id=new_filing_id,
        work_unit_id=baseline.work_unit_id,
        calculation_revision_id=new_revision_id,
        bucket_id=baseline.bucket_id,
        modelo=baseline.modelo,
        filing_year=baseline.filing_year,
        period=baseline.period,
        filed_at=now,
        filed_by=actor.strip(),
        notes=None,
        aeat_accepted=False,
        status=ModeloRecordStatus.VIGENTE,
        external_evidence=None,
        amends_filing_record_id=baseline.filing_record_id,
    )

    superseded_baseline = baseline.model_copy(
        update={
            "status": ModeloRecordStatus.SUPERSEDIDO,
            "superseded_at": now,
            "superseded_by_filing_record_id": new_filing_id,
        }
    )
    updated_filing_catalogue = upsert_filing_record(filing_catalogue, superseded_baseline)
    updated_filing_catalogue = upsert_filing_record(updated_filing_catalogue, new_filing)

    filed_amendment = verified_amendment.model_copy(
        update={
            "state": CalculationRevisionState.PRESENTADO,
            "filed_at": now,
            "filed_by": actor.strip(),
            "updated_at": now,
        }
    )
    revisions = upsert_calculation_revision(revisions, filed_amendment)

    cr_repo.save(revisions)
    fr_repo.save(updated_filing_catalogue)

    wu_repo.save(
        upsert_work_unit(
            work_units,
            work_unit.model_copy(
                update={
                    "current_calculation_revision_id": new_revision_id,
                    "filed_calculation_revision_id": new_revision_id,
                    "current_filing_record_id": new_filing_id,
                    "updated_at": now,
                }
            ),
        )
    )

    _emit_bucket_event(
        repository=bv_repo,
        bucket_id=baseline.bucket_id,
        event_type=BucketEventType.MODELO_AMENDED,
        occurred_at=now,
        actor=actor,
        object_type=BucketEventObjectType.FILING_RECORD,
        object_id=new_filing_id,
        payload={
            "amends_filing_record_id": baseline.filing_record_id,
            "calculation_revision_id": new_revision_id,
            "work_unit_id": baseline.work_unit_id,
            "modelo": str(baseline.modelo),
            "filing_year": str(baseline.filing_year),
            "period": baseline.period,
            "amendment_kind": amendment_kind.value,
            "override_count": str(len(overrides)),
        },
    )

    return new_filing


def import_external_filing_evidence(
    *,
    work_unit_id: str,
    casilla_values: Mapping[str, Decimal],
    evidence_kind: ExternalEvidenceKind,
    evidence_reference_id: str,
    actor: str = "aeat-import",
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol | None = None,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol | None = None,
    filing_repository: ModeloRecordCatalogueRepositoryProtocol | None = None,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol | None = None,
    clock: datetime | None = None,
) -> ModeloRecord:
    """Persist an externally-filed return as a baseline filing record.

    This is the canonical entry point the import path (justificante
    PDF reader, AEAT CSV register importer, AEAT live capture) uses
    to land an externally-filed return as the bucket's baseline:

    1. Verify the work unit exists and is not discarded.
    2. Persist a fresh ``FILED`` calculation revision carrying the
       imported casilla values (no inputs / overrides — the operator
       did not compute this locally; AEAT's records are the source
       of truth).
    3. Build a ``CURRENT`` filing record with ``external_evidence``
       populated and ``aeat_accepted=True``.
    4. If a prior current filing exists for the (bucket, modelo,
       year, period) tuple, supersede it (same supersession chain
       the file path uses).
    5. Advance the work-unit pointers to the imported baseline.
    6. Emit a ``modelo.filing.imported`` bucket event linking the
       new filing record id to the evidence reference.

    The amend path consumes records produced here as its baseline.

    Args:
        work_unit_id: The stable id of the work unit to attach the imported
            filing to.
        casilla_values: The AEAT-attested casilla values from the imported
            filing. Must be non-empty.
        evidence_kind: The kind of external evidence being imported (e.g.
            justificante, borrador).
        evidence_reference_id: The AEAT-issued reference identifier for the
            imported filing. Must be non-blank after stripping.
        actor: Operator identifier recorded in the audit trail. Defaults to
            ``"aeat-import"``.
        work_unit_repository: Optional work-unit catalogue repository override.
        calculation_repository: Optional calculation-revision catalogue
            repository override.
        filing_repository: Optional filing-record catalogue repository override.
        bucket_event_repository: Optional bucket-event history repository
            override.
        clock: Optional UTC timestamp override.

    Returns:
        The newly created :class:`ModeloRecord` in ``CURRENT`` status.

    Raises:
        WorkUnitNotFoundError: when ``work_unit_id`` is absent.
        WorkUnitMutationRefusedError: when the work unit is discarded.
        ExternalModeloImportError: when ``casilla_values`` is empty,
            ``evidence_reference_id`` is blank, or the derived revision id
            already exists in the catalogue.
    """
    wu_repo = work_unit_repository or WorkUnitCatalogueRepository()
    cr_repo = calculation_repository or CalculationRevisionCatalogueRepository()
    fr_repo = filing_repository or ModeloRecordCatalogueRepository()
    bv_repo = bucket_event_repository or BucketEventHistoryRepository()

    if not casilla_values:
        raise ExternalModeloImportError(
            translated_message="application.modelo.errors.external_filing_no_casilla_values",
        )
    cleaned_reference = evidence_reference_id.strip()
    if not cleaned_reference:
        raise ExternalModeloImportError(
            translated_message="application.modelo.errors.external_filing_evidence_reference_blank",
        )

    work_units = wu_repo.load()
    work_unit = work_units.get(work_unit_id)
    if work_unit is None:
        raise WorkUnitNotFoundError(
            translated_message="application.modelo.errors.work_unit_not_found",
            context={"work_unit_id": work_unit_id},
        )
    if work_unit.state is WorkUnitState.DESCARTADO:
        raise WorkUnitMutationRefusedError(
            translated_message="application.modelo.errors.work_unit_discarded_cannot_import",
            context={"work_unit_id": work_unit_id},
        )

    snapshot = _reject_unknown_import_casillas(
        modelo=work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=work_unit.period,
        casilla_values=casilla_values,
    )

    inputs_snapshot: dict[str, str] = {}
    binding_overrides: dict[str, str] = {}
    outputs = dict(casilla_values)
    observations = _external_filing_observations(casilla_values=outputs, snapshot=snapshot)

    now = clock or _utc_now()
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        inputs_snapshot=inputs_snapshot,
        binding_overrides=binding_overrides,
        casilla_values=outputs,
    )
    revisions = cr_repo.load()
    if revision_id in revisions:
        raise ExternalModeloImportError(
            tr(
                "application.modelo.errors.external_import_duplicate_revision",
                calculation_revision_id=revision_id,
            ),
            translated_message="application.modelo.errors.external_import_duplicate_revision",
            context={"calculation_revision_id": revision_id},
        )

    revision = CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit_id,
        state=CalculationRevisionState.PRESENTADO,
        inputs_snapshot=inputs_snapshot,
        binding_overrides=binding_overrides,
        casilla_values=outputs,
        created_at=now,
        updated_at=now,
        verified_at=now,
        verified_by=actor.strip(),
        filed_at=now,
        filed_by=actor.strip(),
        observations=observations,
    )
    revisions = upsert_calculation_revision(revisions, revision)

    new_filing_id = derive_filing_record_id(
        work_unit_id=work_unit_id,
        calculation_revision_id=revision_id,
        filed_at=now,
        filed_by=actor.strip(),
    )

    filing_catalogue = fr_repo.load()
    prior_current = filing_catalogue.current_for(
        bucket_id=work_unit.bucket_id,
        modelo=work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=work_unit.period,
    )

    new_filing = ModeloRecord(
        filing_record_id=new_filing_id,
        work_unit_id=work_unit_id,
        calculation_revision_id=revision_id,
        bucket_id=work_unit.bucket_id,
        modelo=work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=work_unit.period,
        filed_at=now,
        filed_by=actor.strip(),
        notes=None,
        aeat_accepted=True,
        status=ModeloRecordStatus.VIGENTE,
        external_evidence=ExternalEvidence(
            kind=evidence_kind,
            reference_id=cleaned_reference,
            imported_at=now,
        ),
    )

    updated_filing_catalogue = filing_catalogue
    if prior_current is not None:
        superseded_prior = prior_current.model_copy(
            update={
                "status": ModeloRecordStatus.SUPERSEDIDO,
                "superseded_at": now,
                "superseded_by_filing_record_id": new_filing_id,
            }
        )
        updated_filing_catalogue = upsert_filing_record(updated_filing_catalogue, superseded_prior)
        prior_revision = revisions.get(prior_current.calculation_revision_id)
        if prior_revision is not None and prior_revision.state is CalculationRevisionState.PRESENTADO:
            superseded_revision = prior_revision.model_copy(
                update={
                    "state": CalculationRevisionState.PRESENTADO_SUPERSEDIDO,
                    "superseded_at": now,
                    "updated_at": now,
                }
            )
            revisions = upsert_calculation_revision(revisions, superseded_revision)
    updated_filing_catalogue = upsert_filing_record(updated_filing_catalogue, new_filing)

    cr_repo.save(revisions)
    fr_repo.save(updated_filing_catalogue)

    wu_repo.save(
        upsert_work_unit(
            work_units,
            work_unit.model_copy(
                update={
                    "current_calculation_revision_id": revision_id,
                    "filed_calculation_revision_id": revision_id,
                    "current_filing_record_id": new_filing_id,
                    "updated_at": now,
                }
            ),
        )
    )

    _emit_bucket_event(
        repository=bv_repo,
        bucket_id=work_unit.bucket_id,
        event_type=BucketEventType.MODELO_FILING_IMPORTED,
        occurred_at=now,
        actor=actor,
        object_type=BucketEventObjectType.FILING_RECORD,
        object_id=new_filing_id,
        payload={
            "work_unit_id": work_unit_id,
            "calculation_revision_id": revision_id,
            "modelo": work_unit.modelo,
            "filing_year": str(work_unit.filing_year),
            "period": work_unit.period,
            "evidence_kind": evidence_kind.value,
            "evidence_reference_id": cleaned_reference,
            "supersedes_filing_record_id": (prior_current.filing_record_id if prior_current is not None else ""),
            "casilla_count": str(len(outputs)),
        },
    )

    return new_filing


__all__ = [
    "AmendmentEvidenceMissingError",
    "AmendmentOverrideCasillaError",
    "AmendmentTargetStateError",
    "AmendmentVerificationRefusedError",
    "CalculationRegistryUnavailableError",
    "CalculationRevisionNotFoundError",
    "CalculationRevisionStateError",
    "CasillaProvenanceMissingError",
    "ExternalModeloImportError",
    "ModeloAggregationBindingError",
    "ModeloApplicabilityFilterError",
    "ModeloCrossPeriodCleanStateError",
    "ModeloIvaWalletReconciliationBlocked",
    "ModeloIvaWalletReconciliationBlockedError",
    "ModeloRecordNotFoundError",
    "ModeloWorkflowGateError",
    "StoredCalculationDriftError",
    "VerificationReportNotFoundError",
    "WorkUnitAlreadyDiscardedError",
    "WorkUnitMutationRefusedError",
    "WorkUnitNotFoundError",
    "amend_modelo_revision",
    "calculate_modelo_revision",
    "calculate_modelo_revision_from_bucket_aggregation",
    "create_work_unit",
    "discard_work_unit",
    "file_modelo_revision",
    "get_calculation_revision",
    "get_filing_record",
    "get_verification_report",
    "get_work_unit",
    "import_external_filing_evidence",
    "list_calculation_revisions",
    "list_filing_records",
    "list_verification_reports",
    "list_work_units",
    "mark_revision_verificado_completo",
    "rename_work_unit",
    "verify_modelo_revision",
    "workflow_period_for_work_unit",
]
