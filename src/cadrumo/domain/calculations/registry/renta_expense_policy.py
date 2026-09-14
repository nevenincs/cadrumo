"""Registry-backed territorial policy declarations for Renta expenses."""

from __future__ import annotations

from datetime import date

from .errors import RegistryValidationError
from .facts.resolution import MappingFactQuery, ResolvedMappingFact
from .governed_fact_scope import GovernedFactSource, governed_facts_in_scope
from .schema_base import DateAxis

_RENTA_EXPENSE_POLICY_FACT_ID = "renta-expense-residence-policy"


def renta_expense_policy_declarations(
    profile_year: int,
    *,
    authority: GovernedFactSource | None = None,
) -> dict[str, str]:
    """Resolve the dated territorial-policy declarations for a filing year."""
    selected_authority = authority or governed_facts_in_scope()
    if selected_authority is None:
        raise RegistryValidationError("Renta expense policy requires an explicit authority operation or scope")
    resolved = selected_authority.resolve_governed_fact(
        MappingFactQuery(
            fact_id=_RENTA_EXPENSE_POLICY_FACT_ID,
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=date(profile_year, 12, 31),
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise RegistryValidationError("Renta expense policy must resolve as a mapping fact")
    declarations: dict[str, str] = {}
    for entry in resolved.payload.entries:
        key = str(entry.key)
        if key in declarations:
            raise RegistryValidationError(f"Renta expense policy contains duplicate key {key!r}")
        declarations[key] = str(entry.value)
    return declarations
