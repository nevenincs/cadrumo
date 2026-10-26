"""Typed projection of the IVA rate-role vocabulary and default."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Final, Self

from .errors import RegistryValidationError
from .facts.resolution import required_mapping_entry, unique_mapping_tokens
from .facts.string_mapping import (
    BooleanTokenCase,
    MappingValueWhitespace,
    StringMappingFact,
    StringMappingPolicy,
    required_mapping_boolean,
)
from .facts.variants import FactSelector
from .governed_fact_scope import GovernedFactSource
from .schema_base import DateAxis

_ENTRY_SUBJECT: Final = "IVA rate-role catalogue"

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


_ENTRIES_POLICY = StringMappingPolicy(subject=_ENTRY_SUBJECT, value_whitespace=MappingValueWhitespace.PRESERVE)


_ENTRIES_FACT = StringMappingFact(
    fact_id=_FACT_ID, date_axis=DateAxis.DEVENGO_DATE, policy=_ENTRIES_POLICY, selectors=(_SCOPE_SELECTOR,)
)


def _catalogue_from_entries(entries: Mapping[str, str]) -> IvaRateRoleCatalogue:
    definitions: list[IvaRateRoleDefinition] = []
    for raw_token in unique_mapping_tokens(entries, _ORDER_KEY, subject=_ENTRY_SUBJECT):
        token = IvaRateRole.from_registry(raw_token)
        prefix = f"{_PREFIX}{raw_token}."
        if required_mapping_entry(entries, f"{prefix}value", subject=_ENTRY_SUBJECT) != raw_token:
            raise RegistryValidationError(
                f"IVA rate-role token {raw_token!r} declares a mismatched value",
            )
        definitions.append(
            IvaRateRoleDefinition(
                token=token,
                is_default=required_mapping_boolean(
                    entries, f"{prefix}is_default", subject=_ENTRY_SUBJECT, case=BooleanTokenCase.CASE_INSENSITIVE
                ),
                supersedes_tier_default=required_mapping_boolean(
                    entries,
                    f"{prefix}supersedes_tier_default",
                    subject=_ENTRY_SUBJECT,
                    case=BooleanTokenCase.CASE_INSENSITIVE,
                ),
            ),
        )
    if not definitions:
        raise RegistryValidationError("IVA rate-role catalogue must declare at least one role")
    default_token = required_mapping_entry(entries, _DEFAULT_KEY, subject=_ENTRY_SUBJECT)
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
    return _catalogue_from_entries(
        _ENTRIES_FACT.resolve_scoped_entries(effective_date=effective_date, authority=authority)
    )


__all__ = [
    "IvaRateRole",
    "IvaRateRoleCatalogue",
    "IvaRateRoleDefinition",
    "resolve_iva_rate_role_catalogue",
]
