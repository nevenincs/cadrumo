"""Typed projection of the third-party declaration-role fact (0134)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType
from typing import Final

from ....core.aggregation import ThirdPartyDeclarationRole
from .errors import RegistryValidationError
from .facts.resolution import required_mapping_entry, unique_mapping_tokens
from .facts.string_mapping import (
    MappingValueWhitespace,
    StringMappingFact,
    StringMappingPolicy,
)
from .governed_fact_scope import GovernedFactSource
from .schema_base import DateAxis

_ENTRY_SUBJECT: Final = "third-party declaration role catalogue"

_FACT_ID = "third-party-declaration-role-catalogue"
_ORDER_KEY = "role.order"
_ROLE_PREFIX = "role."
_SELECTION_PREFIX = "selection."
_SELECTION_CLAVES = ("C", "D", "E")


@dataclass(frozen=True, slots=True)
class ThirdPartyDeclarationRoleDefinition:
    """One registry-declared third-party declaration role and its semantics."""

    token: ThirdPartyDeclarationRole
    description: str
    legal_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ThirdPartyDeclarationRoleCatalogue:
    """Complete typed projection of fact 0134 for one filing date."""

    declarations: Mapping[str, str]
    definitions: tuple[ThirdPartyDeclarationRoleDefinition, ...]
    selections: Mapping[str, tuple[ThirdPartyDeclarationRole, ...]]

    @property
    def roles(self) -> tuple[ThirdPartyDeclarationRole, ...]:
        """Return the registry-declared role choices in canonical order."""
        return tuple(item.token for item in self.definitions)

    @property
    def choices(self) -> tuple[ThirdPartyDeclarationRole, ...]:
        """Alias used by choice-building consumers."""
        return self.roles

    def require(self, value: object) -> ThirdPartyDeclarationRole:
        """Project one role only when fact 0134 declares it."""
        if isinstance(value, ThirdPartyDeclarationRole):
            token = value
        elif isinstance(value, str):
            raw = value.strip()
            if not raw:
                raise RegistryValidationError("third-party declaration role must be non-empty")
            try:
                token = ThirdPartyDeclarationRole.from_registry(raw)
            except (TypeError, ValueError) as exc:
                raise RegistryValidationError(
                    "third-party declaration role must be a non-empty string",
                ) from exc
        else:
            raise RegistryValidationError("third-party declaration role must be a string token")
        if token not in self.roles:
            raise RegistryValidationError(
                f"third-party declaration role {str(token)!r} is not declared by fact {_FACT_ID!r}",
            )
        return token

    def definition(self, value: object) -> ThirdPartyDeclarationRoleDefinition:
        """Return the selected role's registry-owned semantics."""
        token = self.require(value)
        return next(item for item in self.definitions if item.token == token)

    def roles_for_clave(self, clave: str) -> frozenset[ThirdPartyDeclarationRole]:
        """Return the registry-owned role population for one C/D/E selector."""
        normalized = clave.strip().upper()
        if normalized not in _SELECTION_CLAVES:
            raise RegistryValidationError(f"unsupported third-party declaration selection {clave!r}")
        return frozenset(self.selections[normalized])


_ENTRIES_POLICY = StringMappingPolicy(subject=_ENTRY_SUBJECT, value_whitespace=MappingValueWhitespace.PRESERVE)


_ENTRIES_FACT = StringMappingFact(fact_id=_FACT_ID, date_axis=DateAxis.FILING_PERIOD, policy=_ENTRIES_POLICY)


def _catalogue(entries: Mapping[str, str]) -> ThirdPartyDeclarationRoleCatalogue:
    definitions: list[ThirdPartyDeclarationRoleDefinition] = []
    for raw_token in unique_mapping_tokens(entries, _ORDER_KEY, subject=_ENTRY_SUBJECT):
        token = ThirdPartyDeclarationRole.from_registry(raw_token)
        prefix = f"{_ROLE_PREFIX}{raw_token}."
        if required_mapping_entry(entries, f"{prefix}value", subject=_ENTRY_SUBJECT) != raw_token:
            raise RegistryValidationError(
                f"third-party declaration role {raw_token!r} declares a mismatched value",
            )
        definitions.append(
            ThirdPartyDeclarationRoleDefinition(
                token=token,
                description=required_mapping_entry(entries, f"{prefix}description", subject=_ENTRY_SUBJECT),
                legal_refs=unique_mapping_tokens(entries, f"{prefix}legal_refs", subject=_ENTRY_SUBJECT),
            ),
        )
    if len(definitions) != len({item.token for item in definitions}):
        raise RegistryValidationError("third-party declaration role catalogue contains duplicate roles")

    role_choices = {item.token for item in definitions}
    selections: dict[str, tuple[ThirdPartyDeclarationRole, ...]] = {}
    for clave in _SELECTION_CLAVES:
        raw_roles = unique_mapping_tokens(entries, f"{_SELECTION_PREFIX}{clave}.roles", subject=_ENTRY_SUBJECT)
        selected = tuple(ThirdPartyDeclarationRole.from_registry(raw) for raw in raw_roles)
        if not set(selected).issubset(role_choices):
            raise RegistryValidationError(
                f"third-party declaration role selection {clave!r} contains an undeclared role",
            )
        selections[clave] = selected

    return ThirdPartyDeclarationRoleCatalogue(
        declarations=entries,
        definitions=tuple(definitions),
        selections=MappingProxyType(selections),
    )


def resolve_third_party_declaration_role_catalogue(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> ThirdPartyDeclarationRoleCatalogue:
    """Resolve the dated third-party declaration-role vocabulary."""
    return _catalogue(_ENTRIES_FACT.resolve_scoped_entries(effective_date=effective_date, authority=authority))


def require_third_party_declaration_role(
    value: object,
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> ThirdPartyDeclarationRole:
    """Project one role through the dated facts-registry catalogue."""
    return resolve_third_party_declaration_role_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).require(value)


def third_party_declaration_role_choices(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> tuple[ThirdPartyDeclarationRole, ...]:
    """Return registry-declared role choices in canonical order."""
    return resolve_third_party_declaration_role_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).roles


__all__ = [
    "ThirdPartyDeclarationRoleCatalogue",
    "ThirdPartyDeclarationRoleDefinition",
    "require_third_party_declaration_role",
    "resolve_third_party_declaration_role_catalogue",
    "third_party_declaration_role_choices",
]
