"""Typed projection of the third-party declaration-role fact (0134)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType
from typing import TYPE_CHECKING

from ....core.aggregation import ThirdPartyDeclarationRole
from .errors import RegistryValidationError
from .facts.resolution import MappingFactQuery, ResolvedMappingFact
from .governed_fact_scope import GovernedFactSource, cache_governed_projection, governed_facts_in_scope
from .schema_base import DateAxis

if TYPE_CHECKING:
    from .authority import ValidatedRegistryAuthority


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
                token = ThirdPartyDeclarationRole._from_registry(raw)
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


def _required(entries: Mapping[str, str], key: str) -> str:
    value = entries.get(key)
    if value is None or not value.strip():
        raise RegistryValidationError(f"third-party declaration role catalogue is missing {key!r}")
    return value.strip()


def _csv(entries: Mapping[str, str], key: str) -> tuple[str, ...]:
    values = tuple(token.strip() for token in _required(entries, key).split(",") if token.strip())
    if not values or len(values) != len(set(values)):
        raise RegistryValidationError(
            f"third-party declaration role catalogue {key!r} must contain unique tokens",
        )
    return values


def _refs(entries: Mapping[str, str], key: str) -> tuple[str, ...]:
    return _csv(entries, key)


def _mapping_entries(resolved: ResolvedMappingFact) -> Mapping[str, str]:
    entries: dict[str, str] = {}
    for entry in resolved.payload.entries:
        if not isinstance(entry.key, str) or not isinstance(entry.value, str):
            raise RegistryValidationError("third-party declaration role entries must be string-to-string")
        if entry.key in entries:
            raise RegistryValidationError(
                f"duplicate third-party declaration role catalogue key {entry.key!r}",
            )
        entries[entry.key] = entry.value
    return MappingProxyType(entries)


def _resolve_entries(*, effective_date: date, authority: GovernedFactSource) -> Mapping[str, str]:
    resolved = authority.resolve_governed_fact(
        MappingFactQuery(
            fact_id=_FACT_ID,
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date,
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise RegistryValidationError("third-party declaration role catalogue must resolve as a mapping fact")
    return _mapping_entries(resolved)


def _catalogue(entries: Mapping[str, str]) -> ThirdPartyDeclarationRoleCatalogue:
    definitions: list[ThirdPartyDeclarationRoleDefinition] = []
    for raw_token in _csv(entries, _ORDER_KEY):
        token = ThirdPartyDeclarationRole._from_registry(raw_token)
        prefix = f"{_ROLE_PREFIX}{raw_token}."
        if _required(entries, f"{prefix}value") != raw_token:
            raise RegistryValidationError(
                f"third-party declaration role {raw_token!r} declares a mismatched value",
            )
        definitions.append(
            ThirdPartyDeclarationRoleDefinition(
                token=token,
                description=_required(entries, f"{prefix}description"),
                legal_refs=_refs(entries, f"{prefix}legal_refs"),
            ),
        )
    if len(definitions) != len({item.token for item in definitions}):
        raise RegistryValidationError("third-party declaration role catalogue contains duplicate roles")

    role_choices = {item.token for item in definitions}
    selections: dict[str, tuple[ThirdPartyDeclarationRole, ...]] = {}
    for clave in _SELECTION_CLAVES:
        raw_roles = _csv(entries, f"{_SELECTION_PREFIX}{clave}.roles")
        selected = tuple(ThirdPartyDeclarationRole._from_registry(raw) for raw in raw_roles)
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


@cache_governed_projection(maxsize=64)
def _bundled_catalogue(effective_date: date) -> ThirdPartyDeclarationRoleCatalogue:
    from .authority import bundled_authority

    return _catalogue(_resolve_entries(
        effective_date=effective_date,
        authority=governed_facts_in_scope() or bundled_authority(),
    ))


def _selected_catalogue(
    *,
    effective_date: date,
    authority: ValidatedRegistryAuthority | None,
) -> ThirdPartyDeclarationRoleCatalogue:
    selected = authority or governed_facts_in_scope()
    if selected is None:
        return _bundled_catalogue(effective_date)
    return _catalogue(_resolve_entries(effective_date=effective_date, authority=selected))


def resolve_third_party_declaration_role_catalogue(
    *,
    effective_date: date | None = None,
    authority: ValidatedRegistryAuthority | None = None,
) -> ThirdPartyDeclarationRoleCatalogue:
    """Resolve the dated third-party declaration-role vocabulary."""
    coordinate = effective_date or date.today()
    return _selected_catalogue(effective_date=coordinate, authority=authority)


def require_third_party_declaration_role(
    value: object,
    *,
    effective_date: date | None = None,
    authority: ValidatedRegistryAuthority | None = None,
) -> ThirdPartyDeclarationRole:
    """Project one role through the dated facts-registry catalogue."""
    return resolve_third_party_declaration_role_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).require(value)


def third_party_declaration_role_choices(
    *,
    effective_date: date | None = None,
    authority: ValidatedRegistryAuthority | None = None,
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
