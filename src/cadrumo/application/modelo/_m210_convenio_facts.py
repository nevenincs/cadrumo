"""Typed governed-fact resolution shared by Modelo 210 treaty consumers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from ...core.irnr import ConvenioOverrideKind, TipoRentaIrnr
from ...domain.calculations.registry.authority import bundled_authority
from ...domain.calculations.registry.convenio import CONVENIO_OVERRIDE_FACT_ID
from ...domain.calculations.registry.errors import RegistryValidationError
from ...domain.calculations.registry.facts.resolution import OverrideFactQuery, ResolvedOverrideFact
from ...domain.calculations.registry.facts.schema import FactSelector
from ...domain.calculations.registry.schema_base import DateAxis


@dataclass(frozen=True, slots=True)
class ResolvedM210ConvenioOverride:
    """One provider-selected treaty override with its legal provenance."""

    kind: ConvenioOverrideKind
    rate: Decimal | None
    country_code: str
    document_id: str
    fact: ResolvedOverrideFact


def resolve_m210_convenio_override(
    *,
    country_code: str,
    tipo_renta: TipoRentaIrnr,
    devengo_date: date,
) -> ResolvedM210ConvenioOverride | None:
    """Resolve the exact dated treaty fact, returning ``None`` only for no row.

    Registry corruption, an ambiguous selection, and unsupported payloads are
    deliberately not translated into an ordinary no-match result: each remains
    a refusal from the typed authority boundary.
    """
    authority = bundled_authority()
    authority.validate_registry()
    normalized_country = country_code.upper()
    selectors = (
        FactSelector(name="country_code", value=normalized_country),
        FactSelector(name="tipo_renta", value=tipo_renta.value),
    )
    fact = authority.catalogues.facts.facts.get(CONVENIO_OVERRIDE_FACT_ID)
    if fact is None:
        raise RegistryValidationError(f"governed fact {CONVENIO_OVERRIDE_FACT_ID!r} is not registered")
    selector_identity = frozenset((selector.name, type(selector.value), selector.value) for selector in selectors)
    if not any(
        variant.date_axis is DateAxis.DEVENGO_DATE
        and variant.valid_from <= devengo_date
        and (variant.valid_to is None or devengo_date <= variant.valid_to)
        and frozenset((selector.name, type(selector.value), selector.value) for selector in variant.selectors)
        == selector_identity
        for variant in fact.variants
    ):
        return None
    resolved = authority.resolve_governed_fact(
        OverrideFactQuery(
            fact_id=CONVENIO_OVERRIDE_FACT_ID,
            date_axis=DateAxis.DEVENGO_DATE,
            effective_date=devengo_date,
            selectors=selectors,
        ),
    )
    if not isinstance(resolved, ResolvedOverrideFact):
        raise RegistryValidationError(f"convenio override resolved non-override fact {resolved.fact_id!r}")
    try:
        kind = ConvenioOverrideKind(resolved.payload.override_code)
    except ValueError as exc:
        raise RegistryValidationError(
            f"convenio override fact {resolved.fact_id!r} has unknown kind {resolved.payload.override_code!r}",
        ) from exc
    rate = resolved.payload.value
    if rate is not None and not isinstance(rate, Decimal):
        raise RegistryValidationError(f"convenio override fact {resolved.fact_id!r} resolved non-decimal rate {rate!r}")
    if not resolved.legal_refs:
        raise RegistryValidationError(f"convenio override fact {resolved.fact_id!r} lacks legal provenance")
    try:
        document_id = authority.catalogues.legal[resolved.legal_refs[0]].document_id
    except KeyError as exc:
        raise RegistryValidationError(
            f"convenio override fact {resolved.fact_id!r} names unknown legal reference {resolved.legal_refs[0]!r}",
        ) from exc
    return ResolvedM210ConvenioOverride(
        kind=kind,
        rate=rate,
        country_code=normalized_country,
        document_id=document_id,
        fact=resolved,
    )


__all__ = ["ResolvedM210ConvenioOverride", "resolve_m210_convenio_override"]
