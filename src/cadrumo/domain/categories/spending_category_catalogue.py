"""Typed projection of the governed spending-category catalogue."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType

from ..calculations.registry.errors import RegistryValidationError
from ..calculations.registry.facts.resolution import MappingFactQuery, ResolvedMappingFact
from ..calculations.registry.facts.schema import FactSelector
from ..calculations.registry.governed_fact_scope import GovernedFactSource, governed_facts_in_scope
from ..calculations.registry.schema_base import DateAxis
from .spending_category import SpendingCategory, SpendingCategoryFamily

_FACT_ID = "categories.profile"
_SCOPE_SELECTOR = FactSelector(name="scope", value="spending_category_catalogue")
_ORDER_KEY = "spending_category.order"
_FAMILY_PREFIX = "spending_category.family."


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
                token = SpendingCategory._from_registry(raw)
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
        try:
            selected = family if isinstance(family, SpendingCategoryFamily) else SpendingCategoryFamily(family)
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


def _mapping_entries(resolved: ResolvedMappingFact) -> Mapping[str, str]:
    entries: dict[str, str] = {}
    for entry in resolved.payload.entries:
        if not isinstance(entry.key, str) or not isinstance(entry.value, str):
            raise RegistryValidationError("spending category catalogue entries must be string-to-string")
        if entry.key in entries:
            raise RegistryValidationError(f"duplicate spending category catalogue key {entry.key!r}")
        entries[entry.key] = entry.value
    return MappingProxyType(entries)


def _required(entries: Mapping[str, str], key: str) -> str:
    value = entries.get(key)
    if value is None or not value.strip():
        raise RegistryValidationError(f"spending category catalogue is missing {key!r}")
    return value.strip()


def _csv(entries: Mapping[str, str], key: str) -> tuple[str, ...]:
    tokens = tuple(token.strip() for token in _required(entries, key).split(",") if token.strip())
    if not tokens or len(tokens) != len(set(tokens)):
        raise RegistryValidationError(f"spending category catalogue {key!r} must contain unique tokens")
    return tokens


def _resolve_entries(*, effective_date: date, authority: GovernedFactSource) -> Mapping[str, str]:
    resolved = authority.resolve_governed_fact(
        MappingFactQuery(
            fact_id=_FACT_ID,
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date,
            selectors=(_SCOPE_SELECTOR,),
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise RegistryValidationError("spending category catalogue must resolve as a mapping fact")
    return _mapping_entries(resolved)


def resolve_spending_category_catalogue(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> SpendingCategoryCatalogue:
    """Resolve and validate the dated spending-category catalogue."""
    coordinate = effective_date or date.today()
    selected = authority or governed_facts_in_scope()
    if selected is None:
        raise RegistryValidationError("spending category catalogue requires an explicit authority operation or scope")
    entries = _resolve_entries(effective_date=coordinate, authority=selected)
    raw_categories = _csv(entries, _ORDER_KEY)
    try:
        categories = tuple(SpendingCategory._from_registry(raw) for raw in raw_categories)
    except (TypeError, ValueError) as exc:
        raise RegistryValidationError("spending category catalogue contains an invalid token") from exc
    category_by_value = {category.value: category for category in categories}
    family_members: dict[SpendingCategoryFamily, tuple[SpendingCategory, ...]] = {}
    seen: set[SpendingCategory] = set()
    for family in SpendingCategoryFamily:
        raw_members = _csv(entries, f"{_FAMILY_PREFIX}{family.value}")
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
    return SpendingCategoryCatalogue(
        categories=categories,
        family_members=MappingProxyType(family_members),
    )


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
