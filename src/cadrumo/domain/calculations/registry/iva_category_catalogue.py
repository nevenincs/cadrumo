"""Typed projection of the governed IVA-category catalogue."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from types import MappingProxyType

from ...iva.schema import IvaCategory
from .errors import RegistryValidationError
from .facts.resolution import MappingFactQuery, ResolvedMappingFact
from .governed_fact_scope import GovernedFactSource, governed_facts_in_scope
from .schema_base import DateAxis

_FACT_ID = "iva-category-component-catalogue"
_ORDER_KEY = "category.order"
_VALUE_PREFIX = "category."
_PROJECTION_PREFIX = "category_projection."
_REASON_PREFIX = "category_reason."


@dataclass(frozen=True, slots=True)
class IvaCategoryDefinition:
    """One registry-declared IVA category token and its metadata."""

    token: IvaCategory
    description: str


@dataclass(frozen=True, slots=True)
class IvaCategoryCatalogue:
    """Typed projection of the dated IVA category vocabulary."""

    definitions: tuple[IvaCategoryDefinition, ...]
    projections: Mapping[str, frozenset[IvaCategory]]
    reasons: Mapping[str, str]
    hints: Mapping[str, str]
    operation_types: Mapping[str, str]
    operation_type_categories: Mapping[str, str]
    untdid_categories: Mapping[str, str]

    @property
    def all_categories(self) -> tuple[IvaCategory, ...]:
        """Return the registry-declared categories in authored order."""
        return tuple(definition.token for definition in self.definitions)

    @property
    def all_category_set(self) -> frozenset[IvaCategory]:
        """Return the registry-declared category membership."""
        return frozenset(self.all_categories)

    def require(self, value: object) -> IvaCategory:
        """Return one category only when this projection declares it."""
        if isinstance(value, IvaCategory):
            token = value
        elif isinstance(value, str):
            token = IvaCategory(value.strip())
        else:
            raise RegistryValidationError("IVA category must be a string token")
        if not str(token) or token not in self.all_category_set:
            raise RegistryValidationError(
                f"IVA category {str(token)!r} is not declared by the facts registry",
            )
        return token

    def projection(self, name: str) -> frozenset[IvaCategory]:
        """Return one explicit category membership projection."""
        try:
            return self.projections[name]
        except KeyError as exc:
            raise RegistryValidationError(f"IVA category projection {name!r} is not declared") from exc

    def reason(self, token: object) -> str:
        """Return the registry-declared operator reason for a category."""
        category = self.require(token)
        try:
            return self.reasons[str(category)]
        except KeyError as exc:
            raise RegistryValidationError(
                f"IVA category {str(category)!r} has no registry-declared reason",
            ) from exc

    def hint(self, token: object) -> str:
        """Return the registry-declared concise classifier hint."""
        category = self.require(token)
        return self.hints.get(
            str(category),
            next(definition.description for definition in self.definitions if definition.token == category),
        )

    def operation_type(self, key: str) -> str:
        """Return a registry-declared Modelo 349 operation-type token."""
        if key not in self.operation_types:
            raise RegistryValidationError(f"IVA category operation type {key!r} is not declared")
        return self.operation_types[key]

    def category_for_operation_type(self, operation_type: str) -> IvaCategory | None:
        """Return the category declared for an operation-type token."""
        if not self.operation_type_categories:
            return None
        token = self.operation_type_categories.get(operation_type)
        return None if token is None else self.require(token)

    def category_for_untdid_code(self, code: str) -> IvaCategory | None:
        """Project an EN 16931/UNTDID 5305 code through registry data."""
        token = self.untdid_categories.get(code)
        return None if not token else self.require(token)


def _mapping_entries(resolved: ResolvedMappingFact) -> Mapping[str, str]:
    entries: dict[str, str] = {}
    for entry in resolved.payload.entries:
        if not isinstance(entry.key, str) or not isinstance(entry.value, str):
            raise RegistryValidationError("IVA category entries must be string-to-string")
        if entry.key in entries:
            raise RegistryValidationError(f"duplicate IVA category key {entry.key!r}")
        entries[entry.key] = entry.value
    return MappingProxyType(entries)


def _required(entries: Mapping[str, str], key: str) -> str:
    value = entries.get(key)
    if value is None or not value.strip():
        raise RegistryValidationError(f"IVA category catalogue is missing {key!r}")
    return value.strip()


def _csv(entries: Mapping[str, str], key: str) -> tuple[str, ...]:
    values = tuple(token.strip() for token in _required(entries, key).split(",") if token.strip())
    if not values or len(values) != len(set(values)):
        raise RegistryValidationError(f"IVA category catalogue {key!r} must contain unique tokens")
    return values


def _resolve_entries(
    *,
    effective_date: date,
    authority: GovernedFactSource,
) -> Mapping[str, str]:
    resolved = authority.resolve_governed_fact(
        MappingFactQuery(
            fact_id=_FACT_ID,
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date,
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise RegistryValidationError("IVA category catalogue must resolve as a mapping fact")
    return _mapping_entries(resolved)


@lru_cache(maxsize=64)
def _bundled_entries(effective_date: date) -> Mapping[str, str]:
    from .authority import bundled_authority

    return _resolve_entries(effective_date=effective_date, authority=bundled_authority())


def _selected_entries(
    *,
    effective_date: date | None,
    authority: GovernedFactSource | None,
) -> Mapping[str, str]:
    coordinate = effective_date or date.today()
    selected = authority or governed_facts_in_scope()
    if selected is None:
        return _bundled_entries(coordinate)
    return _resolve_entries(effective_date=coordinate, authority=selected)


def _catalogue_from_entries(entries: Mapping[str, str]) -> IvaCategoryCatalogue:
    definitions: list[IvaCategoryDefinition] = []
    for raw_token in _csv(entries, _ORDER_KEY):
        token = IvaCategory(raw_token)
        if _required(entries, f"{_VALUE_PREFIX}{raw_token}.value") != raw_token:
            raise RegistryValidationError(f"IVA category token {raw_token!r} declares a mismatched value")
        definitions.append(
            IvaCategoryDefinition(
                token=token,
                description=_required(entries, f"{_VALUE_PREFIX}{raw_token}.description"),
            ),
        )
    declared = frozenset(definition.token for definition in definitions)
    projections: dict[str, frozenset[IvaCategory]] = {}
    for key, raw_value in entries.items():
        if not key.startswith(_PROJECTION_PREFIX):
            continue
        name = key.removeprefix(_PROJECTION_PREFIX)
        members = frozenset(IvaCategory(token) for token in _csv(entries, key))
        if not members.issubset(declared):
            raise RegistryValidationError(f"IVA category projection {name!r} names an undeclared category")
        projections[name] = members
    reasons: dict[str, str] = {}
    for key, value in entries.items():
        if key.startswith(_REASON_PREFIX):
            token = key.removeprefix(_REASON_PREFIX)
            if token not in {str(item) for item in declared}:
                raise RegistryValidationError(f"IVA category reason names an undeclared category {token!r}")
            reasons[token] = value.strip()
    hints: dict[str, str] = {}
    for key, value in entries.items():
        if key.startswith("category_hint."):
            token = key.removeprefix("category_hint.")
            if token not in {str(item) for item in declared}:
                raise RegistryValidationError(f"IVA category hint names an undeclared category {token!r}")
            hints[token] = value.strip()
    operation_types = {
        key.removeprefix("category_operation_type."): value.strip()
        for key, value in entries.items()
        if key.startswith("category_operation_type.")
    }
    operation_type_categories = {
        key.removeprefix("category_for_operation_type."): value.strip()
        for key, value in entries.items()
        if key.startswith("category_for_operation_type.")
    }
    untdid_categories = {
        key.removeprefix("category_for_untdid."): value.strip()
        for key, value in entries.items()
        if key.startswith("category_for_untdid.")
    }
    return IvaCategoryCatalogue(
        definitions=tuple(definitions),
        projections=MappingProxyType(projections),
        reasons=MappingProxyType(reasons),
        hints=MappingProxyType(hints),
        operation_types=MappingProxyType(operation_types),
        operation_type_categories=MappingProxyType(operation_type_categories),
        untdid_categories=MappingProxyType(untdid_categories),
    )


def resolve_iva_category_catalogue(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> IvaCategoryCatalogue:
    """Resolve the complete IVA category vocabulary through fact 0084."""
    return _catalogue_from_entries(_selected_entries(effective_date=effective_date, authority=authority))


def require_iva_category(
    value: object,
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> IvaCategory:
    """Return one registry-declared IVA category or refuse it."""
    return resolve_iva_category_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).require(value)


def registry_category_projection(
    name: str,
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> frozenset[IvaCategory]:
    """Return one explicit category projection from fact 0084."""
    return resolve_iva_category_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).projection(name)


__all__ = [
    "IvaCategoryCatalogue",
    "IvaCategoryDefinition",
    "registry_category_projection",
    "require_iva_category",
    "resolve_iva_category_catalogue",
]
