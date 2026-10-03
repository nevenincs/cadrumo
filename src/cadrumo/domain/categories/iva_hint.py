"""Typed projection of registry-owned category IVA hint vocabulary."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Final

from ...core.time.clock import today_madrid
from ..calculations.registry.errors import RegistryValidationError
from ..calculations.registry.facts.resolution import (
    required_mapping_entry,
    unique_mapping_tokens,
)
from ..calculations.registry.facts.string_mapping import (
    MappingValueWhitespace,
    StringMappingFact,
    StringMappingPolicy,
)
from ..calculations.registry.facts.variants import FactSelector
from ..calculations.registry.governed_fact_scope import GovernedFactSource, require_governed_fact_authority
from ..calculations.registry.schema_base import DateAxis
from .profile import IvaDeductibilityHint

_ENTRY_SUBJECT: Final = "IVA deductibility hint mapping"
_UNIQUE_TOKENS_REQUIREMENT: Final = "must declare unique tokens"

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


_ENTRIES_POLICY = StringMappingPolicy(subject=_ENTRY_SUBJECT, value_whitespace=MappingValueWhitespace.PRESERVE)

_ENTRIES_FACT = StringMappingFact(
    fact_id=_FACT_ID, date_axis=DateAxis.FILING_PERIOD, policy=_ENTRIES_POLICY, selectors=(_SCOPE_SELECTOR,)
)


def resolve_iva_deductibility_hint_catalogue(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> IvaDeductibilityHintCatalogue:
    """Resolve the dated IVA hint vocabulary through the facts authority."""
    selected_authority = require_governed_fact_authority(authority, subject="IVA deductibility hint catalogue")
    entries = _ENTRIES_FACT.resolve_entries(selected_authority, effective_date=effective_date or today_madrid())
    values = tuple(
        IvaDeductibilityHint(token)
        for token in unique_mapping_tokens(
            entries, _ORDER_KEY, subject=_ENTRY_SUBJECT, requirement=_UNIQUE_TOKENS_REQUIREMENT
        )
    )
    return IvaDeductibilityHintCatalogue(
        values=values, semantics=required_mapping_entry(entries, _SEMANTICS_KEY, subject=_ENTRY_SUBJECT)
    )


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
