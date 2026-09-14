"""Typed projection of the governed Anexo D inventory applicability fact."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from .errors import RegistryValidationError
from .facts.resolution import ResolvedScalarFact, ScalarFactQuery
from .schema_base import DateAxis

if TYPE_CHECKING:
    from .authority import ValidatedRegistryAuthority


_FACT_ID = "inventory-anexo-d-applicability"
_FILING_YEAR_UNIT = "filing_year"


def resolve_inventory_anexo_d_filing_year(
    *,
    filing_year: int,
    authority: ValidatedRegistryAuthority | None = None,
) -> int:
    """Resolve the applicable Anexo D filing year, failing closed if absent."""
    if authority is None:
        from .authority import bundled_authority

        authority = bundled_authority()
    resolved = authority.resolve_governed_fact(
        ScalarFactQuery(
            fact_id=_FACT_ID,
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=date(filing_year, 12, 31),
        ),
    )
    if not isinstance(resolved, ResolvedScalarFact):
        raise RegistryValidationError(f"{_FACT_ID} must resolve as a scalar fact")
    if resolved.payload.unit != _FILING_YEAR_UNIT:
        raise RegistryValidationError(
            f"{_FACT_ID} must use unit {_FILING_YEAR_UNIT!r}, got {resolved.payload.unit!r}",
        )
    value = resolved.payload.value
    if isinstance(value, bool) or not isinstance(value, int):
        raise RegistryValidationError(f"{_FACT_ID} must resolve to an integer filing year")
    return value


__all__ = ["resolve_inventory_anexo_d_filing_year"]
