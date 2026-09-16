"""Typed projection of the registry-owned proportionality vocabulary."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType
from typing import Final

from ..calculations.registry.errors import RegistryValidationError
from ..calculations.registry.facts.resolution import MappingFactQuery, ResolvedMappingFact, required_mapping_entry
from ..calculations.registry.facts.schema import FactSelector
from ..calculations.registry.governed_fact_scope import GovernedFactSource, governed_facts_in_scope
from ..calculations.registry.schema_base import DateAxis
from .proportionality import ProportionalityKind, StatutoryCapPeriod

_ENTRY_SUBJECT: Final = "proportionality vocabulary"

_FACT_ID = "categories.profile"
_SCOPE_SELECTOR = FactSelector(name="scope", value="proportionality_vocabulary")
_KIND_ORDER_KEY = "proportionality_kind.order"
_PERIOD_ORDER_KEY = "statutory_cap_period.order"
_KIND_PREFIX = "proportionality_kind."
_PERIOD_PREFIX = "statutory_cap_period."
_KIND_ROLES = (
    "is_full_deductible",
    "is_usage_ratio",
    "is_statutory_cap",
    "requires_fixed_pct",
    "is_non_deductible",
    "requires_exclusive_use",
)


@dataclass(frozen=True, slots=True)
class ProportionalityCatalogue:
    """Dated facts projection for proportionality tokens and evaluator roles."""

    kinds: tuple[ProportionalityKind, ...]
    periods: tuple[StatutoryCapPeriod, ...]

    @property
    def all_kinds(self) -> frozenset[ProportionalityKind]:
        """Return every kind declared by the selected authority."""
        return frozenset(self.kinds)

    @property
    def all_periods(self) -> frozenset[StatutoryCapPeriod]:
        """Return every cap period declared by the selected authority."""
        return frozenset(self.periods)

    def require_kind(self, value: object) -> ProportionalityKind:
        """Return one canonical projected kind or refuse it."""
        raw = value.value if isinstance(value, ProportionalityKind) else value
        if not isinstance(raw, str) or not raw.strip():
            raise RegistryValidationError("proportionality kind must be a non-empty string token")
        for kind in self.kinds:
            if kind.value == raw:
                return kind
        raise RegistryValidationError(f"proportionality kind {raw!r} is not declared by fact {_FACT_ID!r}")

    def require_period(self, value: object) -> StatutoryCapPeriod:
        """Return one canonical projected cap period or refuse it."""
        raw = value.value if isinstance(value, StatutoryCapPeriod) else value
        if not isinstance(raw, str) or not raw.strip():
            raise RegistryValidationError("statutory-cap period must be a non-empty string token")
        for period in self.periods:
            if period.value == raw:
                return period
        raise RegistryValidationError(f"statutory-cap period {raw!r} is not declared by fact {_FACT_ID!r}")


def _mapping_entries(resolved: ResolvedMappingFact) -> Mapping[str, str]:
    """Narrow a mapping payload to a unique string-to-string mapping."""
    entries: dict[str, str] = {}
    for entry in resolved.payload.entries:
        if not isinstance(entry.key, str) or not isinstance(entry.value, str):
            raise RegistryValidationError("proportionality vocabulary entries must be string-to-string")
        if entry.key in entries:
            raise RegistryValidationError(f"duplicate proportionality vocabulary key {entry.key!r}")
        entries[entry.key] = entry.value
    return MappingProxyType(entries)


def _csv(entries: Mapping[str, str], key: str) -> tuple[str, ...]:
    values = tuple(
        token.strip()
        for token in required_mapping_entry(entries, key, subject=_ENTRY_SUBJECT).split(",")
        if token.strip()
    )
    if not values or len(values) != len(set(values)):
        raise RegistryValidationError(f"proportionality vocabulary {key!r} must contain unique tokens")
    return values


def _bool(entries: Mapping[str, str], key: str) -> bool:
    value = required_mapping_entry(entries, key, subject=_ENTRY_SUBJECT).lower()
    if value == "true":
        return True
    if value == "false":
        return False
    raise RegistryValidationError(f"proportionality vocabulary {key!r} must be true or false")


def _resolve_entries(*, effective_date: date, authority: GovernedFactSource) -> Mapping[str, str]:
    resolved = authority.resolve_governed_fact(
        MappingFactQuery(
            fact_id=_FACT_ID,
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date,
            selectors=(_SCOPE_SELECTOR,),
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise RegistryValidationError("proportionality vocabulary must resolve as a mapping fact")
    return _mapping_entries(resolved)


def resolve_proportionality_catalogue(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> ProportionalityCatalogue:
    """Resolve and validate the dated proportionality vocabulary."""
    coordinate = effective_date or date.today()
    selected = authority or governed_facts_in_scope()
    if selected is None:
        raise RegistryValidationError("proportionality catalogue requires an explicit authority operation or scope")
    entries = _resolve_entries(effective_date=coordinate, authority=selected)

    kinds: list[ProportionalityKind] = []
    for raw_token in _csv(entries, _KIND_ORDER_KEY):
        prefix = f"{_KIND_PREFIX}{raw_token}."
        declared_value = required_mapping_entry(entries, f"{prefix}value", subject=_ENTRY_SUBJECT)
        if declared_value != raw_token:
            raise RegistryValidationError(
                f"proportionality kind {raw_token!r} declares mismatched value {declared_value!r}",
            )
        roles = {role: _bool(entries, f"{prefix}{role}") for role in _KIND_ROLES}
        kinds.append(ProportionalityKind.from_registry(raw_token, **roles))

    periods: list[StatutoryCapPeriod] = []
    for raw_token in _csv(entries, _PERIOD_ORDER_KEY):
        prefix = f"{_PERIOD_PREFIX}{raw_token}."
        declared_value = required_mapping_entry(entries, f"{prefix}value", subject=_ENTRY_SUBJECT)
        if declared_value != raw_token:
            raise RegistryValidationError(
                f"statutory-cap period {raw_token!r} declares mismatched value {declared_value!r}",
            )
        periods.append(
            StatutoryCapPeriod.from_registry(
                raw_token,
                is_per_person=_bool(entries, f"{prefix}is_per_person"),
            ),
        )

    catalogue = ProportionalityCatalogue(kinds=tuple(kinds), periods=tuple(periods))
    if not catalogue.kinds or not catalogue.periods:
        raise RegistryValidationError("proportionality vocabulary must declare kinds and cap periods")
    return catalogue


def require_proportionality_kind(
    value: object,
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> ProportionalityKind:
    """Return one registry-declared proportionality kind or refuse it."""
    return resolve_proportionality_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).require_kind(value)


def require_statutory_cap_period(
    value: object,
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> StatutoryCapPeriod:
    """Return one registry-declared cap period or refuse it."""
    return resolve_proportionality_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).require_period(value)


__all__ = [
    "ProportionalityCatalogue",
    "require_proportionality_kind",
    "require_statutory_cap_period",
    "resolve_proportionality_catalogue",
]
