"""Resolve the governed IVA compensation carry-forward window."""

from __future__ import annotations

from datetime import date

from ..calculations.registry.authority import PinnedAuthorityOperation
from ..calculations.registry.errors import RegistryValidationError
from ..calculations.registry.facts.resolution import ResolvedScalarFact, ScalarFactQuery
from ..calculations.registry.schema_base import DateAxis

_CARRY_WINDOW_FACT_ID = "liva-art-99-compensation-carry-window-years"


def resolve_iva_compensation_carry_window_years(
    *,
    effective_date: date,
    operation: PinnedAuthorityOperation,
) -> int:
    """Resolve the carry-window years for an explicit filing-period date.

    ``operation`` is required so every consumer resolves against the authority
    generation it already holds. This resolver never consults ambient scope or
    opens a fresh authority operation.
    """
    resolved = operation.resolve_governed_fact(
        ScalarFactQuery(
            fact_id=_CARRY_WINDOW_FACT_ID,
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date,
        ),
    )
    if not isinstance(resolved, ResolvedScalarFact):
        raise RegistryValidationError("IVA compensation carry-window fact must resolve as a scalar fact")

    value = resolved.payload.value
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise RegistryValidationError(
            f"IVA compensation carry-window fact {resolved.fact_id!r} resolved invalid years payload {value!r}",
        )
    return value


__all__ = ["resolve_iva_compensation_carry_window_years"]
