"""Verification actions and predicates for modelo filings.

``verify_modelo_revision`` evaluates a draft
:class:`~aeat.domain.modelos.CalculationRevision` against
its :class:`~aeat.domain.calculations.registry.RegistrySnapshot`, workflow
:class:`~aeat.domain.deadlines.TaxpayerProfile`, ledger diagnostics, registry
verification predicates, and cross-period clean-state verdicts before persisting
a :class:`~aeat.domain.modelos.VerificationReport`.

Verification findings are the operator-facing gate vocabulary. BLOCKING-severity
findings refuse the verified-complete transition; WARNING-severity ADVISORY
findings remain visible in the report without bricking verify, file, or export.
Calculate-path source diagnostics are separate
:class:`~aeat.application.aggregation.CalculationSourceDiagnostic` advisories;
this module converts only verify-time registry, profile, provenance, and
cross-period facts into :class:`~aeat.domain.modelos.ModeloVerificationFinding`
records.

Verification emits bucket-history entries through
:class:`~aeat.domain.buckets.BucketEventHistoryRepository`, stores casilla-level
:class:`~aeat.domain.calculations.registry.CasillaObservation` provenance, and
uses :class:`~aeat.domain.transactions.TransactionCatalogueRepository` only for
evidence advisories over source transactions.

See Also:
    :func:`~aeat.application.calculations.evaluate_cross_period_clean_state`:
        Shared cross-period gate used by verify, file, and export.
    :mod:`aeat.application.modelo._calculation_diagnostics`:
        Calculate-path diagnostics that feed advisory observations before verify.
    :mod:`aeat.domain.modelos`:
        Finding kind, severity, and completeness-status authority.
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
    CasillaId,
    CasillaObservation,
    InputKind,
    RegistrySnapshot,
    VerificationPredicateDefinition,
    derive_modelo_202_modality,
    validated_casilla_id,
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
from ...domain.modelos._errors import ModeloError, ModeloValidationError
from ...domain.modelos._filing_repository import ModeloRecordCatalogueRepository
from ...domain.modelos._ledger_filing_snapshot import (
    LedgerFilingEvidence,
    LedgerFilingSnapshot,
    ManualFactBasisEntry,
)
from ...domain.modelos._participation_index import (
    TransactionParticipationIndexRepository,
    TransactionRevisionParticipation,
    upsert_transaction_participation,
)
from ...domain.modelos._protocols import (
    CalculationRevisionCatalogueRepositoryProtocol,
    ModeloRecordCatalogueRepositoryProtocol,
    VerificationReportCatalogueRepositoryProtocol,
    WorkUnitCatalogueRepositoryProtocol,
)
from ...domain.modelos._repository import WorkUnitCatalogueRepository, upsert_work_unit
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
from ..aggregation import (
    CalculationSourceDiagnostic,
    missing_evidence_advisory_observations,
)
from ..aggregation._evidence_advisory import MISSING_DEDUCTIBLE_VAT_EVIDENCE_SOURCE_KIND
from ..aggregation._ledger_filing_snapshot import (
    compute_ledger_filing_evidence,
    compute_ledger_filing_snapshot,
)
from ..calculations import (
    CalculationObservationRepository,
    CrossPeriodExpectedMemberSet,
)
from ..workflow import WorkflowEngine, WorkflowPurpose, WorkflowRunRepository
from ._action_errors import (
    CalculationRevisionNotFoundError,
    CalculationRevisionStateError,
    ModeloApplicabilityFilterError,
    WorkUnitNotFoundError,
)
from ._art20_advisory import _art20_reduccion_advisory_finding
from ._dt12_advisory import _dt12_reduccion_advisory_finding
from ._iva_wallet_gate import (
    ModeloIvaWalletReconciliationBlocked,
)
from ._iva_wallet_gate import (
    iva_wallet_blocked_message as _iva_wallet_blocked_message,
)
from ._iva_wallet_gate import (
    require_persisted_iva_compensation_decision_matches_revision as _require_iva_compensation_revision_match,
)
from ._m210_rate import resolve_m210_rate as _resolve_m210_rate
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
    from ...domain.iva_compensation._reconciliation import IvaCompensationReconciliationDecision
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
# implies_any_nonzero(["antecedent_id", "c1_id", "c2_id", ...]) — the
# N-consequent generalisation of implies_nonzero: predicate holds iff the
# antecedent is <= 0 OR at least one of the listed consequents is non-zero.
# Authored for the M303 official-Diseño under-declaration contradiction (a
# positive computed total with every constituent official numbered box still
# zero). See the implies_any_nonzero branch in _evaluate_advisory_predicate_fires.
_PREDICATE_IMPLIES_ANY_NONZERO = _re.compile(r"^implies_any_nonzero\(\[(?P<ids>[^\]]*)\]\)$")
# equals(["lhs_id", "rhs_id"]) — binary consistency invariant: predicate holds
# iff the two named casillas hold the same value. Authored for the M303 official
# Diseño box projections (Stage 2): each numbered box copies an already-computed
# semantic source, so box == source must hold for VERIFICADO_COMPLETO. A copy
# cannot drift from its source within one evaluation, so the live filing always
# satisfies it; the predicate's value is catching a FUTURE mis-edit (a box
# re-flipped to manual, or a projection pointed at the wrong source). As a
# BLOCKING_RULE it refuses a filing whose projected box has drifted from its
# semantic source. See the equals branch in _evaluate_predicate_expression.
_PREDICATE_EQUALS = _re.compile(r"^equals\(\[(?P<ids>[^\]]*)\]\)$")
# profile_field_required("field_name", "applicability_filter") —
# profile-state-aware conditional non-zero requirement; sibling of
# implies_nonzero per the dsl-conditional-predicate ADR. The
# applicability filter is dispatched via _evaluate_applicability_filter
# against the TaxpayerProfile threaded through the verification pipeline.
# First use site: M210 representante-fiscal gate per
# m210-irnr-full-engine ADR §D2.5 (TRLIRNR Art 10).
_PREDICATE_PROFILE_FIELD_REQUIRED = _re.compile(r'^profile_field_required\("(?P<field>[^"]+)", "(?P<filter>[^"]+)"\)$')
_M349_NUMERO_RECTIFICACIONES_CASILLA: CasillaId = "decl.numero-rectificaciones"
_M349_IMPORTE_RECTIFICACIONES_CASILLA: CasillaId = "decl.importe-rectificaciones"

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
# and denominator > 0. Used for Art. 109 RIRPF M130 high-retention exemption.
_PREDICATE_ADVISORY_WHEN_RATIO_GE = _re.compile(
    r'^advisory_when_ratio_ge\(\["(?P<num>[^"]+)",\s*"(?P<den>[^"]+)",\s*"(?P<thr>[^"]+)"\]\)$',
)
# roll_forward_balances(["closing_id", "opening_id", "applied_id", "base_id"]) —
# carry-forward stock continuity: closing == opening − applied + max(0, −base),
# within a one-cent tolerance. See _roll_forward_balance_reconciles.
_PREDICATE_ROLL_FORWARD_BALANCES = _re.compile(r"^roll_forward_balances\(\[(?P<ids>[^\]]*)\]\)$")

#: One-cent tolerance for the roll-forward continuity reconciliation — absorbs the
#: sub-cent drift a total-of-per-year-detail figure can accumulate without masking
#: a genuine discontinuity (which is euros, not cents).
_BALANCE_CENT_TOLERANCE = Decimal("0.01")


def _parse_predicate_casilla_ids(ids_fragment: str) -> list[CasillaId]:
    """Parse the comma-separated quoted-id list from a predicate expression."""
    ids: list[CasillaId] = []
    for token in ids_fragment.split(","):
        token = token.strip().strip('"').strip("'")
        if token:
            ids.append(_validated_predicate_casilla_id(token))
    return ids


def _validated_predicate_casilla_id(token: str) -> CasillaId:
    try:
        return validated_casilla_id(token, surface="verification predicate casilla id")
    except ValueError as exc:
        raise ModeloError(f"verification predicate references non-canonical casilla.id {token!r}") from exc


def _roll_forward_balance_reconciles(
    ids: list[CasillaId],
    casilla_values: Mapping[CasillaId, Decimal],
) -> bool | None:
    """Return whether a carry-forward closing balance reconciles to its roll-forward.

    ``ids`` is ``[closing, opening, applied, base]``. The carry-forward stock
    continuity invariant is::

        closing == opening − applied + max(0, −base)

    the opening stock less the amount applied (consumed) this period plus any
    stock newly generated this period — the ``base`` being negative when a new
    negative base / BIN is generated, so ``max(0, −base)`` is the generated
    amount and contributes nothing in a profit year. Holds within a one-cent
    tolerance to absorb per-year-detail rounding. Returns ``None`` on a malformed
    arity (the caller treats that as "not applicable"); a missing casilla reads as
    ``Decimal(0)`` via ``.get`` so an absent closing/opening does not crash the
    gate. Authored for the Modelo 200 BIN total-pendiente roll-forward
    (modelo-200-bin-continuity ADR); general to any carry-forward stock.
    """
    if len(ids) != 4:
        return None
    closing = casilla_values.get(ids[0], Decimal(0))
    opening = casilla_values.get(ids[1], Decimal(0))
    applied = casilla_values.get(ids[2], Decimal(0))
    base = casilla_values.get(ids[3], Decimal(0))
    generated = max(Decimal(0), -base)
    expected = opening - applied + generated
    return abs(closing - expected) <= _BALANCE_CENT_TOLERANCE


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
        # M210 uses the broader ue_eee_status: EEA residents are exempt
        # because of the bilateral mutual-assistance regime.
        return profile.fiscal_residency is FiscalResidency.NON_RESIDENT_IRNR and not profile.ue_eee_status
    raise ModeloApplicabilityFilterError(f"Unknown applicability filter: {filter_name!r}")


def _evaluate_predicate_expression(
    expression: str,
    casilla_values: Mapping[CasillaId, Decimal],
    profile: TaxpayerProfile,
) -> bool:
    """Return True when the predicate holds, False when it is violated.

    Supports the DSL operators registered in
    :data:`aeat.domain.calculations.registry._schema.KNOWN_VERIFICATION_PREDICATE_OPERATORS`:

    - ``all_nonzero(["id1", "id2", ...])`` — all ids must have a non-zero value.
    - ``any_nonzero(["id1", "id2", ...])`` — at least one id must have a non-zero value.
    - ``cap_le_when_positive(["limited_id", "ceiling_id"])`` — when the ceiling
      casilla is strictly positive, the limited casilla MUST NOT exceed it.
    - ``equals(["lhs_id", "rhs_id"])`` — binary consistency invariant: predicate
      holds iff the two named casillas hold the same value (M303 official-box
      projection consistency: box == its semantic source).
    - ``implies_nonzero(["antecedent_id", "consequent_id"])`` — material
      implication with strictly-positive antecedent: predicate holds iff
      antecedent <= 0 OR consequent != 0.
    - ``implies_any_nonzero(["antecedent_id", "c1_id", ...])`` — N-consequent
      generalisation: predicate holds iff antecedent <= 0 OR at least one
      listed consequent != 0 (M303 official-Diseño under-declaration shape).
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

    m = _PREDICATE_EQUALS.match(expr)
    if m:
        # equals(["lhs_id", "rhs_id"]) — binary consistency check. Predicate holds
        # (returns True, no violation) iff the two named casillas hold the same
        # value. A malformed arity reads as holding (defensive, same convention as
        # the other operators); the authoring-time validator in
        # _validate_surfaces rejects a malformed equals at registry load, so a
        # bad arity cannot reach here from a validated registry. A missing casilla
        # reads as Decimal(0) via .get. The violation case (returns False) is
        # "the two casillas differ" — a projected box that has drifted from its
        # semantic source (a future mis-edit).
        ids = _parse_predicate_casilla_ids(m.group("ids"))
        if len(ids) != 2:
            return True
        lhs = casilla_values.get(ids[0], Decimal(0))
        rhs = casilla_values.get(ids[1], Decimal(0))
        return lhs == rhs

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

    m = _PREDICATE_IMPLIES_ANY_NONZERO.match(expr)
    if m:
        # implies_any_nonzero(["antecedent_id", "c1_id", ...]) — material
        # implication "antecedent strictly positive → at least one consequent
        # non-zero". Predicate holds (returns True) when the expression names
        # no consequents (defensive), the antecedent is <= 0 (implication
        # trivially holds), or ANY consequent is non-zero. The violation case
        # (returns False) is "antecedent strictly positive AND every consequent
        # == 0" — the M303 silent-under-declaration shape. Missing consequents
        # read as Decimal(0) via .get, same convention as the other operators.
        ids = _parse_predicate_casilla_ids(m.group("ids"))
        if len(ids) < 2:
            return True
        antecedent = casilla_values.get(ids[0], Decimal(0))
        if antecedent <= Decimal(0):
            return True
        return any(casilla_values.get(cid, Decimal(0)) != Decimal(0) for cid in ids[1:])

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

    m = _PREDICATE_ROLL_FORWARD_BALANCES.match(expr)
    if m:
        # roll_forward_balances(["closing", "opening", "applied", "base"]) — as a
        # BLOCKING_RULE the predicate HOLDS (returns True) when the closing
        # balance reconciles to opening − applied + max(0, −base) within a cent.
        # A malformed arity reads as holding (defensive, like the other
        # operators); the authoring validator rejects it at registry load.
        reconciles = _roll_forward_balance_reconciles(_parse_predicate_casilla_ids(m.group("ids")), casilla_values)
        return True if reconciles is None else reconciles

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
    ``M210_RATE_SENTINELS`` Decimals (``-1``, ``-2``) when the
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


rewrite_m210_sentinels = _rewrite_m210_sentinels


def _evaluate_advisory_predicate_fires(
    expression: str,
    casilla_values: Mapping[CasillaId, Decimal],
) -> bool:
    """Return True when an advisory predicate's condition is met (i.e. advisory should fire).

    Supports:

    - ``advisory_when_ratio_ge(["num_id", "den_id", "threshold"])`` — fires when
      num/den >= threshold and den > 0. Art. 109 RIRPF: exempt from M130
      when retenciones_acumuladas / rendimientos_brutos >= 0.70.
    - ``implies_nonzero(["antecedent_id", "consequent_id"])`` — fires when the
      material implication is violated, i.e. the antecedent is strictly positive
      but the consequent is zero. As an ADVISORY this surfaces a non-blocking
      operator alert for the same shape the BLOCKING_RULE variant refuses: e.g.
      a positive resultado contable with an undetermined (zero) base imponible,
      a likely silent under-declaration that a positive-result entity should
      confirm (legitimate zero-base via BIN compensation remains permissible,
      hence advisory rather than blocking).
    - ``implies_any_nonzero(["antecedent_id", "c1_id", ...])`` — the
      N-consequent generalisation: fires when the antecedent is strictly
      positive but EVERY listed consequent is zero. The M303 official-Diseño
      contradiction (a positive computed total whose constituent official
      numbered boxes are all unpopulated by the calculate path).
    """
    expr = expression.strip()
    m = _PREDICATE_ADVISORY_WHEN_RATIO_GE.match(expr)
    if m:
        num_id = _validated_predicate_casilla_id(m.group("num"))
        den_id = _validated_predicate_casilla_id(m.group("den"))
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
    m = _PREDICATE_IMPLIES_ANY_NONZERO.match(expr)
    if m:
        # Fires (advisory shown) when the antecedent is strictly positive but
        # EVERY listed consequent is zero — the M303 official-Diseño
        # contradiction (a positive computed total whose constituent official
        # numbered boxes are all unpopulated). See the docstring branch in
        # _evaluate_predicate_expression for the BLOCKING_RULE complement.
        ids = _parse_predicate_casilla_ids(m.group("ids"))
        if len(ids) < 2:
            return False
        antecedent = casilla_values.get(ids[0], Decimal(0))
        if antecedent <= Decimal(0):
            return False
        return all(casilla_values.get(cid, Decimal(0)) == Decimal(0) for cid in ids[1:])
    m = _PREDICATE_ROLL_FORWARD_BALANCES.match(expr)
    if m:
        # roll_forward_balances(["closing", "opening", "applied", "base"]) — as an
        # ADVISORY the predicate FIRES (returns True, advisory shown) when the
        # closing balance does NOT reconcile to opening − applied + max(0, −base):
        # a carry-forward stock discontinuity (e.g. a silently-dropped BIN
        # carryforward) that would compound into future-year compensation. A
        # reconciling balance (within a cent) or a malformed arity does not fire.
        reconciles = _roll_forward_balance_reconciles(_parse_predicate_casilla_ids(m.group("ids")), casilla_values)
        return reconciles is False
    return False


def _evaluate_verification_predicates(
    predicates: tuple[VerificationPredicateDefinition, ...],
    casilla_values: Mapping[CasillaId, Decimal],
    profile: TaxpayerProfile,
) -> list[ModeloVerificationFinding]:
    """Evaluate Layer 2 cross-casilla predicates; return findings for violations or advisories.

    ``BLOCKING_RULE`` predicates use negative logic: the predicate expression must
    hold, and a violation emits a BLOCKING finding. ``ADVISORY`` predicates use
    affirmative logic: when their condition fires, the operator receives a
    WARNING-severity ADVISORY finding and the verified-complete grant remains
    possible if no blocking findings exist.

    ``profile`` is threaded through to support profile-state-aware
    predicate operators such as ``profile_field_required`` (m210
    representante-fiscal gate per ADR §D2.5). Casilla-only operators
    ignore the parameter.

    See Also:
        :func:`_evaluate_predicate_expression`:
            Evaluates the blocking-rule predicate DSL.
        :func:`_evaluate_advisory_predicate_fires`:
            Evaluates the advisory predicate DSL.
        :func:`_classify_verification_outcome`:
            Converts finding severity into report completeness and grant status.
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
                    ),
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
                    ),
                )
    return findings


evaluate_advisory_predicate_fires = _evaluate_advisory_predicate_fires
evaluate_predicate_expression = _evaluate_predicate_expression
evaluate_verification_predicates = _evaluate_verification_predicates


def _manual_fact_basis_entries(input_values_by_casilla_id: Mapping[CasillaId, str]) -> tuple[ManualFactBasisEntry, ...]:
    """Project a revision's operator casilla inputs into manual fact-basis entries.

    The ``input_values_by_casilla_id`` holds the caller-supplied (operator-entered) casilla
    values that are not ledger-derived; each non-empty entry is part of the fact
    basis a filing artefact must explain. Blank values are skipped (they carry no
    fact).
    """
    return tuple(
        ManualFactBasisEntry(casilla_id=casilla, value=value)
        for casilla, value in sorted(input_values_by_casilla_id.items())
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

    Loads the revision's source transactions and projects each
    :class:`~aeat.application.aggregation.CalculationSourceDiagnostic`
    (reason ``missing_transaction_evidence``) into a
    :class:`~aeat.domain.modelos.ModeloVerificationFinding`. Deductible input-IVA
    gaps are blocking; output-IVA gaps remain advisory. A revision with no contributing
    transactions, or whose significant rows all carry evidence, yields no
    findings.
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
    for diagnostic in diagnostics:
        is_deductible_gap = diagnostic.source_kind == MISSING_DEDUCTIBLE_VAT_EVIDENCE_SOURCE_KIND
        findings.append(
            ModeloVerificationFinding(
                kind=(
                    ModeloVerificationFindingKind.BLOCKING_RULE
                    if is_deductible_gap
                    else ModeloVerificationFindingKind.ADVISORY
                ),
                severity=(
                    ModeloVerificationFindingSeverity.BLOCKING
                    if is_deductible_gap
                    else ModeloVerificationFindingSeverity.WARNING
                ),
                message=diagnostic.message,
                next_action=(
                    f"Attach supplier evidence to ledger row {diagnostic.binding_id}, then rerun verification."
                    if is_deductible_gap
                    else f"Attach supporting evidence to ledger row {diagnostic.binding_id}, then rerun verification."
                ),
                legal_refs=_MISSING_EVIDENCE_LEGAL_REFS,
                source_refs=(diagnostic.source_kind,),
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
) -> tuple[list[ModeloVerificationFinding], list[CasillaId], list[CasillaId]]:
    findings, resolved_casilla_ids, missing_required_casilla_ids = _collect_revision_verification_findings(
        work_unit=work_unit,
        target=target,
        profile=workflow_profile,
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
    participation_index_repository: TransactionParticipationIndexRepository | None = None,
    cross_period_expected_member_sets: Iterable[CrossPeriodExpectedMemberSet] = (),
    workflow_engine: WorkflowEngine | None = None,
    workflow_runs_dir: Path | None = None,
    settings: Settings | None = None,
    clock: datetime | None = None,
) -> VerificationReport:
    """Evaluate a draft revision against registry, clean-state, provenance, and workflow gates.

    The verifier loads the draft
    :class:`~aeat.domain.modelos.CalculationRevision`,
    resolves its work unit and registry snapshot, builds verify-time findings,
    classifies the outcome, persists a
    :class:`~aeat.domain.modelos.VerificationReport`, records
    bucket history, and updates the calculation revision only when the
    verified-complete transition is granted.

    The supplied :class:`~aeat.domain.deadlines.TaxpayerProfile` scopes
    deadline/applicability decisions, while
    :class:`~aeat.domain.transactions.TransactionCatalogueRepository` supplies
    non-blocking transaction-evidence advisories for source rows attached to the
    revision. WARNING-severity advisories remain report content; only BLOCKING
    severity can refuse the transition.

    Returns:
        The persisted :class:`~aeat.domain.modelos.VerificationReport`.

    Raises:
        CalculationRevisionNotFoundError: The requested calculation revision does
            not exist in the active catalogue.
        CalculationRevisionStateError: The revision is not in ``BORRADOR`` state.
        WorkUnitNotFoundError: The owning work unit is missing.
        ModeloCrossPeriodCleanStateError: A required cross-period dependency has a
            blocking clean-state finding.
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
        iva_compensation_decision_repository=iva_compensation_decision_repository,
        cross_period_expected_member_sets=cross_period_expected_member_sets,
    )
    completeness, granted = _classify_verification_outcome(
        findings=findings,
        missing_required=missing_required_casilla_ids,
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
    :class:`~aeat.domain.modelos.TransactionRevisionParticipationIndex`, upsert
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
    filing_evidence = compute_ledger_filing_evidence(
        source_transaction_ids=target.source_transaction_ids,
        catalogue=catalogue,
        snapshot_fingerprint=filing_snapshot.snapshot_fingerprint,
        captured_at=now,
        manual_entries=_manual_fact_basis_entries(target.input_values_by_casilla_id),
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


def _collect_revision_verification_findings(
    *,
    work_unit: WorkUnit,
    target: CalculationRevision,
    profile: TaxpayerProfile,
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

    # Layer 2: cross-casilla predicate gate.
    findings.extend(
        _evaluate_verification_predicates(
            snapshot.revision.verification_predicates,
            target.casilla_values,
            profile,
        ),
    )

    # Advisory: DT 12ª LIRPF — warn when a large trabajo income (0003 > 20 000)
    # is present but the trabajo reducción slot (0011) is zero / absent.
    # This heuristic surfaces the DT_12A_REDUCCION_POSSIBLE advisory so
    # retirees do not silently lose the 40% reducción for pre-2007 aportaciones.
    dt12_finding = _dt12_reduccion_advisory_finding(snapshot.revision, target.casilla_values)
    if dt12_finding is not None:
        findings.append(dt12_finding)

    # Advisory: art. 20 LIRPF — warn when the rendimiento neto del trabajo (0022) is
    # within the reducción band (strictly below the RNT ceiling) but the general
    # reducción casilla (0023) is zero. Stays ADVISORY because the art. 20 eligibility
    # gate ("otras rentas distintas del trabajo" ≤ 6.500 €) is a cross-section aggregate
    # the engine cannot yet evaluate, so a legitimately-zero reduction must remain
    # permissible (no-silent-under-declaration).
    art20_finding = _art20_reduccion_advisory_finding(snapshot.revision, target.casilla_values)
    if art20_finding is not None:
        findings.append(art20_finding)

    findings.extend(_objective_estimation_exclusion_advisory_findings(work_unit=work_unit, profile=profile))

    return findings, resolved_casilla_ids, missing_required_casilla_ids


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
