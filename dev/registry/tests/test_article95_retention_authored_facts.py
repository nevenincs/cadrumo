"""BOE-redaction grounding and adapter retirement for RIRPF art. 95 rates."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.facts.resolution import (
    ResolvedScalarFact,
    ScalarFactQuery,
    resolve_governed_fact,
)
from cadrumo.domain.calculations.registry.facts.schema import GovernedFactCatalogue
from dev.registry.compiler.fact_validation import governed_fact_catalogue_failures
from cadrumo.domain.calculations.registry.schema_base import DateAxis
from dev.registry.compiler.fact_loader import load_governed_facts
from dev.registry.compiler.loader import load_shared_catalogues

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_RATE_IDS = frozenset(
    {
        "rirpf-art-95:retencion-actividades-profesionales-general",
        "rirpf-art-95:retencion-actividades-profesionales-inicio",
        "rirpf-art-95:retencion-actividades-agricolas-ganaderas-general",
        "rirpf-art-95:retencion-actividades-ganaderas-engorde-porcino-avicultura",
        "rirpf-art-95:retencion-actividades-forestales",
        "rirpf-art-95:retencion-actividades-estimacion-objetiva",
    }
)
_REDACTION_STARTS = (
    date(2007, 4, 1),
    date(2015, 1, 1),
    date(2015, 7, 12),
    date(2018, 12, 23),
    date(2023, 1, 26),
)
_REDACTION_PUBLICATIONS = (
    date(2007, 3, 31),
    date(2014, 12, 6),
    date(2015, 7, 11),
    date(2018, 12, 22),
    date(2023, 1, 25),
)
_EXPECTED_RATE_VALUES = {
    "rirpf-art-95:retencion-actividades-profesionales-general": ("0.15", "0.18", "0.15", "0.15", "0.15"),
    "rirpf-art-95:retencion-actividades-profesionales-inicio": ("0.07", "0.09", "0.07", "0.07", "0.07"),
    "rirpf-art-95:retencion-actividades-agricolas-ganaderas-general": ("0.02",) * 5,
    "rirpf-art-95:retencion-actividades-ganaderas-engorde-porcino-avicultura": ("0.01",) * 5,
    "rirpf-art-95:retencion-actividades-forestales": ("0.02",) * 5,
    "rirpf-art-95:retencion-actividades-estimacion-objetiva": ("0.01",) * 5,
}


def _catalogue() -> GovernedFactCatalogue:
    facts = load_governed_facts(bundled_path("registry", "aeat", "facts"))
    return GovernedFactCatalogue(facts={fact.fact_id: fact for fact in facts if fact.fact_id in _RATE_IDS})


def _resolve(fact_id: str, effective_date: date) -> ResolvedScalarFact:
    resolved = resolve_governed_fact(
        _catalogue(),
        ScalarFactQuery(fact_id=fact_id, date_axis=DateAxis.FILING_PERIOD, effective_date=effective_date),
        authority_digest="9" * 64,
    )
    assert isinstance(resolved, ResolvedScalarFact)
    return resolved


def test_article_95_rates_are_authored_once() -> None:
    assert set(_catalogue().facts) == _RATE_IDS


@pytest.mark.parametrize(
    ("fact_id", "effective_date", "value", "variant_suffix"),
    tuple(
        (fact_id, effective_date, value, effective_date.isoformat())
        for fact_id, values in _EXPECTED_RATE_VALUES.items()
        for effective_date, value in zip(_REDACTION_STARTS, values, strict=True)
    ),
)
def test_article_95_rate_boundaries_select_the_boe_redaction_value(
    fact_id: str, effective_date: date, value: str, variant_suffix: str
) -> None:
    resolved = _resolve(fact_id, effective_date)

    assert resolved.payload.value == Decimal(value)
    assert resolved.variant_id.endswith(variant_suffix)
    assert resolved.source_refs == (f"boe-rirpf-art-95-{variant_suffix}",)


def test_article_95_rates_refuse_before_the_first_captured_redaction() -> None:
    with pytest.raises(RegistryValidationError, match="has no variant for the exact query context"):
        _resolve("rirpf-art-95:retencion-actividades-profesionales-general", date(2007, 3, 31))


def test_each_authored_rate_variant_has_its_own_hash_pinned_boe_window() -> None:
    source_root = bundled_path()
    shared = load_shared_catalogues(source_root / "registry" / "aeat")

    for fact in _catalogue().facts.values():
        assert tuple(variant.valid_from for variant in fact.variants) == _REDACTION_STARTS
        for variant, published_at in zip(fact.variants, _REDACTION_PUBLICATIONS, strict=True):
            source = shared.sources[variant.source_refs[0]]
            assert source.applies_from == variant.valid_from
            assert source.applies_to == variant.valid_to
            assert source.published_at == published_at
            assert variant.source_citations[0].source_ref == source.id

    assert (
        governed_fact_catalogue_failures(
            _catalogue(),
            legal_ref_ids=shared.legal,
            source_ref_ids=shared.sources,
            legal_refs=shared.legal,
            source_refs=shared.sources,
            source_root=source_root,
        )
        == ()
    )
