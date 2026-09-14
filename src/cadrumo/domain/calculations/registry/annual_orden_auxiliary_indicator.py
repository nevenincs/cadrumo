"""Typed projection of annual Orden auxiliary-activity indicators (fact 0145)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType

from .errors import RegistryValidationError
from .facts.resolution import MappingFactQuery, ResolvedMappingFact
from .governed_fact_scope import GovernedFactSource, governed_facts_in_scope
from .schema_base import DateAxis

_FACT_ID = "liva-orden-auxiliary-activity-indicator"
_KEY_SEPARATOR = "|"


@dataclass(frozen=True, slots=True)
class AnnualOrdenAuxiliaryActivityIndicators:
    """The source-declared indicator projection for one annual Orden vintage."""

    by_iae_and_activity: Mapping[tuple[str, str], str]

    def for_activity(self, *, iae_epigrafe: str, activity_code: str) -> str | None:
        """Return the registry value for an activity, if no indicator is declared."""
        return self.by_iae_and_activity.get((iae_epigrafe, activity_code))


def _mapping_entries(resolved: ResolvedMappingFact) -> Mapping[str, str]:
    entries: dict[str, str] = {}
    for entry in resolved.payload.entries:
        if not isinstance(entry.key, str) or not isinstance(entry.value, str):
            raise RegistryValidationError(
                "annual Orden auxiliary-activity indicator entries must be string-to-string",
            )
        key = entry.key.strip()
        value = entry.value.strip()
        if not key or not value:
            raise RegistryValidationError(
                "annual Orden auxiliary-activity indicator entries must be non-empty",
            )
        if key in entries:
            raise RegistryValidationError(
                f"duplicate annual Orden auxiliary-activity indicator key {key!r}",
            )
        entries[key] = value
    return MappingProxyType(entries)


def resolve_annual_orden_auxiliary_activity_indicators(
    *,
    effective_date: date,
    authority: GovernedFactSource | None = None,
) -> AnnualOrdenAuxiliaryActivityIndicators:
    """Resolve auxiliary indicators from the selected facts authority.

    The compiler supplies a :class:`CandidateFactAuthority` through the
    governed-facts scope.  Refusing when no authority is selected prevents the
    annual Orden compiler from silently consulting a published bundle or
    recreating the mapping locally.
    """
    selected = authority or governed_facts_in_scope()
    if selected is None:
        raise RegistryValidationError(
            "annual Orden auxiliary-activity indicators require a selected candidate facts authority",
        )
    resolved = selected.resolve_governed_fact(
        MappingFactQuery(
            fact_id=_FACT_ID,
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date,
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise RegistryValidationError(
            "annual Orden auxiliary-activity indicators must resolve as a mapping fact",
        )
    by_key = _mapping_entries(resolved)
    by_iae_and_activity: dict[tuple[str, str], str] = {}
    for key, value in by_key.items():
        parts = tuple(part.strip() for part in key.split(_KEY_SEPARATOR))
        if len(parts) != 2 or not all(parts):
            raise RegistryValidationError(
                f"annual Orden auxiliary-activity indicator key {key!r} must be iae|activity",
            )
        identity = (parts[0], parts[1])
        if identity in by_iae_and_activity:
            raise RegistryValidationError(
                f"duplicate annual Orden auxiliary-activity indicator identity {identity!r}",
            )
        by_iae_and_activity[identity] = value
    if not by_iae_and_activity:
        raise RegistryValidationError(
            "annual Orden auxiliary-activity indicator fact declares no activity mappings",
        )
    return AnnualOrdenAuxiliaryActivityIndicators(
        by_iae_and_activity=MappingProxyType(by_iae_and_activity),
    )


__all__ = [
    "AnnualOrdenAuxiliaryActivityIndicators",
    "resolve_annual_orden_auxiliary_activity_indicators",
]
