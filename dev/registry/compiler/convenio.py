"""Project canonical Convenio override facts into the runtime catalogue."""

from __future__ import annotations

from collections.abc import Mapping

from cadrumo.core.irnr import ConvenioOverrideKind, TipoRentaIrnr
from cadrumo.domain.calculations.registry.convenio import (
    CONVENIO_OVERRIDE_FACT_ID,
    ConvenioAuthority,
    ConvenioOverrideRow,
    ConvenioTreaty,
)
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.facts.schema import (
    GovernedFactCatalogue,
    GovernedFactFamily,
    OverrideFactPayload,
)
from cadrumo.domain.calculations.registry.schema_base import DateAxis
from cadrumo.domain.calculations.registry.schema_references import LegalReference

__all__ = ["convenio_authority_from_facts"]


def convenio_authority_from_facts(
    facts: GovernedFactCatalogue,
    legal: Mapping[str, LegalReference],
) -> ConvenioAuthority:
    """Build the immutable runtime catalogue from the canonical override fact.

    The fact is the sole declaration of treaty applicability and evidence. This
    projection only retains the established typed lookup shape used by the IRNR
    runtime; it never reads a second treaty source surface.
    """
    fact = facts.facts.get(CONVENIO_OVERRIDE_FACT_ID)
    if fact is None:
        raise RegistryValidationError(f"governed fact {CONVENIO_OVERRIDE_FACT_ID!r} is not registered")
    if fact.family is not GovernedFactFamily.OVERRIDE:
        raise RegistryValidationError(f"governed fact {CONVENIO_OVERRIDE_FACT_ID!r} must be an override family")

    rows_by_country: dict[str, list[ConvenioOverrideRow]] = {}
    document_by_country: dict[str, str] = {}
    for variant in fact.variants:
        if variant.date_axis is not DateAxis.DEVENGO_DATE:
            raise RegistryValidationError(
                f"convenio fact variant {variant.variant_id!r} must use devengo_date applicability",
            )
        selector_values = {selector.name: selector.value for selector in variant.selectors}
        if set(selector_values) != {"country_code", "tipo_renta"}:
            raise RegistryValidationError(
                f"convenio fact variant {variant.variant_id!r} must select exactly country_code and tipo_renta",
            )
        country_code_value = selector_values["country_code"]
        if not isinstance(country_code_value, str):
            raise RegistryValidationError(
                f"convenio fact variant {variant.variant_id!r} country_code must be text",
            )
        country_code = country_code_value.upper()
        if len(country_code) != 2 or not country_code.isalpha():
            raise RegistryValidationError(
                f"convenio fact variant {variant.variant_id!r} has invalid country_code {country_code!r}",
            )
        if not isinstance(variant.payload, OverrideFactPayload):
            raise RegistryValidationError(
                f"convenio fact variant {variant.variant_id!r} must carry an override payload",
            )
        if not variant.legal_refs:
            raise RegistryValidationError(f"convenio fact variant {variant.variant_id!r} must declare legal_refs")
        legal_ref_anchor = variant.legal_refs[0]
        try:
            document_id = legal[legal_ref_anchor].document_id
        except KeyError as exc:
            raise RegistryValidationError(
                f"convenio fact variant {variant.variant_id!r} legal_ref {legal_ref_anchor!r} is not registered",
            ) from exc
        previous_document_id = document_by_country.setdefault(country_code, document_id)
        if previous_document_id != document_id:
            raise RegistryValidationError(
                f"convenio country {country_code!r} cannot combine legal documents "
                f"{previous_document_id!r} and {document_id!r}",
            )
        tipo_renta_value = selector_values["tipo_renta"]
        if not isinstance(tipo_renta_value, str):
            raise RegistryValidationError(
                f"convenio fact variant {variant.variant_id!r} tipo_renta must be text",
            )
        rows_by_country.setdefault(country_code, []).append(
            ConvenioOverrideRow(
                tipo_renta=TipoRentaIrnr(tipo_renta_value),
                kind=ConvenioOverrideKind(variant.payload.override_code),
                rate=str(variant.payload.value) if variant.payload.value is not None else None,
                legal_ref_anchor=legal_ref_anchor,
                legal_refs=variant.legal_refs,
                valid_from=variant.valid_from,
                valid_to=variant.valid_to,
            ),
        )
    return ConvenioAuthority(
        treaties={
            country_code: ConvenioTreaty(
                country_code=country_code,
                document_id=document_by_country[country_code],
                overrides=tuple(rows),
            )
            for country_code, rows in sorted(rows_by_country.items())
        },
    )
