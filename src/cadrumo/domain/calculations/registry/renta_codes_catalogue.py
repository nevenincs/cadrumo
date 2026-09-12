"""Typed projections for the cross-cutting Renta residency catalogues."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from types import MappingProxyType
from typing import TYPE_CHECKING

from ...contribuyente.renta_codes import FiscalResidency
from .errors import RegistryValidationError
from .facts.resolution import (
    EntitySetFactQuery,
    MappingFactQuery,
    ResolvedEntitySetFact,
    ResolvedMappingFact,
)
from .schema_base import DateAxis

if TYPE_CHECKING:
    from .authority import ValidatedRegistryAuthority


_FISCAL_RESIDENCY_FACT_ID = "renta-fiscal-residency-vocabulary"
_EU_EEA_COUNTRY_FACT_ID = "eu-eea-country-membership"
_FISCAL_RESIDENCY_ORDER_KEY = "fiscal_residency.order"
_FISCAL_RESIDENCY_DEFAULT_KEY = "fiscal_residency.default_token"
_FISCAL_RESIDENCY_PREFIX = "fiscal_residency."


@dataclass(frozen=True, slots=True)
class FiscalResidencyDefinition:
    """One registry-declared fiscal-residency token and its semantics."""

    token: FiscalResidency
    description: str
    tax_regime: str
    requires_country: bool
    is_default: bool


@dataclass(frozen=True, slots=True)
class FiscalResidencyCatalogue:
    """Typed projection of the dated fiscal-residency vocabulary."""

    definitions: tuple[FiscalResidencyDefinition, ...]
    default_token: FiscalResidency

    @property
    def all_residencies(self) -> frozenset[FiscalResidency]:
        return frozenset(definition.token for definition in self.definitions)

    @property
    def choices(self) -> tuple[FiscalResidency, ...]:
        return tuple(definition.token for definition in self.definitions)

    def require(self, value: object) -> FiscalResidency:
        """Project one token only when the selected fact declares it."""
        if isinstance(value, FiscalResidency):
            token = value
        elif isinstance(value, str):
            raw = value.strip()
            if not raw:
                raise RegistryValidationError("fiscal-residency token must be non-empty")
            if raw not in {str(item) for item in self.all_residencies}:
                raise RegistryValidationError(f"fiscal-residency token {raw!r} is not declared by the facts registry")
            token = FiscalResidency._from_registry(raw)
        else:
            raise RegistryValidationError("fiscal-residency token must be a string token")
        if token not in self.all_residencies:
            raise RegistryValidationError(
                f"fiscal-residency token {str(token)!r} is not declared by the facts registry",
            )
        return token

    def definition(self, value: object) -> FiscalResidencyDefinition:
        token = self.require(value)
        return next(item for item in self.definitions if item.token == token)


def _required(entries: Mapping[str, str], key: str) -> str:
    value = entries.get(key)
    if value is None or not value.strip():
        raise RegistryValidationError(f"fiscal-residency catalogue is missing {key!r}")
    return value.strip()


def _csv(entries: Mapping[str, str], key: str) -> tuple[str, ...]:
    values = tuple(token.strip() for token in _required(entries, key).split(",") if token.strip())
    if not values or len(values) != len(set(values)):
        raise RegistryValidationError(f"fiscal-residency catalogue {key!r} must contain unique tokens")
    return values


def _boolean(entries: Mapping[str, str], key: str) -> bool:
    value = _required(entries, key)
    if value not in {"true", "false"}:
        raise RegistryValidationError(f"fiscal-residency catalogue {key!r} must be true or false")
    return value == "true"


def _mapping_entries(resolved: ResolvedMappingFact) -> Mapping[str, str]:
    entries: dict[str, str] = {}
    for entry in resolved.payload.entries:
        if not isinstance(entry.key, str) or not isinstance(entry.value, str):
            raise RegistryValidationError("fiscal-residency mapping entries must be string-to-string")
        if entry.key in entries:
            raise RegistryValidationError(f"duplicate fiscal-residency mapping key {entry.key!r}")
        entries[entry.key] = entry.value
    return MappingProxyType(entries)


def _resolve_mapping_entries(
    *,
    effective_date: date,
    authority: ValidatedRegistryAuthority,
) -> Mapping[str, str]:
    resolved = authority.resolve_governed_fact(
        MappingFactQuery(
            fact_id=_FISCAL_RESIDENCY_FACT_ID,
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date,
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise RegistryValidationError("fiscal-residency catalogue must resolve as a mapping fact")
    return _mapping_entries(resolved)


@lru_cache(maxsize=64)
def _bundled_mapping_entries(effective_date: date) -> Mapping[str, str]:
    from .authority import bundled_authority

    return _resolve_mapping_entries(effective_date=effective_date, authority=bundled_authority())


def _selected_mapping_entries(
    *,
    effective_date: date | None,
    authority: ValidatedRegistryAuthority | None,
) -> Mapping[str, str]:
    coordinate = effective_date or date.today()
    if authority is None:
        return _bundled_mapping_entries(coordinate)
    return _resolve_mapping_entries(effective_date=coordinate, authority=authority)


def resolve_fiscal_residency_catalogue(
    *,
    effective_date: date | None = None,
    authority: ValidatedRegistryAuthority | None = None,
) -> FiscalResidencyCatalogue:
    """Resolve the dated fiscal-residency vocabulary through fact 0122."""
    entries = _selected_mapping_entries(effective_date=effective_date, authority=authority)
    definitions: list[FiscalResidencyDefinition] = []
    for raw_token in _csv(entries, _FISCAL_RESIDENCY_ORDER_KEY):
        prefix = f"{_FISCAL_RESIDENCY_PREFIX}{raw_token}."
        if _required(entries, f"{prefix}value") != raw_token:
            raise RegistryValidationError(f"fiscal-residency token {raw_token!r} declares a mismatched value")
        definitions.append(
            FiscalResidencyDefinition(
                token=FiscalResidency._from_registry(raw_token),
                description=_required(entries, f"{prefix}description"),
                tax_regime=_required(entries, f"{prefix}tax_regime"),
                requires_country=_boolean(entries, f"{prefix}requires_country"),
                is_default=_boolean(entries, f"{prefix}default"),
            ),
        )
    catalogue = FiscalResidencyCatalogue(
        definitions=tuple(definitions),
        default_token=FiscalResidency._from_registry(_required(entries, _FISCAL_RESIDENCY_DEFAULT_KEY)),
    )
    if len(catalogue.all_residencies) != len(catalogue.definitions):
        raise RegistryValidationError("fiscal-residency catalogue has duplicate tokens")
    if catalogue.default_token not in catalogue.all_residencies:
        raise RegistryValidationError("fiscal-residency default token is not declared in the order")
    if sum(definition.is_default for definition in catalogue.definitions) != 1:
        raise RegistryValidationError("fiscal-residency catalogue must declare exactly one default token")
    if next(definition for definition in catalogue.definitions if definition.is_default).token != catalogue.default_token:
        raise RegistryValidationError("fiscal-residency default declaration disagrees with default_token")
    return catalogue


def require_fiscal_residency(
    value: object,
    *,
    effective_date: date | None = None,
    authority: ValidatedRegistryAuthority | None = None,
) -> FiscalResidency:
    """Project one registry-governed fiscal-residency token."""
    return resolve_fiscal_residency_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).require(value)


def fiscal_residency_choices(
    *,
    effective_date: date | None = None,
    authority: ValidatedRegistryAuthority | None = None,
) -> tuple[FiscalResidency, ...]:
    """Return fiscal-residency choices in authored order."""
    return resolve_fiscal_residency_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).choices


def default_fiscal_residency(
    *,
    effective_date: date | None = None,
    authority: ValidatedRegistryAuthority | None = None,
) -> FiscalResidency:
    """Return the registry-declared default residency token."""
    return resolve_fiscal_residency_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).default_token


def fiscal_residency_requires_country(
    value: FiscalResidency | str | None,
    *,
    effective_date: date | None = None,
    authority: ValidatedRegistryAuthority | None = None,
) -> bool:
    """Return the registry-declared country requirement for one token."""
    if value is None or value == "":
        return False
    return resolve_fiscal_residency_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).definition(value).requires_country


def _resolve_country_entities(
    *,
    effective_date: date,
    authority: ValidatedRegistryAuthority,
) -> frozenset[str]:
    resolved = authority.resolve_governed_fact(
        EntitySetFactQuery(
            fact_id=_EU_EEA_COUNTRY_FACT_ID,
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date,
        ),
    )
    if not isinstance(resolved, ResolvedEntitySetFact):
        raise RegistryValidationError("EU/EEA country membership must resolve as an entity-set fact")
    entities = tuple(str(entity).strip().upper() for entity in resolved.payload.entities)
    if not entities or len(entities) != len(set(entities)) or any(len(entity) != 2 for entity in entities):
        raise RegistryValidationError("EU/EEA country membership must contain unique two-letter country codes")
    return frozenset(entities)


@lru_cache(maxsize=64)
def _bundled_country_entities(effective_date: date) -> frozenset[str]:
    from .authority import bundled_authority

    return _resolve_country_entities(effective_date=effective_date, authority=bundled_authority())


def ue_eea_country_codes(
    *,
    effective_date: date | None = None,
    authority: ValidatedRegistryAuthority | None = None,
) -> frozenset[str]:
    """Return the selected EU/EEA country-code entity set from fact 0123."""
    coordinate = effective_date or date.today()
    if authority is None:
        return _bundled_country_entities(coordinate)
    return _resolve_country_entities(effective_date=coordinate, authority=authority)


def is_ue_eea_country_code(
    country_code: str | None,
    *,
    effective_date: date | None = None,
    authority: ValidatedRegistryAuthority | None = None,
) -> bool:
    """Return whether a country token is in the selected EU/EEA entity set."""
    if country_code is None:
        return False
    return country_code.strip().upper() in ue_eea_country_codes(
        effective_date=effective_date,
        authority=authority,
    )


__all__ = [
    "FiscalResidencyCatalogue",
    "FiscalResidencyDefinition",
    "default_fiscal_residency",
    "fiscal_residency_choices",
    "fiscal_residency_requires_country",
    "is_ue_eea_country_code",
    "require_fiscal_residency",
    "resolve_fiscal_residency_catalogue",
    "ue_eea_country_codes",
]
