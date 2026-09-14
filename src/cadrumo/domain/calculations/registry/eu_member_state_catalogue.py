"""Typed projection of the dated EU IVA member-state vocabulary (fact 0131)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from types import MappingProxyType

from ...iva.schema import EUMemberState
from .errors import RegistryValidationError
from .facts.resolution import MappingFactQuery, ResolvedMappingFact
from .governed_fact_scope import GovernedFactSource, governed_facts_in_scope
from .schema_base import DateAxis

_FACT_ID = "eu-member-state-catalogue"
_ORDER_KEY = "member_state.order"
_ALIASES_KEY = "member_state.aliases"


@dataclass(frozen=True, slots=True)
class EuMemberStateDefinition:
    """One registry-declared IVA member-state token and its aliases."""

    token: EUMemberState
    aliases: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EuMemberStateCatalogue:
    """Typed projection of the dated EU member-state vocabulary."""

    definitions: tuple[EuMemberStateDefinition, ...]
    aliases: Mapping[str, EUMemberState]

    @property
    def all_states(self) -> frozenset[EUMemberState]:
        """Return every member-state token declared by the selected fact."""
        return frozenset(definition.token for definition in self.definitions)

    @property
    def choices(self) -> tuple[EUMemberState, ...]:
        """Return member-state tokens in the authored order."""
        return tuple(definition.token for definition in self.definitions)

    def require(self, value: object) -> EUMemberState:
        """Project one token only when fact 0131 declares it."""
        if isinstance(value, EUMemberState):
            token = value
        elif isinstance(value, str):
            alias = value.strip().upper()
            if not alias:
                raise RegistryValidationError("EU member-state token must be non-empty")
            token = self.aliases.get(alias)
            if token is None:
                raise RegistryValidationError(
                    f"EU member-state token {value!r} is not declared by fact {_FACT_ID!r}",
                )
        else:
            raise RegistryValidationError("EU member-state token must be a string token")
        if token not in self.all_states:
            raise RegistryValidationError(
                f"EU member-state token {str(token)!r} is not declared by fact {_FACT_ID!r}",
            )
        return token

    def definition(self, value: object) -> EuMemberStateDefinition:
        """Return the authored definition for one projected token."""
        token = self.require(value)
        return next(definition for definition in self.definitions if definition.token == token)


def _required(entries: Mapping[str, str], key: str) -> str:
    value = entries.get(key)
    if value is None or not value.strip():
        raise RegistryValidationError(f"EU member-state catalogue is missing {key!r}")
    return value.strip()


def _csv(entries: Mapping[str, str], key: str) -> tuple[str, ...]:
    values = tuple(token.strip() for token in _required(entries, key).split(",") if token.strip())
    if not values or len(values) != len(set(values)):
        raise RegistryValidationError(f"EU member-state catalogue {key!r} must contain unique tokens")
    return values


def _mapping_entries(resolved: ResolvedMappingFact) -> Mapping[str, str]:
    entries: dict[str, str] = {}
    for entry in resolved.payload.entries:
        if not isinstance(entry.key, str) or not isinstance(entry.value, str):
            raise RegistryValidationError("EU member-state entries must be string-to-string")
        if entry.key in entries:
            raise RegistryValidationError(f"duplicate EU member-state key {entry.key!r}")
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
        raise RegistryValidationError("EU member-state catalogue must resolve as a mapping fact")
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


def resolve_eu_member_state_catalogue(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> EuMemberStateCatalogue:
    """Resolve the complete EU member-state vocabulary through fact 0131."""
    entries = _selected_entries(effective_date=effective_date, authority=authority)
    raw_order = _csv(entries, _ORDER_KEY)
    raw_aliases = _csv(entries, _ALIASES_KEY)
    aliases: dict[str, EUMemberState] = {}
    definitions: list[EuMemberStateDefinition] = []
    aliases_by_token: dict[EUMemberState, list[str]] = {}
    for raw_alias in raw_aliases:
        parts = raw_alias.split("=", 1)
        if len(parts) != 2:
            raise RegistryValidationError("EU member-state aliases must use ALIAS=token entries")
        alias, raw_token = (part.strip() for part in parts)
        if not alias or not raw_token:
            raise RegistryValidationError("EU member-state aliases must not be blank")
        token = EUMemberState._from_registry(raw_token.lower())
        alias_key = alias.upper()
        if alias_key in aliases and aliases[alias_key] != token:
            raise RegistryValidationError(f"EU member-state alias {alias!r} has conflicting targets")
        aliases[alias_key] = token
        aliases_by_token.setdefault(token, []).append(alias_key)
    for raw_token in raw_order:
        token = EUMemberState._from_registry(raw_token.lower())
        if token in {definition.token for definition in definitions}:
            raise RegistryValidationError(f"EU member-state catalogue repeats {raw_token!r}")
        if token not in aliases_by_token:
            raise RegistryValidationError(f"EU member-state {raw_token!r} has no declared alias")
        definitions.append(
            EuMemberStateDefinition(token=token, aliases=tuple(aliases_by_token[token])),
        )
    catalogue = EuMemberStateCatalogue(definitions=tuple(definitions), aliases=MappingProxyType(aliases))
    if len(catalogue.all_states) != len(raw_order):
        raise RegistryValidationError("EU member-state catalogue contains duplicate tokens")
    if any(alias_target not in catalogue.all_states for alias_target in aliases.values()):
        raise RegistryValidationError("EU member-state aliases target undeclared tokens")
    return catalogue


def require_eu_member_state(
    value: object,
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> EUMemberState:
    """Return one EU member-state token only when fact 0131 declares it."""
    return resolve_eu_member_state_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).require(value)


def require_registry_declared_eu_member_state(value: object, *, effective_date: date) -> EUMemberState:
    """Validate a token against the governed facts currently being decoded."""
    authority = governed_facts_in_scope()
    if authority is None:
        raise RegistryValidationError(
            "EU member-state validation requires the governed facts being validated to be in scope; "
            "registry validation must not resolve the published authority artifact",
        )
    return require_eu_member_state(value, effective_date=effective_date, authority=authority)


__all__ = [
    "EuMemberStateCatalogue",
    "EuMemberStateDefinition",
    "require_eu_member_state",
    "require_registry_declared_eu_member_state",
    "resolve_eu_member_state_catalogue",
]
