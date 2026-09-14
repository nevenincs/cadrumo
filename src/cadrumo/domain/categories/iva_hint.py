"""Typed projection of registry-owned category IVA hint vocabulary."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType

from ..calculations.registry.errors import RegistryValidationError
from ..calculations.registry.facts.resolution import MappingFactQuery, ResolvedMappingFact
from ..calculations.registry.facts.schema import FactSelector
from ..calculations.registry.governed_fact_scope import GovernedFactSource, governed_facts_in_scope
from ..calculations.registry.schema_base import DateAxis
from .profile import IvaDeductibilityHint

_FACT_ID = "categories.profile"
_SCOPE_SELECTOR = FactSelector(name="scope", value="iva_deductibility_hint")
_ORDER_KEY = "iva_deductibility_hint.order"
_SEMANTICS_KEY = "iva_deductibility_hint.semantics"


@dataclass(frozen=True, slots=True)
class IvaDeductibilityHintCatalogue:
    """Registry-projected, dated IVA hint vocabulary."""

    values: tuple[IvaDeductibilityHint, ...]
    semantics: str

    @property
    def all_hints(self) -> frozenset[IvaDeductibilityHint]:
        """Return every registry-declared hint token."""
        return frozenset(self.values)

    def require(self, value: object) -> IvaDeductibilityHint:
        """Validate one opaque token against the registry projection."""
        if isinstance(value, IvaDeductibilityHint):
            token = value
        elif isinstance(value, str):
            token = IvaDeductibilityHint(value.strip())
        else:
            raise RegistryValidationError("IVA deductibility hint must be a string token")
        if not str(token):
            raise RegistryValidationError("IVA deductibility hint token must not be blank")
        if token not in self.all_hints:
            raise RegistryValidationError(f"IVA deductibility hint {str(token)!r} is not registry-declared")
        return token


def _mapping_entries(resolved: ResolvedMappingFact) -> Mapping[str, str]:
    """Narrow a resolved mapping payload to a unique string-to-string map."""
    entries: dict[str, str] = {}
    for entry in resolved.payload.entries:
        if not isinstance(entry.key, str) or not isinstance(entry.value, str):
            raise RegistryValidationError("IVA deductibility hint entries must be string-to-string")
        if entry.key in entries:
            raise RegistryValidationError(f"duplicate IVA deductibility hint key {entry.key!r}")
        entries[entry.key] = entry.value
    return MappingProxyType(entries)


def _required(entries: Mapping[str, str], key: str) -> str:
    value = entries.get(key)
    if value is None or not value.strip():
        raise RegistryValidationError(f"IVA deductibility hint mapping is missing {key!r}")
    return value.strip()


def _csv_tokens(entries: Mapping[str, str], key: str) -> tuple[str, ...]:
    tokens = tuple(token.strip() for token in _required(entries, key).split(",") if token.strip())
    if not tokens or len(set(tokens)) != len(tokens):
        raise RegistryValidationError(f"IVA deductibility hint mapping {key!r} must declare unique tokens")
    return tokens


def resolve_iva_deductibility_hint_catalogue(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> IvaDeductibilityHintCatalogue:
    """Resolve the dated IVA hint vocabulary through the facts authority."""
    selected_authority = authority or governed_facts_in_scope()
    if selected_authority is None:
        raise RegistryValidationError(
            "IVA deductibility hint catalogue requires an explicit authority operation or scope"
        )
    resolved = selected_authority.resolve_governed_fact(
        MappingFactQuery(
            fact_id=_FACT_ID,
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date or date.today(),
            selectors=(_SCOPE_SELECTOR,),
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise RegistryValidationError("categories.profile IVA hint vocabulary must resolve as a mapping fact")
    entries = _mapping_entries(resolved)
    values = tuple(IvaDeductibilityHint(token) for token in _csv_tokens(entries, _ORDER_KEY))
    return IvaDeductibilityHintCatalogue(values=values, semantics=_required(entries, _SEMANTICS_KEY))


def require_iva_deductibility_hint(
    value: object,
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> IvaDeductibilityHint:
    """Return one registry-declared IVA hint token or refuse it."""
    return resolve_iva_deductibility_hint_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).require(value)


__all__ = [
    "IvaDeductibilityHintCatalogue",
    "require_iva_deductibility_hint",
    "resolve_iva_deductibility_hint_catalogue",
]
