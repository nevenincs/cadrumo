"""Typed projection of the governed rental-reduction tier catalogue."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType
from typing import Final

from ....domain.renta.rental_reduction import RentalReductionArt232Tier
from .errors import RegistryValidationError
from .facts.resolution import MappingFactQuery, ResolvedMappingFact, required_mapping_entry, unique_mapping_tokens
from .governed_fact_scope import GovernedFactSource, governed_facts_in_scope
from .schema_base import DateAxis

_ENTRY_SUBJECT: Final = "rental reduction mapping"
_UNIQUE_TOKENS_REQUIREMENT: Final = "must declare unique non-empty tokens"

_FACT_ID = "renta-rental-reduccion-art-23-2-tier-catalogue"
_ORDER_KEY = "tier_order"
_TIER_PREFIX = "tier."


@dataclass(frozen=True, slots=True)
class RentalReductionArt232TierDefinition:
    """One registry-declared tier and its legal selection metadata."""

    token: RentalReductionArt232Tier
    description: str
    legal_ref: str
    parameter_id: str


@dataclass(frozen=True, slots=True)
class RentalReductionArt232TierCatalogue:
    """Typed projection of the dated rental-reduction mapping fact."""

    definitions: tuple[RentalReductionArt232TierDefinition, ...]

    @property
    def all_tiers(self) -> frozenset[RentalReductionArt232Tier]:
        """Return every registry-declared tier token."""
        return frozenset(definition.token for definition in self.definitions)

    def require(self, value: object) -> RentalReductionArt232Tier:
        """Validate one opaque tier token against the selected authority."""
        if isinstance(value, RentalReductionArt232Tier):
            token = value
        elif isinstance(value, str):
            token = RentalReductionArt232Tier(value.strip())
        else:
            raise RegistryValidationError("rental reduction tier must be a string token")
        if not str(token):
            raise RegistryValidationError("rental reduction tier token must not be blank")
        if token not in self.all_tiers:
            raise RegistryValidationError(
                f"rental reduction tier {str(token)!r} is not declared by the facts registry",
            )
        return token


def _mapping_entries(resolved: ResolvedMappingFact) -> Mapping[str, str]:
    """Narrow a resolved mapping payload to a unique string-to-string map."""
    entries: dict[str, str] = {}
    for entry in resolved.payload.entries:
        if not isinstance(entry.key, str) or not isinstance(entry.value, str):
            raise RegistryValidationError("rental reduction mapping entries must be string-to-string")
        if entry.key in entries:
            raise RegistryValidationError(f"duplicate rental reduction mapping key {entry.key!r}")
        entries[entry.key] = entry.value
    return MappingProxyType(entries)


def resolve_rental_reduction_art232_tier_catalogue(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> RentalReductionArt232TierCatalogue:
    """Resolve the dated rental-reduction tier catalogue through authority."""
    authority = authority or governed_facts_in_scope()
    if authority is None:
        raise RegistryValidationError("rental reduction catalogue requires an explicit authority operation or scope")
    resolved = authority.resolve_governed_fact(
        MappingFactQuery(
            fact_id=_FACT_ID,
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date or date.today(),
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise RegistryValidationError("rental reduction tier fact must resolve as a mapping fact")
    entries = _mapping_entries(resolved)
    definitions: list[RentalReductionArt232TierDefinition] = []
    for raw_token in unique_mapping_tokens(
        entries, _ORDER_KEY, subject=_ENTRY_SUBJECT, requirement=_UNIQUE_TOKENS_REQUIREMENT
    ):
        token = RentalReductionArt232Tier(raw_token)
        prefix = f"{_TIER_PREFIX}{raw_token}"
        declared_value = required_mapping_entry(entries, f"{prefix}.value", subject=_ENTRY_SUBJECT)
        if declared_value != raw_token:
            raise RegistryValidationError(
                f"rental reduction tier {raw_token!r} declares mismatched value {declared_value!r}",
            )
        definitions.append(
            RentalReductionArt232TierDefinition(
                token=token,
                description=required_mapping_entry(entries, f"{prefix}.description", subject=_ENTRY_SUBJECT),
                legal_ref=required_mapping_entry(entries, f"{prefix}.legal_ref", subject=_ENTRY_SUBJECT),
                parameter_id=required_mapping_entry(entries, f"{prefix}.parameter_id", subject=_ENTRY_SUBJECT),
            ),
        )
    return RentalReductionArt232TierCatalogue(definitions=tuple(definitions))


def require_rental_reduction_art232_tier(
    value: object,
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> RentalReductionArt232Tier:
    """Return one registry-declared opaque tier token or refuse it."""
    return resolve_rental_reduction_art232_tier_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).require(value)


__all__ = [
    "RentalReductionArt232TierCatalogue",
    "RentalReductionArt232TierDefinition",
    "require_rental_reduction_art232_tier",
    "resolve_rental_reduction_art232_tier_catalogue",
]
