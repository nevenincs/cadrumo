"""Private compilation of registry-projected IVA classification predicates."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING

from .errors import IvaValidationError
from .schema import spanish_eu_member_state

if TYPE_CHECKING:
    from ..calculations.registry.authority import PinnedAuthorityOperation
    from .classification import (
        CustomerTaxStatus,
        IvaClassificationCatalogue,
        IvaInvoiceClassificationCriteria,
        IvaTerritorialScope,
        TransactionKind,
        TransactionKindCatalogue,
    )
    from .schema import EUMemberState


def _scope_predicate_values(
    value: str,
    *,
    vocabulary: IvaClassificationCatalogue,
) -> frozenset[IvaTerritorialScope]:
    """Resolve one registry scope selector to its declared members."""
    all_scopes = frozenset(vocabulary.territorial_scopes)
    mainland = vocabulary.territorial_scope_alias("mainland")
    canarias = vocabulary.territorial_scope_alias("canarias")
    ceuta_melilla = vocabulary.territorial_scope_alias("ceuta_melilla")
    third_country = vocabulary.territorial_scope_alias("third_country")
    if value == "non_spanish_eu":
        return all_scopes - {mainland, canarias, ceuta_melilla}
    if value == "outside_tai":
        return all_scopes - {mainland}
    if value == "outside_comunidad":
        return frozenset({canarias, ceuta_melilla, third_country})
    try:
        return frozenset({vocabulary.territorial_scope_alias(value)})
    except IvaValidationError:
        return frozenset({vocabulary.require_territorial_scope(value)})


def _status_predicate_values(
    value: str,
    *,
    vocabulary: IvaClassificationCatalogue,
) -> frozenset[CustomerTaxStatus]:
    """Resolve one registry customer-status selector to its members."""
    aliases = vocabulary.customer_status_aliases
    if value == "b2b_or_public":
        return frozenset(
            {
                aliases["b2b_registered"],
                aliases["b2b_not_registered"],
                aliases["public_administration"],
            },
        )
    if value == "b2c_or_public":
        return frozenset({aliases["b2c_consumer"], aliases["public_administration"]})
    if value == "b2c":
        return frozenset({aliases["b2c_consumer"]})
    try:
        return frozenset({aliases[value]})
    except KeyError:
        return frozenset({vocabulary.require_customer_tax_status(value)})


def _selector_union[T](value: str, resolve: Callable[[str], frozenset[T]]) -> frozenset[T]:
    """Resolve a comma-separated selector as the union of its members."""
    members = tuple(member.strip() for member in value.split(","))
    if any(not member for member in members) or len(members) != len(set(members)):
        raise IvaValidationError(f"IVA classification predicate selector {value!r} is malformed")
    resolved: set[T] = set()
    for member in members:
        resolved |= resolve(member)
    return frozenset(resolved)


def _kind_predicate_values(
    value: str,
    *,
    catalogue: TransactionKindCatalogue,
) -> frozenset[TransactionKind]:
    """Resolve one registry kind selector to its declared members."""
    if value == "domestic_default":
        return frozenset(
            definition.token
            for definition in catalogue.definitions
            if not definition.token.value.endswith("_reverse_charge")
        )
    return frozenset({catalogue.require(value)})


def _issuer_identification_state(criteria: IvaInvoiceClassificationCriteria) -> EUMemberState | None:
    """Read the issuer's identification axis for a compiled predicate."""
    return criteria.issuer_identification_state


def _customer_identification_state(criteria: IvaInvoiceClassificationCriteria) -> EUMemberState | None:
    """Read the customer's identification axis for a compiled predicate."""
    return criteria.customer_identification_state


def matches_nothing(criteria: IvaInvoiceClassificationCriteria) -> bool:
    """Predicate of the registry's terminal `no_match` row, which reads no axis."""
    del criteria
    return False


@dataclass(frozen=True, slots=True)
class _ClassificationPredicateContext:
    vocabulary: IvaClassificationCatalogue
    kind_catalogue: TransactionKindCatalogue
    spanish_state: EUMemberState
    third_country: IvaTerritorialScope


def _compile_classification_predicate(
    expression: str,
    *,
    vocabulary: IvaClassificationCatalogue,
    kind_catalogue: TransactionKindCatalogue,
    effective_date: date,
    operation: PinnedAuthorityOperation,
) -> Callable[[IvaInvoiceClassificationCriteria], bool]:
    """Compile one registry predicate without introducing a second rule table."""
    if expression.strip() == "no_match":
        return matches_nothing
    clauses = tuple(part.strip() for part in expression.split(";") if part.strip())
    if not clauses:
        raise IvaValidationError("IVA classification predicate must not be empty")
    context = _ClassificationPredicateContext(
        vocabulary=vocabulary,
        kind_catalogue=kind_catalogue,
        spanish_state=spanish_eu_member_state(effective_date=effective_date, authority=operation),
        third_country=vocabulary.territorial_scope_alias("third_country"),
    )
    conditions: list[Callable[[IvaInvoiceClassificationCriteria], bool]] = []
    seen: set[str] = set()
    for clause in clauses:
        field, value = _parse_classification_clause(clause, seen)
        conditions.append(_compile_classification_condition(field, value, context))
    return lambda criteria: all(condition(criteria) for condition in conditions)


def _parse_classification_clause(clause: str, seen: set[str]) -> tuple[str, str]:
    if "=" not in clause:
        raise IvaValidationError(f"IVA classification predicate clause {clause!r} is malformed")
    field, value = (part.strip() for part in clause.split("=", 1))
    if not field or not value or field in seen:
        raise IvaValidationError(f"IVA classification predicate clause {clause!r} is malformed")
    seen.add(field)
    return field, value


def _compile_classification_condition(
    field: str,
    value: str,
    context: _ClassificationPredicateContext,
) -> Callable[[IvaInvoiceClassificationCriteria], bool]:
    if field in {"issuer", "customer"}:
        return _compile_residency_condition(field, value, context.vocabulary)
    if field == "status":
        return _compile_status_condition(value, context.vocabulary)
    if field == "kind":
        return _compile_kind_condition(value, context.kind_catalogue)
    if field == "direction":
        return _compile_direction_condition(value)
    if field in {"issuer_identification", "customer_identification"}:
        return _compile_identification_condition(field, value, context.spanish_state)
    if field == "art_69_dos_service":
        return _compile_art69_condition(value, context.third_country)
    raise IvaValidationError(f"IVA classification predicate names unknown field {field!r}")


def _compile_residency_condition(
    field: str,
    value: str,
    vocabulary: IvaClassificationCatalogue,
) -> Callable[[IvaInvoiceClassificationCriteria], bool]:
    allowed = _selector_union(value, lambda member: _scope_predicate_values(member, vocabulary=vocabulary))
    if field == "issuer":
        return lambda criteria: criteria.issuer_residency in allowed
    return lambda criteria: criteria.customer_residency in allowed


def _compile_status_condition(
    value: str,
    vocabulary: IvaClassificationCatalogue,
) -> Callable[[IvaInvoiceClassificationCriteria], bool]:
    allowed = _selector_union(value, lambda member: _status_predicate_values(member, vocabulary=vocabulary))
    return lambda criteria: criteria.customer_tax_status in allowed


def _compile_kind_condition(
    value: str,
    catalogue: TransactionKindCatalogue,
) -> Callable[[IvaInvoiceClassificationCriteria], bool]:
    allowed = _kind_predicate_values(value, catalogue=catalogue)
    return lambda criteria: criteria.kind in allowed


def _compile_direction_condition(value: str) -> Callable[[IvaInvoiceClassificationCriteria], bool]:
    from .classification import InvoiceKind

    try:
        direction = InvoiceKind(value)
    except ValueError as exc:
        raise IvaValidationError(f"IVA classification predicate names unknown direction {value!r}") from exc
    return lambda criteria: criteria.direction is direction


def _compile_identification_condition(
    field: str,
    value: str,
    spanish_state: EUMemberState,
) -> Callable[[IvaInvoiceClassificationCriteria], bool]:
    state_reader = _issuer_identification_state if field == "issuer_identification" else _customer_identification_state
    if value == "other_member_state":
        return lambda criteria: (state := state_reader(criteria)) is not None and state != spanish_state
    if value == "present":
        return lambda criteria: state_reader(criteria) is not None
    if value == "absent":
        return lambda criteria: state_reader(criteria) is None
    if value == "spanish":
        return lambda criteria: state_reader(criteria) == spanish_state
    raise IvaValidationError(f"IVA classification predicate names unknown identification selector {value!r}")


def _compile_art69_condition(
    value: str,
    third_country: IvaTerritorialScope,
) -> Callable[[IvaInvoiceClassificationCriteria], bool]:
    if value == "present":
        return lambda criteria: criteria.art_69_dos_service is not None
    if value == "absent_or_excepted":
        return lambda criteria: (
            not (criteria.art_69_dos_service is not None and criteria.customer_residency == third_country)
        )
    if value == "absent":
        return lambda criteria: criteria.art_69_dos_service is None
    raise IvaValidationError(f"IVA classification predicate names unknown Art. 69.Dos selector {value!r}")
