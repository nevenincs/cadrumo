"""Authority query seam for the registry-owned tax-domain catalogue."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date

from ....core.tax_domain import TaxDomain
from .authority import bundled_authority
from .facts.resolution import MappingFactQuery, ResolvedMappingFact
from .schema_base import DateAxis

_TAX_DOMAIN_FACT_ID = "tax-domain-catalogue"


def tax_domain_registry_declarations(effective_date: date | None = None) -> Mapping[str, str]:
    """Resolve the selected tax-domain catalogue from published authority."""
    resolved = bundled_authority().resolve_governed_fact(
        MappingFactQuery(
            fact_id=_TAX_DOMAIN_FACT_ID,
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date or date.today(),
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise ValueError(f"tax-domain catalogue did not resolve as a mapping: {_TAX_DOMAIN_FACT_ID}")
    return {str(entry.key): str(entry.value) for entry in resolved.payload.entries}


def tax_domain_metadata(
    domain: TaxDomain | str,
    *,
    effective_date: date | None = None,
) -> Mapping[str, str]:
    """Return registry metadata for one tax-domain identifier."""
    normalized = TaxDomain(domain)
    declarations = tax_domain_registry_declarations(effective_date)
    prefix = f"tax_domain.{normalized.value}."
    return {
        key.removeprefix(prefix): value
        for key, value in declarations.items()
        if key.startswith(prefix)
    }


def registered_tax_domain(value: str | TaxDomain, *, effective_date: date | None = None) -> TaxDomain:
    """Validate that an identifier is a currently registered tax domain."""
    normalized = TaxDomain(value)
    declarations = tax_domain_registry_declarations(effective_date)
    if f"tax_domain.{normalized.value}.description" not in declarations:
        raise ValueError(f"tax-domain metadata is missing for {normalized.value!r}")
    return normalized


__all__ = ["registered_tax_domain", "tax_domain_metadata", "tax_domain_registry_declarations"]
