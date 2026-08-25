"""Authoring-time semantic validators for verification-predicate expressions.

The typed syntax parser and every operator grammar live in
:mod:`._schema_verification`. This module applies revision-specific reference,
scalar-family, and literal checks to its parsed captures.
"""

from __future__ import annotations

from collections.abc import Mapping

from ....core import CasillaId
from ....core.decimal import try_parse_canonical_decimal
from .schema_scalars import registry_scalar_value_type
from .schema_surfaces import CasillaDefinition
from .schema_verification import (
    KNOWN_PROFILE_FLAG_ADVISORY_FIELDS,
    VERIFICATION_PREDICATE_SPECIFICATIONS,
    ParsedVerificationPredicate,
    VerificationPredicateOperator,
    VerificationPredicateSyntax,
    parse_verification_predicate_expression,
)

__all__ = [
    "_CASILLA_LIST_OPERATORS",
    "_advisory_when_ratio_ge_predicate_failures",
    "_casilla_equals_implies_diverges_predicate_failures",
    "_casilla_equals_implies_nonzero_predicate_failures",
    "_casilla_equals_implies_profile_flag_predicate_failures",
    "_casilla_list_predicate_failures",
    "_deduccion_requires_adquisicion_before_predicate_failures",
    "_profile_field_required_predicate_failures",
    "_profile_flag_enabled_predicate_failures",
]


_CASILLA_LIST_OPERATORS = frozenset(
    specification.operator.value
    for specification in VERIFICATION_PREDICATE_SPECIFICATIONS.values()
    if specification.syntax is VerificationPredicateSyntax.CASILLA_LIST
)


def _parsed_expression(
    expression: str,
    operator: VerificationPredicateOperator,
) -> ParsedVerificationPredicate | None:
    parsed = parse_verification_predicate_expression(expression)
    return parsed if parsed is not None and parsed.operator is operator else None


def _malformed_expression_failure(
    prefix: str,
    owner: str,
    expression: str,
    operator: VerificationPredicateOperator,
) -> str:
    return f"{prefix}: {owner} {operator.value} expression {expression!r} is malformed"


def _casilla_list_predicate_failures(
    prefix: str,
    owner: str,
    expression: str,
    *,
    operator_name: str,
    casillas: set[CasillaId],
) -> list[str]:
    operator = VerificationPredicateOperator(operator_name)
    parsed = _parsed_expression(expression, operator)
    if parsed is None:
        return [
            f"{_malformed_expression_failure(prefix, owner, expression, operator)}; expected "
            f'{operator.value}(["casilla_id", ...])',
        ]
    specification = VERIFICATION_PREDICATE_SPECIFICATIONS[operator]
    ids = parsed.casilla_ids
    failures: list[str] = []
    if specification.maximum_casilla_ids is None and len(ids) < specification.minimum_casilla_ids:
        failures.append(
            f"{prefix}: {owner} {operator.value} expression must name at least "
            f"{specification.minimum_casilla_ids} casilla ids, got {len(ids)}: {list(ids)!r}",
        )
    if specification.maximum_casilla_ids is not None and len(ids) != specification.maximum_casilla_ids:
        expected_arity = (
            "four"
            if operator is VerificationPredicateOperator.ROLL_FORWARD_BALANCES
            else str(specification.maximum_casilla_ids)
        )
        failures.append(
            f"{prefix}: {owner} {operator.value} expression must name exactly "
            f"{expected_arity} casilla ids, got {len(ids)}: {list(ids)!r}",
        )
    for casilla_id in ids:
        if casilla_id not in casillas:
            failures.append(f"{prefix}: {owner} {operator.value} references unknown casilla {casilla_id!r}")
    return failures


def _casilla_equals_implies_nonzero_predicate_failures(
    prefix: str,
    owner: str,
    expression: str,
    casillas: set[CasillaId],
    casilla_by_id: Mapping[CasillaId, CasillaDefinition],
) -> list[str]:
    operator = VerificationPredicateOperator.CASILLA_EQUALS_IMPLIES_NONZERO
    parsed = _parsed_expression(expression, operator)
    if parsed is None:
        return [
            f"{_malformed_expression_failure(prefix, owner, expression, operator)}; expected "
            'casilla_equals_implies_nonzero(["antecedent_casilla_id", "literal", "consequent_casilla_id"])',
        ]
    if len(parsed.arguments) != 3:
        return [
            f"{prefix}: {owner} {operator.value} must name exactly three tokens "
            f"(antecedent casilla id, literal, consequent casilla id), got {len(parsed.arguments)}: "
            f"{list(parsed.arguments)!r}",
        ]
    antecedent_id, consequent_id = parsed.casilla_ids
    failures = _text_antecedent_failures(prefix, owner, operator, antecedent_id, casillas, casilla_by_id)
    if not parsed.literal:
        failures.append(f"{prefix}: {owner} {operator.value} literal must be non-empty")
    failures.extend(
        _numeric_casilla_failures(prefix, owner, operator, "consequent", consequent_id, casillas, casilla_by_id),
    )
    return failures


def _casilla_equals_implies_profile_flag_predicate_failures(
    prefix: str,
    owner: str,
    expression: str,
    casillas: set[CasillaId],
    casilla_by_id: Mapping[CasillaId, CasillaDefinition],
) -> list[str]:
    operator = VerificationPredicateOperator.CASILLA_EQUALS_IMPLIES_PROFILE_FLAG
    parsed = _parsed_expression(expression, operator)
    if parsed is None:
        return [
            f"{_malformed_expression_failure(prefix, owner, expression, operator)}; expected "
            'casilla_equals_implies_profile_flag(["antecedent_casilla_id", "literal", "profile_field"])',
        ]
    if len(parsed.arguments) != 3:
        return [
            f"{prefix}: {owner} {operator.value} must name exactly three tokens "
            f"(antecedent casilla id, literal, profile field), got {len(parsed.arguments)}: {list(parsed.arguments)!r}",
        ]
    antecedent_id = parsed.casilla_ids[0]
    failures = _text_antecedent_failures(prefix, owner, operator, antecedent_id, casillas, casilla_by_id)
    if not parsed.literal:
        failures.append(f"{prefix}: {owner} {operator.value} literal must be non-empty")
    if parsed.profile_field not in KNOWN_PROFILE_FLAG_ADVISORY_FIELDS:
        failures.append(
            f"{prefix}: {owner} {operator.value} references unsupported profile field {parsed.profile_field!r}; "
            f"supported fields: {sorted(KNOWN_PROFILE_FLAG_ADVISORY_FIELDS)!r}",
        )
    return failures


def _casilla_equals_implies_diverges_predicate_failures(
    prefix: str,
    owner: str,
    expression: str,
    casillas: set[CasillaId],
    casilla_by_id: Mapping[CasillaId, CasillaDefinition],
) -> list[str]:
    operator = VerificationPredicateOperator.CASILLA_EQUALS_IMPLIES_DIVERGES
    parsed = _parsed_expression(expression, operator)
    if parsed is None:
        return [
            f"{_malformed_expression_failure(prefix, owner, expression, operator)}; expected "
            'casilla_equals_implies_diverges(["antecedent_casilla_id", "literal", "casilla_a_id", "casilla_b_id"])',
        ]
    if len(parsed.arguments) != 4:
        return [
            f"{prefix}: {owner} {operator.value} must name exactly four tokens "
            f"(antecedent casilla id, literal, casilla_a id, casilla_b id), got {len(parsed.arguments)}: "
            f"{list(parsed.arguments)!r}",
        ]
    antecedent_id, casilla_a_id, casilla_b_id = parsed.casilla_ids
    failures = _text_antecedent_failures(prefix, owner, operator, antecedent_id, casillas, casilla_by_id)
    if not parsed.literal:
        failures.append(f"{prefix}: {owner} {operator.value} literal must be non-empty")
    failures.extend(
        _numeric_casilla_failures(prefix, owner, operator, "casilla_a", casilla_a_id, casillas, casilla_by_id),
    )
    failures.extend(
        _numeric_casilla_failures(prefix, owner, operator, "casilla_b", casilla_b_id, casillas, casilla_by_id),
    )
    return failures


def _deduccion_requires_adquisicion_before_predicate_failures(
    prefix: str,
    owner: str,
    expression: str,
    casillas: set[CasillaId],
    casilla_by_id: Mapping[CasillaId, CasillaDefinition],
) -> list[str]:
    operator = VerificationPredicateOperator.DEDUCCION_REQUIRES_ADQUISICION_BEFORE
    parsed = _parsed_expression(expression, operator)
    if parsed is None:
        return [
            f"{_malformed_expression_failure(prefix, owner, expression, operator)}; expected "
            'deduccion_requires_adquisicion_before(["amount_casilla_id", "acquisition_date_casilla_id", '
            '"construction_date_casilla_id", "cutoff_iso"])',
        ]
    if len(parsed.arguments) != 4:
        return [
            f"{prefix}: {owner} {operator.value} must name exactly four tokens "
            f"(amount casilla id, acquisition-date casilla id, construction-date casilla id, cutoff ISO date), "
            f"got {len(parsed.arguments)}: {list(parsed.arguments)!r}",
        ]
    amount_id, acquisition_date_id, construction_date_id = parsed.casilla_ids
    failures: list[str] = []
    if amount_id not in casillas:
        failures.append(f"{prefix}: {owner} {operator.value} references unknown amount casilla {amount_id!r}")
    for role, date_id in (("acquisition-date", acquisition_date_id), ("construction-date", construction_date_id)):
        if date_id not in casillas:
            failures.append(f"{prefix}: {owner} {operator.value} references unknown {role} casilla {date_id!r}")
            continue
        casilla = casilla_by_id.get(date_id)
        if casilla is not None and registry_scalar_value_type(casilla.data_type) not in {"str", "date"}:
            failures.append(
                f"{prefix}: {owner} {operator.value} {role} casilla {date_id!r} must carry a parseable date "
                f"(scalar family 'str' or 'date'), not data_type {casilla.data_type!r}",
            )
    if not _is_iso_date_literal(parsed.cutoff):
        failures.append(
            f"{prefix}: {owner} {operator.value} cutoff {parsed.cutoff!r} must be an ISO date literal (YYYY-MM-DD)",
        )
    return failures


def _advisory_when_ratio_ge_predicate_failures(
    prefix: str,
    owner: str,
    expression: str,
    casillas: set[CasillaId],
    casilla_by_id: Mapping[CasillaId, CasillaDefinition],
) -> list[str]:
    operator = VerificationPredicateOperator.ADVISORY_WHEN_RATIO_GE
    parsed = _parsed_expression(expression, operator)
    if parsed is None:
        return [
            f"{_malformed_expression_failure(prefix, owner, expression, operator)}; expected "
            'advisory_when_ratio_ge(["numerator_casilla_id", "denominator_casilla_id", "threshold"])',
        ]
    numerator_id, denominator_id = parsed.casilla_ids
    failures = _numeric_casilla_failures(prefix, owner, operator, "numerator", numerator_id, casillas, casilla_by_id)
    failures.extend(
        _numeric_casilla_failures(prefix, owner, operator, "denominator", denominator_id, casillas, casilla_by_id),
    )
    if try_parse_canonical_decimal(parsed.threshold) is None:
        failures.append(
            f"{prefix}: {owner} {operator.value} threshold {parsed.threshold!r} is not a plain decimal number; "
            "write it as digits with an optional '.' fraction (for example \"0.5\"). Scientific notation, a "
            "leading '+', underscore separators, 'NaN' and 'Infinity' are refused: an advisory whose threshold "
            "is not an ordinary number either never fires or fails at comparison, and neither is visible to the "
            "operator it was written to warn.",
        )
    return failures


def _profile_field_required_predicate_failures(prefix: str, owner: str, expression: str) -> list[str]:
    operator = VerificationPredicateOperator.PROFILE_FIELD_REQUIRED
    if _parsed_expression(expression, operator) is not None:
        return []
    return [
        f"{_malformed_expression_failure(prefix, owner, expression, operator)}; expected "
        'profile_field_required("profile_field_name", "applicability_filter")',
    ]


def _profile_flag_enabled_predicate_failures(prefix: str, owner: str, expression: str) -> list[str]:
    operator = VerificationPredicateOperator.PROFILE_FLAG_ENABLED
    parsed = _parsed_expression(expression, operator)
    if parsed is None:
        return [
            f"{_malformed_expression_failure(prefix, owner, expression, operator)}; expected "
            'profile_flag_enabled("profile_field_name")',
        ]
    if parsed.profile_field not in KNOWN_PROFILE_FLAG_ADVISORY_FIELDS:
        return [
            f"{prefix}: {owner} {operator.value} references unsupported profile field {parsed.profile_field!r}; "
            f"supported fields: {sorted(KNOWN_PROFILE_FLAG_ADVISORY_FIELDS)!r}",
        ]
    return []


def _text_antecedent_failures(
    prefix: str,
    owner: str,
    operator: VerificationPredicateOperator,
    casilla_id: str,
    casillas: set[CasillaId],
    casilla_by_id: Mapping[CasillaId, CasillaDefinition],
) -> list[str]:
    if casilla_id not in casillas:
        return [f"{prefix}: {owner} {operator.value} references unknown antecedent casilla {casilla_id!r}"]
    casilla = casilla_by_id.get(casilla_id)
    if casilla is not None and registry_scalar_value_type(casilla.data_type) != "str":
        return [
            f"{prefix}: {owner} {operator.value} antecedent casilla {casilla_id!r} must be a text-family casilla "
            f"(scalar family 'str'), not data_type {casilla.data_type!r}",
        ]
    return []


def _numeric_casilla_failures(
    prefix: str,
    owner: str,
    operator: VerificationPredicateOperator,
    role: str,
    casilla_id: str,
    casillas: set[CasillaId],
    casilla_by_id: Mapping[CasillaId, CasillaDefinition],
) -> list[str]:
    if casilla_id not in casillas:
        return [f"{prefix}: {owner} {operator.value} references unknown {role} casilla {casilla_id!r}"]
    casilla = casilla_by_id.get(casilla_id)
    if casilla is not None and registry_scalar_value_type(casilla.data_type) == "str":
        return [
            f"{prefix}: {owner} {operator.value} {role} casilla {casilla_id!r} must be a numeric casilla, not a "
            f"text-family one; declares data_type {casilla.data_type!r}",
        ]
    return []


def _is_iso_date_literal(value: str) -> bool:
    if len(value) != 10 or value[4:5] != "-" or value[7:8] != "-":
        return False
    return value.replace("-", "").isdigit()
