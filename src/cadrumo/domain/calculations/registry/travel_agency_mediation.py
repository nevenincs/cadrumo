"""Typed projection of the RD 1619/2012 travel-agency mediation vocabulary."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Final

from ....core.aggregation import TravelAgencyMediationType
from .errors import RegistryValidationError
from .facts.resolution import required_mapping_entry, unique_mapping_tokens
from .facts.string_mapping import (
    MappingValueWhitespace,
    StringMappingFact,
    StringMappingPolicy,
)
from .governed_fact_scope import GovernedFactSource
from .schema_base import DateAxis

_ENTRY_SUBJECT: Final = "travel-agency mediation catalogue"

_FACT_ID = "travel-agency-mediation-catalogue"
_ORDER_KEY = "travel_agency_mediation.order"
_AIR_PASSENGER_TRANSPORT_KEY = "travel_agency_mediation.air_passenger_transport_token"
_PREFIX = "travel_agency_mediation."


@dataclass(frozen=True, slots=True)
class TravelAgencyMediationDefinition:
    """One registry-declared mediation token and its legal semantics."""

    token: TravelAgencyMediationType
    description: str
    legal_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TravelAgencyMediationCatalogue:
    """Complete typed projection of fact 0133."""

    definitions: tuple[TravelAgencyMediationDefinition, ...]
    air_passenger_transport_token: TravelAgencyMediationType

    @property
    def tokens(self) -> frozenset[TravelAgencyMediationType]:
        """Return every mediation token declared by the selected fact."""
        return frozenset(item.token for item in self.definitions)

    def require(self, value: object) -> TravelAgencyMediationType:
        """Project one token only when the selected fact declares it."""
        if isinstance(value, TravelAgencyMediationType):
            token = value
        elif isinstance(value, str):
            raw = value.strip()
            if not raw:
                raise RegistryValidationError("travel-agency mediation token must be non-empty")
            try:
                token = TravelAgencyMediationType.from_registry(raw)
            except (TypeError, ValueError) as exc:
                raise RegistryValidationError(
                    "travel-agency mediation token must be a non-empty string",
                ) from exc
        else:
            raise RegistryValidationError("travel-agency mediation token must be a string token")
        if token not in self.tokens:
            raise RegistryValidationError(
                f"travel-agency mediation token {str(token)!r} is not declared by fact {_FACT_ID!r}",
            )
        return token

    def definition(self, value: object) -> TravelAgencyMediationDefinition:
        """Return the selected token's registry-owned semantics."""
        token = self.require(value)
        return next(item for item in self.definitions if item.token == token)

    def is_air_passenger_transport(self, value: object) -> bool:
        """Return whether the selected token is the registry's air subset."""
        token = self.require(value)
        return token == self.air_passenger_transport_token


_ENTRIES_POLICY = StringMappingPolicy(subject=_ENTRY_SUBJECT, value_whitespace=MappingValueWhitespace.PRESERVE)


_ENTRIES_FACT = StringMappingFact(fact_id=_FACT_ID, date_axis=DateAxis.INVOICE_DATE, policy=_ENTRIES_POLICY)


def _catalogue(entries: Mapping[str, str]) -> TravelAgencyMediationCatalogue:
    definitions: list[TravelAgencyMediationDefinition] = []
    for raw_token in unique_mapping_tokens(entries, _ORDER_KEY, subject=_ENTRY_SUBJECT):
        token = TravelAgencyMediationType.from_registry(raw_token)
        prefix = f"{_PREFIX}{raw_token}."
        if required_mapping_entry(entries, f"{prefix}value", subject=_ENTRY_SUBJECT) != raw_token:
            raise RegistryValidationError(
                f"travel-agency mediation token {raw_token!r} declares a mismatched value",
            )
        definitions.append(
            TravelAgencyMediationDefinition(
                token=token,
                description=required_mapping_entry(entries, f"{prefix}description", subject=_ENTRY_SUBJECT),
                legal_refs=unique_mapping_tokens(entries, f"{prefix}legal_refs", subject=_ENTRY_SUBJECT),
            ),
        )
    if len(definitions) != len({item.token for item in definitions}):
        raise RegistryValidationError("travel-agency mediation catalogue contains duplicate tokens")
    air_token = TravelAgencyMediationType.from_registry(
        required_mapping_entry(entries, _AIR_PASSENGER_TRANSPORT_KEY, subject=_ENTRY_SUBJECT)
    )
    if air_token not in {item.token for item in definitions}:
        raise RegistryValidationError("travel-agency mediation air token is not in the declared order")
    return TravelAgencyMediationCatalogue(
        definitions=tuple(definitions),
        air_passenger_transport_token=air_token,
    )


def resolve_travel_agency_mediation_catalogue(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> TravelAgencyMediationCatalogue:
    """Resolve the dated travel-agency mediation vocabulary."""
    return _catalogue(_ENTRIES_FACT.resolve_scoped_entries(effective_date=effective_date, authority=authority))


def require_travel_agency_mediation(
    value: object,
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> TravelAgencyMediationType:
    """Project one travel-agency mediation token through fact 0133."""
    return resolve_travel_agency_mediation_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).require(value)


def is_travel_agency_air_passenger_transport(
    value: object,
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> bool:
    """Return the registry-derived air-passenger mediation predicate."""
    return resolve_travel_agency_mediation_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).is_air_passenger_transport(value)


__all__ = [
    "TravelAgencyMediationCatalogue",
    "TravelAgencyMediationDefinition",
    "is_travel_agency_air_passenger_transport",
    "require_travel_agency_mediation",
    "resolve_travel_agency_mediation_catalogue",
]
