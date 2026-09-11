"""Direct authored-fact contract for IRNR treaty overrides."""

from __future__ import annotations

from datetime import date

import pytest

from cadrumo.core.irnr import ConvenioOverrideKind, TipoRentaIrnr
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.convenio import CONVENIO_OVERRIDE_FACT_ID
from cadrumo.domain.calculations.registry.facts.resolution import (
    OverrideFactQuery,
    ResolvedOverrideFact,
    resolve_governed_fact,
)
from cadrumo.domain.calculations.registry.facts.schema import FactSelector, GovernedFactCatalogue
from cadrumo.domain.calculations.registry.schema_base import DateAxis
from dev.registry.compiler.convenio import convenio_authority_from_facts
from dev.registry.compiler.fact_loader import load_governed_facts
from dev.registry.compiler.loader import load_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_EXPECTED_ROWS = {
    ("AR", "pension", "2025-01-01", "allocation_domestic_tariff", None, "convenio-es-ar-1992:art-19"),
    ("BE", "dividend", "2003-06-25", "ceiling", "0.15", "convenio-es-be-1995:art-10"),
    ("BE", "interest", "2003-06-25", "ceiling", "0.10", "convenio-es-be-1995:art-11"),
    ("BE", "canones", "2025-01-01", "ceiling", "0.05", "convenio-es-be-1995:art-12"),
    ("DE", "dividend", "2025-01-01", "ceiling", "0.15", "convenio-es-de-2011:art-10"),
    ("DE", "interest", "2025-01-01", "exempt", None, "convenio-es-de-2011:art-11"),
    ("DE", "canones", "2025-01-01", "exempt", None, "convenio-es-de-2011:art-12"),
    ("FR", "dividend", "2025-01-01", "ceiling", "0.15", "convenio-es-fr-1995:art-10"),
    ("FR", "interest", "2025-01-01", "ceiling", "0.10", "convenio-es-fr-1995:art-11"),
    ("FR", "canones", "2025-01-01", "ceiling", "0.05", "convenio-es-fr-1995:art-12"),
    ("GB", "general", "2025-01-01", "flat", "0.24", "convenio-es-gb-2013:art-6"),
    ("MA", "interest", "2025-01-01", "ceiling", "0.10", "convenio-es-ma-1978:art-11"),
    ("NL", "dividend", "1972-09-20", "ceiling", "0.15", "convenio-es-nl-1971:art-10"),
    ("NL", "interest", "1972-09-20", "ceiling", "0.10", "convenio-es-nl-1971:art-11"),
    ("NL", "canones", "2025-01-01", "ceiling", "0.06", "convenio-es-nl-1971:art-12"),
    ("PT", "dividend", "1995-06-28", "ceiling", "0.15", "convenio-es-pt-1993:art-10"),
    ("PT", "interest", "1995-06-28", "ceiling", "0.15", "convenio-es-pt-1993:art-11"),
    ("PT", "canones", "2025-01-01", "ceiling", "0.05", "convenio-es-pt-1993:art-12"),
    ("US", "dividend", "2019-11-27", "ceiling", "0.15", "convenio-es-us-1990:art-10"),
    ("US", "interest", "2019-11-27", "exempt", None, "convenio-es-us-1990:art-11"),
    ("US", "canones", "2019-11-27", "exempt", None, "convenio-es-us-1990:art-12"),
}


def _bundled_fact_catalogue() -> GovernedFactCatalogue:
    facts = load_governed_facts(bundled_path("registry", "aeat", "facts"))
    return GovernedFactCatalogue(facts={fact.fact_id: fact for fact in facts})


def test_authored_convenio_fact_preserves_every_row_and_its_legal_anchor() -> None:
    fact = _bundled_fact_catalogue().facts[CONVENIO_OVERRIDE_FACT_ID]
    actual_rows = {
        (
            {selector.name: selector.value for selector in variant.selectors}["country_code"],
            {selector.name: selector.value for selector in variant.selectors}["tipo_renta"],
            variant.valid_from.isoformat(),
            variant.payload.override_code,
            str(variant.payload.value) if variant.payload.value is not None else None,
            variant.legal_refs[0],
        )
        for variant in fact.variants
    }

    assert actual_rows == _EXPECTED_ROWS
    assert len(fact.variants) == 21
    for variant in fact.variants:
        assert variant.source_refs == (f"boe-{variant.legal_refs[0].replace(':', '-')}",)
        assert variant.source_citations[0].required_text == ("Art", variant.legal_refs[0].rsplit("-", 1)[-1])


def test_direct_fact_resolves_and_projects_the_existing_runtime_catalogue() -> None:
    root = bundled_path("registry", "aeat")
    catalogue = _bundled_fact_catalogue()
    resolved = resolve_governed_fact(
        catalogue,
        OverrideFactQuery(
            fact_id=CONVENIO_OVERRIDE_FACT_ID,
            date_axis=DateAxis.DEVENGO_DATE,
            effective_date=date(2025, 6, 30),
            selectors=(
                FactSelector(name="country_code", value="GB"),
                FactSelector(name="tipo_renta", value="general"),
            ),
        ),
        authority_digest="a" * 64,
    )
    _modelos, catalogues = load_registry_tree(root)
    convenio = convenio_authority_from_facts(catalogue, catalogues.legal)

    assert isinstance(resolved, ResolvedOverrideFact)
    assert resolved.payload.override_code == ConvenioOverrideKind.FLAT.value
    assert resolved.payload.value == "0.24"
    assert convenio.resolve("GB", TipoRentaIrnr.GENERAL, 2025) is not None
    assert convenio.resolve("DE", TipoRentaIrnr.INTEREST, 2025).kind is ConvenioOverrideKind.EXEMPT


def test_authored_convenio_fact_has_no_raw_treaty_provider_or_directory() -> None:
    root = bundled_path("registry", "aeat")

    assert not (root / "treaties").exists()
    assert not (root / "facts" / "0068-convenio-override.toml").is_dir()
