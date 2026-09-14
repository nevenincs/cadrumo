"""Typed projection of the governed IVA refund-period eligibility policy."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from types import MappingProxyType
from typing import TYPE_CHECKING

from ....core.period import Period, accepted_filing_period_codes, registry_period_kind
from .errors import RegistryValidationError
from .facts.resolution import MappingFactQuery, ResolvedMappingFact
from .governed_fact_scope import GovernedFactSource, governed_facts_in_scope
from .schema_base import DateAxis

if TYPE_CHECKING:
    from .authority import ValidatedRegistryAuthority


_FACT_ID = "iva-refund-eligibility-policy"
_FINAL_PERIOD_ORDER_KEY = "refund.final_period.order"
_FINAL_PERIOD_PREFIX = "refund.final_period."


@dataclass(frozen=True, slots=True)
class RefundFinalPeriodDefinition:
    """One registry-declared final filing period and its legal metadata."""

    token: str
    cadence: str
    description: str
    legal_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RefundEligibilityPolicy:
    """Dated projection of the final-period refund eligibility policy."""

    definitions: tuple[RefundFinalPeriodDefinition, ...]

    @property
    def final_period_tokens(self) -> frozenset[str]:
        """Return the registry-declared final-period tokens."""
        return frozenset(definition.token for definition in self.definitions)

    def is_final_period(self, period: Period) -> bool:
        """Return whether ``period`` is declared final by this policy."""
        return period.registry_token in self.final_period_tokens


def _required(entries: Mapping[str, str], key: str) -> str:
    value = entries.get(key)
    if value is None or not value.strip():
        raise RegistryValidationError(f"IVA refund eligibility policy is missing {key!r}")
    return value.strip()


def _csv(entries: Mapping[str, str], key: str) -> tuple[str, ...]:
    values = tuple(token.strip() for token in _required(entries, key).split(",") if token.strip())
    if not values or len(values) != len(set(values)):
        raise RegistryValidationError(f"IVA refund eligibility policy {key!r} must contain unique tokens")
    return values


def _legal_refs(entries: Mapping[str, str], key: str) -> tuple[str, ...]:
    values = tuple(token.strip() for token in _required(entries, key).split(",") if token.strip())
    if not values or len(values) != len(set(values)):
        raise RegistryValidationError(f"IVA refund eligibility policy {key!r} must contain unique legal references")
    return values


def _mapping_entries(resolved: ResolvedMappingFact) -> Mapping[str, str]:
    entries: dict[str, str] = {}
    for entry in resolved.payload.entries:
        if not isinstance(entry.key, str) or not isinstance(entry.value, str):
            raise RegistryValidationError("IVA refund eligibility policy entries must be string-to-string")
        if entry.key in entries:
            raise RegistryValidationError(f"duplicate IVA refund eligibility policy key {entry.key!r}")
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
        raise RegistryValidationError("IVA refund eligibility policy must resolve as a mapping fact")
    return _mapping_entries(resolved)


@lru_cache(maxsize=64)
def _bundled_mapping_entries(effective_date: date) -> Mapping[str, str]:
    from .authority import bundled_authority

    return _resolve_entries(effective_date=effective_date, authority=bundled_authority())


def _selected_mapping_entries(
    *,
    effective_date: date,
    authority: ValidatedRegistryAuthority | None,
) -> Mapping[str, str]:
    selected = authority or governed_facts_in_scope()
    if selected is None:
        return _bundled_mapping_entries(effective_date)
    return _resolve_entries(effective_date=effective_date, authority=selected)


def _policy(entries: Mapping[str, str]) -> RefundEligibilityPolicy:
    definitions: list[RefundFinalPeriodDefinition] = []
    accepted_periods = frozenset(accepted_filing_period_codes())
    for raw_token in _csv(entries, _FINAL_PERIOD_ORDER_KEY):
        if raw_token not in accepted_periods:
            raise RegistryValidationError(
                f"IVA refund eligibility period {raw_token!r} is not a valid filing-period token",
            )
        prefix = f"{_FINAL_PERIOD_PREFIX}{raw_token}."
        declared_value = _required(entries, f"{prefix}value")
        if declared_value != raw_token:
            raise RegistryValidationError(
                f"IVA refund eligibility period {raw_token!r} declares mismatched value {declared_value!r}",
            )
        cadence = _required(entries, f"{prefix}cadence")
        try:
            expected_cadence = registry_period_kind(raw_token).value
        except ValueError as exc:
            raise RegistryValidationError(
                f"IVA refund eligibility period {raw_token!r} has an invalid cadence coordinate",
            ) from exc
        if cadence != expected_cadence:
            raise RegistryValidationError(
                f"IVA refund eligibility period {raw_token!r} declares cadence {cadence!r}, "
                f"expected {expected_cadence!r}",
            )
        definitions.append(
            RefundFinalPeriodDefinition(
                token=raw_token,
                cadence=cadence,
                description=_required(entries, f"{prefix}description"),
                legal_refs=_legal_refs(entries, f"{prefix}legal_refs"),
            ),
        )
    if not definitions:
        raise RegistryValidationError("IVA refund eligibility policy must declare a final-period set")
    return RefundEligibilityPolicy(definitions=tuple(definitions))


@lru_cache(maxsize=64)
def _bundled_policy(effective_date: date) -> RefundEligibilityPolicy:
    return _policy(_bundled_mapping_entries(effective_date))


def resolve_refund_eligibility_policy(
    *,
    effective_date: date | None = None,
    authority: ValidatedRegistryAuthority | None = None,
) -> RefundEligibilityPolicy:
    """Resolve the dated refund-period policy, failing closed if absent."""
    coordinate = effective_date or date.today()
    if authority is None and governed_facts_in_scope() is None:
        return _bundled_policy(coordinate)
    return _policy(_selected_mapping_entries(effective_date=coordinate, authority=authority))


def resolve_refund_eligibility_policy_for_period(
    period: Period,
    *,
    authority: ValidatedRegistryAuthority | None = None,
) -> RefundEligibilityPolicy:
    """Resolve refund eligibility at a concrete filing-period coordinate."""
    effective_date = period.end_date if period.has_date_span() else date(period.filing_year, 12, 31)
    return resolve_refund_eligibility_policy(effective_date=effective_date, authority=authority)


__all__ = [
    "RefundEligibilityPolicy",
    "RefundFinalPeriodDefinition",
    "resolve_refund_eligibility_policy",
    "resolve_refund_eligibility_policy_for_period",
]
