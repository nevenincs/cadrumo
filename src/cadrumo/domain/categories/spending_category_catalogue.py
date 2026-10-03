"""Typed projection of the governed spending-category catalogue."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType
from typing import Final

from ...core.time.clock import today_madrid
from ..calculations.registry.errors import RegistryValidationError
from ..calculations.registry.facts.resolution import (
    unique_mapping_tokens,
)
from ..calculations.registry.facts.string_mapping import (
    MappingValueWhitespace,
    StringMappingFact,
    StringMappingPolicy,
)
from ..calculations.registry.facts.variants import FactSelector
from ..calculations.registry.governed_fact_scope import GovernedFactSource, require_governed_fact_authority
from ..calculations.registry.schema_base import DateAxis
from .spending_category import SpendingCategory, SpendingCategoryFamily

_ENTRY_SUBJECT: Final = "spending category catalogue"

_FACT_ID = "categories.profile"
_SCOPE_SELECTOR = FactSelector(name="scope", value="spending_category_catalogue")
_ORDER_KEY = "spending_category.order"
_FAMILY_PREFIX = "spending_category.family."


def _runtime_object(value: object) -> object:
    """Capture a family token before applying the runtime enum check."""
    return value


@dataclass(frozen=True, slots=True)
class SpendingCategoryCatalogue:
    """Dated facts projection for category tokens and mechanical buckets."""

    categories: tuple[SpendingCategory, ...]
    family_members: Mapping[SpendingCategoryFamily, tuple[SpendingCategory, ...]]

    @property
    def all_categories(self) -> frozenset[SpendingCategory]:
        """Return every category declared by the selected authority."""
        return frozenset(self.categories)

    def require(self, value: object) -> SpendingCategory:
        """Return one category only when the selected authority declares it."""
        if isinstance(value, SpendingCategory):
            token = value
        elif isinstance(value, str):
            raw = value.strip()
            if not raw:
                raise RegistryValidationError("spending category token must be non-empty")
            try:
                token = SpendingCategory.from_registry(raw)
            except (TypeError, ValueError) as exc:
                raise RegistryValidationError("spending category token must be non-empty") from exc
        else:
            raise RegistryValidationError("spending category must be a registry-projected token")
        if token not in self.all_categories:
            raise RegistryValidationError(
                f"spending category {str(token)!r} is not declared by fact {_FACT_ID!r}",
            )
        return token

    def categories_for_family(self, family: SpendingCategoryFamily) -> tuple[SpendingCategory, ...]:
        """Return the ordered category projection for one retained family."""
        raw_family = _runtime_object(family)
        try:
            selected = raw_family if isinstance(raw_family, SpendingCategoryFamily) else SpendingCategoryFamily(family)
        except (TypeError, ValueError) as exc:
            raise RegistryValidationError(f"unknown spending category family {family!r}") from exc
        try:
            return self.family_members[selected]
        except KeyError as exc:
            raise RegistryValidationError(f"spending category family {selected.value!r} is not declared") from exc

    def family_for(self, category: SpendingCategory) -> SpendingCategoryFamily:
        """Return the unique retained family containing one category."""
        token = self.require(category)
        for family, members in self.family_members.items():
            if token in members:
                return family
        raise RegistryValidationError(f"spending category {token.value!r} has no declared family")


_ENTRIES_POLICY = StringMappingPolicy(subject=_ENTRY_SUBJECT, value_whitespace=MappingValueWhitespace.PRESERVE)


_ENTRIES_FACT = StringMappingFact(
    fact_id=_FACT_ID, date_axis=DateAxis.FILING_PERIOD, policy=_ENTRIES_POLICY, selectors=(_SCOPE_SELECTOR,)
)


def resolve_spending_category_catalogue(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> SpendingCategoryCatalogue:
    """Resolve and validate the dated spending-category catalogue."""
    coordinate = effective_date or today_madrid()
    selected = require_governed_fact_authority(authority, subject="spending category catalogue")
    entries = _ENTRIES_FACT.resolve_entries(selected, effective_date=coordinate)
    categories = _spending_categories(entries)
    family_members = _spending_category_families(entries, categories)
    return SpendingCategoryCatalogue(
        categories=categories,
        family_members=MappingProxyType(family_members),
    )


def _spending_categories(entries: Mapping[str, str]) -> tuple[SpendingCategory, ...]:
    raw_categories = unique_mapping_tokens(entries, _ORDER_KEY, subject=_ENTRY_SUBJECT)
    try:
        return tuple(SpendingCategory.from_registry(raw) for raw in raw_categories)
    except (TypeError, ValueError) as exc:
        raise RegistryValidationError("spending category catalogue contains an invalid token") from exc


def _spending_category_families(
    entries: Mapping[str, str], categories: tuple[SpendingCategory, ...]
) -> dict[SpendingCategoryFamily, tuple[SpendingCategory, ...]]:
    category_by_value = {category.value: category for category in categories}
    family_members: dict[SpendingCategoryFamily, tuple[SpendingCategory, ...]] = {}
    seen: set[SpendingCategory] = set()
    for family in SpendingCategoryFamily:
        raw_members = unique_mapping_tokens(entries, f"{_FAMILY_PREFIX}{family.value}", subject=_ENTRY_SUBJECT)
        try:
            members = tuple(category_by_value[raw] for raw in raw_members)
        except KeyError as exc:
            raise RegistryValidationError(
                f"spending category family {family.value!r} names an undeclared category {exc.args[0]!r}",
            ) from exc
        if seen.intersection(members):
            raise RegistryValidationError("spending category catalogue assigns a category to multiple families")
        seen.update(members)
        family_members[family] = members
    if seen != set(categories):
        missing = sorted(category.value for category in set(categories) - seen)
        raise RegistryValidationError(f"spending category catalogue leaves categories unmapped: {missing!r}")
    return family_members


def require_spending_category(
    value: object,
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> SpendingCategory:
    """Return one registry-declared spending category or refuse it."""
    return resolve_spending_category_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).require(value)


def spending_category_tokens(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> tuple[SpendingCategory, ...]:
    """Return category choices in the authority-authored order."""
    return resolve_spending_category_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).categories


__all__ = [
    "SpendingCategoryCatalogue",
    "require_spending_category",
    "resolve_spending_category_catalogue",
    "spending_category_tokens",
]
