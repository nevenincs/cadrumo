"""Advisory registry predicate evaluators: each says whether its warning fires."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import date as _date
from decimal import Decimal
from types import MappingProxyType

from ...core.casilla_id import CasillaId
from ...domain.calculations.registry.schema_verification import VerificationPredicateOperator
from ...domain.deadlines.models import TaxpayerProfile
from .verification_predicate_operands import (
    AdmittedPredicate,
    equals_sum_operands,
    parse_predicate_date,
    profile_flag,
    roll_forward_balance_reconciles,
)

AdvisoryPredicateEvaluator = Callable[
    [
        AdmittedPredicate,
        Mapping[CasillaId, Decimal],
        Mapping[CasillaId, str],
        TaxpayerProfile | None,
        _date | None,
    ],
    bool,
]


def _advisory_ratio_ge_fires(
    predicate: AdmittedPredicate,
    casilla_values: Mapping[CasillaId, Decimal],
    _text_values: Mapping[CasillaId, str],
    _profile: TaxpayerProfile | None,
    _fact_date: _date | None,
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
    predicate: AdmittedPredicate,
    _casilla_values: Mapping[CasillaId, Decimal],
    _text_values: Mapping[CasillaId, str],
    profile: TaxpayerProfile | None,
    fact_date: _date | None,
) -> bool:
    if profile is None:
        return False
    return profile_flag(profile, predicate.parsed.profile_field, fact_date)


def _advisory_positive_fires(
    predicate: AdmittedPredicate,
    casilla_values: Mapping[CasillaId, Decimal],
    _text_values: Mapping[CasillaId, str],
    _profile: TaxpayerProfile | None,
    _fact_date: _date | None,
) -> bool:
    (casilla_id,) = predicate.casilla_ids
    return casilla_values.get(casilla_id, Decimal(0)) > Decimal(0)


def _advisory_at_most_one_positive_fires(
    predicate: AdmittedPredicate,
    casilla_values: Mapping[CasillaId, Decimal],
    _text_values: Mapping[CasillaId, str],
    _profile: TaxpayerProfile | None,
    _fact_date: _date | None,
) -> bool:
    return sum(1 for cid in predicate.casilla_ids if casilla_values.get(cid, Decimal(0)) > Decimal(0)) > 1


def _advisory_implies_nonzero_fires(
    predicate: AdmittedPredicate,
    casilla_values: Mapping[CasillaId, Decimal],
    _text_values: Mapping[CasillaId, str],
    _profile: TaxpayerProfile | None,
    _fact_date: _date | None,
) -> bool:
    antecedent_id, consequent_id = predicate.casilla_ids
    antecedent = casilla_values.get(antecedent_id, Decimal(0))
    consequent = casilla_values.get(consequent_id, Decimal(0))
    return antecedent > Decimal(0) and consequent == Decimal(0)


def _advisory_implies_any_nonzero_fires(
    predicate: AdmittedPredicate,
    casilla_values: Mapping[CasillaId, Decimal],
    _text_values: Mapping[CasillaId, str],
    _profile: TaxpayerProfile | None,
    _fact_date: _date | None,
) -> bool:
    antecedent_id, *consequent_ids = predicate.casilla_ids
    antecedent = casilla_values.get(antecedent_id, Decimal(0))
    if antecedent <= Decimal(0):
        return False
    return all(casilla_values.get(cid, Decimal(0)) == Decimal(0) for cid in consequent_ids)


def _advisory_roll_forward_balances_fires(
    predicate: AdmittedPredicate,
    casilla_values: Mapping[CasillaId, Decimal],
    _text_values: Mapping[CasillaId, str],
    _profile: TaxpayerProfile | None,
    _fact_date: _date | None,
) -> bool:
    return not roll_forward_balance_reconciles(predicate.casilla_ids, casilla_values)


def _advisory_equals_fires(
    predicate: AdmittedPredicate,
    casilla_values: Mapping[CasillaId, Decimal],
    _text_values: Mapping[CasillaId, str],
    _profile: TaxpayerProfile | None,
    _fact_date: _date | None,
) -> bool:
    lhs, rhs = (casilla_values.get(cid, Decimal(0)) for cid in predicate.casilla_ids)
    return lhs != rhs


def _advisory_equals_sum_fires(
    predicate: AdmittedPredicate,
    casilla_values: Mapping[CasillaId, Decimal],
    _text_values: Mapping[CasillaId, str],
    _profile: TaxpayerProfile | None,
    _fact_date: _date | None,
) -> bool:
    _total_id, total, addend_sum = equals_sum_operands(predicate, casilla_values)
    return total != addend_sum


def _advisory_casilla_equals_implies_nonzero_fires(
    predicate: AdmittedPredicate,
    casilla_values: Mapping[CasillaId, Decimal],
    text_values: Mapping[CasillaId, str],
    _profile: TaxpayerProfile | None,
    _fact_date: _date | None,
) -> bool:
    antecedent_id, consequent_id = predicate.casilla_ids
    if text_values.get(antecedent_id) != predicate.parsed.literal:
        return False
    return casilla_values.get(consequent_id, Decimal(0)) == Decimal(0)


def _advisory_casilla_equals_implies_zero_fires(
    predicate: AdmittedPredicate,
    casilla_values: Mapping[CasillaId, Decimal],
    text_values: Mapping[CasillaId, str],
    _profile: TaxpayerProfile | None,
    _fact_date: _date | None,
) -> bool:
    antecedent, consequent = predicate.casilla_ids
    return text_values.get(antecedent) == predicate.parsed.literal and (
        consequent not in casilla_values or casilla_values[consequent] != 0
    )


def _advisory_casilla_equals_implies_profile_flag_fires(
    predicate: AdmittedPredicate,
    _casilla_values: Mapping[CasillaId, Decimal],
    text_values: Mapping[CasillaId, str],
    profile: TaxpayerProfile | None,
    fact_date: _date | None,
) -> bool:
    (antecedent_id,) = predicate.casilla_ids
    if text_values.get(antecedent_id) != predicate.parsed.literal:
        return False
    if profile is None:
        return False
    return not profile_flag(profile, predicate.parsed.profile_field, fact_date)


def _advisory_casilla_equals_implies_diverges_fires(
    predicate: AdmittedPredicate,
    casilla_values: Mapping[CasillaId, Decimal],
    text_values: Mapping[CasillaId, str],
    _profile: TaxpayerProfile | None,
    _fact_date: _date | None,
) -> bool:
    antecedent_id, casilla_a_id, casilla_b_id = predicate.casilla_ids
    if text_values.get(antecedent_id) != predicate.parsed.literal:
        return False
    casilla_a = casilla_values.get(casilla_a_id, Decimal(0))
    casilla_b = casilla_values.get(casilla_b_id, Decimal(0))
    return abs(casilla_a - casilla_b) > Decimal("0.01")


def _advisory_deduccion_requires_adquisicion_before_fires(
    predicate: AdmittedPredicate,
    casilla_values: Mapping[CasillaId, Decimal],
    text_values: Mapping[CasillaId, str],
    _profile: TaxpayerProfile | None,
    _fact_date: _date | None,
) -> bool:
    amount_id, acquisition_date_id, construction_date_id = predicate.casilla_ids
    cutoff = predicate.cutoff
    if cutoff is None:
        raise AssertionError("admission reads every deduction cutoff")
    if casilla_values.get(amount_id, Decimal(0)) <= Decimal(0):
        return False
    acquisition_date = parse_predicate_date(text_values.get(acquisition_date_id, ""))
    eligible_by_acquisition = acquisition_date is not None and acquisition_date < cutoff
    eligible_by_construction = bool(text_values.get(construction_date_id, "").strip())
    return not (eligible_by_acquisition or eligible_by_construction)


def _advisory_computed_diverges_fires(
    predicate: AdmittedPredicate,
    casilla_values: Mapping[CasillaId, Decimal],
    _text_values: Mapping[CasillaId, str],
    _profile: TaxpayerProfile | None,
    _fact_date: _date | None,
) -> bool:
    declared_id, computed_id = predicate.casilla_ids
    computed = casilla_values.get(computed_id, Decimal(0))
    if computed <= Decimal(0):
        return False
    declared = casilla_values.get(declared_id, Decimal(0))
    return abs(declared - computed) > Decimal("0.01")


ADVISORY_PREDICATE_EVALUATORS: Mapping[VerificationPredicateOperator, AdvisoryPredicateEvaluator] = MappingProxyType(
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
