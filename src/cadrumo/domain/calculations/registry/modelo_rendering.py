"""Authority query seam for registry-owned Modelo rendering declarations."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date

from .facts.string_mapping import MappingValueWhitespace, StringMappingFact, StringMappingPolicy
from .governed_fact_scope import GovernedFactSource
from .schema_base import DateAxis

_MODELO_RENDERING_FACT_ID = "modelo-rendering-tax-notice-catalogue"

_MODELO_RENDERING_FACT = StringMappingFact(
    fact_id=_MODELO_RENDERING_FACT_ID,
    date_axis=DateAxis.FILING_PERIOD,
    policy=StringMappingPolicy(subject="Modelo rendering catalogue", value_whitespace=MappingValueWhitespace.PRESERVE),
)


def modelo_rendering_declarations(
    effective_date: date | None = None,
    *,
    authority: GovernedFactSource | None = None,
) -> Mapping[str, str]:
    """Resolve the Modelo rendering mapping from registry authority.

    A dated call reads that date's edition; without a date the read takes the
    editions inside the support envelope, never the run date.
    """
    return _MODELO_RENDERING_FACT.resolve_scoped_entries(effective_date=effective_date, authority=authority)


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
