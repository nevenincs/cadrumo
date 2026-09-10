"""BOE-redaction grounding and closure for administrator-retention facts."""

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
from dev.registry.compiler.facts_validation import governed_fact_catalogue_failures
from cadrumo.domain.calculations.registry.schema_base import DateAxis
from dev.registry.compiler.fact_loader import load_governed_facts
from dev.registry.compiler.loader import load_shared_catalogues

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_FACT_IDS = frozenset(
    {
        "lirpf-art-101:retencion-administrador-general",
        "lirpf-art-101:retencion-administrador-reducida",
        "lirpf-art-101:retencion-administrador-incn-umbral-eur",
    }
)
_REDUCTION_START = date(2015, 1, 1)


def _catalogue() -> GovernedFactCatalogue:
    facts = load_governed_facts(bundled_path("registry", "aeat", "facts"))
    selected = {fact.fact_id: fact for fact in facts if fact.fact_id in _FACT_IDS}
    return GovernedFactCatalogue(facts=selected)


def _resolve(fact_id: str, effective_date: date) -> ResolvedScalarFact:
    resolved = resolve_governed_fact(
        _catalogue(),
        ScalarFactQuery(
            fact_id=fact_id,
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date,
        ),
        authority_digest="a" * 64,
    )
    assert isinstance(resolved, ResolvedScalarFact)
    return resolved


def test_administrator_facts_are_authored_once() -> None:
    authored_ids = set(_catalogue().facts)

    assert authored_ids == _FACT_IDS


@pytest.mark.parametrize(
    ("effective_date", "variant_suffix"),
    (
        (date(2015, 1, 1), "2015-01-01"),
        (date(2015, 7, 12), "2015-07-12"),
        (date(2018, 7, 5), "2018-07-05"),
        (date(2018, 12, 29), "2018-12-29"),
        (date(2021, 1, 1), "2021-01-01"),
        (date(2023, 1, 1), "2023-01-01"),
    ),
)
def test_each_boe_redaction_boundary_selects_the_exact_variant(
    effective_date: date,
    variant_suffix: str,
) -> None:
    resolved = _resolve("lirpf-art-101:retencion-administrador-reducida", effective_date)

    assert resolved.variant_id.endswith(variant_suffix)
    assert resolved.payload.value == Decimal("0.19")
    assert resolved.valid_from == effective_date
    assert resolved.source_refs == (f"boe-lirpf-art-101-administrator-{variant_suffix}",)


def test_pre_2015_administrator_reduced_rate_refuses_instead_of_backdating_the_19_percent_value() -> None:
    with pytest.raises(RegistryValidationError, match="has no variant for the exact query context"):
        _resolve("lirpf-art-101:retencion-administrador-reducida", date(2014, 12, 31))


def test_authored_facts_preserve_units_values_and_exact_source_windows() -> None:
    general = _resolve("lirpf-art-101:retencion-administrador-general", _REDUCTION_START)
    reduced = _resolve("lirpf-art-101:retencion-administrador-reducida", _REDUCTION_START)
    threshold = _resolve("lirpf-art-101:retencion-administrador-incn-umbral-eur", _REDUCTION_START)
    source_root = bundled_path()
    shared = load_shared_catalogues(source_root / "registry" / "aeat")

    assert (general.payload.value, general.payload.unit) == (Decimal("0.35"), "fraction")
    assert (reduced.payload.value, reduced.payload.unit) == (Decimal("0.19"), "fraction")
    assert (threshold.payload.value, threshold.payload.unit) == (Decimal("100000"), "EUR")
    for resolved in (general, reduced, threshold):
        source = shared.sources[resolved.source_refs[0]]
        assert source.applies_from == resolved.valid_from
        assert source.applies_to == resolved.valid_to
        assert resolved.source_citations[0].source_ref == source.id

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
