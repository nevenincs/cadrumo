"""Typed projection of the non-Modelo NIF-IVA country-format fact."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from types import MappingProxyType
from typing import TYPE_CHECKING

from ....core.identity.nif_iva import NifIvaFormatSpec, NifIvaPrefix
from .errors import RegistryValidationError
from .facts.resolution import MappingFactQuery, ResolvedMappingFact
from .schema_base import DateAxis

if TYPE_CHECKING:
    from .authority import ValidatedRegistryAuthority


_FACT_ID = "nif-iva-country-format-catalogue"
_ORDER_KEY = "nif_iva.order"
_PREFIX = "nif_iva.prefix."


@dataclass(frozen=True, slots=True)
class NifIvaDefinition:
    """One registry-declared NIF-IVA prefix and its structural format."""

    prefix: NifIvaPrefix
    iso_country: str
    iso_aliases: tuple[str, ...]
    spec: NifIvaFormatSpec


@dataclass(frozen=True, slots=True)
class NifIvaCatalogue:
    """Complete typed projection of the dated NIF-IVA country catalogue."""

    definitions: tuple[NifIvaDefinition, ...]

    @property
    def prefixes(self) -> frozenset[NifIvaPrefix]:
        return frozenset(item.prefix for item in self.definitions)

    def require_prefix(self, value: object) -> NifIvaPrefix:
        """Return a prefix only when the selected fact declares it."""
        if isinstance(value, NifIvaPrefix):
            token = value
        elif isinstance(value, str):
            raw = value.strip().upper()
            if not raw:
                raise RegistryValidationError("NIF-IVA prefix must be non-empty")
            token = NifIvaPrefix._from_registry(raw)
        else:
            raise RegistryValidationError("NIF-IVA prefix must be a string token")
        if token not in self.prefixes:
            raise RegistryValidationError(
                f"NIF-IVA prefix {str(token)!r} is not declared by fact {_FACT_ID!r}",
            )
        return token

    def definition(self, value: object) -> NifIvaDefinition:
        token = self.require_prefix(value)
        return next(item for item in self.definitions if item.prefix == token)

    def prefix_for_country(self, value: object) -> NifIvaPrefix | None:
        """Resolve an ISO/IVA country token, refusing undeclared countries."""
        if isinstance(value, NifIvaPrefix):
            return self.require_prefix(value)
        if not isinstance(value, str):
            return None
        country = value.strip().upper()
        if not country:
            return None
        return next(
            (item.prefix for item in self.definitions if country in item.iso_aliases),
            None,
        )

    def format_for_country(self, value: object) -> NifIvaFormatSpec | None:
        prefix = self.prefix_for_country(value)
        if prefix is None:
            return None
        return self.definition(prefix).spec

    def iso_country_for_prefix(self, value: object) -> str:
        return self.definition(value).iso_country


def _required(entries: Mapping[str, str], key: str) -> str:
    value = entries.get(key)
    if value is None or not value.strip():
        raise RegistryValidationError(f"NIF-IVA catalogue is missing {key!r}")
    return value.strip()


def _csv(entries: Mapping[str, str], key: str) -> tuple[str, ...]:
    values = tuple(token.strip() for token in _required(entries, key).split(",") if token.strip())
    if not values or len(values) != len(set(values)):
        raise RegistryValidationError(f"NIF-IVA catalogue {key!r} must contain unique tokens")
    return values


def _mapping_entries(resolved: ResolvedMappingFact) -> Mapping[str, str]:
    entries: dict[str, str] = {}
    for entry in resolved.payload.entries:
        if not isinstance(entry.key, str) or not isinstance(entry.value, str):
            raise RegistryValidationError("NIF-IVA catalogue entries must be string-to-string")
        if entry.key in entries:
            raise RegistryValidationError(f"duplicate NIF-IVA catalogue key {entry.key!r}")
        entries[entry.key] = entry.value
    return MappingProxyType(entries)


def _resolve_entries(
    *,
    effective_date: date,
    authority: ValidatedRegistryAuthority,
) -> Mapping[str, str]:
    resolved = authority.resolve_governed_fact(
        MappingFactQuery(
            fact_id=_FACT_ID,
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date,
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise RegistryValidationError("NIF-IVA country-format fact must resolve as a mapping")
    return _mapping_entries(resolved)


def _definition(entries: Mapping[str, str], raw_prefix: str) -> NifIvaDefinition:
    key = f"{_PREFIX}{raw_prefix}."
    if _required(entries, f"{key}value") != raw_prefix:
        raise RegistryValidationError(f"NIF-IVA prefix {raw_prefix!r} declares a mismatched value")
    prefix = NifIvaPrefix._from_registry(raw_prefix)
    iso_country = _required(entries, f"{key}iso_country").upper()
    iso_aliases = tuple(alias.upper() for alias in _csv(entries, f"{key}iso_aliases"))
    if iso_country not in iso_aliases:
        raise RegistryValidationError(f"NIF-IVA prefix {raw_prefix!r} omits its canonical ISO country")
    pattern = _required(entries, f"{key}pattern")
    if not pattern.startswith("^") or not pattern.endswith("$"):
        raise RegistryValidationError(f"NIF-IVA prefix {raw_prefix!r} pattern must be anchored")
    try:
        compiled = re.compile(pattern)
    except re.error as exc:
        raise RegistryValidationError(f"NIF-IVA prefix {raw_prefix!r} pattern is invalid") from exc
    example = _required(entries, f"{key}example")
    if compiled.fullmatch(example) is None:
        raise RegistryValidationError(f"NIF-IVA prefix {raw_prefix!r} example does not match its pattern")
    return NifIvaDefinition(
        prefix=prefix,
        iso_country=iso_country,
        iso_aliases=iso_aliases,
        spec=NifIvaFormatSpec(
            prefix=prefix,
            country_name=_required(entries, f"{key}country_name"),
            pattern=compiled,
            description=_required(entries, f"{key}description"),
            example=example,
        ),
    )


def _catalogue(entries: Mapping[str, str]) -> NifIvaCatalogue:
    definitions = tuple(_definition(entries, raw_prefix) for raw_prefix in _csv(entries, _ORDER_KEY))
    prefixes = [item.prefix for item in definitions]
    if len(prefixes) != len(set(prefixes)):
        raise RegistryValidationError("NIF-IVA catalogue contains duplicate prefixes")
    countries = [country for item in definitions for country in item.iso_aliases]
    if len(countries) != len(set(countries)):
        raise RegistryValidationError("NIF-IVA catalogue contains duplicate country aliases")
    if "ES" in countries:
        raise RegistryValidationError("Spain must remain absent from the NIF-IVA structural catalogue")
    return NifIvaCatalogue(definitions=definitions)


@lru_cache(maxsize=64)
def _bundled_catalogue(effective_date: date) -> NifIvaCatalogue:
    from .authority import bundled_authority

    return _catalogue(_resolve_entries(effective_date=effective_date, authority=bundled_authority()))


def resolve_nif_iva_catalogue(
    *,
    effective_date: date | None = None,
    authority: ValidatedRegistryAuthority | None = None,
) -> NifIvaCatalogue:
    """Resolve the selected NIF-IVA country/format fact."""
    coordinate = effective_date or date.today()
    if authority is None:
        return _bundled_catalogue(coordinate)
    return _catalogue(_resolve_entries(effective_date=coordinate, authority=authority))


def iso_country_for_nif_iva_prefix(prefix: NifIvaPrefix) -> str:
    """Return the catalogue country for a projected IVA prefix."""
    return resolve_nif_iva_catalogue().iso_country_for_prefix(prefix)


def nif_iva_prefix_for_country(iso_country: str) -> NifIvaPrefix | None:
    """Resolve a country or IVA prefix through the dated catalogue."""
    return resolve_nif_iva_catalogue().prefix_for_country(iso_country)


def nif_iva_format_for_country(iso_country: str) -> NifIvaFormatSpec | None:
    """Return the published structural format for a country, when declared."""
    return resolve_nif_iva_catalogue().format_for_country(iso_country)


__all__ = [
    "NifIvaCatalogue",
    "NifIvaDefinition",
    "iso_country_for_nif_iva_prefix",
    "nif_iva_format_for_country",
    "nif_iva_prefix_for_country",
    "resolve_nif_iva_catalogue",
]
