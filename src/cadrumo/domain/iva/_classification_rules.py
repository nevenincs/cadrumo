"""Generic predicate adapter for registry-projected IVA classification rows.

Concrete invoice predicates and the ordered classification catalogue live in
the versioned registry. This module only provides the callable shape used by a
consumer that has projected one of those declarations into Python mechanics.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

from .classification import IvaInvoiceClassificationCriteria

IvaClassificationPredicate = Callable[[IvaInvoiceClassificationCriteria], bool]


def evaluate_classification_predicate(
    predicate: IvaClassificationPredicate,
    criteria: IvaInvoiceClassificationCriteria,
) -> bool:
    """Evaluate one caller-supplied predicate against typed criteria."""
    return bool(predicate(criteria))


def classification_predicate_from_declaration(
    declaration: str,
    *,
    territorial_aliases: Mapping[str, object],
    status_aliases: Mapping[str, object],
) -> IvaClassificationPredicate:
    """Compile the closed registry predicate grammar into a criteria predicate."""
    if declaration == "no_match":
        return lambda _criteria: True
    clauses: list[tuple[str, str]] = []
    for raw_clause in declaration.split(";"):
        field, separator, expected = raw_clause.partition("=")
        if not separator or not field or not expected:
            raise ValueError(f"invalid IVA classification predicate clause {raw_clause!r}")
        clauses.append((field, expected))

    mainland = territorial_aliases["mainland"]
    canarias = territorial_aliases["canarias"]
    ceuta_melilla = territorial_aliases["ceuta_melilla"]
    eu_member = territorial_aliases["eu_member"]
    third_country = territorial_aliases["third_country"]
    b2b_registered = status_aliases["b2b_registered"]
    b2b_not_registered = status_aliases["b2b_not_registered"]
    b2c = status_aliases["b2c_consumer"]
    public = status_aliases["public_administration"]

    def predicate(criteria: IvaInvoiceClassificationCriteria) -> bool:
        for field, expected in clauses:
            if field in {"issuer", "customer"}:
                actual = criteria.issuer_residency if field == "issuer" else criteria.customer_residency
                scopes = {
                    "es_mainland": frozenset({mainland}),
                    "non_spanish_eu": frozenset({eu_member}),
                    "eu_member": frozenset({eu_member}),
                    "third_country": frozenset({third_country}),
                    "outside_comunidad": frozenset({canarias, ceuta_melilla, third_country}),
                    "outside_tai": frozenset({canarias, ceuta_melilla, eu_member, third_country}),
                }.get(expected)
                if scopes is None or actual not in scopes:
                    return False
            elif field == "status":
                statuses = {
                    "b2b_registered": frozenset({b2b_registered}),
                    "b2b_or_public": frozenset({b2b_registered, b2b_not_registered, public}),
                    "b2c": frozenset({b2c}),
                    "b2c_or_public": frozenset({b2c, public}),
                }.get(expected)
                if statuses is None or criteria.customer_tax_status not in statuses:
                    return False
            elif field == "kind":
                if expected == "domestic_default":
                    excluded = {
                        "construction_reverse_charge",
                        "waste_reverse_charge",
                        "electronics_reverse_charge",
                        "immovable_property",
                    }
                    if str(criteria.kind) in excluded:
                        return False
                elif str(criteria.kind) != expected:
                    return False
            elif field == "direction":
                if criteria.direction.value.lower() != expected:
                    return False
            elif field in {"issuer_identification", "customer_identification"}:
                actual = (
                    criteria.issuer_identification_state
                    if field == "issuer_identification"
                    else criteria.customer_identification_state
                )
                if expected != "other_member_state" or actual is None or str(actual).upper() == "ES":
                    return False
            elif field == "art_69_dos_service":
                present = criteria.art_69_dos_service is not None
                if (expected == "present" and not present) or (expected == "absent_or_excepted" and present):
                    return False
                if expected not in {"present", "absent_or_excepted"}:
                    return False
            else:
                return False
        return True

    return predicate


__all__ = [
    "IvaClassificationPredicate",
    "classification_predicate_from_declaration",
    "evaluate_classification_predicate",
]
