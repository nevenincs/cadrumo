"""Generic registry-authored predicate evaluation mechanics."""

from __future__ import annotations

import decimal as _decimal
from collections.abc import Callable, Mapping
from datetime import date as _date
from decimal import Decimal
from types import MappingProxyType

from ...core.casilla_id import CasillaId, validated_casilla_id
from ...core.money.rounding import CENT
from ...core.parsing.dates import parse_date
from ...domain.calculations.registry.authority import bundled_authority
from ...domain.calculations.registry.queries import RegistryQueryService
from ...domain.calculations.registry.schema_verification import (
    KNOWN_PROFILE_FLAG_ADVISORY_FIELDS,
    ParsedVerificationPredicate,
    VerificationPredicateDefinition,
    VerificationPredicateOperator,
    parse_verification_predicate_expression,
)
from ...domain.deadlines.models import TaxpayerProfile
from ...domain.modelos.errors import ModeloError
from ...domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from .action_errors import ModeloApplicabilityFilterError

"""Predicate operator mechanics; all predicate instances come from the registry."""


def _predicate_casilla_ids(predicate: ParsedVerificationPredicate) -> list[CasillaId]:
    """Validate a parsed predicate's casilla captures at the runtime boundary."""
    return [_validated_predicate_casilla_id(token) for token in predicate.casilla_ids]


def _validated_predicate_casilla_id(token: str) -> CasillaId:
    try:
        return validated_casilla_id(token, surface="verification predicate casilla id")
    except ValueError as exc:
        raise ModeloError(
            translated_message="errors.error.error_modelos",
            context={"casilla_id_token": token, "casilla_id_canonical": False},
        ) from exc


def _unique_predicate_casilla_id(predicate: VerificationPredicateDefinition) -> CasillaId | None:
    """Return the predicate's sole casilla, preserving cross-casilla findings at record grain."""
    parsed = parse_verification_predicate_expression(predicate.expression)
    if parsed is None:
        return None
    casilla_ids = _predicate_casilla_ids(parsed)
    return casilla_ids[0] if len(casilla_ids) == 1 else None


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

    the opening stock less the amount applied plus any stock newly generated
    this period. Holds within a one-cent tolerance to absorb per-detail
    rounding. Returns ``None`` on malformed arity; a missing casilla reads as
    ``Decimal(0)`` via ``.get``.
    """
    if len(ids) != 4:
        return None
    closing = casilla_values.get(ids[0], Decimal(0))
    opening = casilla_values.get(ids[1], Decimal(0))
    applied = casilla_values.get(ids[2], Decimal(0))
    base = casilla_values.get(ids[3], Decimal(0))
    generated = max(Decimal(0), -base)
    expected = opening - applied + generated
    # Bounded at the cent quantum: absorbs the sub-cent drift a
    # total-of-per-year-detail figure accumulates, without masking a genuine
    # discontinuity, which is euros rather than cents.
    return abs(closing - expected) <= CENT


def _evaluate_applicability_filter(filter_name: str, profile: TaxpayerProfile) -> bool:
    """Reject undeclared applicability filters instead of embedding registry data."""
    del profile
    if not filter_name:
        return True
    raise ModeloApplicabilityFilterError(f"Unknown applicability filter: {filter_name!r}")


_BlockingPredicateEvaluator = Callable[
    [ParsedVerificationPredicate, Mapping[CasillaId, Decimal], TaxpayerProfile],
    bool,
]


def _evaluate_all_nonzero(
    predicate: ParsedVerificationPredicate,
    casilla_values: Mapping[CasillaId, Decimal],
    _profile: TaxpayerProfile,
) -> bool:
    ids = _predicate_casilla_ids(predicate)
    return all(casilla_values.get(cid, Decimal(0)) != Decimal(0) for cid in ids)


def _evaluate_any_nonzero(
    predicate: ParsedVerificationPredicate,
    casilla_values: Mapping[CasillaId, Decimal],
    _profile: TaxpayerProfile,
) -> bool:
    ids = _predicate_casilla_ids(predicate)
    return any(casilla_values.get(cid, Decimal(0)) != Decimal(0) for cid in ids)


def _evaluate_at_most_one_positive(
    predicate: ParsedVerificationPredicate,
    casilla_values: Mapping[CasillaId, Decimal],
    _profile: TaxpayerProfile,
) -> bool:
    ids = _predicate_casilla_ids(predicate)
    if len(ids) < 2:
        return True
    return sum(1 for cid in ids if casilla_values.get(cid, Decimal(0)) > Decimal(0)) <= 1


def _evaluate_cap_le_when_positive(
    predicate: ParsedVerificationPredicate,
    casilla_values: Mapping[CasillaId, Decimal],
    _profile: TaxpayerProfile,
) -> bool:
    ids = _predicate_casilla_ids(predicate)
    if len(ids) != 2:
        return True
    limited_id, ceiling_id = ids
    ceiling = casilla_values.get(ceiling_id, Decimal(0))
    if ceiling <= Decimal(0):
        return True
    limited = casilla_values.get(limited_id, Decimal(0))
    return limited <= ceiling


def _evaluate_equals(
    predicate: ParsedVerificationPredicate,
    casilla_values: Mapping[CasillaId, Decimal],
    _profile: TaxpayerProfile,
) -> bool:
    ids = _predicate_casilla_ids(predicate)
    if len(ids) != 2:
        return True
    lhs, rhs = (casilla_values.get(cid, Decimal(0)) for cid in ids)
    return lhs == rhs


def _evaluate_implies_nonzero(
    predicate: ParsedVerificationPredicate,
    casilla_values: Mapping[CasillaId, Decimal],
    _profile: TaxpayerProfile,
) -> bool:
    ids = _predicate_casilla_ids(predicate)
    if len(ids) != 2:
        return True
    antecedent_id, consequent_id = ids
    antecedent = casilla_values.get(antecedent_id, Decimal(0))
    if antecedent <= Decimal(0):
        return True
    consequent = casilla_values.get(consequent_id, Decimal(0))
    return consequent != Decimal(0)


def _evaluate_implies_any_nonzero(
    predicate: ParsedVerificationPredicate,
    casilla_values: Mapping[CasillaId, Decimal],
    _profile: TaxpayerProfile,
) -> bool:
    ids = _predicate_casilla_ids(predicate)
    if len(ids) < 2:
        return True
    antecedent_id, *consequent_ids = ids
    antecedent = casilla_values.get(antecedent_id, Decimal(0))
    if antecedent <= Decimal(0):
        return True
    return any(casilla_values.get(cid, Decimal(0)) != Decimal(0) for cid in consequent_ids)


def _evaluate_profile_field_required(
    predicate: ParsedVerificationPredicate,
    _casilla_values: Mapping[CasillaId, Decimal],
    profile: TaxpayerProfile,
) -> bool:
    if not _evaluate_applicability_filter(predicate.applicability_filter, profile):
        return True
    field_value = getattr(profile, predicate.profile_field, None)
    return not (field_value is None or (isinstance(field_value, str) and not field_value.strip()))


def _evaluate_roll_forward_balances(
    predicate: ParsedVerificationPredicate,
    casilla_values: Mapping[CasillaId, Decimal],
    _profile: TaxpayerProfile,
) -> bool:
    reconciles = _roll_forward_balance_reconciles(_predicate_casilla_ids(predicate), casilla_values)
    if reconciles is None:
        return True
    return reconciles


_BLOCKING_PREDICATE_EVALUATORS: Mapping[VerificationPredicateOperator, _BlockingPredicateEvaluator] = MappingProxyType(
    {
        VerificationPredicateOperator.ALL_NONZERO: _evaluate_all_nonzero,
        VerificationPredicateOperator.ANY_NONZERO: _evaluate_any_nonzero,
        VerificationPredicateOperator.AT_MOST_ONE_POSITIVE: _evaluate_at_most_one_positive,
        VerificationPredicateOperator.CAP_LE_WHEN_POSITIVE: _evaluate_cap_le_when_positive,
        VerificationPredicateOperator.EQUALS: _evaluate_equals,
        VerificationPredicateOperator.IMPLIES_NONZERO: _evaluate_implies_nonzero,
        VerificationPredicateOperator.IMPLIES_ANY_NONZERO: _evaluate_implies_any_nonzero,
        VerificationPredicateOperator.PROFILE_FIELD_REQUIRED: _evaluate_profile_field_required,
        VerificationPredicateOperator.ROLL_FORWARD_BALANCES: _evaluate_roll_forward_balances,
    }
)


def evaluate_predicate_expression(
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
      holds iff the two named casillas hold the same value.
    - ``implies_nonzero(["antecedent_id", "consequent_id"])`` — material
      implication with strictly-positive antecedent: predicate holds iff
      antecedent <= 0 OR consequent != 0.
    - ``implies_any_nonzero(["antecedent_id", "c1_id", ...])`` — N-consequent
      generalisation: predicate holds iff antecedent <= 0 OR at least one
      listed consequent != 0.
    - ``profile_field_required("field_name", "applicability_filter")`` —
      profile-state-aware conditional non-zero requirement; sibling of
      ``implies_nonzero``.

    An expression that does not match any registered pattern is treated as
    holding (i.e. unknown predicates do not block the operator). The
    authoring-time validator in
    :mod:`~domain.calculations.registry._validate_surfaces` is the gate
    against typos reaching this branch.
    """
    predicate = parse_verification_predicate_expression(expression)
    if predicate is None:
        return True
    evaluator = _BLOCKING_PREDICATE_EVALUATORS.get(predicate.operator)
    if evaluator is None:
        return True
    return evaluator(predicate, casilla_values, profile)


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
    predicate = parse_verification_predicate_expression(expr)
    if predicate is None or predicate.operator is not VerificationPredicateOperator.ADVISORY_WHEN_RATIO_GE:
        return None
    num_id, den_id = _predicate_casilla_ids(predicate)
    den = casilla_values.get(den_id, Decimal(0))
    if den <= Decimal(0):
        return False
    # The threshold is registry-authored text. Its shape is refused at registry
    # build by _advisory_when_ratio_ge_predicate_failures, so a validated
    # registry cannot reach here with a bad one; this is the defence in depth for
    # anything that bypasses that gate. Both guards below are load-bearing:
    # a bare Decimal builds "NaN" and "Infinity" WITHOUT raising, and the
    # comparison is where they do their damage -- NaN raises InvalidOperation at
    # `>=` (which is why the comparison is inside this try, not after it), and
    # Infinity compares False to every ratio, silently disabling an advisory
    # written to catch under-declaration. Refusing to fire on an unreadable
    # threshold is the honest reading: the predicate cannot be evaluated.
    try:
        threshold = Decimal(predicate.threshold)
        if not threshold.is_finite():
            return False
        return (casilla_values.get(num_id, Decimal(0)) / den) >= threshold
    except _decimal.InvalidOperation:
        return False


def _advisory_profile_flag_fires(
    expr: str,
    _casilla_values: Mapping[CasillaId, Decimal],
    _text_values: Mapping[CasillaId, str],
    profile: TaxpayerProfile | None,
) -> bool | None:
    predicate = parse_verification_predicate_expression(expr)
    if predicate is None or predicate.operator is not VerificationPredicateOperator.PROFILE_FLAG_ENABLED:
        return None
    if profile is None:
        return False
    field = predicate.profile_field
    if field not in KNOWN_PROFILE_FLAG_ADVISORY_FIELDS:
        return False
    return bool(getattr(profile, field, False))


def _advisory_positive_fires(
    expr: str,
    casilla_values: Mapping[CasillaId, Decimal],
    _text_values: Mapping[CasillaId, str],
    _profile: TaxpayerProfile | None,
) -> bool | None:
    predicate = parse_verification_predicate_expression(expr)
    if predicate is None or predicate.operator is not VerificationPredicateOperator.ADVISORY_WHEN_POSITIVE:
        return None
    ids = _predicate_casilla_ids(predicate)
    if len(ids) != 1:
        return False
    return casilla_values.get(ids[0], Decimal(0)) > Decimal(0)


def _advisory_at_most_one_positive_fires(
    expr: str,
    casilla_values: Mapping[CasillaId, Decimal],
    _text_values: Mapping[CasillaId, str],
    _profile: TaxpayerProfile | None,
) -> bool | None:
    predicate = parse_verification_predicate_expression(expr)
    if predicate is None or predicate.operator is not VerificationPredicateOperator.AT_MOST_ONE_POSITIVE:
        return None
    ids = _predicate_casilla_ids(predicate)
    if len(ids) < 2:
        return False
    return sum(1 for cid in ids if casilla_values.get(cid, Decimal(0)) > Decimal(0)) > 1


def _advisory_implies_nonzero_fires(
    expr: str,
    casilla_values: Mapping[CasillaId, Decimal],
    _text_values: Mapping[CasillaId, str],
    _profile: TaxpayerProfile | None,
) -> bool | None:
    predicate = parse_verification_predicate_expression(expr)
    if predicate is None or predicate.operator is not VerificationPredicateOperator.IMPLIES_NONZERO:
        return None
    ids = _predicate_casilla_ids(predicate)
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
    predicate = parse_verification_predicate_expression(expr)
    if predicate is None or predicate.operator is not VerificationPredicateOperator.IMPLIES_ANY_NONZERO:
        return None
    ids = _predicate_casilla_ids(predicate)
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
    predicate = parse_verification_predicate_expression(expr)
    if predicate is None or predicate.operator is not VerificationPredicateOperator.ROLL_FORWARD_BALANCES:
        return None
    reconciles = _roll_forward_balance_reconciles(_predicate_casilla_ids(predicate), casilla_values)
    return reconciles is False


def _advisory_casilla_equals_implies_nonzero_fires(
    expr: str,
    casilla_values: Mapping[CasillaId, Decimal],
    text_values: Mapping[CasillaId, str],
    _profile: TaxpayerProfile | None,
) -> bool | None:
    predicate = parse_verification_predicate_expression(expr)
    if predicate is None or predicate.operator is not VerificationPredicateOperator.CASILLA_EQUALS_IMPLIES_NONZERO:
        return None
    if len(predicate.arguments) != 3:
        return False
    antecedent_id, consequent_id = _predicate_casilla_ids(predicate)
    literal = predicate.literal
    if text_values.get(antecedent_id) != literal:
        return False
    return casilla_values.get(consequent_id, Decimal(0)) == Decimal(0)


def _advisory_casilla_equals_implies_profile_flag_fires(
    expr: str,
    _casilla_values: Mapping[CasillaId, Decimal],
    text_values: Mapping[CasillaId, str],
    profile: TaxpayerProfile | None,
) -> bool | None:
    predicate = parse_verification_predicate_expression(expr)
    if predicate is None or predicate.operator is not VerificationPredicateOperator.CASILLA_EQUALS_IMPLIES_PROFILE_FLAG:
        return None
    if len(predicate.arguments) != 3:
        return False
    antecedent_id = _predicate_casilla_ids(predicate)[0]
    literal = predicate.literal
    field = predicate.profile_field
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
    predicate = parse_verification_predicate_expression(expr)
    if predicate is None or predicate.operator is not VerificationPredicateOperator.CASILLA_EQUALS_IMPLIES_DIVERGES:
        return None
    if len(predicate.arguments) != 4:
        return False
    antecedent_id, casilla_a_id, casilla_b_id = _predicate_casilla_ids(predicate)
    literal = predicate.literal
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
    predicate = parse_verification_predicate_expression(expr)
    if (
        predicate is None
        or predicate.operator is not VerificationPredicateOperator.DEDUCCION_REQUIRES_ADQUISICION_BEFORE
    ):
        return None
    if len(predicate.arguments) != 4:
        return False
    amount_id, acquisition_date_id, construction_date_id = _predicate_casilla_ids(predicate)
    cutoff = _parse_predicate_date(predicate.cutoff)
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
    predicate = parse_verification_predicate_expression(expr)
    if predicate is None or predicate.operator is not VerificationPredicateOperator.ADVISORY_WHEN_COMPUTED_DIVERGES:
        return None
    ids = _predicate_casilla_ids(predicate)
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


def evaluate_advisory_predicate_fires(
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


def _advisory_predicate_finding(predicate: VerificationPredicateDefinition) -> ModeloVerificationFinding:
    """Build the generic warning for a registry-authored advisory predicate."""
    legal_refs = tuple(str(r) for r in predicate.legal_refs)
    message_facts = {"predicate_id": predicate.predicate_id}
    casilla_id = _unique_predicate_casilla_id(predicate)
    return ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.ADVISORY,
        severity=ModeloVerificationFindingSeverity.WARNING,
        casilla_id=casilla_id,
        message_locale_key="application.modelo.findings.registry_advisory_predicate_fired",
        message_facts=message_facts,
        legal_refs=legal_refs,
    )


def _selected_revision_verification_predicates(
    *,
    modelo: str,
    filing_year: int,
    period: str,
    query_service: RegistryQueryService | None = None,
    as_of: _date | None = None,
) -> tuple[VerificationPredicateDefinition, ...]:
    """Read predicate instances from the revision selected by registry query."""
    service = query_service or RegistryQueryService(bundled_authority())
    revision = service._resolve_revision_for_scope(
        modelo,
        filing_year=filing_year,
        period=period,
        as_of=as_of,
    ).revision
    return tuple(revision.verification_predicates)


# Predicate instances, finding reasons, operands, and legal references are
# supplied by the selected ``RegistrySnapshot.revision`` at the verification
# action boundary.  This module deliberately retains only the generic
# predicate operators and finding projection; it does not author predicate
# facts or provide a fallback catalogue.
def evaluate_verification_predicates(
    predicates: tuple[VerificationPredicateDefinition, ...] | None,
    casilla_values: Mapping[CasillaId, Decimal],
    profile: TaxpayerProfile,
    text_values: Mapping[CasillaId, str] = MappingProxyType({}),
    blocking_finding_observer: Callable[
        [ModeloVerificationFinding, VerificationPredicateDefinition],
        None,
    ]
    | None = None,
    *,
    modelo: str | None = None,
    filing_year: int | None = None,
    period: str | None = None,
    query_service: RegistryQueryService | None = None,
    as_of: _date | None = None,
) -> list[ModeloVerificationFinding]:
    """Evaluate Layer 2 cross-casilla predicates into verification findings.

    ``predicates`` are
    :class:`~domain.calculations.registry.VerificationPredicateDefinition`
    entries from the selected registry snapshot. The returned records are
    :class:`~ModeloVerificationFinding` values.

    ``text_values`` carries operator-entered raw strings (e.g.
    :attr:`~CalculationRevision.input_values_by_casilla_id`),
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
        :func:`evaluate_predicate_expression`:
            Evaluates the blocking-rule predicate DSL.
        :func:`evaluate_advisory_predicate_fires`:
            Evaluates the advisory predicate DSL.
        :func:`_classify_verification_outcome`:
            Converts finding severity into report completeness and grant status.
    """
    if predicates is None:
        if modelo is None or filing_year is None or period is None:
            raise ValueError("predicate evaluation requires a selected registry revision")
        predicates = _selected_revision_verification_predicates(
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            query_service=query_service,
            as_of=as_of,
        )

    if not predicates:
        return []

    findings: list[ModeloVerificationFinding] = []
    for predicate in predicates:
        if predicate.finding_kind == "ADVISORY":
            # ADVISORY predicates fire a WARNING finding when their condition IS met
            # (affirmative logic — opposite of BLOCKING_RULE predicates).
            if evaluate_advisory_predicate_fires(predicate.expression, casilla_values, text_values, profile):
                findings.append(_advisory_predicate_finding(predicate))
        else:
            if not evaluate_predicate_expression(predicate.expression, casilla_values, profile):
                finding = ModeloVerificationFinding(
                    kind=ModeloVerificationFindingKind.BLOCKING_RULE,
                    severity=ModeloVerificationFindingSeverity.BLOCKING,
                    casilla_id=_unique_predicate_casilla_id(predicate),
                    message_locale_key="application.modelo.findings.cross_casilla_invariant_violated",
                    message_facts={"predicate_id": predicate.predicate_id},
                    legal_refs=tuple(str(r) for r in predicate.legal_refs),
                )
                findings.append(finding)
                if blocking_finding_observer is not None:
                    blocking_finding_observer(finding, predicate)
    return findings
