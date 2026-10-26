"""Authority query seam for registry-owned Modelo rendering declarations."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date

from ....core.time.clock import today_madrid
from .facts.resolution import MappingFactQuery, ResolvedMappingFact
from .governed_fact_scope import GovernedFactSource, require_governed_fact_authority
from .schema_base import DateAxis

_MODELO_RENDERING_FACT_ID = "modelo-rendering-tax-notice-catalogue"


def modelo_rendering_declarations(
    effective_date: date | None = None,
    *,
    authority: GovernedFactSource | None = None,
) -> Mapping[str, str]:
    """Resolve the selected Modelo rendering mapping from registry authority."""
    selected_authority = require_governed_fact_authority(authority, subject="Modelo rendering catalogue")
    resolved = selected_authority.resolve_governed_fact(
        MappingFactQuery(
            fact_id=_MODELO_RENDERING_FACT_ID,
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date or today_madrid(),
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
