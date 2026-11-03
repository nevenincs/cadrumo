"""Typed projection of the governed Anexo D inventory applicability fact."""

from __future__ import annotations

from datetime import date

from .errors import RegistryValidationError
from .facts.resolution import ResolvedScalarFact, ScalarFactQuery
from .governed_fact_scope import GovernedFactSource, require_governed_fact_authority
from .schema_base import DateAxis

_FACT_ID = "inventory-anexo-d-applicability"
_FILING_YEAR_UNIT = "filing_year"


def resolve_inventory_anexo_d_first_filing_year(
    *,
    filing_year: int,
    authority: GovernedFactSource | None = None,
) -> int:
    """Resolve the first filing year the Anexo D inventory rows are authored for, failing closed if absent.

    The fact is read at ``filing_year`` through the registry's temporal fact
    selection, which carries its open variant past the newest authored edition.
    """
    authority = require_governed_fact_authority(authority, subject="inventory Anexo D applicability")
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


def inventory_anexo_d_applies(
    *,
    filing_year: int,
    authority: GovernedFactSource | None = None,
) -> bool:
    """Whether the Anexo D inventory rows apply to ``filing_year``, failing closed if the fact is absent.

    The rows apply from the first filing year the governed fact names, and a
    year no edition authors reads the nearest edition the way every other
    registry reader does, so a projected year applies exactly when its edition
    does.
    """
    first_filing_year = resolve_inventory_anexo_d_first_filing_year(filing_year=filing_year, authority=authority)
    return filing_year >= first_filing_year


__all__ = ["inventory_anexo_d_applies", "resolve_inventory_anexo_d_first_filing_year"]
