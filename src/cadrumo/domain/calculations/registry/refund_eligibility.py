"""Typed projection of the governed IVA refund-period eligibility policy."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Final

from ....core.period import Period, accepted_filing_period_codes, registry_period_kind
from .errors import RegistryValidationError
from .facts.resolution import required_mapping_entry, unique_mapping_tokens
from .facts.string_mapping import (
    MappingValueWhitespace,
    StringMappingFact,
    StringMappingPolicy,
    unique_mapping_legal_refs,
)
from .schema_base import DateAxis

_ENTRY_SUBJECT: Final = "IVA refund eligibility policy"

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


_ENTRIES_POLICY = StringMappingPolicy(subject=_ENTRY_SUBJECT, value_whitespace=MappingValueWhitespace.PRESERVE)


_ENTRIES_FACT = StringMappingFact(fact_id=_FACT_ID, date_axis=DateAxis.FILING_PERIOD, policy=_ENTRIES_POLICY)


def _policy(entries: Mapping[str, str]) -> RefundEligibilityPolicy:
    definitions: list[RefundFinalPeriodDefinition] = []
    accepted_periods = frozenset(accepted_filing_period_codes())
    for raw_token in unique_mapping_tokens(entries, _FINAL_PERIOD_ORDER_KEY, subject=_ENTRY_SUBJECT):
        if raw_token not in accepted_periods:
            raise RegistryValidationError(
                f"IVA refund eligibility period {raw_token!r} is not a valid filing-period token",
            )
        prefix = f"{_FINAL_PERIOD_PREFIX}{raw_token}."
        declared_value = required_mapping_entry(entries, f"{prefix}value", subject=_ENTRY_SUBJECT)
        if declared_value != raw_token:
            raise RegistryValidationError(
                f"IVA refund eligibility period {raw_token!r} declares mismatched value {declared_value!r}",
            )
        cadence = required_mapping_entry(entries, f"{prefix}cadence", subject=_ENTRY_SUBJECT)
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
                description=required_mapping_entry(entries, f"{prefix}description", subject=_ENTRY_SUBJECT),
                legal_refs=unique_mapping_legal_refs(entries, f"{prefix}legal_refs", subject=_ENTRY_SUBJECT),
            ),
        )
    if not definitions:
        raise RegistryValidationError("IVA refund eligibility policy must declare a final-period set")
    return RefundEligibilityPolicy(definitions=tuple(definitions))


def resolve_refund_eligibility_policy(
    *,
    effective_date: date | None = None,
    authority: ValidatedRegistryAuthority | None = None,
) -> RefundEligibilityPolicy:
    """Resolve the dated refund-period policy, failing closed if absent.

    Core types:
    :class:`~cadrumo.domain.calculations.registry.authority.ValidatedRegistryAuthority`.
    """
    return _policy(_ENTRIES_FACT.resolve_scoped_entries(effective_date=effective_date, authority=authority))


def resolve_refund_eligibility_policy_for_period(
    period: Period,
    *,
    authority: ValidatedRegistryAuthority | None = None,
) -> RefundEligibilityPolicy:
    """Resolve refund eligibility at a concrete filing-period coordinate.

    Core types:
    :class:`~cadrumo.domain.calculations.registry.authority.ValidatedRegistryAuthority`.
    """
    effective_date = period.end_date if period.has_date_span() else date(period.filing_year, 12, 31)
    return resolve_refund_eligibility_policy(effective_date=effective_date, authority=authority)


__all__ = [
    "RefundEligibilityPolicy",
    "RefundFinalPeriodDefinition",
    "resolve_refund_eligibility_policy",
    "resolve_refund_eligibility_policy_for_period",
]
