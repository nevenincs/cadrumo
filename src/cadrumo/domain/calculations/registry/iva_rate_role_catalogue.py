"""Typed projection of the IVA rate-role vocabulary and default."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType
from typing import TYPE_CHECKING, Self

from .errors import RegistryValidationError
from .facts.resolution import MappingFactQuery, ResolvedMappingFact
from .facts.schema import FactSelector
from .governed_fact_scope import GovernedFactSource, governed_facts_in_scope
from .schema_base import DateAxis

if TYPE_CHECKING:
    pass


_FACT_ID = "iva-rate-schedule"
_SCOPE_SELECTOR = FactSelector(name="scope", value="rate_role_catalogue")
_ORDER_KEY = "rate_role.order"
_DEFAULT_KEY = "rate_role.default"
_PREFIX = "rate_role."


class IvaRateRole(str):
    """Opaque IVA rate-role token projected from the facts registry."""

    __slots__ = ()

    def __new__(cls, value: str, *, _registry_validated: bool = False) -> Self:
        """Construct a rate-role token after registry validation."""
        if not _registry_validated:
            raise TypeError("IvaRateRole tokens must be projected from the facts registry")
        if not isinstance(value, str) or not value.strip():
            raise ValueError("IvaRateRole token must be a non-empty string")
        return str.__new__(cls, value)

    @classmethod
    def from_registry(cls, value: str) -> Self:
        """Construct the typed value from its canonical registry token."""
        return cls(value, _registry_validated=True)

    @property
    def value(self) -> str:
        """Return the persisted registry token."""
        return str(self)


@dataclass(frozen=True, slots=True)
class IvaRateRoleDefinition:
    """One registry-declared rate role and its selector semantics."""

    token: IvaRateRole
    is_default: bool
    supersedes_tier_default: bool


@dataclass(frozen=True, slots=True)
class IvaRateRoleCatalogue:
    """Dated projection of the rate-role selector vocabulary."""

    definitions: tuple[IvaRateRoleDefinition, ...]
    default_role: IvaRateRole

    @property
    def roles(self) -> tuple[IvaRateRole, ...]:
        """Return roles in registry-authored order."""
        return tuple(item.token for item in self.definitions)

    def require(self, value: object | None = None) -> IvaRateRole:
        """Return a declared role, or the declared default when omitted."""
        if value is None:
            return self.default_role
        raw = value.value if isinstance(value, IvaRateRole) else value
        if not isinstance(raw, str) or not raw.strip():
            raise RegistryValidationError("IVA rate role must be a non-empty string token")
        for definition in self.definitions:
            if definition.token.value == raw:
                return definition.token
        raise RegistryValidationError(
            f"IVA rate role {raw!r} is not declared by fact {_FACT_ID!r}",
        )


def _mapping_entries(resolved: ResolvedMappingFact) -> Mapping[str, str]:
    """Narrow a mapping payload to a unique string-to-string mapping."""
    entries: dict[str, str] = {}
    for entry in resolved.payload.entries:
        if not isinstance(entry.key, str) or not isinstance(entry.value, str):
            raise RegistryValidationError("IVA rate-role entries must be string-to-string")
        if entry.key in entries:
            raise RegistryValidationError(f"duplicate IVA rate-role key {entry.key!r}")
        entries[entry.key] = entry.value
    return MappingProxyType(entries)


def _required(entries: Mapping[str, str], key: str) -> str:
    value = entries.get(key)
    if value is None or not value.strip():
        raise RegistryValidationError(f"IVA rate-role catalogue is missing {key!r}")
    return value.strip()


def _csv(entries: Mapping[str, str], key: str) -> tuple[str, ...]:
    values = tuple(token.strip() for token in _required(entries, key).split(",") if token.strip())
    if not values or len(values) != len(set(values)):
        raise RegistryValidationError(f"IVA rate-role catalogue {key!r} must contain unique tokens")
    return values


def _bool(entries: Mapping[str, str], key: str) -> bool:
    value = _required(entries, key).lower()
    if value == "true":
        return True
    if value == "false":
        return False
    raise RegistryValidationError(f"IVA rate-role catalogue {key!r} must be true or false")


def _resolve_entries(*, effective_date: date, authority: GovernedFactSource) -> Mapping[str, str]:
    resolved = authority.resolve_governed_fact(
        MappingFactQuery(
            fact_id=_FACT_ID,
            date_axis=DateAxis.DEVENGO_DATE,
            effective_date=effective_date,
            selectors=(_SCOPE_SELECTOR,),
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise RegistryValidationError("IVA rate-role catalogue must resolve as a mapping fact")
    return _mapping_entries(resolved)


def _catalogue_from_entries(entries: Mapping[str, str]) -> IvaRateRoleCatalogue:
    definitions: list[IvaRateRoleDefinition] = []
    for raw_token in _csv(entries, _ORDER_KEY):
        token = IvaRateRole.from_registry(raw_token)
        prefix = f"{_PREFIX}{raw_token}."
        if _required(entries, f"{prefix}value") != raw_token:
            raise RegistryValidationError(
                f"IVA rate-role token {raw_token!r} declares a mismatched value",
            )
        definitions.append(
            IvaRateRoleDefinition(
                token=token,
                is_default=_bool(entries, f"{prefix}is_default"),
                supersedes_tier_default=_bool(entries, f"{prefix}supersedes_tier_default"),
            ),
        )
    if not definitions:
        raise RegistryValidationError("IVA rate-role catalogue must declare at least one role")
    default_token = _required(entries, _DEFAULT_KEY)
    defaults = tuple(item for item in definitions if item.is_default)
    if len(defaults) != 1:
        raise RegistryValidationError("IVA rate-role catalogue must declare exactly one default role")
    if defaults[0].token.value != default_token:
        raise RegistryValidationError("IVA rate-role default does not match its role declaration")
    if defaults[0].supersedes_tier_default:
        raise RegistryValidationError("IVA rate-role default cannot supersede the tier default")
    return IvaRateRoleCatalogue(definitions=tuple(definitions), default_role=defaults[0].token)


def resolve_iva_rate_role_catalogue(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> IvaRateRoleCatalogue:
    """Resolve the IVA rate-role vocabulary through the selected facts authority."""
    coordinate = effective_date or date.today()
    selected = authority or governed_facts_in_scope()
    if selected is None:
        raise RegistryValidationError("IVA rate-role catalogue requires an explicit authority operation or scope")
    return _catalogue_from_entries(_resolve_entries(effective_date=coordinate, authority=selected))


__all__ = [
    "IvaRateRole",
    "IvaRateRoleCatalogue",
    "IvaRateRoleDefinition",
    "resolve_iva_rate_role_catalogue",
]
