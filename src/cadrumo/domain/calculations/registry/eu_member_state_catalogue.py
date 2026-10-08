"""Typed projection of the dated EU IVA member-state vocabulary (fact 0131)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType
from typing import Final

from ....core.time.clock import today_madrid
from ...iva.schema import EUMemberState
from .errors import RegistryValidationError
from .facts.resolution import unique_mapping_tokens
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
    validating_governed_facts,
)
from .schema_base import DateAxis

_ENTRY_SUBJECT: Final = "EU member-state catalogue"

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
                    f"EU member-state token {value!r} is not declared by fact {_FACT_ID!r}; "
                    f"accepted tokens: {', '.join(map(str, self.choices))}",
                )
        else:
            raise RegistryValidationError("EU member-state token must be a string token")
        if token not in self.all_states:
            raise RegistryValidationError(
                f"EU member-state token {str(token)!r} is not declared by fact {_FACT_ID!r}; "
                f"accepted tokens: {', '.join(map(str, self.choices))}",
            )
        return token

    def definition(self, value: object) -> EuMemberStateDefinition:
        """Return the authored definition for one projected token."""
        token = self.require(value)
        return next(definition for definition in self.definitions if definition.token == token)


_ENTRIES_POLICY = StringMappingPolicy(subject=_ENTRY_SUBJECT, value_whitespace=MappingValueWhitespace.PRESERVE)


_ENTRIES_FACT = StringMappingFact(fact_id=_FACT_ID, date_axis=DateAxis.FILING_PERIOD, policy=_ENTRIES_POLICY)


@cache_governed_projection(maxsize=512)
def _scoped_catalogue(effective_date: date) -> EuMemberStateCatalogue:
    entries = _ENTRIES_FACT.resolve_scoped_entries(effective_date=effective_date, authority=None)
    raw_order = unique_mapping_tokens(entries, _ORDER_KEY, subject=_ENTRY_SUBJECT)
    raw_aliases = unique_mapping_tokens(entries, _ALIASES_KEY, subject=_ENTRY_SUBJECT)
    aliases, aliases_by_token = _member_state_aliases(raw_aliases)
    definitions = _member_state_definitions(raw_order, aliases_by_token)
    catalogue = EuMemberStateCatalogue(definitions=definitions, aliases=MappingProxyType(aliases))
    _validate_member_state_catalogue(catalogue, raw_order)
    return catalogue


def _member_state_aliases(
    raw_aliases: tuple[str, ...],
) -> tuple[dict[str, EUMemberState], dict[EUMemberState, list[str]]]:
    aliases: dict[str, EUMemberState] = {}
    aliases_by_token: dict[EUMemberState, list[str]] = {}
    for raw_alias in raw_aliases:
        parts = raw_alias.split("=", 1)
        if len(parts) != 2:
            raise RegistryValidationError("EU member-state aliases must use ALIAS=token entries")
        alias, raw_token = (part.strip() for part in parts)
        if not alias or not raw_token:
            raise RegistryValidationError("EU member-state aliases must not be blank")
        token = EUMemberState.from_registry(raw_token.lower())
        alias_key = alias.upper()
        if alias_key in aliases and aliases[alias_key] != token:
            raise RegistryValidationError(f"EU member-state alias {alias!r} has conflicting targets")
        aliases[alias_key] = token
        aliases_by_token.setdefault(token, []).append(alias_key)
    return aliases, aliases_by_token


def _member_state_definitions(
    raw_order: tuple[str, ...],
    aliases_by_token: Mapping[EUMemberState, list[str]],
) -> tuple[EuMemberStateDefinition, ...]:
    definitions: list[EuMemberStateDefinition] = []
    for raw_token in raw_order:
        token = EUMemberState.from_registry(raw_token.lower())
        if token in {definition.token for definition in definitions}:
            raise RegistryValidationError(f"EU member-state catalogue repeats {raw_token!r}")
        if token not in aliases_by_token:
            raise RegistryValidationError(f"EU member-state {raw_token!r} has no declared alias")
        definitions.append(
            EuMemberStateDefinition(token=token, aliases=tuple(aliases_by_token[token])),
        )
    return tuple(definitions)


def _validate_member_state_catalogue(
    catalogue: EuMemberStateCatalogue,
    raw_order: tuple[str, ...],
) -> None:
    if len(catalogue.all_states) != len(raw_order):
        raise RegistryValidationError("EU member-state catalogue contains duplicate tokens")
    if any(alias_target not in catalogue.all_states for alias_target in catalogue.aliases.values()):
        raise RegistryValidationError("EU member-state aliases target undeclared tokens")


def resolve_eu_member_state_catalogue(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> EuMemberStateCatalogue:
    """Resolve the complete EU member-state vocabulary through fact 0131."""
    coordinate = effective_date or today_madrid()
    selected = require_governed_fact_authority(authority, subject=_ENTRY_SUBJECT)
    with validating_governed_facts(selected):
        return _scoped_catalogue(coordinate)


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
