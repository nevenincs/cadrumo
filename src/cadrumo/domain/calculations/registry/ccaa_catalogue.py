"""Typed projection of the Spanish CCAA tax-residence catalogue."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType

from ....core.text_fold import fold_diacritics
from ...contribuyente.ccaa import CCAA
from .errors import RegistryValidationError
from .facts.resolution import MappingFactQuery, ResolvedMappingFact
from .governed_fact_scope import GovernedFactSource, governed_facts_in_scope
from .schema_base import DateAxis

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


def _required(entries: Mapping[str, str], key: str) -> str:
    value = entries.get(key)
    if value is None or not value.strip():
        raise RegistryValidationError(f"CCAA catalogue is missing {key!r}")
    return value.strip()


def _csv(entries: Mapping[str, str], key: str) -> tuple[str, ...]:
    values = tuple(token.strip() for token in _required(entries, key).split(",") if token.strip())
    if not values or len(values) != len(set(values)):
        raise RegistryValidationError(f"CCAA catalogue {key!r} must contain unique tokens")
    return values


def _boolean(entries: Mapping[str, str], key: str) -> bool:
    value = _required(entries, key)
    if value not in {"true", "false"}:
        raise RegistryValidationError(f"CCAA catalogue {key!r} must be true or false")
    return value == "true"


def _mapping_entries(resolved: ResolvedMappingFact) -> Mapping[str, str]:
    entries: dict[str, str] = {}
    for entry in resolved.payload.entries:
        if not isinstance(entry.key, str) or not isinstance(entry.value, str):
            raise RegistryValidationError("CCAA catalogue entries must be string-to-string")
        if entry.key in entries:
            raise RegistryValidationError(f"duplicate CCAA catalogue key {entry.key!r}")
        entries[entry.key] = entry.value
    return MappingProxyType(entries)


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
        raise RegistryValidationError("CCAA tax-residence catalogue must resolve as a mapping fact")
    return _mapping_entries(resolved)


def _catalogue(entries: Mapping[str, str]) -> CcaaCatalogue:
    raw_tokens = _csv(entries, _CCAA_ORDER_KEY)
    definitions: list[CcaaDefinition] = []
    for raw_token in raw_tokens:
        token = _normalize_token(raw_token)
        if token != raw_token:
            raise RegistryValidationError(f"CCAA token {raw_token!r} is not canonical")
        prefix = f"{_CCAA_PREFIX}{raw_token}."
        if _required(entries, f"{prefix}value") != raw_token:
            raise RegistryValidationError(f"CCAA token {raw_token!r} declares a mismatched value")
        member_name = _required(entries, f"{prefix}member_name").upper()
        definitions.append(
            CcaaDefinition(token=CCAA.from_registry(raw_token), member_name=member_name),
        )
    tokens = [definition.token for definition in definitions]
    if len(tokens) != len(set(tokens)):
        raise RegistryValidationError("CCAA catalogue contains duplicate common-regime tokens")
    member_names = [definition.member_name for definition in definitions]
    if len(member_names) != len(set(member_names)):
        raise RegistryValidationError("CCAA catalogue contains duplicate member names")

    token_set = frozenset(tokens)
    iso_aliases: dict[str, CCAA] = {}
    for alias in _csv(entries, _ISO_ORDER_KEY):
        normalized_alias = alias.upper()
        if normalized_alias != alias:
            raise RegistryValidationError(f"CCAA ISO alias {alias!r} must be uppercase")
        prefix = f"{_ISO_PREFIX}{alias}."
        target = CCAA.from_registry(_required(entries, f"{prefix}value"))
        if target not in token_set:
            raise RegistryValidationError(f"CCAA ISO alias {alias!r} targets an undeclared token")
        if target != CCAA.from_registry(_required(entries, f"{prefix}ccaa")):
            raise RegistryValidationError(f"CCAA ISO alias {alias!r} has inconsistent target metadata")
        if alias in iso_aliases:
            raise RegistryValidationError(f"duplicate CCAA ISO alias {alias!r}")
        iso_aliases[alias] = target

    raw_foral_aliases = _csv(entries, _FORAL_ORDER_KEY)
    foral_aliases = frozenset(_normalize_token(alias) for alias in raw_foral_aliases)
    if foral_aliases & {str(token) for token in token_set}:
        raise RegistryValidationError("foral aliases must remain outside the common-regime CCAA vocabulary")
    excluded_territories = frozenset(_normalize_token(value) for value in _csv(entries, _EXCLUDED_ORDER_KEY))
    for territory in excluded_territories:
        _required(entries, f"{_EXCLUDED_PREFIX}{territory}.classification")
        _required(entries, f"{_EXCLUDED_PREFIX}{territory}.iso_aliases")
    if not foral_aliases <= excluded_territories:
        raise RegistryValidationError("every foral alias must identify an excluded territory")
    foral_cli_aliases = tuple(
        _normalize_token(alias)
        for alias in raw_foral_aliases
        if _boolean(entries, f"{_FORAL_PREFIX}{alias}.operator_choice")
    )
    for alias in raw_foral_aliases:
        target = _normalize_token(_required(entries, f"{_FORAL_PREFIX}{alias}.value"))
        if target not in excluded_territories:
            raise RegistryValidationError(f"foral alias {alias!r} targets an undeclared excluded territory")
        _required(entries, f"{_FORAL_PREFIX}{alias}.classification")
    default_token = CCAA.from_registry(_required(entries, _CCAA_DEFAULT_KEY))
    if default_token not in token_set:
        raise RegistryValidationError("CCAA catalogue default token is not in the common-regime order")
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
    coordinate = effective_date or date.today()
    authority = authority or governed_facts_in_scope()
    if authority is None:
        raise RegistryValidationError(
            "CCAA catalogue resolution requires a generation-pinned governed-fact source",
        )
    return _catalogue(_resolve_entries(effective_date=coordinate, authority=authority))


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
