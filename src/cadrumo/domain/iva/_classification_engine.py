"""Private IVA classification predicate, projection, and result helpers."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from types import MappingProxyType
from typing import TYPE_CHECKING

from ...core.logging import get_logger
from ...core.type_guards import is_object_mapping
from ._classification_predicates import compile_classification_predicate
from .errors import IvaRateNotFoundError, IvaValidationError
from .place_of_supply import place_of_supply_rule
from .schema import spanish_eu_member_state

if TYPE_CHECKING:
    from ..calculations.registry.authority import PinnedAuthorityOperation
    from ..calculations.registry.facts.resolution import ResolvedMappingFact
    from ..calculations.registry.governed_fact_scope import GovernedFactSource
    from ..calculations.registry.iva_category_catalogue import IvaCategoryCatalogue
    from ..calculations.registry.iva_rate_kind_catalogue import IvaRateKindCatalogue
    from .classification import (
        IvaClassificationCatalogue,
        IvaClassificationResult,
        IvaClassificationRule,
        IvaInvoiceClassificationCriteria,
        IvaTerritorialScope,
        PartyFact,
        TransactionKindCatalogue,
    )
    from .schema import IvaCategory, IvaRateKind, IvaRateRecord

_logger = get_logger(__name__)


def _registry_reverse_charge_by_category(operation: PinnedAuthorityOperation) -> Mapping[str, bool]:
    """Read each IVA category's inversión-del-sujeto-pasivo flag from the published regulations."""
    from ..calculations.registry.runtime_catalogues import PublishedIvaRegulation

    loaded = operation.runtime_catalogue("iva_regulations")
    if not is_object_mapping(loaded):
        raise IvaValidationError("indexed authority IVA regulation component has an invalid shape")
    flags: dict[str, bool] = {}
    for category, regulation in loaded.items():
        if not isinstance(category, str) or not isinstance(regulation, PublishedIvaRegulation):
            raise IvaValidationError("indexed authority IVA regulation component has an invalid shape")
        flags[category] = regulation.requires_reverse_charge
    return MappingProxyType(flags)


def _requires_reverse_charge(flags: Mapping[str, bool], category: IvaCategory) -> bool:
    """Return the registry's reverse-charge flag, refusing a rule category with no regulation."""
    flag = flags.get(category.value)
    if flag is None:
        raise IvaValidationError(f"IVA classification category {category.value!r} has no published regulation")
    return flag


def resolve_rate_category_mapping(
    entries: Mapping[str, str],
    rate_catalogue: IvaRateKindCatalogue,
    category_catalogue: IvaCategoryCatalogue,
) -> dict[IvaRateKind, IvaCategory]:
    rate_categories: dict[IvaRateKind, IvaCategory] = {}
    for key, raw_category in entries.items():
        if not key.startswith("rate_categories."):
            continue
        raw_rate_kind = key.removeprefix("rate_categories.")
        if not raw_rate_kind:
            raise IvaValidationError("IVA classification mapping contains a blank rate-kind selector")
        rate_kind = rate_catalogue.require(raw_rate_kind)
        if rate_kind in rate_categories:
            raise IvaValidationError(f"IVA classification mapping repeats rate kind {raw_rate_kind!r}")
        rate_categories[rate_kind] = category_catalogue.require(raw_category)
    if not rate_categories:
        raise IvaValidationError("IVA classification mapping must declare rate categories")

    return rate_categories


def resolve_rate_territories(
    entries: Mapping[str, str],
    vocabulary: IvaClassificationCatalogue,
) -> frozenset[IvaTerritorialScope]:
    from .classification import required_classification_entry

    rate_territories = frozenset(
        vocabulary.require_territorial_scope(raw_value)
        for raw_value in required_classification_entry(entries, "rate_territories").split(",")
        if raw_value.strip()
    )
    if not rate_territories:
        raise IvaValidationError("IVA classification mapping rate_territories must not be empty")
    return rate_territories


def resolve_classification_rules(
    entries: Mapping[str, str],
    *,
    vocabulary: IvaClassificationCatalogue,
    kind_catalogue: TransactionKindCatalogue,
    category_catalogue: IvaCategoryCatalogue,
    effective_date: date,
    operation: PinnedAuthorityOperation,
) -> tuple[IvaClassificationRule, ...]:
    from .classification import classification_csv

    reverse_charge_by_category = _registry_reverse_charge_by_category(operation)
    rules: list[IvaClassificationRule] = []
    for rule_id in classification_csv(entries, "rule_order"):
        rules.append(
            _resolve_classification_rule(
                rule_id,
                entries,
                vocabulary=vocabulary,
                kind_catalogue=kind_catalogue,
                category_catalogue=category_catalogue,
                reverse_charge_by_category=reverse_charge_by_category,
                effective_date=effective_date,
                operation=operation,
            )
        )
    return tuple(rules)


def _resolve_classification_rule(
    rule_id: str,
    entries: Mapping[str, str],
    *,
    vocabulary: IvaClassificationCatalogue,
    kind_catalogue: TransactionKindCatalogue,
    category_catalogue: IvaCategoryCatalogue,
    reverse_charge_by_category: Mapping[str, bool],
    effective_date: date,
    operation: PinnedAuthorityOperation,
) -> IvaClassificationRule:
    from .classification import IvaClassificationRule, required_classification_entry

    prefix = f"rule.{rule_id}"
    expression = required_classification_entry(entries, f"{prefix}.predicate")
    raw_category = required_classification_entry(entries, f"{prefix}.category")
    category = None if raw_category == "rate_categories[rate_tier]" else category_catalogue.require(raw_category)
    consumes = _rule_party_facts(entries.get(f"{prefix}.consumes"), rule_id)
    return IvaClassificationRule(
        rule_id=rule_id,
        predicate=compile_classification_predicate(
            expression,
            vocabulary=vocabulary,
            kind_catalogue=kind_catalogue,
            effective_date=effective_date,
            operation=operation,
        ),
        category=category,
        description=required_classification_entry(entries, f"{prefix}.label"),
        consumes=consumes,
        requires_reverse_charge=(
            category is not None and _requires_reverse_charge(reverse_charge_by_category, category)
        ),
    )


def _rule_party_facts(raw_consumes: str | None, rule_id: str) -> frozenset[PartyFact]:
    from .classification import PartyFact

    if raw_consumes is None:
        return frozenset(PartyFact)
    consume_tokens = tuple(token.strip() for token in raw_consumes.split(",") if token.strip())
    if not consume_tokens or len(consume_tokens) != len(set(consume_tokens)):
        raise IvaValidationError(f"IVA classification rule {rule_id!r} has invalid party-fact membership")
    try:
        return frozenset(PartyFact(token) for token in consume_tokens)
    except ValueError as exc:
        raise IvaValidationError(f"IVA classification rule {rule_id!r} names an unknown party fact") from exc


def registry_iva_classification_catalogue(
    effective_date: date,
    *,
    operation: GovernedFactSource,
) -> ResolvedMappingFact:
    """Resolve the dated IVA catalogue consumed by the generic evaluator."""
    from ..calculations.registry.facts.resolution import MappingFactQuery, ResolvedMappingFact
    from ..calculations.registry.schema_base import DateAxis

    resolved = operation.resolve_governed_fact(
        MappingFactQuery(
            fact_id="iva-invoice-classification-catalogue",
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date,
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise IvaValidationError("IVA classification catalogue must resolve as a mapping fact")
    return resolved


def first_matching_classification(
    rules: tuple[IvaClassificationRule, ...],
    criteria: IvaInvoiceClassificationCriteria,
    *,
    category_catalogue: IvaCategoryCatalogue,
    rate_catalogue: IvaRateKindCatalogue,
    rate_categories: Mapping[IvaRateKind, IvaCategory] | None,
    rate_territories: frozenset[IvaTerritorialScope] | None,
    operation: PinnedAuthorityOperation,
) -> IvaClassificationResult | None:
    for rule in rules:
        if rule.category is not None:
            category_catalogue.require(rule.category)
        if rule.predicate(criteria):
            return _matched_classification(
                rule,
                criteria,
                category_catalogue=category_catalogue,
                rate_catalogue=rate_catalogue,
                rate_categories=rate_categories,
                rate_territories=rate_territories,
                operation=operation,
            )
    return None


def _matched_classification(
    rule: IvaClassificationRule,
    criteria: IvaInvoiceClassificationCriteria,
    *,
    category_catalogue: IvaCategoryCatalogue,
    rate_catalogue: IvaRateKindCatalogue,
    rate_categories: Mapping[IvaRateKind, IvaCategory] | None,
    rate_territories: frozenset[IvaTerritorialScope] | None,
    operation: PinnedAuthorityOperation,
) -> IvaClassificationResult:
    from .classification import IvaClassificationResult

    category = _matched_rule_category(rule, criteria, rate_categories)
    rate = _resolve_rate_for_category(
        criteria,
        category,
        rate_categories=rate_categories,
        rate_territories=rate_territories,
        operation=operation,
    )
    category = category_catalogue.require(category)
    if category == category_catalogue.require("domestic_exempt") and criteria.rate_tier is not None:
        rate_catalogue.require(criteria.rate_tier)
    projected_year = operation.supported_filing_years().projection_coordinate(criteria.transaction_date.year)
    if projected_year is None:
        raise IvaValidationError(
            f"transaction year {criteria.transaction_date.year} falls outside the supported filing years"
        )
    return IvaClassificationResult(
        category=category,
        rate=rate,
        requires_reverse_charge=rule.requires_reverse_charge,
        matched_rule_id=rule.rule_id,
        notes=rule.description,
        consumes_party_facts=rule.consumes,
        place_of_supply=place_of_supply_rule(
            rule.rule_id,
            on=criteria.transaction_date,
            operation=operation,
            projected_year=projected_year,
        ),
    )


def _matched_rule_category(
    rule: IvaClassificationRule,
    criteria: IvaInvoiceClassificationCriteria,
    rate_categories: Mapping[IvaRateKind, IvaCategory] | None,
) -> IvaCategory:
    category = rule.category
    if category is not None:
        return category
    if criteria.rate_tier is None or rate_categories is None:
        raise IvaValidationError("matched IVA row requires a registry rate/category mapping")
    try:
        return rate_categories[criteria.rate_tier]
    except KeyError as exc:
        raise IvaValidationError("registry rate/category mapping has no matched rate tier") from exc


def fallback_classification(
    rules: tuple[IvaClassificationRule, ...],
    criteria: IvaInvoiceClassificationCriteria,
    category_catalogue: IvaCategoryCatalogue,
    operation: PinnedAuthorityOperation,
) -> IvaClassificationResult:
    from .classification import IvaClassificationResult

    fallback = next((rule for rule in rules if rule.rule_id == "R99_fallthrough"), None)
    if fallback is None:
        raise IvaValidationError("no registry IVA classification row matched the supplied criteria")
    fallback_category = category_catalogue.require(fallback.category or "unknown")
    return IvaClassificationResult(
        category=fallback_category,
        rate=None,
        requires_reverse_charge=fallback.requires_reverse_charge,
        matched_rule_id=fallback.rule_id,
        notes=fallback.description,
        consumes_party_facts=fallback.consumes,
        place_of_supply=place_of_supply_rule(
            fallback.rule_id,
            on=criteria.transaction_date,
            operation=operation,
            projected_year=criteria.transaction_date.year,
        ),
    )


def _resolve_rate_for_category(
    criteria: IvaInvoiceClassificationCriteria,
    category: IvaCategory,
    *,
    rate_categories: Mapping[IvaRateKind, IvaCategory] | None,
    rate_territories: frozenset[IvaTerritorialScope] | None,
    operation: PinnedAuthorityOperation,
) -> IvaRateRecord | None:
    """Resolve a rate through caller-supplied registry mappings."""
    from .lookup import lookup_rate

    if rate_categories is None or rate_territories is None:
        return None
    tier = next((candidate for candidate, mapped in rate_categories.items() if mapped == category), None)
    if tier is None:
        return None
    if criteria.issuer_residency not in rate_territories:
        return None
    member_state = spanish_eu_member_state(effective_date=criteria.transaction_date, authority=operation)
    try:
        return lookup_rate(member_state, tier, criteria.transaction_date, operation=operation)
    except IvaRateNotFoundError:
        _logger.debug(
            "classify_iva: lookup_rate(%s, %s, %s) failed; returning rate=None",
            member_state.value,
            tier.value,
            criteria.transaction_date.isoformat(),
        )
        return None
