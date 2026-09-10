"""Source-grounded Modelo 036 selectors for RIRPF articles 109 and 110."""

from __future__ import annotations

from datetime import date

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.facts.legal_parameters import compile_legal_parameter_facts
from cadrumo.domain.calculations.registry.facts.loader import load_governed_facts
from cadrumo.domain.calculations.registry.facts.resolution import (
    EntitySetFactQuery,
    ResolvedEntitySetFact,
    resolve_governed_fact,
)
from cadrumo.domain.calculations.registry.facts.schema import GovernedFactCatalogue
from cadrumo.domain.calculations.registry.facts.validation import governed_fact_catalogue_failures
from cadrumo.domain.calculations.registry.loader import load_shared_catalogues
from cadrumo.domain.calculations.registry.schema_base import DateAxis

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_SELECTOR_IDS = frozenset(
    {
        "rd-439-2007-art-109:selector-m036-actividades-exencion-pago-fraccionado",
        "rd-439-2007-art-109:selector-m036-actividades-base-neta-de-subvenciones",
        "rd-439-2007-art-110:selector-m036-actividades-pago-fraccionado-agrarias-pesqueras",
        "modelo-131:selector-m036-volumen-ingresos-agrario",
    }
)
_M036_TABLE_SOURCE = "aeat-m036-activity-code-table-2026-03-26"
_ARTICLE_109_SOURCE = "boe-rirpf-art-109-2007-04-01"
_ARTICLE_110_SOURCE = "boe-rirpf-art-110-2018-12-23"
_FIRST_GROUNDED_DATE = date(2026, 3, 26)
_M131_FIRST_GROUNDED_DATE = date(2026, 4, 1)


def _catalogue() -> GovernedFactCatalogue:
    facts = load_governed_facts(bundled_path("registry", "aeat", "facts"))
    return GovernedFactCatalogue(facts={fact.fact_id: fact for fact in facts if fact.fact_id in _SELECTOR_IDS})


def _resolve(fact_id: str, effective_date: date) -> ResolvedEntitySetFact:
    resolved = resolve_governed_fact(
        _catalogue(),
        EntitySetFactQuery(fact_id=fact_id, date_axis=DateAxis.FILING_PERIOD, effective_date=effective_date),
        authority_digest="7" * 64,
    )
    assert isinstance(resolved, ResolvedEntitySetFact)
    return resolved


@pytest.mark.parametrize(
    ("fact_id", "entities", "source_refs"),
    (
        (
            "rd-439-2007-art-109:selector-m036-actividades-exencion-pago-fraccionado",
            frozenset({"A02", "A04", "A05", "B01", "B02", "B03"}),
            (_M036_TABLE_SOURCE, _ARTICLE_109_SOURCE),
        ),
        (
            "rd-439-2007-art-109:selector-m036-actividades-base-neta-de-subvenciones",
            frozenset({"A02", "B01", "B02", "B03"}),
            (_M036_TABLE_SOURCE, _ARTICLE_109_SOURCE),
        ),
        (
            "rd-439-2007-art-110:selector-m036-actividades-pago-fraccionado-agrarias-pesqueras",
            frozenset({"A02", "B01", "B02", "B03", "B05"}),
            (_M036_TABLE_SOURCE, _ARTICLE_110_SOURCE),
        ),
        (
            "modelo-131:selector-m036-volumen-ingresos-agrario",
            frozenset({"A02", "B01", "B02", "B03"}),
            (_M036_TABLE_SOURCE, "aeat-modelo-131-instructions-2026-04-01", _ARTICLE_110_SOURCE),
        ),
    ),
)
def test_payment_fraction_selectors_resolve_from_the_bounded_m036_mapping_and_exact_boe_redaction(
    fact_id: str, entities: frozenset[str], source_refs: tuple[str, ...]
) -> None:
    effective_date = _M131_FIRST_GROUNDED_DATE if fact_id.startswith("modelo-131:") else _FIRST_GROUNDED_DATE
    resolved = _resolve(fact_id, effective_date)

    assert resolved.payload.entities == entities
    assert resolved.variant_id.endswith(effective_date.isoformat())
    assert resolved.source_refs == source_refs


def test_payment_fraction_selectors_are_not_projected_by_the_legal_parameter_adapter() -> None:
    adapter_ids = {fact.fact_id for fact in compile_legal_parameter_facts(bundled_path("registry", "aeat"))}
    authored_ids = {fact.fact_id for fact in load_governed_facts(bundled_path("registry", "aeat", "facts"))}

    assert not _SELECTOR_IDS & adapter_ids
    assert "rd-439-2007-art-110:selector-m036-actividades-pago-fraccionado-agrario-objetiva" not in authored_ids


@pytest.mark.parametrize(
    ("fact_id", "before_first_window"),
    (
        ("rd-439-2007-art-109:selector-m036-actividades-exencion-pago-fraccionado", date(2026, 3, 25)),
        ("rd-439-2007-art-109:selector-m036-actividades-base-neta-de-subvenciones", date(2026, 3, 25)),
        ("rd-439-2007-art-110:selector-m036-actividades-pago-fraccionado-agrarias-pesqueras", date(2026, 3, 25)),
        ("modelo-131:selector-m036-volumen-ingresos-agrario", date(2026, 3, 31)),
    ),
)
def test_payment_fraction_selectors_refuse_before_their_first_citable_window(
    fact_id: str, before_first_window: date
) -> None:
    with pytest.raises(RegistryValidationError, match="has no variant for the exact query context"):
        _resolve(fact_id, before_first_window)


def test_payment_fraction_selectors_cite_hash_pinned_boe_redactions_and_the_m036_table() -> None:
    source_root = bundled_path()
    shared = load_shared_catalogues(source_root / "registry" / "aeat")
    catalogue = _catalogue()

    assert shared.sources[_ARTICLE_109_SOURCE].sha256 == "ca201b3eb296e5af063ff5bb1ff9944fc9e14f0cf84053cb29c002245397d2c9"
    assert shared.sources[_ARTICLE_109_SOURCE].bytes == 1994
    assert shared.sources[_ARTICLE_109_SOURCE].applies_from == date(2007, 4, 1)
    assert shared.sources[_ARTICLE_110_SOURCE].sha256 == "2d2f769c57987b8a14fa8ed861ef921a0345a1d8b898d3342f0c9de87ba5405c"
    assert shared.sources[_ARTICLE_110_SOURCE].bytes == 11554
    assert shared.sources[_ARTICLE_110_SOURCE].applies_from == date(2018, 12, 23)
    assert shared.sources[_M036_TABLE_SOURCE].applies_from == _FIRST_GROUNDED_DATE
    assert catalogue.facts["modelo-131:selector-m036-volumen-ingresos-agrario"].variants[0].valid_from == _M131_FIRST_GROUNDED_DATE
    assert shared.sources["aeat-modelo-131-instructions-2026-04-01"].applies_from == _M131_FIRST_GROUNDED_DATE
    assert (
        governed_fact_catalogue_failures(
            catalogue,
            legal_ref_ids=shared.legal,
            source_ref_ids=shared.sources,
            legal_refs=shared.legal,
            source_refs=shared.sources,
            source_root=source_root,
        )
        == ()
    )
