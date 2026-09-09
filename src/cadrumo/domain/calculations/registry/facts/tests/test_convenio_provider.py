"""Convenio adapter contracts for the governed-fact authority."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ......core.irnr import ConvenioOverrideKind, TipoRentaIrnr
from ......core.resources.bundled_data import bundled_path
from ...authority import ValidatedRegistryAuthority
from ...convenio import (
    CONVENIO_OVERRIDE_FACT_ID,
    compile_convenio_facts,
    load_convenio_authority,
)
from ...schema_base import DateAxis
from ..resolution import OverrideFactQuery, ResolvedOverrideFact, resolve_governed_fact
from ..schema import FactSelector, GovernedFactCatalogue

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def convenio_override_query(country_code: str, tipo_renta: TipoRentaIrnr, devengo_date: date) -> OverrideFactQuery:
    return OverrideFactQuery(
        fact_id=CONVENIO_OVERRIDE_FACT_ID,
        date_axis=DateAxis.DEVENGO_DATE,
        effective_date=devengo_date,
        selectors=(
            FactSelector(name="country_code", value=country_code.upper()),
            FactSelector(name="tipo_renta", value=tipo_renta.value),
        ),
    )


def test_convenio_provider_projects_exact_typed_overrides_with_provenance() -> None:
    root = bundled_path("registry", "aeat")
    fact = compile_convenio_facts(root)[0]
    catalogue = GovernedFactCatalogue(facts={fact.fact_id: fact})

    resolved = resolve_governed_fact(
        catalogue,
        convenio_override_query("gb", TipoRentaIrnr.GENERAL, date(2025, 6, 30)),
        authority_digest="a" * 64,
    )

    assert isinstance(resolved, ResolvedOverrideFact)
    assert resolved.fact_id == CONVENIO_OVERRIDE_FACT_ID
    assert resolved.payload.override_code == ConvenioOverrideKind.FLAT.value
    assert resolved.payload.value == Decimal("0.24")
    assert resolved.payload.unit == "ratio"
    assert resolved.legal_refs == (
        "convenio-es-gb-2013:art-6",
        "trlirnr-rdleg-5-2004:art-25.1.a",
    )
    assert resolved.source_refs == ("boe-convenio-es-gb-2013-art-6",)
    assert resolved.source_citations[0].required_text == ("Art", "6")


def test_convenio_provider_preserves_every_legacy_row_and_non_rate_kind() -> None:
    root = bundled_path("registry", "aeat")
    authority = load_convenio_authority(root / "treaties")
    fact = compile_convenio_facts(root)[0]

    assert len(fact.variants) == sum(len(treaty.overrides) for treaty in authority.treaties.values())
    catalogue = GovernedFactCatalogue(facts={fact.fact_id: fact})
    resolved = resolve_governed_fact(
        catalogue,
        convenio_override_query("DE", TipoRentaIrnr.INTEREST, date(2025, 1, 1)),
        authority_digest="b" * 64,
    )

    assert isinstance(resolved, ResolvedOverrideFact)
    assert resolved.payload.override_code == ConvenioOverrideKind.EXEMPT.value
    assert resolved.payload.value is None
    assert authority.resolve("DE", TipoRentaIrnr.INTEREST, 2025) is not None


def test_convenio_provider_references_validate_through_full_authority(
    registry_authority: ValidatedRegistryAuthority,
) -> None:
    registry_authority.validate_registry()
    resolved = registry_authority.resolve_governed_fact(
        convenio_override_query("GB", TipoRentaIrnr.GENERAL, date(2025, 1, 1)),
    )

    assert isinstance(resolved, ResolvedOverrideFact)
    assert resolved.source_refs == ("boe-convenio-es-gb-2013-art-6",)
