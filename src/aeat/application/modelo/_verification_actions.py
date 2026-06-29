"""Verification actions and predicates for modelo filings.

``verify_modelo_revision`` evaluates a draft :class:`CalculationRevision` against
its :class:`RegistrySnapshot`, workflow :class:`TaxpayerProfile`, ledger
diagnostics, and cross-period clean-state verdicts before persisting a
:class:`~aeat.domain.modelos._verification_report.VerificationReport`.

Verification emits bucket-history entries through
:class:`BucketEventHistoryRepository`, stores casilla-level
:class:`CasillaObservation` provenance, and uses
:class:`TransactionCatalogueRepository` only for evidence advisories over source
transactions. See also
:func:`~aeat.application.calculations.evaluate_cross_period_clean_state` for the
shared cross-period gate used by verify, file, and export.
"""

from __future__ import annotations

import decimal as _decimal
import re as _re
from collections.abc import Iterable, Mapping
from datetime import date, datetime
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
    ApplicabilityVerdict,
    CasillaDefinition,
    CasillaId,
    CasillaObservation,
    InputKind,
    Modelo202Modality,
    RegistrySnapshot,
    VerificationPredicateDefinition,
    derive_modelo_202_modality,
    derive_modelo_applicability,
    validated_casilla_id,
)
from ...domain.deadlines import FiscalResidency, IrpfIncomeCategory, TaxpayerProfile
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
from ._revision_persistence import emit_bucket_event as _emit_bucket_event
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
# and denominator > 0. Used for Art. 110.3.b RIRPF M130 high-retention exemption.
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
        # Phase 1 uses the broader ue_eee_status per m210-irnr-full-engine
        # ADR §D2.5 escape hatch: EEA residents are exempt because of the
        # bilateral mutual-assistance regime.
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


rewrite_m210_sentinels = _rewrite_m210_sentinels


def _evaluate_advisory_predicate_fires(
    expression: str,
    casilla_values: Mapping[CasillaId, Decimal],
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
    each dependency that carried a legacy / indeterminate revision stamp
    (``unstamped_revision_advisory``). The advisory is surfaced even when the
    dependency is otherwise ``clean`` — ADR 2026-06-10-period-revision-resolution-adr,
    Ruling 3 / R2 mandates that a legacy-unstamped carry must never degrade
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
    whose persisted observation has no revision stamp (legacy record) — or whose
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
            "law-determined revision (legacy or indeterminate record)."
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
            "amount on the corresponding casilla; for mutually exclusive pagos fraccionados, confirm the "
            "activity-estimation regime on the profile."
        ),
        next_action=(
            "Enter suffered retenciones from the income certificate where applicable, and confirm the "
            "profile's IRPF estimation regime if a mutually exclusive pago-fraccionado modelo was scoped out."
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
    # advisories (e.g. the legacy/indeterminate revision-stamp advisory) surface
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


#: Legal grounding for missing IVA evidence. Deducting input IVA requires the
#: original factura (LIVA art. 97, RD 1619/2012 art. 2). Output-IVA evidence
#: gaps stay advisory until the transaction model can distinguish every valid
#: issued-invoice support path without over-blocking.
_MISSING_EVIDENCE_LEGAL_REFS: tuple[str, ...] = (
    "ley-37-1992:art-97",
    "rd-1619-2012:art-2",
)


def _missing_evidence_advisory_findings(
    *,
    target: CalculationRevision,
    work_unit: WorkUnit,
    transaction_repository: TransactionCatalogueRepository | None,
) -> list[ModeloVerificationFinding]:
    """Build verification findings for evidence-less positive IVA rows.

    Loads the revision's source transactions and projects each
    :class:`~aeat.application.aggregation.CalculationSourceDiagnostic`
    (reason ``missing_transaction_evidence``) into a
    :class:`ModeloVerificationFinding`. Deductible input-IVA gaps are blocking;
    output-IVA gaps remain advisory. A revision with no contributing
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

    Returns a :class:`VerificationReport`. The supplied :class:`TaxpayerProfile`
    scopes deadline/applicability decisions, while
    :class:`TransactionCatalogueRepository` supplies transaction-evidence
    advisories for source rows attached to the :class:`CalculationRevision`.
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
                observation_repository=obs_repo,
                filing_repository=fr_repo,
                calculation_repository=cr_repo,
                verification_repository=vr_repo,
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
        _missing_evidence_advisory_findings(
            target=target,
            work_unit=work_unit,
            transaction_repository=transaction_repository,
        ),
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
    transaction's existing :class:`TransactionRevisionParticipationIndex`, upsert
    the new ``VERIFICADO_COMPLETO`` participation (replacing any prior entry for
    the same revision), and return the resulting ``SecureObjectWrite`` so the
    caller co-emits them in the same atomic unit of work as the revision save.
    A revision with no contributing transactions yields no writes.
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
