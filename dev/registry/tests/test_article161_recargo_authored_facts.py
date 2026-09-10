"""Source-grounded temporal equivalence-surcharge rates in LIVA article 161."""

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

_RATE_IDS = frozenset(
    {
        "liva-art-161:recargo-rate-general",
        "liva-art-161:recargo-rate-reducido",
        "liva-art-161:recargo-rate-super-reducido",
        "liva-art-161:recargo-rate-tabaco",
    }
)
_SOURCES = {
    "boe-liva-art-161-1993-01-01": (
        "d3d03690f5d833a832b1c81309cb76a806ba4bc7d02594233f08f2e071ad2e01",
        692,
        date(1993, 1, 1),
        date(1996, 12, 31),
    ),
    "boe-liva-art-161-1997-01-01": (
        "a75415a2ddc099e2114bf46e7888e4e8693d903d8d805e15f74a7e80e8a19c8a",
        1023,
        date(1997, 1, 1),
        date(2012, 8, 31),
    ),
    "boe-liva-art-161-2012-07-15": (
        "b80529868fb4904f88b67e98ec54dbb82e8ff876478bcce8666ddb84e1ffee34",
        1452,
        date(2012, 9, 1),
        None,
    ),
    "boe-rdl-20-2012-art-23-2012-09-01": (
        "73cdc93bfe9819ebe29c68f3e6a57ccec8d7d9b6d744c3e8756a567e811fea6b",
        26194,
        date(2012, 9, 1),
        None,
    ),
}


def _catalogue() -> GovernedFactCatalogue:
    facts = load_governed_facts(bundled_path("registry", "aeat", "facts"))
    return GovernedFactCatalogue(facts={fact.fact_id: fact for fact in facts if fact.fact_id in _RATE_IDS})


def _resolve(fact_id: str, effective_date: date) -> ResolvedScalarFact:
    resolved = resolve_governed_fact(
        _catalogue(),
        ScalarFactQuery(fact_id=fact_id, date_axis=DateAxis.FILING_PERIOD, effective_date=effective_date),
        authority_digest="1" * 64,
    )
    assert isinstance(resolved, ResolvedScalarFact)
    return resolved


@pytest.mark.parametrize(
    ("effective_date", "variant_start", "values", "source_refs"),
    (
        (
            date(1993, 1, 1),
            date(1993, 1, 1),
            {
                "liva-art-161:recargo-rate-general": Decimal("0.04"),
                "liva-art-161:recargo-rate-reducido": Decimal("0.01"),
                "liva-art-161:recargo-rate-super-reducido": Decimal("0.005"),
            },
            ("boe-liva-art-161-1993-01-01",),
        ),
        (
            date(1997, 1, 1),
            date(1997, 1, 1),
            {
                "liva-art-161:recargo-rate-general": Decimal("0.04"),
                "liva-art-161:recargo-rate-reducido": Decimal("0.01"),
                "liva-art-161:recargo-rate-super-reducido": Decimal("0.005"),
                "liva-art-161:recargo-rate-tabaco": Decimal("0.0175"),
            },
            ("boe-liva-art-161-1997-01-01",),
        ),
        (
            date(2012, 8, 31),
            date(1997, 1, 1),
            {
                "liva-art-161:recargo-rate-general": Decimal("0.04"),
                "liva-art-161:recargo-rate-reducido": Decimal("0.01"),
                "liva-art-161:recargo-rate-super-reducido": Decimal("0.005"),
                "liva-art-161:recargo-rate-tabaco": Decimal("0.0175"),
            },
            ("boe-liva-art-161-1997-01-01",),
        ),
        (
            date(2012, 9, 1),
            date(2012, 9, 1),
            {
                "liva-art-161:recargo-rate-general": Decimal("0.052"),
                "liva-art-161:recargo-rate-reducido": Decimal("0.014"),
                "liva-art-161:recargo-rate-super-reducido": Decimal("0.005"),
                "liva-art-161:recargo-rate-tabaco": Decimal("0.0175"),
            },
            ("boe-liva-art-161-2012-07-15", "boe-rdl-20-2012-art-23-2012-09-01"),
        ),
    ),
)
def test_equivalence_surcharge_rates_resolve_from_their_exact_boe_legal_window(
    effective_date: date, variant_start: date, values: dict[str, Decimal], source_refs: tuple[str, ...]
) -> None:
    for fact_id, value in values.items():
        resolved = _resolve(fact_id, effective_date)

        assert resolved.payload.value == value
        assert resolved.payload.unit == "fraction"
        assert resolved.variant_id.endswith(variant_start.isoformat())
        assert resolved.source_refs == source_refs


@pytest.mark.parametrize(
    ("fact_id", "before_first_window"),
    (
        ("liva-art-161:recargo-rate-general", date(1992, 12, 31)),
        ("liva-art-161:recargo-rate-reducido", date(1992, 12, 31)),
        ("liva-art-161:recargo-rate-super-reducido", date(1992, 12, 31)),
        ("liva-art-161:recargo-rate-tabaco", date(1996, 12, 31)),
    ),
)
def test_equivalence_surcharge_rates_refuse_before_their_first_citable_window(
    fact_id: str, before_first_window: date
) -> None:
    with pytest.raises(RegistryValidationError, match="has no variant for the exact query context"):
        _resolve(fact_id, before_first_window)


def test_equivalence_surcharge_rates_are_authored() -> None:
    authored_ids = {fact.fact_id for fact in load_governed_facts(bundled_path("registry", "aeat", "facts"))}

    assert authored_ids >= _RATE_IDS


def test_each_rate_variant_is_bounded_by_its_exact_boe_redaction_window() -> None:
    source_root = bundled_path()
    shared = load_shared_catalogues(source_root / "registry" / "aeat")

    for fact in _catalogue().facts.values():
        for variant in fact.variants:
            rate_source_ref = next(
                source_ref for source_ref in variant.source_refs if source_ref.startswith("boe-liva")
            )
            source = shared.sources[rate_source_ref]
            assert variant.valid_from == source.applies_from
            assert variant.valid_to == source.applies_to
            if variant.valid_from == date(2012, 9, 1):
                assert "boe-rdl-20-2012-art-23-2012-09-01" in variant.source_refs


def test_equivalence_surcharge_rates_cite_hash_pinned_boe_redactions() -> None:
    source_root = bundled_path()
    shared = load_shared_catalogues(source_root / "registry" / "aeat")
    catalogue = _catalogue()

    for source_ref, (sha256, byte_count, applies_from, applies_to) in _SOURCES.items():
        source = shared.sources[source_ref]
        assert source.sha256 == sha256
        assert source.bytes == byte_count
        assert source.applies_from == applies_from
        assert source.applies_to == applies_to
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
