"""How many years a cobros y pagos election binds, read from the dated governed fact.

RD 439/2007 art. 7.2.1.º makes the statement in the return the election and binds
it for a minimum term; the term is registry data, selected by the ejercicio asked about.
"""

from __future__ import annotations

from datetime import date
from typing import Final

from .errors import RegistryValidationError
from .facts.resolution import ResolvedScalarFact, ScalarFactQuery, reading_dated_facts_below_support
from .governed_fact_scope import GovernedFactSource, require_governed_fact_authority
from .schema_base import DateAxis

_FACT_ID: Final = "rirpf-art-7-cash-election-minimum-years"
_UNIT: Final = "years"


def cash_election_minimum_years(*, filing_year: int, authority: GovernedFactSource | None = None) -> int:
    """Return the term in force for ``filing_year``'s ejercicio.

    A taxpayer's election can date from before the years the product files for, so
    the read reaches below the support floor as far as the fact itself reaches.

    Raises:
        InternalInvariantError: When no authority is supplied and no scope is active.
        GovernedFactNotApplicableError: When the fact does not reach that ejercicio.
        RegistryValidationError: When the fact is not a whole number of years.
    """
    selected = require_governed_fact_authority(authority, subject=_FACT_ID)
    with reading_dated_facts_below_support():
        query = ScalarFactQuery(
            fact_id=_FACT_ID,
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=date(filing_year, 12, 31),
        )
    resolved = selected.resolve_governed_fact(query)
    if not isinstance(resolved, ResolvedScalarFact) or resolved.payload.unit != _UNIT:
        raise RegistryValidationError(f"{_FACT_ID} must resolve as a scalar in {_UNIT}")
    value = resolved.payload.value
    if isinstance(value, bool) or not isinstance(value, int):
        raise RegistryValidationError(f"{_FACT_ID} must resolve to a whole number of years")
    return value


__all__ = ["cash_election_minimum_years"]
