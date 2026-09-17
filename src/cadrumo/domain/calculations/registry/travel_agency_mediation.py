"""Typed projection of the RD 1619/2012 travel-agency mediation vocabulary."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType
from typing import Final

from ....core.aggregation import TravelAgencyMediationType
from ....core.time.clock import today_madrid
from .errors import RegistryValidationError
from .facts.resolution import MappingFactQuery, ResolvedMappingFact, required_mapping_entry, unique_mapping_tokens
from .governed_fact_scope import GovernedFactSource, governed_facts_in_scope
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


def _refs(entries: Mapping[str, str], key: str) -> tuple[str, ...]:
    return unique_mapping_tokens(entries, key, subject=_ENTRY_SUBJECT)


def _mapping_entries(resolved: ResolvedMappingFact) -> Mapping[str, str]:
    entries: dict[str, str] = {}
    for entry in resolved.payload.entries:
        if not isinstance(entry.key, str) or not isinstance(entry.value, str):
            raise RegistryValidationError("travel-agency mediation entries must be string-to-string")
        if entry.key in entries:
            raise RegistryValidationError(
                f"duplicate travel-agency mediation catalogue key {entry.key!r}",
            )
        entries[entry.key] = entry.value
    return MappingProxyType(entries)


def _resolve_entries(*, effective_date: date, authority: GovernedFactSource) -> Mapping[str, str]:
    resolved = authority.resolve_governed_fact(
        MappingFactQuery(
            fact_id=_FACT_ID,
            date_axis=DateAxis.INVOICE_DATE,
            effective_date=effective_date,
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise RegistryValidationError("travel-agency mediation catalogue must resolve as a mapping fact")
    return _mapping_entries(resolved)


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
                legal_refs=_refs(entries, f"{prefix}legal_refs"),
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


def _selected_catalogue(
    *,
    effective_date: date,
    authority: GovernedFactSource | None,
) -> TravelAgencyMediationCatalogue:
    selected = authority or governed_facts_in_scope()
    if selected is None:
        raise RegistryValidationError(
            "travel-agency mediation resolution requires a generation-pinned governed-fact source",
        )
    return _catalogue(_resolve_entries(effective_date=effective_date, authority=selected))


def resolve_travel_agency_mediation_catalogue(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> TravelAgencyMediationCatalogue:
    """Resolve the dated travel-agency mediation vocabulary."""
    coordinate = effective_date or today_madrid()
    return _selected_catalogue(effective_date=coordinate, authority=authority)


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
