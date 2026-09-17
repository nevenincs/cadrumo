"""Typed projection of the deadline-calendar CCAA territory vocabulary.

The deadline calendar has a wider territory axis than the Renta tax-residence
catalogue: it includes the two foral communities and the autonomous cities of
Ceuta and Melilla because each may publish holidays that affect an AEAT filing
deadline.  Fact 0143 owns the ISO 3166-2:ES values; fact 0129 remains the
separate fifteen-member common-regime tax-residence vocabulary.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType
from typing import Final

from ....core.time.clock import today_madrid
from ....domain.deadlines.festivos import CalendarCCAA
from .errors import RegistryValidationError
from .facts.resolution import MappingFactQuery, ResolvedMappingFact, required_mapping_entry, unique_mapping_tokens
from .governed_fact_scope import GovernedFactSource, cache_governed_projection, governed_facts_in_scope
from .schema_base import DateAxis

_ENTRY_SUBJECT: Final = "calendar CCAA catalogue"

_FACT_ID = "deadline-calendar-territory-catalogue"
_ORDER_KEY = "calendar_ccaa.order"
_PREFIX = "calendar_ccaa."
_RELATION_PREFIX = "calendar_ccaa.relation."


@dataclass(frozen=True, slots=True)
class CalendarCcaaDefinition:
    """One registry-declared deadline-calendar territory."""

    token: CalendarCCAA
    member_name: str
    description: str
    territory_kind: str


@dataclass(frozen=True, slots=True)
class CalendarCcaaCatalogue:
    """Complete typed projection of the dated calendar-territory fact."""

    definitions: tuple[CalendarCcaaDefinition, ...]
    tax_residence_fact_id: str
    tax_residence_common_regime_count: int
    includes_foral_territories: bool
    includes_autonomous_cities: bool

    @property
    def choices(self) -> tuple[CalendarCCAA, ...]:
        """Return calendar territories in authored order."""
        return tuple(definition.token for definition in self.definitions)

    @property
    def tokens(self) -> frozenset[CalendarCCAA]:
        """Return all calendar territories declared by the selected fact."""
        return frozenset(self.choices)

    def require(self, value: object) -> CalendarCCAA:
        """Project an ISO territory code only when the selected fact declares it."""
        if isinstance(value, CalendarCCAA):
            token = value
        elif isinstance(value, str):
            raw = value.strip().upper()
            if not raw:
                raise RegistryValidationError("calendar CCAA code must be non-empty")
            try:
                token = CalendarCCAA.from_registry(raw)
            except (TypeError, ValueError) as exc:
                raise RegistryValidationError("calendar CCAA code must be a string token") from exc
        else:
            raise RegistryValidationError("calendar CCAA code must be a string token")
        if token not in self.tokens:
            raise RegistryValidationError(
                f"calendar CCAA code {str(token)!r} is not declared by fact {_FACT_ID!r}",
            )
        return token

    def require_member_name(self, name: str) -> CalendarCCAA:
        """Project a historical enum-style member name from the catalogue."""
        if not isinstance(name, str):
            raise KeyError(name)
        normalized = name.strip().upper()
        for definition in self.definitions:
            if definition.member_name == normalized:
                return definition.token
        raise KeyError(name)

    def definition(self, value: object) -> CalendarCcaaDefinition:
        """Return the selected territory's registry-owned metadata."""
        token = self.require(value)
        return next(definition for definition in self.definitions if definition.token == token)


def _boolean(entries: Mapping[str, str], key: str) -> bool:
    value = required_mapping_entry(entries, key, subject=_ENTRY_SUBJECT).lower()
    if value == "true":
        return True
    if value == "false":
        return False
    raise RegistryValidationError(f"calendar CCAA catalogue {key!r} must be true or false")


def _integer(entries: Mapping[str, str], key: str) -> int:
    value = required_mapping_entry(entries, key, subject=_ENTRY_SUBJECT)
    try:
        parsed = int(value)
    except ValueError as exc:
        raise RegistryValidationError(f"calendar CCAA catalogue {key!r} must be an integer") from exc
    if parsed < 0:
        raise RegistryValidationError(f"calendar CCAA catalogue {key!r} must not be negative")
    return parsed


def _mapping_entries(resolved: ResolvedMappingFact) -> Mapping[str, str]:
    entries: dict[str, str] = {}
    for entry in resolved.payload.entries:
        if not isinstance(entry.key, str) or not isinstance(entry.value, str):
            raise RegistryValidationError("calendar CCAA entries must be string-to-string")
        if entry.key in entries:
            raise RegistryValidationError(f"duplicate calendar CCAA catalogue key {entry.key!r}")
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
        raise RegistryValidationError("deadline calendar territory fact must resolve as a mapping fact")
    return _mapping_entries(resolved)


@cache_governed_projection(maxsize=64)
def _bundled_entries(effective_date: date) -> Mapping[str, str]:
    del effective_date
    raise RegistryValidationError("calendar CCAA catalogue requires an explicit authority operation or scope")


def _selected_entries(
    *,
    effective_date: date | None,
    authority: GovernedFactSource | None,
) -> Mapping[str, str]:
    coordinate = effective_date or today_madrid()
    selected = authority or governed_facts_in_scope()
    if selected is None:
        return _bundled_entries(coordinate)
    return _resolve_entries(effective_date=coordinate, authority=selected)


def _catalogue(entries: Mapping[str, str]) -> CalendarCcaaCatalogue:
    definitions: list[CalendarCcaaDefinition] = []
    for raw_code in unique_mapping_tokens(entries, _ORDER_KEY, subject=_ENTRY_SUBJECT):
        code = raw_code.upper()
        if code != raw_code or not code.startswith("ES-") or len(code) != 5:
            raise RegistryValidationError(f"calendar CCAA code {raw_code!r} is not canonical ISO 3166-2:ES syntax")
        suffix = code[3:]
        if not suffix.isalpha() or not suffix.isupper():
            raise RegistryValidationError(f"calendar CCAA code {raw_code!r} is not canonical ISO 3166-2:ES syntax")
        prefix = f"{_PREFIX}{code}."
        if required_mapping_entry(entries, f"{prefix}value", subject=_ENTRY_SUBJECT) != code:
            raise RegistryValidationError(f"calendar CCAA code {code!r} declares a mismatched value")
        member_name = required_mapping_entry(entries, f"{prefix}member_name", subject=_ENTRY_SUBJECT).upper()
        definitions.append(
            CalendarCcaaDefinition(
                token=CalendarCCAA.from_registry(code),
                member_name=member_name,
                description=required_mapping_entry(entries, f"{prefix}description", subject=_ENTRY_SUBJECT),
                territory_kind=required_mapping_entry(entries, f"{prefix}territory_kind", subject=_ENTRY_SUBJECT),
            ),
        )
    tokens = [definition.token for definition in definitions]
    if len(tokens) != len(set(tokens)):
        raise RegistryValidationError("calendar CCAA catalogue contains duplicate codes")
    member_names = [definition.member_name for definition in definitions]
    if len(member_names) != len(set(member_names)):
        raise RegistryValidationError("calendar CCAA catalogue contains duplicate member names")

    tax_residence_fact_id = required_mapping_entry(
        entries, f"{_RELATION_PREFIX}tax_residence_fact_id", subject=_ENTRY_SUBJECT
    )
    tax_residence_common_regime_count = _integer(
        entries,
        f"{_RELATION_PREFIX}tax_residence_common_regime_count",
    )
    calendar_territory_count = _integer(entries, f"{_RELATION_PREFIX}calendar_territory_count")
    if calendar_territory_count != len(definitions):
        raise RegistryValidationError(
            "calendar CCAA catalogue relation count does not match its declared territory order",
        )
    includes_foral_territories = _boolean(entries, f"{_RELATION_PREFIX}includes_foral_territories")
    includes_autonomous_cities = _boolean(entries, f"{_RELATION_PREFIX}includes_autonomous_cities")
    return CalendarCcaaCatalogue(
        definitions=tuple(definitions),
        tax_residence_fact_id=tax_residence_fact_id,
        tax_residence_common_regime_count=tax_residence_common_regime_count,
        includes_foral_territories=includes_foral_territories,
        includes_autonomous_cities=includes_autonomous_cities,
    )


@cache_governed_projection(maxsize=64)
def _bundled_catalogue(effective_date: date) -> CalendarCcaaCatalogue:
    return _catalogue(_bundled_entries(effective_date))


def resolve_calendar_ccaa_catalogue(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> CalendarCcaaCatalogue:
    """Resolve the selected dated deadline-calendar territory catalogue."""
    coordinate = effective_date or today_madrid()
    if authority is None and governed_facts_in_scope() is None:
        return _bundled_catalogue(coordinate)
    return _catalogue(_selected_entries(effective_date=coordinate, authority=authority))


def require_calendar_ccaa(
    value: object,
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> CalendarCCAA:
    """Project one ISO 3166-2:ES deadline-calendar code through fact 0143."""
    return resolve_calendar_ccaa_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).require(value)


__all__ = [
    "CalendarCcaaCatalogue",
    "CalendarCcaaDefinition",
    "require_calendar_ccaa",
    "resolve_calendar_ccaa_catalogue",
]
