"""Authority query seam for registry-owned Spanish tax-ID declarations."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date

from .authority import bundled_authority
from .facts.resolution import MappingFactQuery, ResolvedMappingFact
from .schema_base import DateAxis

_TAX_ID_FORMAT_FACT_ID = "spanish-tax-identifier-format"


def tax_id_format_declarations(effective_date: date | None = None) -> Mapping[str, str]:
    """Resolve Spanish tax-ID shape declarations from published authority."""
    resolved = bundled_authority().resolve_governed_fact(
        MappingFactQuery(
            fact_id=_TAX_ID_FORMAT_FACT_ID,
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date or date.today(),
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise ValueError(f"Spanish tax-ID format did not resolve as a mapping: {_TAX_ID_FORMAT_FACT_ID}")
    return {str(entry.key): str(entry.value) for entry in resolved.payload.entries}


def tax_id_format_value(key: str, *, effective_date: date | None = None) -> str:
    """Return one required Spanish tax-ID declaration or fail closed."""
    declarations = tax_id_format_declarations(effective_date)
    try:
        return declarations[key]
    except KeyError as exc:
        raise ValueError(f"Spanish tax-ID format declaration is missing: {key}") from exc


__all__ = ["tax_id_format_declarations", "tax_id_format_value"]
