"""Typed projection of the governed IVA rate-kind catalogue."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType

from ...iva.schema import IvaRateKind
from .errors import RegistryValidationError
from .facts.resolution import MappingFactQuery, ResolvedMappingFact
from .governed_fact_scope import (
    GovernedFactSource,
    cache_governed_projection,
    governed_facts_in_scope,
    validating_governed_facts,
)
from .schema_base import DateAxis

_FACT_ID = "iva-rate-slot-catalogue"
_ORDER_KEY = "rate_kind.order"
_POSITIVE_ORDER_KEY = "rate_kind.positive_order"
_ZERO_KEY = "rate_kind.zero_token"
_EXEMPT_KEY = "rate_kind.exempt_token"
_NON_RATE_KEY = "rate_kind.non_rate_token"
_PREFIX = "rate_kind."


@dataclass(frozen=True, slots=True)
class IvaRateKindDefinition:
    """One registry-declared IVA rate tier and its category projection."""

    token: IvaRateKind
    description: str
    category: str


@dataclass(frozen=True, slots=True)
class IvaRateKindCatalogue:
    """Typed projection of the dated IVA rate-kind vocabulary."""

    definitions: tuple[IvaRateKindDefinition, ...]
    positive_kinds: tuple[IvaRateKind, ...]
    zero_token: IvaRateKind
    exempt_token: IvaRateKind
    non_rate_token: str

    @property
    def all_kinds(self) -> frozenset[IvaRateKind]:
        """Return every rate-kind token declared by the registry."""
        return frozenset(definition.token for definition in self.definitions)

    def require(self, value: object) -> IvaRateKind:
        """Return one token only when it belongs to this registry projection."""
        if isinstance(value, IvaRateKind):
            token = value
        elif isinstance(value, str):
            token = IvaRateKind(value.strip())
        else:
            raise RegistryValidationError("IVA rate kind must be a string token")
        if not str(token) or token not in self.all_kinds:
            raise RegistryValidationError(
                f"IVA rate kind {str(token)!r} is not declared by the facts registry",
            )
        return token

    def definition(self, value: object) -> IvaRateKindDefinition:
        """Return the registry definition for one rate-kind token."""
        token = self.require(value)
        return next(definition for definition in self.definitions if definition.token == token)

    def for_category(self, category: str) -> IvaRateKind:
        """Return the unique rate kind projected for one IVA category token."""
        matches = tuple(definition.token for definition in self.definitions if definition.category == category)
        if len(matches) != 1:
            raise RegistryValidationError(
                f"IVA category {category!r} must map to exactly one rate kind",
            )
        return matches[0]


def _mapping_entries(resolved: ResolvedMappingFact) -> Mapping[str, str]:
    entries: dict[str, str] = {}
    for entry in resolved.payload.entries:
        if not isinstance(entry.key, str) or not isinstance(entry.value, str):
            raise RegistryValidationError("IVA rate-kind entries must be string-to-string")
        if entry.key in entries:
            raise RegistryValidationError(f"duplicate IVA rate-kind key {entry.key!r}")
        entries[entry.key] = entry.value
    return MappingProxyType(entries)


def _required(entries: Mapping[str, str], key: str) -> str:
    value = entries.get(key)
    if value is None or not value.strip():
        raise RegistryValidationError(f"IVA rate-kind catalogue is missing {key!r}")
    return value.strip()


def _csv(entries: Mapping[str, str], key: str) -> tuple[str, ...]:
    values = tuple(token.strip() for token in _required(entries, key).split(",") if token.strip())
    if not values or len(values) != len(set(values)):
        raise RegistryValidationError(f"IVA rate-kind catalogue {key!r} must contain unique tokens")
    return values


def _resolve_entries(
    *,
    effective_date: date,
    authority: GovernedFactSource,
) -> Mapping[str, str]:
    resolved = authority.resolve_governed_fact(
        MappingFactQuery(
            fact_id=_FACT_ID,
            date_axis=DateAxis.DEVENGO_DATE,
            effective_date=effective_date,
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise RegistryValidationError("IVA rate-kind catalogue must resolve as a mapping fact")
    return _mapping_entries(resolved)


def _scoped_entries(effective_date: date) -> Mapping[str, str]:
    authority = governed_facts_in_scope()
    if authority is None:
        raise RegistryValidationError("IVA rate-kind catalogue requires an explicit authority operation or scope")
    return _resolve_entries(effective_date=effective_date, authority=authority)


@cache_governed_projection(maxsize=512)
def _scoped_catalogue(effective_date: date) -> IvaRateKindCatalogue:
    entries = _scoped_entries(effective_date)
    definitions: list[IvaRateKindDefinition] = []
    for raw_token in _csv(entries, _ORDER_KEY):
        prefix = f"{_PREFIX}{raw_token}"
        token = IvaRateKind(raw_token)
        if _required(entries, f"{prefix}.value") != raw_token:
            raise RegistryValidationError(f"IVA rate-kind token {raw_token!r} declares a mismatched value")
        definitions.append(
            IvaRateKindDefinition(
                token=token,
                description=_required(entries, f"{prefix}.description"),
                category=_required(entries, f"{prefix}.category"),
            ),
        )
    catalogue = IvaRateKindCatalogue(
        definitions=tuple(definitions),
        positive_kinds=tuple(IvaRateKind(token) for token in _csv(entries, _POSITIVE_ORDER_KEY)),
        zero_token=IvaRateKind(_required(entries, _ZERO_KEY)),
        exempt_token=IvaRateKind(_required(entries, _EXEMPT_KEY)),
        non_rate_token=_required(entries, _NON_RATE_KEY),
    )
    all_kinds = catalogue.all_kinds
    if not set(catalogue.positive_kinds).issubset(all_kinds):
        raise RegistryValidationError("IVA positive rate kinds must be declared in rate_kind.order")
    if catalogue.zero_token not in all_kinds or catalogue.exempt_token not in all_kinds:
        raise RegistryValidationError("IVA zero and exempt rate kinds must be declared in rate_kind.order")
    if catalogue.zero_token in catalogue.positive_kinds or catalogue.exempt_token in catalogue.positive_kinds:
        raise RegistryValidationError("IVA zero and exempt rate kinds cannot be positive tiers")
    return catalogue


def resolve_iva_rate_kind_catalogue(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> IvaRateKindCatalogue:
    """Resolve the complete IVA rate-kind vocabulary through fact 0094."""
    coordinate = effective_date or date.today()
    selected = authority or governed_facts_in_scope()
    if selected is None:
        raise RegistryValidationError("IVA rate-kind catalogue requires an explicit authority operation or scope")
    with validating_governed_facts(selected):
        return _scoped_catalogue(coordinate)


def require_iva_rate_kind(
    value: object,
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> IvaRateKind:
    """Return one rate-kind token only when fact 0094 declares it."""
    return resolve_iva_rate_kind_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).require(value)


def require_registry_declared_iva_rate_kind(value: object, *, effective_date: date) -> IvaRateKind:
    """Return one rate-kind token declared by the facts a validation is validating.

    A registry validator resolves its vocabulary from the candidate in scope,
    never from the published authority: the artifact reader validates the
    document it has just decoded while holding the shared-artifact lock, so a
    validator reaching for the bundle asks that lock for the artifact it is in
    the middle of producing and the process stops there. Absence of a scope is a
    refusal rather than a fallback, because the fallback is the deadlock.
    """
    authority = governed_facts_in_scope()
    if authority is None:
        raise RegistryValidationError(
            "IVA rate-kind validation requires the governed facts being validated to be in "
            "scope; registry validation must not resolve a rate kind through the published "
            "authority artifact",
        )
    return resolve_iva_rate_kind_catalogue(effective_date=effective_date, authority=authority).require(value)


__all__ = [
    "IvaRateKindCatalogue",
    "IvaRateKindDefinition",
    "require_iva_rate_kind",
    "require_registry_declared_iva_rate_kind",
    "resolve_iva_rate_kind_catalogue",
]
