"""Registry-authored predicate runtime for modelo verification.

The verification action feeds this module predicate rows from the selected
:class:`~domain.calculations.registry.RegistrySnapshot`. The runtime evaluates
blocking and advisory DSL expressions against calculated casilla values,
profile state, and typed unresolved calculation outcomes, then returns
operator-facing verification findings.

See Also:
    :mod:`~application.modelo._verification_actions`
        Verification workflow that resolves the snapshot and persists reports.
    :class:`~domain.calculations.registry.VerificationPredicateDefinition`
        Registry-authored predicate records evaluated here.
    :class:`~domain.calculations.registry.RegistryCalculationUnresolvedOutcome`
        Typed unresolved engine outcomes converted into verification findings.
    :class:`~domain.modelos.ModeloVerificationFinding`
        Finding records returned to the verification report.
"""

from __future__ import annotations

import decimal as _decimal
import re as _re
from collections.abc import Callable, Mapping
from datetime import date as _date
from decimal import Decimal
from types import MappingProxyType

from ...core.i18n import tr
from ...core.parsing import parse_date
from ...domain.calculations.registry import (
    KNOWN_PROFILE_FLAG_ADVISORY_FIELDS,
    CasillaId,
    RegistryCalculationUnresolvedOutcome,
    RegistrySnapshot,
    RegistryUnresolvedOutcomeReason,
    VerificationPredicateDefinition,
    validated_casilla_id,
)
from ...domain.deadlines import FiscalResidency, TaxpayerProfile
from ...domain.modelos import (
    ModeloError,
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from ._action_errors import ModeloApplicabilityFilterError
from ._m210_rate import resolve_m210_rate as _resolve_m210_rate

_PREDICATE_ALL_NONZERO = _re.compile(r"^all_nonzero\(\[(?P<ids>[^\]]*)\]\)$")
_PREDICATE_ANY_NONZERO = _re.compile(r"^any_nonzero\(\[(?P<ids>[^\]]*)\]\)$")
_PREDICATE_AT_MOST_ONE_POSITIVE = _re.compile(r"^at_most_one_positive\(\[(?P<ids>[^\]]*)\]\)$")
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
# implies_nonzero. The applicability filter is dispatched via
# _evaluate_applicability_filter against the TaxpayerProfile threaded
# through the verification pipeline. First use site: M210
# representante-fiscal gate (TRLIRNR Art 10).
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


# Per-advisory fallback message for advisory predicates whose finding text is
# not (yet) carried in the locale catalogue. The advisory finding message is
# resolved via ``tr(advisory_key, default=...)``: a registered locale key still
# takes precedence, and this default is used only when the key is absent — so
# translators can enrich the catalogue later without a code change. Mirrors the
# ``_resolve_predicate_next_action`` per-predicate dispatch shape.
def _resolve_advisory_message_default(predicate_id: str) -> str | None:
    if predicate_id == "modelo-130-art109-exencion-alta-retencion":
        return (
            "The taxpayer profile says the Art. 109 RIRPF 70% income-coverage exception is met "
            "for covered professional, agricultural, livestock, or forestry activity income. "
            "Modelo 130 casilla 17 remains the official form subtraction; confirm that "
            "preparing an M130 draft is intentional for this profile before filing."
        )
    if predicate_id in {
        "modelo-100-2024-deduccion-vivienda-habitual-requiere-adquisicion-anterior-2013",
        "modelo-100-2025-deduccion-vivienda-habitual-requiere-adquisicion-anterior-2013",
    }:
        return (
            "The deducción por inversión en vivienda habitual is claimed but no pre-2013 "
            "acquisition signal is recorded. The transitional régimen (LIRPF DT 18ª) admits "
            "only dwellings acquired before 1 January 2013 (or pre-2013 construction / "
            "rehabilitation amounts); the deducción was abolished for later acquisitions. "
            "Confirm the acquisition date qualifies before filing."
        )
    return None


# advisory_when_ratio_ge(["numerator_id", "denominator_id", "threshold"]) —
# fires a WARNING-severity ADVISORY finding when numerator/denominator >= threshold
# and denominator > 0. This is a generic casilla-ratio predicate; it is not an
# Art. 109 RIRPF exemption test for Modelo 130.
_PREDICATE_ADVISORY_WHEN_RATIO_GE = _re.compile(
    r'^advisory_when_ratio_ge\(\["(?P<num>[^"]+)",\s*"(?P<den>[^"]+)",\s*"(?P<thr>[^"]+)"\]\)$',
)
_PREDICATE_PROFILE_FLAG_ENABLED = _re.compile(r'^profile_flag_enabled\("(?P<field>[^"]+)"\)$')
# advisory_when_positive(["casilla_id"]) — single-casilla positive advisory:
# fires (advisory shown) iff the one named casilla value is strictly > 0.
# ADVISORY-only; see the advisory_when_positive branch in
# _evaluate_advisory_predicate_fires. A generic single-casilla positive-value
# advisory operator; it carries no modelo-specific prose of its own (the M100
# anualidades por alimentos separate-escala it was first authored for is now a
# fully computed, correctly-gated chain and no longer uses this advisory).
_PREDICATE_ADVISORY_WHEN_POSITIVE = _re.compile(
    r"^advisory_when_positive\(\[(?P<ids>[^\]]*)\]\)$",
)
# roll_forward_balances(["closing_id", "opening_id", "applied_id", "base_id"]) —
# carry-forward stock continuity: closing == opening − applied + max(0, −base),
# within a one-cent tolerance. See _roll_forward_balance_reconciles.
_PREDICATE_ROLL_FORWARD_BALANCES = _re.compile(r"^roll_forward_balances\(\[(?P<ids>[^\]]*)\]\)$")
# casilla_equals_implies_nonzero(["antecedent_casilla_id", "literal",
# "consequent_casilla_id"]) — categorical-conditional material implication:
# fires when the antecedent TEXT casilla's operator-entered raw value equals
# the literal AND the consequent (Decimal) casilla is zero. ADVISORY-only
# (no BLOCKING_RULE branch); see the casilla_equals_implies_nonzero branch in
# _evaluate_advisory_predicate_fires and the
# Authored for the M210
# inmobiliaria branch (tipo_renta == "inmobiliaria" implies a non-zero
# base_imponible), the no-silent-under-declaration shape implies_nonzero
# cannot express because its trigger is a categorical equality, not a
# numeric antecedent.
_PREDICATE_CASILLA_EQUALS_IMPLIES_NONZERO = _re.compile(
    r"^casilla_equals_implies_nonzero\(\[(?P<ids>[^\]]*)\]\)$",
)
# casilla_equals_implies_profile_flag(["antecedent_casilla_id", "literal",
# "profile_field"]) — categorical-antecedent / profile-state-consequent
# conditional advisory: fires when the named antecedent TEXT casilla's
# operator-entered raw value equals the literal AND the named boolean
# TaxpayerProfile field/property is False. ADVISORY-only (no BLOCKING_RULE
# branch); sibling of casilla_equals_implies_nonzero (whose consequent test
# reads a Decimal casilla) and profile_flag_enabled (whose antecedent is
# unconditional). Authored for the M210 IRNR tipo_renta="ue_residente"
# category (TRLIRNR Art 25.1.a reduced rate): the operator-entered
# categorical rate election is not cross-checked against the declared
# country_of_fiscal_residence, so a non-EU/EEA filer could self-declare the
# reduced 19% rate reserved for EU/EEE residents rather than the correct 24%
# general rate. See the casilla_equals_implies_profile_flag branch in
# _evaluate_advisory_predicate_fires.
_PREDICATE_CASILLA_EQUALS_IMPLIES_PROFILE_FLAG = _re.compile(
    r"^casilla_equals_implies_profile_flag\(\[(?P<ids>[^\]]*)\]\)$",
)
# casilla_equals_implies_diverges(["antecedent_casilla_id", "literal",
# "casilla_a_id", "casilla_b_id"]) — categorical-conditional divergence
# check: fires when the antecedent TEXT casilla's operator-entered raw value
# equals the literal AND the two named (Decimal) casillas differ by more
# than one cent. ADVISORY-only (no BLOCKING_RULE branch); sibling of
# casilla_equals_implies_nonzero (whose consequent test is "== 0" rather
# than a cross-casilla divergence). See the
# casilla_equals_implies_diverges branch in
# _evaluate_advisory_predicate_fires. Authored for the M131/M100
# estimación-objetiva índice corrector de exceso (b.3), which Orden
# HAC/1347/2024 Anexo II instrucción 2.3 declares incompatible with the
# índices correctores especiales (a.2 transporte por autotaxis, a.4
# transporte de mercancías por carretera / servicios de mudanzas) for the
# activities that carry both — a shape no existing operator can express
# because it combines a categorical epígrafe equality with a Decimal-pair
# divergence test.
_PREDICATE_CASILLA_EQUALS_IMPLIES_DIVERGES = _re.compile(
    r"^casilla_equals_implies_diverges\(\[(?P<ids>[^\]]*)\]\)$",
)
# deduccion_requires_adquisicion_before(["amount_id", "acquisition_date_id",
# "construction_date_id", "cutoff_iso"]) — eligibility-conditional advisory:
# fires when the amount (Decimal) casilla is strictly positive but neither the
# acquisition-date TEXT casilla holds a date strictly before the cutoff nor the
# construction-date TEXT casilla is non-empty. ADVISORY-only; see the
# deduccion_requires_adquisicion_before branch in
# _evaluate_advisory_predicate_fires. Authored for the M100 deducción por
# inversión en vivienda habitual transitional régimen (LIRPF DT 18ª), whose
# eligibility requires acquisition before 01-01-2013 — a date-threshold trigger
# neither implies_nonzero (numeric antecedent) nor casilla_equals_implies_nonzero
# (categorical text equality) can express.
_PREDICATE_DEDUCCION_REQUIRES_ADQUISICION_BEFORE = _re.compile(
    r"^deduccion_requires_adquisicion_before\(\[(?P<ids>[^\]]*)\]\)$",
)
# advisory_when_computed_diverges(["declared_id", "computed_id"]) —
# table-driven-engine-vs-operator-declared discrepancy: fires when the named
# COMPUTED reference casilla resolves strictly > 0 (the engine has table
# coverage for the declared activity) AND it differs from the named
# operator-declared casilla by more than one cent. ADVISORY-only; see the
# advisory_when_computed_diverges branch in _evaluate_advisory_predicate_fires.
# Authored for the M131
# estimación-objetiva módulos engine: casilla 01 ("Suma de rendimientos
# netos") stays a manual operator input (fases 2ª/3ª are not yet wired),
# but a tabled first-slice activity now has a computed reference figure
# (modulos-rendimiento-neto-actividad) the operator can be prompted to
# reconcile against.
_PREDICATE_ADVISORY_WHEN_COMPUTED_DIVERGES = _re.compile(
    r"^advisory_when_computed_diverges\(\[(?P<ids>[^\]]*)\]\)$",
)

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


def _parse_predicate_raw_tokens(ids_fragment: str) -> list[str]:
    """Parse the comma-separated quoted-token list without casilla-id validation.

    Used for ``casilla_equals_implies_nonzero``, whose middle token is a
    literal string (e.g. ``"inmobiliaria"``), not a casilla id — unlike
    :func:`_parse_predicate_casilla_ids`, which validates every token. The
    caller validates the antecedent/consequent slots individually via
    :func:`_validated_predicate_casilla_id`.
    """
    return [token.strip().strip('"').strip("'") for token in ids_fragment.split(",") if token.strip()]


def _parse_predicate_date(raw: str) -> _date | None:
    """Parse an operator-entered date string, or ``None`` when absent/unparseable.

    Accepts the ISO form (the cutoff literal shape) and the Spanish day-first
    operator-entry forms ``DD/MM/YYYY`` and ``DD-MM-YYYY``, both resolved by the
    canonical :func:`core.parsing.parse_date` contract rather than a local
    format list. Used by the ``deduccion_requires_adquisicion_before`` advisory
    to read the acquisition-date TEXT casilla and the cutoff literal.

    The canonical parser requires two-digit day and month components, so a
    partially-typed ``1/2/2024`` is no longer silently resolved to a date. That
    matters here specifically: the value decides a deduction's eligibility
    against a statutory cutoff, and an under-specified entry is a date the
    operator has not actually stated. It returns ``None`` like any other
    unparseable value, so the advisory treats it as "no eligibility signal" --
    a non-blocking prompt to correct or confirm the date -- rather than acting
    on a guess.
    """
    text = raw.strip()
    if not text:
        return None
    for fmt in ("iso8601", "ddmmyyyy"):
        parsed = parse_date(text, fmt=fmt, on_error="none")
        if parsed is not None:
            return parsed
    return None


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
    gate. Authored for the Modelo 200 BIN total-pendiente roll-forward;
    general to any carry-forward stock.
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
    :data:`~domain.calculations.registry._schema_verification.KNOWN_VERIFICATION_PREDICATE_OPERATORS`:

    - ``all_nonzero(["id1", "id2", ...])`` — all ids must have a non-zero value.
    - ``any_nonzero(["id1", "id2", ...])`` — at least one id must have a non-zero value.
    - ``at_most_one_positive(["id1", "id2", ...])`` — no more than one named
      casilla may be strictly positive.
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
      ``implies_nonzero``.

    An expression that does not match any registered pattern is treated as
    holding (i.e. unknown predicates do not block the operator). The
    authoring-time validator in
    :mod:`~domain.calculations.registry._validate_surfaces` is the gate
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

    m = _PREDICATE_AT_MOST_ONE_POSITIVE.match(expr)
    if m:
        ids = _parse_predicate_casilla_ids(m.group("ids"))
        if len(ids) < 2:
            return True
        return sum(1 for cid in ids if casilla_values.get(cid, Decimal(0)) > Decimal(0)) <= 1

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


_M210_UNRESOLVED_RATE_REASONS = frozenset(
    {
        RegistryUnresolvedOutcomeReason.M210_BASELINE_TIPO_DEFERRED,
        RegistryUnresolvedOutcomeReason.M210_CONVENIO_RATE_MISSING,
    },
)


def _m210_unresolved_outcome_findings(
    unresolved_outcomes: tuple[RegistryCalculationUnresolvedOutcome, ...],
    *,
    profile: TaxpayerProfile,
    snapshot: RegistrySnapshot,
    year: int,
    tipo_renta: str,
) -> list[ModeloVerificationFinding]:
    """Convert typed M210 unresolved engine outcomes into verification findings.

    The formula runtime reports an unresolvable IRNR rate beside the Decimal
    value channels as :class:`RegistryCalculationUnresolvedOutcome`. This
    verification-layer consumer replays the application M210 rate resolver over
    each M210 rate outcome and returns any BLOCKING findings it emits.
    """
    findings: list[ModeloVerificationFinding] = []
    for outcome in unresolved_outcomes:
        if outcome.reason not in _M210_UNRESOLVED_RATE_REASONS:
            continue
        resolved_tipo_renta = tipo_renta or outcome.context.get("tipo_renta", "")
        _rate, obs_findings = _resolve_m210_rate(profile, resolved_tipo_renta, year, snapshot)
        findings.extend(obs_findings)
    return findings


_AdvisoryPredicateEvaluator = Callable[
    [str, Mapping[CasillaId, Decimal], Mapping[CasillaId, str], TaxpayerProfile | None],
    bool | None,
]


def _advisory_ratio_ge_fires(
    expr: str,
    casilla_values: Mapping[CasillaId, Decimal],
    _text_values: Mapping[CasillaId, str],
    _profile: TaxpayerProfile | None,
) -> bool | None:
    m = _PREDICATE_ADVISORY_WHEN_RATIO_GE.match(expr)
    if not m:
        return None
    num_id = _validated_predicate_casilla_id(m.group("num"))
    den_id = _validated_predicate_casilla_id(m.group("den"))
    den = casilla_values.get(den_id, Decimal(0))
    if den <= Decimal(0):
        return False
    try:
        threshold = Decimal(m.group("thr"))
    except _decimal.InvalidOperation:
        return False
    return (casilla_values.get(num_id, Decimal(0)) / den) >= threshold


def _advisory_profile_flag_fires(
    expr: str,
    _casilla_values: Mapping[CasillaId, Decimal],
    _text_values: Mapping[CasillaId, str],
    profile: TaxpayerProfile | None,
) -> bool | None:
    m = _PREDICATE_PROFILE_FLAG_ENABLED.match(expr)
    if not m:
        return None
    if profile is None:
        return False
    field = m.group("field")
    if field not in KNOWN_PROFILE_FLAG_ADVISORY_FIELDS:
        return False
    return bool(getattr(profile, field, False))


def _advisory_positive_fires(
    expr: str,
    casilla_values: Mapping[CasillaId, Decimal],
    _text_values: Mapping[CasillaId, str],
    _profile: TaxpayerProfile | None,
) -> bool | None:
    m = _PREDICATE_ADVISORY_WHEN_POSITIVE.match(expr)
    if not m:
        return None
    ids = _parse_predicate_casilla_ids(m.group("ids"))
    if len(ids) != 1:
        return False
    return casilla_values.get(ids[0], Decimal(0)) > Decimal(0)


def _advisory_at_most_one_positive_fires(
    expr: str,
    casilla_values: Mapping[CasillaId, Decimal],
    _text_values: Mapping[CasillaId, str],
    _profile: TaxpayerProfile | None,
) -> bool | None:
    m = _PREDICATE_AT_MOST_ONE_POSITIVE.match(expr)
    if not m:
        return None
    ids = _parse_predicate_casilla_ids(m.group("ids"))
    if len(ids) < 2:
        return False
    return sum(1 for cid in ids if casilla_values.get(cid, Decimal(0)) > Decimal(0)) > 1


def _advisory_implies_nonzero_fires(
    expr: str,
    casilla_values: Mapping[CasillaId, Decimal],
    _text_values: Mapping[CasillaId, str],
    _profile: TaxpayerProfile | None,
) -> bool | None:
    m = _PREDICATE_IMPLIES_NONZERO.match(expr)
    if not m:
        return None
    ids = _parse_predicate_casilla_ids(m.group("ids"))
    if len(ids) != 2:
        return False
    antecedent = casilla_values.get(ids[0], Decimal(0))
    consequent = casilla_values.get(ids[1], Decimal(0))
    return antecedent > Decimal(0) and consequent == Decimal(0)


def _advisory_implies_any_nonzero_fires(
    expr: str,
    casilla_values: Mapping[CasillaId, Decimal],
    _text_values: Mapping[CasillaId, str],
    _profile: TaxpayerProfile | None,
) -> bool | None:
    m = _PREDICATE_IMPLIES_ANY_NONZERO.match(expr)
    if not m:
        return None
    ids = _parse_predicate_casilla_ids(m.group("ids"))
    if len(ids) < 2:
        return False
    antecedent = casilla_values.get(ids[0], Decimal(0))
    if antecedent <= Decimal(0):
        return False
    return all(casilla_values.get(cid, Decimal(0)) == Decimal(0) for cid in ids[1:])


def _advisory_roll_forward_balances_fires(
    expr: str,
    casilla_values: Mapping[CasillaId, Decimal],
    _text_values: Mapping[CasillaId, str],
    _profile: TaxpayerProfile | None,
) -> bool | None:
    m = _PREDICATE_ROLL_FORWARD_BALANCES.match(expr)
    if not m:
        return None
    reconciles = _roll_forward_balance_reconciles(_parse_predicate_casilla_ids(m.group("ids")), casilla_values)
    return reconciles is False


def _advisory_casilla_equals_implies_nonzero_fires(
    expr: str,
    casilla_values: Mapping[CasillaId, Decimal],
    text_values: Mapping[CasillaId, str],
    _profile: TaxpayerProfile | None,
) -> bool | None:
    m = _PREDICATE_CASILLA_EQUALS_IMPLIES_NONZERO.match(expr)
    if not m:
        return None
    tokens = _parse_predicate_raw_tokens(m.group("ids"))
    if len(tokens) != 3:
        return False
    antecedent_id = _validated_predicate_casilla_id(tokens[0])
    literal = tokens[1]
    consequent_id = _validated_predicate_casilla_id(tokens[2])
    if text_values.get(antecedent_id) != literal:
        return False
    return casilla_values.get(consequent_id, Decimal(0)) == Decimal(0)


def _advisory_casilla_equals_implies_profile_flag_fires(
    expr: str,
    _casilla_values: Mapping[CasillaId, Decimal],
    text_values: Mapping[CasillaId, str],
    profile: TaxpayerProfile | None,
) -> bool | None:
    m = _PREDICATE_CASILLA_EQUALS_IMPLIES_PROFILE_FLAG.match(expr)
    if not m:
        return None
    tokens = _parse_predicate_raw_tokens(m.group("ids"))
    if len(tokens) != 3:
        return False
    antecedent_id = _validated_predicate_casilla_id(tokens[0])
    literal = tokens[1]
    field = tokens[2]
    if text_values.get(antecedent_id) != literal:
        return False
    if profile is None or field not in KNOWN_PROFILE_FLAG_ADVISORY_FIELDS:
        return False
    return not bool(getattr(profile, field, False))


def _advisory_casilla_equals_implies_diverges_fires(
    expr: str,
    casilla_values: Mapping[CasillaId, Decimal],
    text_values: Mapping[CasillaId, str],
    _profile: TaxpayerProfile | None,
) -> bool | None:
    m = _PREDICATE_CASILLA_EQUALS_IMPLIES_DIVERGES.match(expr)
    if not m:
        return None
    tokens = _parse_predicate_raw_tokens(m.group("ids"))
    if len(tokens) != 4:
        return False
    antecedent_id = _validated_predicate_casilla_id(tokens[0])
    literal = tokens[1]
    casilla_a_id = _validated_predicate_casilla_id(tokens[2])
    casilla_b_id = _validated_predicate_casilla_id(tokens[3])
    if text_values.get(antecedent_id) != literal:
        return False
    casilla_a = casilla_values.get(casilla_a_id, Decimal(0))
    casilla_b = casilla_values.get(casilla_b_id, Decimal(0))
    return abs(casilla_a - casilla_b) > Decimal("0.01")


def _advisory_deduccion_requires_adquisicion_before_fires(
    expr: str,
    casilla_values: Mapping[CasillaId, Decimal],
    text_values: Mapping[CasillaId, str],
    _profile: TaxpayerProfile | None,
) -> bool | None:
    m = _PREDICATE_DEDUCCION_REQUIRES_ADQUISICION_BEFORE.match(expr)
    if not m:
        return None
    tokens = _parse_predicate_raw_tokens(m.group("ids"))
    if len(tokens) != 4:
        return False
    amount_id = _validated_predicate_casilla_id(tokens[0])
    acquisition_date_id = _validated_predicate_casilla_id(tokens[1])
    construction_date_id = _validated_predicate_casilla_id(tokens[2])
    cutoff = _parse_predicate_date(tokens[3])
    if cutoff is None or casilla_values.get(amount_id, Decimal(0)) <= Decimal(0):
        return False
    acquisition_date = _parse_predicate_date(text_values.get(acquisition_date_id, ""))
    eligible_by_acquisition = acquisition_date is not None and acquisition_date < cutoff
    eligible_by_construction = bool(text_values.get(construction_date_id, "").strip())
    return not (eligible_by_acquisition or eligible_by_construction)


def _advisory_computed_diverges_fires(
    expr: str,
    casilla_values: Mapping[CasillaId, Decimal],
    _text_values: Mapping[CasillaId, str],
    _profile: TaxpayerProfile | None,
) -> bool | None:
    m = _PREDICATE_ADVISORY_WHEN_COMPUTED_DIVERGES.match(expr)
    if not m:
        return None
    ids = _parse_predicate_casilla_ids(m.group("ids"))
    if len(ids) != 2:
        return False
    declared_id, computed_id = ids[0], ids[1]
    computed = casilla_values.get(computed_id, Decimal(0))
    if computed <= Decimal(0):
        return False
    declared = casilla_values.get(declared_id, Decimal(0))
    return abs(declared - computed) > Decimal("0.01")


_ADVISORY_PREDICATE_EVALUATORS: tuple[_AdvisoryPredicateEvaluator, ...] = (
    _advisory_ratio_ge_fires,
    _advisory_profile_flag_fires,
    _advisory_positive_fires,
    _advisory_at_most_one_positive_fires,
    _advisory_implies_nonzero_fires,
    _advisory_implies_any_nonzero_fires,
    _advisory_roll_forward_balances_fires,
    _advisory_casilla_equals_implies_nonzero_fires,
    _advisory_casilla_equals_implies_profile_flag_fires,
    _advisory_casilla_equals_implies_diverges_fires,
    _advisory_deduccion_requires_adquisicion_before_fires,
    _advisory_computed_diverges_fires,
)


def _evaluate_advisory_predicate_fires(
    expression: str,
    casilla_values: Mapping[CasillaId, Decimal],
    text_values: Mapping[CasillaId, str] = MappingProxyType({}),
    profile: TaxpayerProfile | None = None,
) -> bool:
    """Return True when a registered ADVISORY predicate condition fires."""
    expr = expression.strip()
    for evaluator in _ADVISORY_PREDICATE_EVALUATORS:
        result = evaluator(expr, casilla_values, text_values, profile)
        if result is not None:
            return result
    return False


def _evaluate_verification_predicates(
    predicates: tuple[VerificationPredicateDefinition, ...],
    casilla_values: Mapping[CasillaId, Decimal],
    profile: TaxpayerProfile,
    text_values: Mapping[CasillaId, str] = MappingProxyType({}),
) -> list[ModeloVerificationFinding]:
    """Evaluate Layer 2 cross-casilla predicates into verification findings.

    ``predicates`` are
    :class:`~domain.calculations.registry.VerificationPredicateDefinition`
    entries from the selected registry snapshot. The returned records are
    :class:`~domain.modelos.ModeloVerificationFinding` values.

    ``text_values`` carries operator-entered raw strings (e.g.
    :attr:`~domain.modelos.CalculationRevision.input_values_by_casilla_id`),
    independent of the Decimal ``casilla_values`` projection. It defaults to an
    empty mapping and is consumed by text-aware ADVISORY operators such as
    ``casilla_equals_implies_nonzero``; every other operator ignores it.

    ``BLOCKING_RULE`` predicates use negative logic: the predicate expression must
    hold, and a violation emits a BLOCKING finding. ``ADVISORY`` predicates use
    affirmative logic: when their condition fires, the operator receives a
    WARNING-severity ADVISORY finding and the verified-complete grant remains
    possible if no blocking findings exist.

    ``profile`` is a :class:`~domain.deadlines.TaxpayerProfile` threaded
    through to support profile-state-aware predicate operators such as
    ``profile_field_required`` and ``profile_flag_enabled``. Casilla-only
    operators ignore the parameter.

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
            if _evaluate_advisory_predicate_fires(predicate.expression, casilla_values, text_values, profile):
                advisory_key = f"application.modelo.findings.{predicate.predicate_id.replace('-', '_')}"
                findings.append(
                    ModeloVerificationFinding(
                        kind=ModeloVerificationFindingKind.ADVISORY,
                        severity=ModeloVerificationFindingSeverity.WARNING,
                        message=tr(advisory_key, default=_resolve_advisory_message_default(predicate.predicate_id)),
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
