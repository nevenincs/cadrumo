"""Generic registry-authored predicate evaluation mechanics."""

from __future__ import annotations

import decimal as _decimal
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date as _date
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType
from typing import TYPE_CHECKING

from ...core.casilla_id import CasillaId, validated_casilla_id
from ...core.money.rounding import CENT
from ...core.parsing.dates import parse_date
from ...domain.calculations.registry.queries import RegistryQueryService
from ...domain.calculations.registry.renta_codes_catalogue import resolve_fiscal_residency_catalogue
from ...domain.calculations.registry.schema_verification import (
    KNOWN_PROFILE_FLAG_ADVISORY_FIELDS,
    VERIFICATION_PREDICATE_SPECIFICATIONS,
    ParsedVerificationPredicate,
    VerificationPredicateDefinition,
    VerificationPredicateOperator,
    parse_verification_predicate_expression,
    verification_predicate_operator_name,
)
from ...domain.deadlines.models import TaxpayerProfile
from ...domain.modelos.errors import ModeloError
from ...domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from .action_errors import ModeloApplicabilityFilterError, ModeloVerificationPredicateMalformedError

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation

"""Predicate operator mechanics; all predicate instances come from the registry."""


class VerificationPredicateRoute(StrEnum):
    """The evaluation route a registry predicate is admitted to."""

    BLOCKING = "blocking"
    ADVISORY = "advisory"


class VerificationPredicateRefusal(StrEnum):
    """Why a registry predicate was refused at admission to its route."""

    #: The expression does not parse as any predicate of the vocabulary.
    UNPARSEABLE = "unparseable"
    #: The casilla count is outside the operator's specification.
    ARITY = "arity"
    #: The route has no evaluator for the operator.
    OPERATOR_FAMILY = "operator_family"
    #: A registry-authored literal of the operator is unreadable.
    LITERAL = "literal"


_BLOCKING_ROUTE = VerificationPredicateRoute.BLOCKING
_ADVISORY_ROUTE = VerificationPredicateRoute.ADVISORY


@dataclass(frozen=True, slots=True)
class _AdmittedPredicate:
    """A registry predicate admitted to one evaluation route, its operands already read.

    ``threshold`` and ``cutoff`` are the registry-authored literals of the
    operators that carry them, read once at admission so no evaluator can meet
    an unreadable one.
    """

    parsed: ParsedVerificationPredicate
    casilla_ids: tuple[CasillaId, ...]
    threshold: Decimal | None = None
    cutoff: _date | None = None


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


def _predicate_refusal(
    operator: VerificationPredicateOperator | None,
    refusal: VerificationPredicateRefusal,
    route: VerificationPredicateRoute,
) -> ModeloVerificationPredicateMalformedError:
    return ModeloVerificationPredicateMalformedError(
        translated_message="errors.refused.refused_modelo_verification_predicate_malformed",
        context={
            "predicate_expression_recognised": False,
            "predicate_operator": None if operator is None else operator.value,
            "predicate_refusal": refusal.value,
            "predicate_route": route.value,
        },
    )


def _vocabulary_operator(expression: str) -> VerificationPredicateOperator | None:
    """Name the expression's operator only when it is in the closed vocabulary."""
    name = verification_predicate_operator_name(expression)
    if name is None:
        return None
    try:
        return VerificationPredicateOperator(name)
    except ValueError:
        return None


def _registry_threshold(raw: str) -> Decimal | None:
    """Read a registry-authored ratio threshold, or ``None`` when it is not a finite number.

    A bare :class:`~decimal.Decimal` builds ``NaN`` and ``Infinity`` without
    raising, and either would silently disable the ratio comparison, so both
    count as unreadable alongside text that is not a number at all.
    """
    try:
        threshold = Decimal(raw)
    except _decimal.InvalidOperation:
        return None
    return threshold if threshold.is_finite() else None


_LITERAL_OPERATORS: frozenset[VerificationPredicateOperator] = frozenset(
    {
        VerificationPredicateOperator.CASILLA_EQUALS_IMPLIES_DIVERGES,
        VerificationPredicateOperator.CASILLA_EQUALS_IMPLIES_NONZERO,
        VerificationPredicateOperator.CASILLA_EQUALS_IMPLIES_ZERO,
        VerificationPredicateOperator.CASILLA_EQUALS_IMPLIES_PROFILE_FLAG,
    }
)
_PROFILE_FLAG_OPERATORS: frozenset[VerificationPredicateOperator] = frozenset(
    {
        VerificationPredicateOperator.PROFILE_FLAG_ENABLED,
        VerificationPredicateOperator.CASILLA_EQUALS_IMPLIES_PROFILE_FLAG,
    }
)


def _required_parsed_predicate(expression: str, *, route: VerificationPredicateRoute) -> _AdmittedPredicate:
    """Admit one registry predicate to its route, refusing it before any evaluation.

    An unparseable expression, an operator the route has no evaluator for, a
    casilla count outside the operator's specification, or an unreadable
    registry-authored literal is a malformed registry predicate and raises the
    registered refusal :class:`ModeloVerificationPredicateMalformedError`; a
    non-canonical casilla token raises :class:`ModeloError`. Each refuses on
    every call; none is read as holding or as not firing.
    """
    parsed = parse_verification_predicate_expression(expression)
    if parsed is None:
        raise _predicate_refusal(_vocabulary_operator(expression), VerificationPredicateRefusal.UNPARSEABLE, route)
    operator = parsed.operator
    route_operators = _BLOCKING_PREDICATE_EVALUATORS if route is _BLOCKING_ROUTE else _ADVISORY_PREDICATE_EVALUATORS
    if operator not in route_operators:
        raise _predicate_refusal(operator, VerificationPredicateRefusal.OPERATOR_FAMILY, route)
    specification = VERIFICATION_PREDICATE_SPECIFICATIONS[operator]
    casilla_count = len(parsed.casilla_ids)
    if casilla_count < specification.minimum_casilla_ids or (
        specification.maximum_casilla_ids is not None and casilla_count > specification.maximum_casilla_ids
    ):
        raise _predicate_refusal(operator, VerificationPredicateRefusal.ARITY, route)
    casilla_ids = tuple(_predicate_casilla_ids(parsed))
    threshold: Decimal | None = None
    cutoff: _date | None = None
    if operator is VerificationPredicateOperator.ADVISORY_WHEN_RATIO_GE:
        threshold = _registry_threshold(parsed.threshold)
        if threshold is None:
            raise _predicate_refusal(operator, VerificationPredicateRefusal.LITERAL, route)
    elif operator is VerificationPredicateOperator.DEDUCCION_REQUIRES_ADQUISICION_BEFORE:
        cutoff = _parse_predicate_date(parsed.cutoff)
        if cutoff is None:
            raise _predicate_refusal(operator, VerificationPredicateRefusal.LITERAL, route)
    if operator in _LITERAL_OPERATORS and not parsed.literal:
        raise _predicate_refusal(operator, VerificationPredicateRefusal.LITERAL, route)
    if operator in _PROFILE_FLAG_OPERATORS and parsed.profile_field not in KNOWN_PROFILE_FLAG_ADVISORY_FIELDS:
        raise _predicate_refusal(operator, VerificationPredicateRefusal.LITERAL, route)
    return _AdmittedPredicate(parsed=parsed, casilla_ids=casilla_ids, threshold=threshold, cutoff=cutoff)


def required_advisory_predicate(expression: str) -> ParsedVerificationPredicate:
    """Return an ADVISORY predicate's parse, refusing a malformed one exactly as evaluation does."""
    return _required_parsed_predicate(expression, route=_ADVISORY_ROUTE).parsed


def _unique_predicate_casilla_id(
    predicate: VerificationPredicateDefinition,
    *,
    route: VerificationPredicateRoute,
) -> CasillaId | None:
    """Return the predicate's sole casilla, preserving cross-casilla findings at record grain."""
    casilla_ids = _required_parsed_predicate(predicate.expression, route=route).casilla_ids
    return casilla_ids[0] if len(casilla_ids) == 1 else None


def _parse_predicate_date(raw: str) -> _date | None:
    """Parse a date string, or ``None`` when absent/unparseable.

    Accepts the ISO form (the cutoff literal shape) and the Spanish day-first
    operator-entry forms ``DD/MM/YYYY`` and ``DD-MM-YYYY``, both resolved by the
    canonical :func:`core.parsing.dates.parse_date` contract rather than a local
    format list. Used by the ``deduccion_requires_adquisicion_before`` advisory
    to read the acquisition-date TEXT casilla and the cutoff literal.

    The canonical parser requires two-digit day and month components, so a
    partially-typed ``1/2/2024`` is no longer silently resolved to a date. That
    matters here specifically: the value decides a deduction's eligibility
    against a statutory cutoff, and an under-specified entry is a date the
    operator has not actually stated. For the operator-entered acquisition date
    it returns ``None`` like any other unparseable value, so the advisory treats
    it as "no eligibility signal" rather than acting on a guess; an unreadable
    registry cutoff is instead refused at predicate admission.
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
    ids: tuple[CasillaId, ...],
    casilla_values: Mapping[CasillaId, Decimal],
) -> bool:
    """Return whether a carry-forward closing balance reconciles to its roll-forward.

    ``ids`` is ``[closing, opening, applied, base]``, its arity fixed by
    predicate admission. The carry-forward stock continuity invariant is::

        closing == opening − applied + max(0, −base)

    the opening stock less the amount applied plus any stock newly generated
    this period. Holds within a one-cent tolerance to absorb per-detail
    rounding. A missing casilla reads as ``Decimal(0)`` via ``.get``.
    """
    closing_id, opening_id, applied_id, base_id = ids
    closing = casilla_values.get(closing_id, Decimal(0))
    opening = casilla_values.get(opening_id, Decimal(0))
    applied = casilla_values.get(applied_id, Decimal(0))
    base = casilla_values.get(base_id, Decimal(0))
    generated = max(Decimal(0), -base)
    expected = opening - applied + generated
    # Bounded at the cent quantum: absorbs the sub-cent drift a
    # total-of-per-year-detail figure accumulates, without masking a genuine
    # discontinuity, which is euros rather than cents.
    return abs(closing - expected) <= CENT


_NON_RESIDENT_IRNR_NON_EEA_FILTER = "non_resident_irnr_non_eea"
_IRNR_TAX_REGIME = "irnr"


def _evaluate_applicability_filter(filter_name: str, profile: TaxpayerProfile) -> bool:
    """Return whether the profile falls inside a predicate's named applicability filter.

    Each filter name a registry predicate may cite has one entry here; any other
    name is refused rather than silently treated as applicable or not.
    """
    if not filter_name:
        return True
    if filter_name == _NON_RESIDENT_IRNR_NON_EEA_FILTER:
        # TRLIRNR art. 10: a non-resident taxed under IRNR must appoint a fiscal
        # representative unless it resides in the EU/EEA.
        residency = profile.fiscal_residency
        if residency is None:
            return False
        tax_regime = resolve_fiscal_residency_catalogue().definition(residency).tax_regime
        return tax_regime == _IRNR_TAX_REGIME and not profile.ue_eee_status
    raise ModeloApplicabilityFilterError(f"Unknown applicability filter: {filter_name!r}")


_BlockingPredicateEvaluator = Callable[
    [_AdmittedPredicate, Mapping[CasillaId, Decimal], TaxpayerProfile, Mapping[CasillaId, str]],
    bool,
]


def _evaluate_all_nonzero(
    predicate: _AdmittedPredicate,
    casilla_values: Mapping[CasillaId, Decimal],
    _profile: TaxpayerProfile,
    _text_values: Mapping[CasillaId, str],
) -> bool:
    return all(casilla_values.get(cid, Decimal(0)) != Decimal(0) for cid in predicate.casilla_ids)


def _evaluate_any_nonzero(
    predicate: _AdmittedPredicate,
    casilla_values: Mapping[CasillaId, Decimal],
    _profile: TaxpayerProfile,
    _text_values: Mapping[CasillaId, str],
) -> bool:
    return any(casilla_values.get(cid, Decimal(0)) != Decimal(0) for cid in predicate.casilla_ids)


def _evaluate_at_most_one_positive(
    predicate: _AdmittedPredicate,
    casilla_values: Mapping[CasillaId, Decimal],
    _profile: TaxpayerProfile,
    _text_values: Mapping[CasillaId, str],
) -> bool:
    return sum(1 for cid in predicate.casilla_ids if casilla_values.get(cid, Decimal(0)) > Decimal(0)) <= 1


def _evaluate_cap_le_when_positive(
    predicate: _AdmittedPredicate,
    casilla_values: Mapping[CasillaId, Decimal],
    _profile: TaxpayerProfile,
    _text_values: Mapping[CasillaId, str],
) -> bool:
    limited_id, ceiling_id = predicate.casilla_ids
    ceiling = casilla_values.get(ceiling_id, Decimal(0))
    if ceiling <= Decimal(0):
        return True
    limited = casilla_values.get(limited_id, Decimal(0))
    return limited <= ceiling


def _evaluate_positive_application_le_present_stock(
    predicate: _AdmittedPredicate,
    casilla_values: Mapping[CasillaId, Decimal],
    _profile: TaxpayerProfile,
    _text_values: Mapping[CasillaId, str],
) -> bool:
    """Bound positive elective application to a present stock operand."""
    application_id, stock_id = predicate.casilla_ids
    application = casilla_values.get(application_id, Decimal(0))
    if application <= Decimal(0):
        return True
    if stock_id not in casilla_values:
        return False
    return application <= casilla_values[stock_id]


def _evaluate_equals(
    predicate: _AdmittedPredicate,
    casilla_values: Mapping[CasillaId, Decimal],
    _profile: TaxpayerProfile,
    _text_values: Mapping[CasillaId, str],
) -> bool:
    lhs, rhs = (casilla_values.get(cid, Decimal(0)) for cid in predicate.casilla_ids)
    return lhs == rhs


def _equals_sum_operands(
    predicate: _AdmittedPredicate,
    casilla_values: Mapping[CasillaId, Decimal],
) -> tuple[CasillaId, Decimal, Decimal]:
    """Return the total casilla, its value, and the sum of its addends.

    Admission guarantees a total and at least two addends; a missing casilla
    reads as ``Decimal(0)`` like every other operator.
    """
    total_id, *addend_ids = predicate.casilla_ids
    addend_sum = sum((casilla_values.get(cid, Decimal(0)) for cid in addend_ids), Decimal(0))
    return total_id, casilla_values.get(total_id, Decimal(0)), addend_sum


def _evaluate_equals_sum(
    predicate: _AdmittedPredicate,
    casilla_values: Mapping[CasillaId, Decimal],
    _profile: TaxpayerProfile,
    _text_values: Mapping[CasillaId, str],
) -> bool:
    _total_id, total, addend_sum = _equals_sum_operands(predicate, casilla_values)
    return total == addend_sum


def _evaluate_implies_nonzero(
    predicate: _AdmittedPredicate,
    casilla_values: Mapping[CasillaId, Decimal],
    _profile: TaxpayerProfile,
    _text_values: Mapping[CasillaId, str],
) -> bool:
    antecedent_id, consequent_id = predicate.casilla_ids
    antecedent = casilla_values.get(antecedent_id, Decimal(0))
    if antecedent <= Decimal(0):
        return True
    consequent = casilla_values.get(consequent_id, Decimal(0))
    return consequent != Decimal(0)


def _evaluate_implies_any_nonzero(
    predicate: _AdmittedPredicate,
    casilla_values: Mapping[CasillaId, Decimal],
    _profile: TaxpayerProfile,
    _text_values: Mapping[CasillaId, str],
) -> bool:
    antecedent_id, *consequent_ids = predicate.casilla_ids
    antecedent = casilla_values.get(antecedent_id, Decimal(0))
    if antecedent <= Decimal(0):
        return True
    return any(casilla_values.get(cid, Decimal(0)) != Decimal(0) for cid in consequent_ids)


def _evaluate_casilla_equals_implies_nonzero(
    predicate: _AdmittedPredicate,
    casilla_values: Mapping[CasillaId, Decimal],
    _profile: TaxpayerProfile,
    text_values: Mapping[CasillaId, str],
) -> bool:
    antecedent, consequent = predicate.casilla_ids
    if text_values.get(antecedent) != predicate.parsed.literal:
        return True
    return casilla_values.get(consequent, Decimal(0)) != 0


def _evaluate_casilla_equals_implies_zero(
    predicate: _AdmittedPredicate,
    casilla_values: Mapping[CasillaId, Decimal],
    _profile: TaxpayerProfile,
    text_values: Mapping[CasillaId, str],
) -> bool:
    antecedent, consequent = predicate.casilla_ids
    if text_values.get(antecedent) != predicate.parsed.literal:
        return True
    return consequent in casilla_values and casilla_values[consequent] == 0


def _evaluate_profile_field_required(
    predicate: _AdmittedPredicate,
    _casilla_values: Mapping[CasillaId, Decimal],
    profile: TaxpayerProfile,
    _text_values: Mapping[CasillaId, str],
) -> bool:
    if not _evaluate_applicability_filter(predicate.parsed.applicability_filter, profile):
        return True
    field_value = getattr(profile, predicate.parsed.profile_field, None)
    return not (field_value is None or (isinstance(field_value, str) and not field_value.strip()))


def _evaluate_roll_forward_balances(
    predicate: _AdmittedPredicate,
    casilla_values: Mapping[CasillaId, Decimal],
    _profile: TaxpayerProfile,
    _text_values: Mapping[CasillaId, str],
) -> bool:
    return _roll_forward_balance_reconciles(predicate.casilla_ids, casilla_values)


_BLOCKING_PREDICATE_EVALUATORS: Mapping[VerificationPredicateOperator, _BlockingPredicateEvaluator] = MappingProxyType(
    {
        VerificationPredicateOperator.ALL_NONZERO: _evaluate_all_nonzero,
        VerificationPredicateOperator.ANY_NONZERO: _evaluate_any_nonzero,
        VerificationPredicateOperator.AT_MOST_ONE_POSITIVE: _evaluate_at_most_one_positive,
        VerificationPredicateOperator.CAP_LE_WHEN_POSITIVE: _evaluate_cap_le_when_positive,
        VerificationPredicateOperator.POSITIVE_APPLICATION_LE_PRESENT_STOCK: (
            _evaluate_positive_application_le_present_stock
        ),
        VerificationPredicateOperator.CASILLA_EQUALS_IMPLIES_NONZERO: _evaluate_casilla_equals_implies_nonzero,
        VerificationPredicateOperator.CASILLA_EQUALS_IMPLIES_ZERO: _evaluate_casilla_equals_implies_zero,
        VerificationPredicateOperator.EQUALS: _evaluate_equals,
        VerificationPredicateOperator.EQUALS_SUM: _evaluate_equals_sum,
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
    text_values: Mapping[CasillaId, str] | None = None,
) -> bool:
    """Return True when the predicate holds, False when it is violated.

    Supports the blocking DSL operators registered in
    :data:`~domain.calculations.registry.schema_verification.KNOWN_VERIFICATION_PREDICATE_OPERATORS`:

    - ``all_nonzero(["id1", "id2", ...])`` — all ids must have a non-zero value.
    - ``any_nonzero(["id1", "id2", ...])`` — at least one id must have a non-zero value.
    - ``at_most_one_positive(["id1", "id2", ...])`` — no more than one named
      casilla may be strictly positive.
    - ``cap_le_when_positive(["limited_id", "ceiling_id"])`` — when the ceiling
      casilla is strictly positive, the limited casilla MUST NOT exceed it.
    - positive_application_le_present_stock(["application_id", "stock_id"]) —
      an omitted/non-positive elective application holds; a positive one
      requires a present stock value and must not exceed that value.
    - ``casilla_equals_implies_nonzero`` / ``casilla_equals_implies_zero`` —
      when the antecedent's operator-entered text equals the literal, the
      consequent must be non-zero, or present and zero.
    - ``equals(["lhs_id", "rhs_id"])`` — binary consistency invariant: predicate
      holds iff the two named casillas hold the same value.
    - ``equals_sum(["total_id", "addend_id", "addend_id", ...])`` — printed-total
      invariant: predicate holds iff the first casilla equals the exact sum of
      the rest.
    - ``implies_nonzero(["antecedent_id", "consequent_id"])`` — material
      implication with strictly-positive antecedent: predicate holds iff
      antecedent <= 0 OR consequent != 0.
    - ``implies_any_nonzero(["antecedent_id", "c1_id", ...])`` — N-consequent
      generalisation: predicate holds iff antecedent <= 0 OR at least one
      listed consequent != 0.
    - ``profile_field_required("field_name", "applicability_filter")`` —
      profile-state-aware conditional non-zero requirement; sibling of
      ``implies_nonzero``.
    - ``roll_forward_balances([closing, opening, applied, base])`` — the
      carry-forward closing balance reconciles to its roll-forward.

    An unparseable expression, an operator with no blocking evaluator, a
    casilla count outside the operator's specification or an unreadable
    comparison literal raises :class:`ModeloVerificationPredicateMalformedError`,
    and a non-canonical casilla token :class:`ModeloError`, before any
    evaluation, on every call. A malformed registry predicate never reads as
    holding.

    Core types:
    :class:`~cadrumo.domain.deadlines.models.TaxpayerProfile`.
    """
    predicate = _required_parsed_predicate(expression, route=_BLOCKING_ROUTE)
    evaluator = _BLOCKING_PREDICATE_EVALUATORS[predicate.parsed.operator]
    return evaluator(predicate, casilla_values, profile, MappingProxyType({}) if text_values is None else text_values)


_AdvisoryPredicateEvaluator = Callable[
    [_AdmittedPredicate, Mapping[CasillaId, Decimal], Mapping[CasillaId, str], TaxpayerProfile | None],
    bool,
]


def _advisory_ratio_ge_fires(
    predicate: _AdmittedPredicate,
    casilla_values: Mapping[CasillaId, Decimal],
    _text_values: Mapping[CasillaId, str],
    _profile: TaxpayerProfile | None,
) -> bool:
    num_id, den_id = predicate.casilla_ids
    threshold = predicate.threshold
    if threshold is None:
        raise AssertionError("admission reads every ratio threshold")
    den = casilla_values.get(den_id, Decimal(0))
    if den <= Decimal(0):
        return False
    return (casilla_values.get(num_id, Decimal(0)) / den) >= threshold


def _advisory_profile_flag_fires(
    predicate: _AdmittedPredicate,
    _casilla_values: Mapping[CasillaId, Decimal],
    _text_values: Mapping[CasillaId, str],
    profile: TaxpayerProfile | None,
) -> bool:
    if profile is None:
        return False
    return bool(getattr(profile, predicate.parsed.profile_field, False))


def _advisory_positive_fires(
    predicate: _AdmittedPredicate,
    casilla_values: Mapping[CasillaId, Decimal],
    _text_values: Mapping[CasillaId, str],
    _profile: TaxpayerProfile | None,
) -> bool:
    (casilla_id,) = predicate.casilla_ids
    return casilla_values.get(casilla_id, Decimal(0)) > Decimal(0)


def _advisory_at_most_one_positive_fires(
    predicate: _AdmittedPredicate,
    casilla_values: Mapping[CasillaId, Decimal],
    _text_values: Mapping[CasillaId, str],
    _profile: TaxpayerProfile | None,
) -> bool:
    return sum(1 for cid in predicate.casilla_ids if casilla_values.get(cid, Decimal(0)) > Decimal(0)) > 1


def _advisory_implies_nonzero_fires(
    predicate: _AdmittedPredicate,
    casilla_values: Mapping[CasillaId, Decimal],
    _text_values: Mapping[CasillaId, str],
    _profile: TaxpayerProfile | None,
) -> bool:
    antecedent_id, consequent_id = predicate.casilla_ids
    antecedent = casilla_values.get(antecedent_id, Decimal(0))
    consequent = casilla_values.get(consequent_id, Decimal(0))
    return antecedent > Decimal(0) and consequent == Decimal(0)


def _advisory_implies_any_nonzero_fires(
    predicate: _AdmittedPredicate,
    casilla_values: Mapping[CasillaId, Decimal],
    _text_values: Mapping[CasillaId, str],
    _profile: TaxpayerProfile | None,
) -> bool:
    antecedent_id, *consequent_ids = predicate.casilla_ids
    antecedent = casilla_values.get(antecedent_id, Decimal(0))
    if antecedent <= Decimal(0):
        return False
    return all(casilla_values.get(cid, Decimal(0)) == Decimal(0) for cid in consequent_ids)


def _advisory_roll_forward_balances_fires(
    predicate: _AdmittedPredicate,
    casilla_values: Mapping[CasillaId, Decimal],
    _text_values: Mapping[CasillaId, str],
    _profile: TaxpayerProfile | None,
) -> bool:
    return not _roll_forward_balance_reconciles(predicate.casilla_ids, casilla_values)


def _advisory_equals_fires(
    predicate: _AdmittedPredicate,
    casilla_values: Mapping[CasillaId, Decimal],
    _text_values: Mapping[CasillaId, str],
    _profile: TaxpayerProfile | None,
) -> bool:
    lhs, rhs = (casilla_values.get(cid, Decimal(0)) for cid in predicate.casilla_ids)
    return lhs != rhs


def _advisory_equals_sum_fires(
    predicate: _AdmittedPredicate,
    casilla_values: Mapping[CasillaId, Decimal],
    _text_values: Mapping[CasillaId, str],
    _profile: TaxpayerProfile | None,
) -> bool:
    _total_id, total, addend_sum = _equals_sum_operands(predicate, casilla_values)
    return total != addend_sum


def _advisory_casilla_equals_implies_nonzero_fires(
    predicate: _AdmittedPredicate,
    casilla_values: Mapping[CasillaId, Decimal],
    text_values: Mapping[CasillaId, str],
    _profile: TaxpayerProfile | None,
) -> bool:
    antecedent_id, consequent_id = predicate.casilla_ids
    if text_values.get(antecedent_id) != predicate.parsed.literal:
        return False
    return casilla_values.get(consequent_id, Decimal(0)) == Decimal(0)


def _advisory_casilla_equals_implies_zero_fires(
    predicate: _AdmittedPredicate,
    casilla_values: Mapping[CasillaId, Decimal],
    text_values: Mapping[CasillaId, str],
    _profile: TaxpayerProfile | None,
) -> bool:
    antecedent, consequent = predicate.casilla_ids
    return text_values.get(antecedent) == predicate.parsed.literal and (
        consequent not in casilla_values or casilla_values[consequent] != 0
    )


def _advisory_casilla_equals_implies_profile_flag_fires(
    predicate: _AdmittedPredicate,
    _casilla_values: Mapping[CasillaId, Decimal],
    text_values: Mapping[CasillaId, str],
    profile: TaxpayerProfile | None,
) -> bool:
    (antecedent_id,) = predicate.casilla_ids
    if text_values.get(antecedent_id) != predicate.parsed.literal:
        return False
    if profile is None:
        return False
    return not bool(getattr(profile, predicate.parsed.profile_field, False))


def _advisory_casilla_equals_implies_diverges_fires(
    predicate: _AdmittedPredicate,
    casilla_values: Mapping[CasillaId, Decimal],
    text_values: Mapping[CasillaId, str],
    _profile: TaxpayerProfile | None,
) -> bool:
    antecedent_id, casilla_a_id, casilla_b_id = predicate.casilla_ids
    if text_values.get(antecedent_id) != predicate.parsed.literal:
        return False
    casilla_a = casilla_values.get(casilla_a_id, Decimal(0))
    casilla_b = casilla_values.get(casilla_b_id, Decimal(0))
    return abs(casilla_a - casilla_b) > Decimal("0.01")


def _advisory_deduccion_requires_adquisicion_before_fires(
    predicate: _AdmittedPredicate,
    casilla_values: Mapping[CasillaId, Decimal],
    text_values: Mapping[CasillaId, str],
    _profile: TaxpayerProfile | None,
) -> bool:
    amount_id, acquisition_date_id, construction_date_id = predicate.casilla_ids
    cutoff = predicate.cutoff
    if cutoff is None:
        raise AssertionError("admission reads every deduction cutoff")
    if casilla_values.get(amount_id, Decimal(0)) <= Decimal(0):
        return False
    acquisition_date = _parse_predicate_date(text_values.get(acquisition_date_id, ""))
    eligible_by_acquisition = acquisition_date is not None and acquisition_date < cutoff
    eligible_by_construction = bool(text_values.get(construction_date_id, "").strip())
    return not (eligible_by_acquisition or eligible_by_construction)


def _advisory_computed_diverges_fires(
    predicate: _AdmittedPredicate,
    casilla_values: Mapping[CasillaId, Decimal],
    _text_values: Mapping[CasillaId, str],
    _profile: TaxpayerProfile | None,
) -> bool:
    declared_id, computed_id = predicate.casilla_ids
    computed = casilla_values.get(computed_id, Decimal(0))
    if computed <= Decimal(0):
        return False
    declared = casilla_values.get(declared_id, Decimal(0))
    return abs(declared - computed) > Decimal("0.01")


_ADVISORY_PREDICATE_EVALUATORS: Mapping[VerificationPredicateOperator, _AdvisoryPredicateEvaluator] = MappingProxyType(
    {
        VerificationPredicateOperator.ADVISORY_WHEN_RATIO_GE: _advisory_ratio_ge_fires,
        VerificationPredicateOperator.PROFILE_FLAG_ENABLED: _advisory_profile_flag_fires,
        VerificationPredicateOperator.ADVISORY_WHEN_POSITIVE: _advisory_positive_fires,
        VerificationPredicateOperator.AT_MOST_ONE_POSITIVE: _advisory_at_most_one_positive_fires,
        VerificationPredicateOperator.IMPLIES_NONZERO: _advisory_implies_nonzero_fires,
        VerificationPredicateOperator.IMPLIES_ANY_NONZERO: _advisory_implies_any_nonzero_fires,
        VerificationPredicateOperator.ROLL_FORWARD_BALANCES: _advisory_roll_forward_balances_fires,
        VerificationPredicateOperator.EQUALS: _advisory_equals_fires,
        VerificationPredicateOperator.EQUALS_SUM: _advisory_equals_sum_fires,
        VerificationPredicateOperator.CASILLA_EQUALS_IMPLIES_NONZERO: _advisory_casilla_equals_implies_nonzero_fires,
        VerificationPredicateOperator.CASILLA_EQUALS_IMPLIES_ZERO: _advisory_casilla_equals_implies_zero_fires,
        VerificationPredicateOperator.CASILLA_EQUALS_IMPLIES_PROFILE_FLAG: (
            _advisory_casilla_equals_implies_profile_flag_fires
        ),
        VerificationPredicateOperator.CASILLA_EQUALS_IMPLIES_DIVERGES: _advisory_casilla_equals_implies_diverges_fires,
        VerificationPredicateOperator.DEDUCCION_REQUIRES_ADQUISICION_BEFORE: (
            _advisory_deduccion_requires_adquisicion_before_fires
        ),
        VerificationPredicateOperator.ADVISORY_WHEN_COMPUTED_DIVERGES: _advisory_computed_diverges_fires,
    }
)

BLOCKING_PREDICATE_OPERATORS: frozenset[VerificationPredicateOperator] = frozenset(_BLOCKING_PREDICATE_EVALUATORS)
ADVISORY_PREDICATE_OPERATORS: frozenset[VerificationPredicateOperator] = frozenset(_ADVISORY_PREDICATE_EVALUATORS)


def evaluate_advisory_predicate_fires(
    expression: str,
    casilla_values: Mapping[CasillaId, Decimal],
    text_values: Mapping[CasillaId, str] = MappingProxyType({}),
    profile: TaxpayerProfile | None = None,
) -> bool:
    """Return True when a registered ADVISORY predicate condition fires.

    An unparseable expression, an operator with no advisory evaluator, a
    casilla count outside the operator's specification, or an unreadable
    registry-authored literal (ratio threshold, deduction cutoff, comparison
    literal, profile-flag field) raises
    :class:`ModeloVerificationPredicateMalformedError`, and a non-canonical
    casilla token :class:`ModeloError`, before any evaluation, on every call. A
    malformed registry predicate never reads as not firing. Unreadable
    operator-entered values remain taxpayer input and follow each operator's
    own reading.

    Core types:
    :class:`~cadrumo.domain.deadlines.models.TaxpayerProfile`.
    """
    predicate = _required_parsed_predicate(expression, route=_ADVISORY_ROUTE)
    evaluator = _ADVISORY_PREDICATE_EVALUATORS[predicate.parsed.operator]
    return evaluator(predicate, casilla_values, text_values, profile)


#: Suffixes of the two suffered-retencion advisory predicates. Their remedy is
#: to enter the payer's certificate value, which the generic message cannot
#: name, so each resolves to its own locale key.
_TRABAJO_RETENCION_ADVISORY_SUFFIX = "retenciones-trabajo-declaradas-cuando-ingresos-integros-trabajo-positivos"
_CAPITAL_MOBILIARIO_RETENCION_ADVISORY_SUFFIX = (
    "retenciones-capital-mobiliario-declaradas-cuando-ingresos-integros-positivos"
)


def _advisory_predicate_finding(predicate: VerificationPredicateDefinition) -> ModeloVerificationFinding:
    """Build the warning for a registry-authored advisory predicate.

    Each constructor carries its ``message_locale_key`` as a literal, so the
    two suffered-retencion families dispatch to their own call sites.
    """
    legal_refs = tuple(predicate.legal_refs)
    message_facts = {"predicate_id": predicate.predicate_id}
    casilla_id = _unique_predicate_casilla_id(predicate, route=_ADVISORY_ROUTE)
    if predicate.predicate_id.endswith(_TRABAJO_RETENCION_ADVISORY_SUFFIX):
        return ModeloVerificationFinding(
            kind=ModeloVerificationFindingKind.ADVISORY,
            severity=ModeloVerificationFindingSeverity.WARNING,
            casilla_id=casilla_id,
            message_locale_key="application.modelo.findings.suffered_retencion_trabajo_uncredited",
            message_facts=message_facts,
            legal_refs=legal_refs,
        )
    if predicate.predicate_id.endswith(_CAPITAL_MOBILIARIO_RETENCION_ADVISORY_SUFFIX):
        return ModeloVerificationFinding(
            kind=ModeloVerificationFindingKind.ADVISORY,
            severity=ModeloVerificationFindingSeverity.WARNING,
            casilla_id=casilla_id,
            message_locale_key="application.modelo.findings.suffered_retencion_capital_mobiliario_uncredited",
            message_facts=message_facts,
            legal_refs=legal_refs,
        )
    return ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.ADVISORY,
        severity=ModeloVerificationFindingSeverity.WARNING,
        casilla_id=casilla_id,
        message_locale_key="application.modelo.findings.registry_advisory_predicate_fired",
        message_facts=message_facts,
        legal_refs=legal_refs,
    )


def _blocking_predicate_finding(
    predicate: VerificationPredicateDefinition,
    casilla_values: Mapping[CasillaId, Decimal],
) -> ModeloVerificationFinding:
    """Build the refusal for a violated registry-authored blocking predicate.

    A violated ``equals_sum`` names its total box and the sum of the boxes the
    design adds into it, so the filer can see the two figures that disagree.
    A categorical requirement names the missing field with a human message;
    other operators retain their predicate identity.
    """
    legal_refs = tuple(predicate.legal_refs)
    admitted = _required_parsed_predicate(predicate.expression, route=_BLOCKING_ROUTE)
    operator = admitted.parsed.operator
    if operator in (
        VerificationPredicateOperator.CASILLA_EQUALS_IMPLIES_NONZERO,
        VerificationPredicateOperator.CASILLA_EQUALS_IMPLIES_ZERO,
    ):
        return ModeloVerificationFinding(
            kind=ModeloVerificationFindingKind.BLOCKING_RULE,
            severity=ModeloVerificationFindingSeverity.BLOCKING,
            casilla_id=admitted.casilla_ids[1],
            message_locale_key=(
                "application.modelo.findings.selected_option_requires_zero"
                if operator is VerificationPredicateOperator.CASILLA_EQUALS_IMPLIES_ZERO
                else "application.modelo.findings.selected_option_requires_nonzero"
            ),
            message_facts={},
            legal_refs=legal_refs,
        )
    if operator is VerificationPredicateOperator.EQUALS_SUM:
        total_id, _total, addend_sum = _equals_sum_operands(admitted, casilla_values)
        return ModeloVerificationFinding(
            kind=ModeloVerificationFindingKind.BLOCKING_RULE,
            severity=ModeloVerificationFindingSeverity.BLOCKING,
            casilla_id=total_id,
            message_locale_key="application.modelo.findings.printed_total_mismatch",
            message_facts={
                "predicate_id": predicate.predicate_id,
                "box": total_id,
                "printed_sum": addend_sum,
            },
            legal_refs=legal_refs,
        )
    return ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.BLOCKING_RULE,
        severity=ModeloVerificationFindingSeverity.BLOCKING,
        casilla_id=admitted.casilla_ids[0] if len(admitted.casilla_ids) == 1 else None,
        message_locale_key="application.modelo.findings.cross_casilla_invariant_violated",
        message_facts={"predicate_id": predicate.predicate_id},
        legal_refs=legal_refs,
    )


def _selected_revision_verification_predicates(
    *,
    modelo: str,
    filing_year: int,
    period: str,
    query_service: RegistryQueryService | None = None,
    operation: PinnedAuthorityOperation | None = None,
    as_of: _date | None = None,
) -> tuple[VerificationPredicateDefinition, ...]:
    """Read predicate instances from the revision selected by registry query."""
    if operation is None:
        from ...domain.calculations.registry.authority import bundled_indexed_authority

        with bundled_indexed_authority().operation() as indexed_operation:
            return _selected_revision_verification_predicates(
                modelo=modelo,
                filing_year=filing_year,
                period=period,
                query_service=query_service,
                operation=indexed_operation,
                as_of=as_of,
            )
    if query_service is not None:
        revision = query_service.resolve_revision_for_scope(
            modelo,
            filing_year=filing_year,
            period=period,
            as_of=as_of,
        ).revision
    else:
        revision = operation.revision_for_context(
            modelo,
            filing_year=filing_year,
            period=period,
            on=as_of,
        )
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
    operation: PinnedAuthorityOperation | None = None,
    as_of: _date | None = None,
) -> list[ModeloVerificationFinding]:
    """Evaluate Layer 2 cross-casilla predicates into verification findings.

    ``predicates`` are
    :class:`~domain.calculations.registry.schema_verification.VerificationPredicateDefinition`
    entries from the selected registry snapshot. The returned records are
    :class:`~ModeloVerificationFinding` values.

    ``text_values`` carries operator-entered raw strings (e.g.
    :attr:`~CalculationRevision.input_values_by_casilla_id`),
    independent of the Decimal ``casilla_values`` projection. It defaults to an
    empty mapping and is consumed by text-aware advisory operators and the
    categorical nonzero blocking rule.

    ``BLOCKING_RULE`` predicates use negative logic: the predicate expression must
    hold, and a violation emits a BLOCKING finding. ``ADVISORY`` predicates use
    affirmative logic: when their condition fires, the operator receives a
    WARNING-severity ADVISORY finding and the verified-complete grant remains
    possible if no blocking findings exist.

    ``profile`` is a :class:`~domain.deadlines.models.TaxpayerProfile` threaded
    through to support profile-state-aware predicate operators such as
    ``profile_field_required`` and ``profile_flag_enabled``. Casilla-only
    operators ignore the parameter.

    See Also:
        :func:`evaluate_predicate_expression`:
            Evaluates the blocking-rule predicate DSL.
        :func:`evaluate_advisory_predicate_fires`:
            Evaluates the advisory predicate DSL.
        :func:`~cadrumo.application.modelo.verification_report_facts.classify_verification_outcome`:
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
            operation=operation,
            as_of=as_of,
        )

    if not predicates:
        return []

    return _evaluate_selected_predicate_findings(
        predicates, casilla_values, profile, text_values, blocking_finding_observer
    )


def _evaluate_selected_predicate_findings(
    predicates: tuple[VerificationPredicateDefinition, ...],
    casilla_values: Mapping[CasillaId, Decimal],
    profile: TaxpayerProfile,
    text_values: Mapping[CasillaId, str],
    blocking_finding_observer: Callable[[ModeloVerificationFinding, VerificationPredicateDefinition], None] | None,
) -> list[ModeloVerificationFinding]:
    """Preserve registry predicate order and notify only after a blocking finding."""
    findings: list[ModeloVerificationFinding] = []
    for predicate in predicates:
        if predicate.finding_kind == "ADVISORY":
            # ADVISORY predicates fire a WARNING finding when their condition IS met
            # (affirmative logic — opposite of BLOCKING_RULE predicates).
            if evaluate_advisory_predicate_fires(predicate.expression, casilla_values, text_values, profile):
                findings.append(_advisory_predicate_finding(predicate))
        else:
            if not evaluate_predicate_expression(predicate.expression, casilla_values, profile, text_values):
                finding = _blocking_predicate_finding(predicate, casilla_values)
                findings.append(finding)
                if blocking_finding_observer is not None:
                    blocking_finding_observer(finding, predicate)
    return findings
