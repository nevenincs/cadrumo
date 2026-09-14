"""Authority query seam for registry-owned Modelo rendering declarations."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date

from .errors import RegistryValidationError
from .facts.resolution import MappingFactQuery, ResolvedMappingFact
from .governed_fact_scope import GovernedFactSource, governed_facts_in_scope
from .schema_base import DateAxis

_MODELO_RENDERING_FACT_ID = "modelo-rendering-tax-notice-catalogue"


def modelo_rendering_declarations(
    effective_date: date | None = None,
    *,
    authority: GovernedFactSource | None = None,
) -> Mapping[str, str]:
    """Resolve the selected Modelo rendering mapping from registry authority."""
    selected_authority = authority or governed_facts_in_scope()
    if selected_authority is None:
        raise RegistryValidationError("Modelo rendering declarations require an explicit authority operation or scope")
    resolved = selected_authority.resolve_governed_fact(
        MappingFactQuery(
            fact_id=_MODELO_RENDERING_FACT_ID,
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date or date.today(),
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise TypeError("Modelo rendering declarations must resolve as a mapping fact")
    return {str(entry.key): str(entry.value) for entry in resolved.payload.entries}


def modelo_rendering_value(
    key: str,
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> str:
    """Resolve one required Modelo rendering declaration without a fallback."""
    declarations = modelo_rendering_declarations(effective_date, authority=authority)
    try:
        return declarations[key]
    except KeyError as exc:
        raise KeyError(f"Modelo rendering declaration {key!r} is missing") from exc


__all__ = ["modelo_rendering_declarations", "modelo_rendering_value"]
