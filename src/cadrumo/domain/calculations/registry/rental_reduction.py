"""Typed projection of the governed rental-reduction tier catalogue."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType
from typing import TYPE_CHECKING

from ....domain.renta.rental_reduction import RentalReductionArt232Tier
from .errors import RegistryValidationError
from .facts.resolution import MappingFactQuery, ResolvedMappingFact
from .schema_base import DateAxis

if TYPE_CHECKING:
    from .authority import ValidatedRegistryAuthority


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


def _required(entries: Mapping[str, str], key: str) -> str:
    value = entries.get(key)
    if value is None or not value.strip():
        raise RegistryValidationError(f"rental reduction mapping is missing {key!r}")
    return value.strip()


def _csv_tokens(entries: Mapping[str, str], key: str) -> tuple[str, ...]:
    tokens = tuple(token.strip() for token in _required(entries, key).split(",") if token.strip())
    if not tokens or len(set(tokens)) != len(tokens):
        raise RegistryValidationError(f"rental reduction mapping {key!r} must declare unique non-empty tokens")
    return tokens


def resolve_rental_reduction_art232_tier_catalogue(
    *,
    effective_date: date | None = None,
    authority: ValidatedRegistryAuthority | None = None,
) -> RentalReductionArt232TierCatalogue:
    """Resolve the dated rental-reduction tier catalogue through authority."""
    if authority is None:
        from .authority import bundled_authority

        authority = bundled_authority()
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
    for raw_token in _csv_tokens(entries, _ORDER_KEY):
        token = RentalReductionArt232Tier(raw_token)
        prefix = f"{_TIER_PREFIX}{raw_token}"
        declared_value = _required(entries, f"{prefix}.value")
        if declared_value != raw_token:
            raise RegistryValidationError(
                f"rental reduction tier {raw_token!r} declares mismatched value {declared_value!r}",
            )
        definitions.append(
            RentalReductionArt232TierDefinition(
                token=token,
                description=_required(entries, f"{prefix}.description"),
                legal_ref=_required(entries, f"{prefix}.legal_ref"),
                parameter_id=_required(entries, f"{prefix}.parameter_id"),
            ),
        )
    return RentalReductionArt232TierCatalogue(definitions=tuple(definitions))


def require_rental_reduction_art232_tier(
    value: object,
    *,
    effective_date: date | None = None,
    authority: ValidatedRegistryAuthority | None = None,
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
