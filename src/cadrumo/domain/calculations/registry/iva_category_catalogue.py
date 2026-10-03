"""Typed projection of the governed IVA-category catalogue."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType
from typing import Final

from ....core.time.clock import today_madrid
from ...iva.schema import IvaCategory
from .errors import RegistryValidationError
from .facts.resolution import required_mapping_entry, unique_mapping_tokens
from .facts.string_mapping import (
    MappingValueWhitespace,
    StringMappingFact,
    StringMappingPolicy,
)
from .governed_fact_scope import (
    GovernedFactSource,
    cache_governed_projection,
    governed_facts_in_scope,
    require_governed_fact_authority,
)
from .schema_base import DateAxis

_ENTRY_SUBJECT: Final = "IVA category catalogue"

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


_ENTRIES_POLICY = StringMappingPolicy(subject=_ENTRY_SUBJECT, value_whitespace=MappingValueWhitespace.PRESERVE)


_ENTRIES_FACT = StringMappingFact(fact_id=_FACT_ID, date_axis=DateAxis.FILING_PERIOD, policy=_ENTRIES_POLICY)


def _category_definitions(
    entries: Mapping[str, str],
) -> tuple[list[IvaCategoryDefinition], frozenset[IvaCategory]]:
    definitions: list[IvaCategoryDefinition] = []
    for raw_token in unique_mapping_tokens(entries, _ORDER_KEY, subject=_ENTRY_SUBJECT):
        token = IvaCategory(raw_token)
        if required_mapping_entry(entries, f"{_VALUE_PREFIX}{raw_token}.value", subject=_ENTRY_SUBJECT) != raw_token:
            raise RegistryValidationError(f"IVA category token {raw_token!r} declares a mismatched value")
        definitions.append(
            IvaCategoryDefinition(
                token=token,
                description=required_mapping_entry(
                    entries, f"{_VALUE_PREFIX}{raw_token}.description", subject=_ENTRY_SUBJECT
                ),
            ),
        )
    declared = frozenset(definition.token for definition in definitions)

    return definitions, declared


def _category_projections(
    entries: Mapping[str, str],
    declared: frozenset[IvaCategory],
) -> dict[str, frozenset[IvaCategory]]:
    projections: dict[str, frozenset[IvaCategory]] = {}
    for key, _raw_value in entries.items():
        if not key.startswith(_PROJECTION_PREFIX):
            continue
        name = key.removeprefix(_PROJECTION_PREFIX)
        members = frozenset(IvaCategory(token) for token in unique_mapping_tokens(entries, key, subject=_ENTRY_SUBJECT))
        if not members.issubset(declared):
            raise RegistryValidationError(f"IVA category projection {name!r} names an undeclared category")
        projections[name] = members

    return projections


def _category_metadata(
    entries: Mapping[str, str],
    *,
    prefix: str,
    label: str,
    declared: frozenset[IvaCategory],
) -> dict[str, str]:
    declared_tokens = {str(item) for item in declared}
    metadata: dict[str, str] = {}
    for key, value in entries.items():
        if not key.startswith(prefix):
            continue
        token = key.removeprefix(prefix)
        if token not in declared_tokens:
            raise RegistryValidationError(f"IVA category {label} names an undeclared category {token!r}")
        metadata[token] = value.strip()
    return metadata


def _category_operation_types(entries: Mapping[str, str]) -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
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
    return operation_types, operation_type_categories, untdid_categories


def _catalogue_from_entries(entries: Mapping[str, str]) -> IvaCategoryCatalogue:
    definitions, declared = _category_definitions(entries)
    projections = _category_projections(entries, declared)
    reasons = _category_metadata(entries, prefix=_REASON_PREFIX, label="reason", declared=declared)
    hints = _category_metadata(entries, prefix="category_hint.", label="hint", declared=declared)
    operation_types, operation_type_categories, untdid_categories = _category_operation_types(entries)
    return IvaCategoryCatalogue(
        definitions=tuple(definitions),
        projections=MappingProxyType(projections),
        reasons=MappingProxyType(reasons),
        hints=MappingProxyType(hints),
        operation_types=MappingProxyType(operation_types),
        operation_type_categories=MappingProxyType(operation_type_categories),
        untdid_categories=MappingProxyType(untdid_categories),
    )


@cache_governed_projection(maxsize=64)
def _scoped_catalogue(effective_date: date) -> IvaCategoryCatalogue:
    """Project the category catalogue once for the active authority scope.

    Callers normally pass the pinned operation explicitly, but the operation
    itself is also the ambient governed-fact scope for a runtime request.
    Keeping the projection cache attached to that scope avoids reparsing the
    same immutable mapping for every transaction while preserving generation
    isolation: a different operation (including a candidate authority) gets
    a different cache owner.
    """
    return _catalogue_from_entries(_ENTRIES_FACT.resolve_scoped_entries(effective_date=effective_date, authority=None))


def resolve_iva_category_catalogue(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> IvaCategoryCatalogue:
    """Resolve the complete IVA category vocabulary through fact 0084."""
    coordinate = effective_date or today_madrid()
    selected = require_governed_fact_authority(authority, subject=_ENTRY_SUBJECT)
    if selected is governed_facts_in_scope():
        return _scoped_catalogue(coordinate)
    return _catalogue_from_entries(_ENTRIES_FACT.resolve_entries(selected, effective_date=coordinate))


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
