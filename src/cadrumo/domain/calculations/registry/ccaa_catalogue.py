"""Typed projection of the Spanish CCAA tax-residence catalogue."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType
from typing import Final

from ....core.text_fold import fold_diacritics
from ...contribuyente.ccaa import CCAA
from .errors import RegistryValidationError
from .facts.resolution import required_mapping_entry, unique_mapping_tokens
from .facts.string_mapping import (
    BooleanTokenCase,
    MappingValueWhitespace,
    StringMappingFact,
    StringMappingPolicy,
    required_mapping_boolean,
)
from .governed_fact_scope import GovernedFactSource
from .schema_base import DateAxis

_ENTRY_SUBJECT: Final = "CCAA catalogue"

_FACT_ID = "renta-ccaa-tax-residence-catalogue"
_CCAA_ORDER_KEY = "ccaa.order"
_CCAA_DEFAULT_KEY = "ccaa.default_token"
_CCAA_PREFIX = "ccaa."
_ISO_ORDER_KEY = "ccaa.iso_alias.order"
_ISO_PREFIX = "ccaa.iso_alias."
_FORAL_ORDER_KEY = "foral_alias.order"
_FORAL_PREFIX = "foral_alias."
_EXCLUDED_ORDER_KEY = "territory_exclusion.order"
_EXCLUDED_PREFIX = "territory_exclusion."


@dataclass(frozen=True, slots=True)
class CcaaDefinition:
    """One registry-declared common-regime autonomous community."""

    token: CCAA
    member_name: str


@dataclass(frozen=True, slots=True)
class CcaaCatalogue:
    """Complete typed projection of the dated CCAA residence catalogue."""

    definitions: tuple[CcaaDefinition, ...]
    default_token: CCAA
    iso_aliases: Mapping[str, CCAA]
    foral_aliases: frozenset[str]
    foral_cli_aliases: tuple[str, ...]
    excluded_territories: frozenset[str]

    @property
    def choices(self) -> tuple[CCAA, ...]:
        """Return CCAA tokens in registry-authored order."""
        return tuple(definition.token for definition in self.definitions)

    @property
    def tokens(self) -> frozenset[CCAA]:
        """Return the set of CCAA tokens declared by the catalogue."""
        return frozenset(self.choices)

    def require(self, value: object) -> CCAA:
        """Project one token only when it is declared by the selected fact."""
        if isinstance(value, CCAA):
            token = value
        elif isinstance(value, str):
            raw = value.strip()
            if not raw:
                raise RegistryValidationError("CCAA token must be non-empty")
            normalized = _normalize_token(raw)
            if normalized in {str(item) for item in self.tokens}:
                token = CCAA.from_registry(normalized)
            else:
                token = self.iso_aliases.get(raw.upper())
                if token is None:
                    raise RegistryValidationError(
                        f"CCAA token or ISO alias {value!r} is not declared by fact {_FACT_ID!r}",
                    )
        else:
            raise RegistryValidationError("CCAA must be a string token")
        if token not in self.tokens:
            raise RegistryValidationError(
                f"CCAA token {str(token)!r} is not declared by fact {_FACT_ID!r}",
            )
        return token

    def require_member_name(self, name: str) -> CCAA:
        """Project a historical enum-style member name from the catalogue."""
        normalized = name.strip().upper()
        for definition in self.definitions:
            if definition.member_name == normalized:
                return definition.token
        raise KeyError(name)

    def from_iso_code(self, code: str) -> CCAA:
        """Resolve a declared three-letter ISO-like alias."""
        if not isinstance(code, str):
            raise KeyError(code)
        normalized = code.strip().upper()
        token = self.iso_aliases.get(normalized)
        if token is None:
            valid = ", ".join(sorted(self.iso_aliases))
            raise KeyError(f"unknown ISO CCAA code {code!r}; recognised codes: {valid}")
        return token

    def from_label(self, label: str) -> CCAA:
        """Resolve a normalized common-regime label or ISO alias."""
        if not isinstance(label, str):
            raise KeyError(label)
        normalized = _normalize_token(label)
        if normalized in self.foral_aliases:
            raise KeyError(f"{label!r} denotes an excluded foral territory")
        return self.require(normalized if normalized in {str(item) for item in self.tokens} else label)

    def is_foral_alias(self, normalized: str) -> bool:
        """Return whether a normalized input is a declared foral redirect."""
        return normalized in self.foral_aliases


def _normalize_token(value: str) -> str:
    return fold_diacritics(value.strip().casefold().replace(" ", "_").replace("-", "_"))


_ENTRIES_POLICY = StringMappingPolicy(subject=_ENTRY_SUBJECT, value_whitespace=MappingValueWhitespace.PRESERVE)


_ENTRIES_FACT = StringMappingFact(fact_id=_FACT_ID, date_axis=DateAxis.FILING_PERIOD, policy=_ENTRIES_POLICY)


def _ccaa_definitions(entries: Mapping[str, str]) -> tuple[list[CcaaDefinition], frozenset[CCAA]]:
    raw_tokens = unique_mapping_tokens(entries, _CCAA_ORDER_KEY, subject=_ENTRY_SUBJECT)
    definitions: list[CcaaDefinition] = []
    for raw_token in raw_tokens:
        token = _normalize_token(raw_token)
        if token != raw_token:
            raise RegistryValidationError(f"CCAA token {raw_token!r} is not canonical")
        prefix = f"{_CCAA_PREFIX}{raw_token}."
        if required_mapping_entry(entries, f"{prefix}value", subject=_ENTRY_SUBJECT) != raw_token:
            raise RegistryValidationError(f"CCAA token {raw_token!r} declares a mismatched value")
        member_name = required_mapping_entry(entries, f"{prefix}member_name", subject=_ENTRY_SUBJECT).upper()
        definitions.append(
            CcaaDefinition(token=CCAA.from_registry(raw_token), member_name=member_name),
        )
    tokens = [definition.token for definition in definitions]
    if len(tokens) != len(set(tokens)):
        raise RegistryValidationError("CCAA catalogue contains duplicate common-regime tokens")
    member_names = [definition.member_name for definition in definitions]
    if len(member_names) != len(set(member_names)):
        raise RegistryValidationError("CCAA catalogue contains duplicate member names")
    return definitions, frozenset(tokens)


def _iso_aliases(entries: Mapping[str, str], token_set: frozenset[CCAA]) -> dict[str, CCAA]:
    iso_aliases: dict[str, CCAA] = {}
    for alias in unique_mapping_tokens(entries, _ISO_ORDER_KEY, subject=_ENTRY_SUBJECT):
        normalized_alias = alias.upper()
        if normalized_alias != alias:
            raise RegistryValidationError(f"CCAA ISO alias {alias!r} must be uppercase")
        prefix = f"{_ISO_PREFIX}{alias}."
        target = CCAA.from_registry(required_mapping_entry(entries, f"{prefix}value", subject=_ENTRY_SUBJECT))
        if target not in token_set:
            raise RegistryValidationError(f"CCAA ISO alias {alias!r} targets an undeclared token")
        if target != CCAA.from_registry(required_mapping_entry(entries, f"{prefix}ccaa", subject=_ENTRY_SUBJECT)):
            raise RegistryValidationError(f"CCAA ISO alias {alias!r} has inconsistent target metadata")
        if alias in iso_aliases:
            raise RegistryValidationError(f"duplicate CCAA ISO alias {alias!r}")
        iso_aliases[alias] = target
    return iso_aliases


def _foral_aliases(
    entries: Mapping[str, str],
    token_set: frozenset[CCAA],
) -> tuple[tuple[str, ...], frozenset[str]]:
    raw_foral_aliases = unique_mapping_tokens(entries, _FORAL_ORDER_KEY, subject=_ENTRY_SUBJECT)
    foral_aliases = frozenset(_normalize_token(alias) for alias in raw_foral_aliases)
    if foral_aliases & {str(token) for token in token_set}:
        raise RegistryValidationError("foral aliases must remain outside the common-regime CCAA vocabulary")
    return raw_foral_aliases, foral_aliases


def _excluded_territories(entries: Mapping[str, str]) -> frozenset[str]:
    excluded_territories = frozenset(
        _normalize_token(value) for value in unique_mapping_tokens(entries, _EXCLUDED_ORDER_KEY, subject=_ENTRY_SUBJECT)
    )
    for territory in excluded_territories:
        required_mapping_entry(entries, f"{_EXCLUDED_PREFIX}{territory}.classification", subject=_ENTRY_SUBJECT)
        required_mapping_entry(entries, f"{_EXCLUDED_PREFIX}{territory}.iso_aliases", subject=_ENTRY_SUBJECT)
    return excluded_territories


def _validate_foral_exclusions(foral_aliases: frozenset[str], excluded_territories: frozenset[str]) -> None:
    if not foral_aliases <= excluded_territories:
        raise RegistryValidationError("every foral alias must identify an excluded territory")


def _foral_cli_aliases(
    entries: Mapping[str, str],
    raw_foral_aliases: tuple[str, ...],
    excluded_territories: frozenset[str],
) -> tuple[str, ...]:
    foral_cli_aliases = tuple(
        _normalize_token(alias)
        for alias in raw_foral_aliases
        if required_mapping_boolean(
            entries, f"{_FORAL_PREFIX}{alias}.operator_choice", subject=_ENTRY_SUBJECT, case=BooleanTokenCase.EXACT
        )
    )
    for alias in raw_foral_aliases:
        target = _normalize_token(
            required_mapping_entry(entries, f"{_FORAL_PREFIX}{alias}.value", subject=_ENTRY_SUBJECT)
        )
        if target not in excluded_territories:
            raise RegistryValidationError(f"foral alias {alias!r} targets an undeclared excluded territory")
        required_mapping_entry(entries, f"{_FORAL_PREFIX}{alias}.classification", subject=_ENTRY_SUBJECT)
    return foral_cli_aliases


def _default_token(entries: Mapping[str, str], token_set: frozenset[CCAA]) -> CCAA:
    default_token = CCAA.from_registry(required_mapping_entry(entries, _CCAA_DEFAULT_KEY, subject=_ENTRY_SUBJECT))
    if default_token not in token_set:
        raise RegistryValidationError("CCAA catalogue default token is not in the common-regime order")
    return default_token


def _catalogue(entries: Mapping[str, str]) -> CcaaCatalogue:
    definitions, token_set = _ccaa_definitions(entries)
    iso_aliases = _iso_aliases(entries, token_set)
    raw_foral_aliases, foral_aliases = _foral_aliases(entries, token_set)
    excluded_territories = _excluded_territories(entries)
    _validate_foral_exclusions(foral_aliases, excluded_territories)
    foral_cli_aliases = _foral_cli_aliases(entries, raw_foral_aliases, excluded_territories)
    default_token = _default_token(entries, token_set)
    return CcaaCatalogue(
        definitions=tuple(definitions),
        default_token=default_token,
        iso_aliases=MappingProxyType(iso_aliases),
        foral_aliases=foral_aliases,
        foral_cli_aliases=foral_cli_aliases,
        excluded_territories=excluded_territories,
    )


def resolve_ccaa_catalogue(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> CcaaCatalogue:
    """Resolve the selected dated CCAA tax-residence fact."""
    return _catalogue(_ENTRIES_FACT.resolve_scoped_entries(effective_date=effective_date, authority=authority))


def require_ccaa(
    value: object,
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> CCAA:
    """Project a common-regime CCAA token through the selected facts."""
    return resolve_ccaa_catalogue(effective_date=effective_date, authority=authority).require(value)


def ccaa_choices(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> tuple[CCAA, ...]:
    """Return the registry-authored CCAA choices in authored order."""
    return resolve_ccaa_catalogue(effective_date=effective_date, authority=authority).choices


def default_ccaa(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> CCAA:
    """Return the profile default declared by the CCAA catalogue."""
    return resolve_ccaa_catalogue(effective_date=effective_date, authority=authority).default_token


__all__ = [
    "CcaaCatalogue",
    "CcaaDefinition",
    "ccaa_choices",
    "default_ccaa",
    "require_ccaa",
    "resolve_ccaa_catalogue",
]
