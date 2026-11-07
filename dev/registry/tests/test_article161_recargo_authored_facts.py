"""Source-grounded temporal equivalence-surcharge rates in LIVA article 161."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from functools import cache

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.facts.resolution import (
    ResolvedScalarFact,
    ScalarFactQuery,
    resolve_governed_fact,
)
from cadrumo.domain.calculations.registry.facts.schema import GovernedFactCatalogue
from cadrumo.domain.calculations.registry.schema_base import DateAxis
from cadrumo.domain.calculations.registry.schema_references import TemporalProjectionDirection

from ..compiler.fact_loader import load_governed_facts
from ..compiler.fact_validation import governed_fact_catalogue_failures
from ..compiler.loader import load_shared_catalogues
from .profile_schema_support import authored_fact_catalogue, authored_history_supported_filing_years

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_RATE_IDS = frozenset(
    {
        "liva-art-161:recargo-rate-general",
        "liva-art-161:recargo-rate-reducido",
        "liva-art-161:recargo-rate-super-reducido",
        "liva-art-161:recargo-rate-tabaco",
    }
)
_REPLACEMENT_SOURCE = "boe-rdl-20-2012-art-23-2012-09-01"
_SOURCES = {
    "boe-liva-art-161-1993-01-01": (
        "d3d03690f5d833a832b1c81309cb76a806ba4bc7d02594233f08f2e071ad2e01",
        692,
    ),
    "boe-liva-art-161-1997-01-01": (
        "a75415a2ddc099e2114bf46e7888e4e8693d903d8d805e15f74a7e80e8a19c8a",
        1023,
    ),
    "boe-liva-art-161-2012-07-15": (
        "b80529868fb4904f88b67e98ec54dbb82e8ff876478bcce8666ddb84e1ffee34",
        1452,
    ),
    _REPLACEMENT_SOURCE: (
        "73cdc93bfe9819ebe29c68f3e6a57ccec8d7d9b6d744c3e8756a567e811fea6b",
        26194,
    ),
}


@cache
def _shared():
    return load_shared_catalogues(bundled_path() / "registry" / "aeat")


def _replacement_start() -> date:
    """Return the day the Real Decreto-ley 20/2012 redaction takes effect, as its pinned source declares it."""
    start = _shared().sources[_REPLACEMENT_SOURCE].applies_from
    assert start is not None
    return start


def _catalogue() -> GovernedFactCatalogue:
    return authored_fact_catalogue(_RATE_IDS)


def _resolve(fact_id: str, effective_date: date) -> ResolvedScalarFact:
    resolved = resolve_governed_fact(
        _catalogue(),
        ScalarFactQuery(fact_id=fact_id, date_axis=DateAxis.FILING_PERIOD, effective_date=effective_date),
        authority_digest="1" * 64,
        support=authored_history_supported_filing_years(),
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
            -timedelta(days=1),
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
            timedelta(0),
            None,
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
    effective_date: date | timedelta,
    variant_start: date | None,
    values: dict[str, Decimal],
    source_refs: tuple[str, ...],
) -> None:
    """A timedelta is an offset from the day the 2012 redaction takes effect, which its source pins."""
    if isinstance(effective_date, timedelta):
        effective_date = _replacement_start() + effective_date
    if variant_start is None:
        variant_start = _replacement_start()
    for fact_id, value in values.items():
        resolved = _resolve(fact_id, effective_date)

        assert resolved.payload.value == value
        assert resolved.payload.unit == "fraction"
        assert resolved.variant_id.endswith(variant_start.isoformat())
        assert resolved.source_refs == source_refs


@pytest.mark.parametrize(
    ("fact_id", "value"),
    (
        ("liva-art-161:recargo-rate-general", Decimal("0.04")),
        ("liva-art-161:recargo-rate-reducido", Decimal("0.01")),
        ("liva-art-161:recargo-rate-super-reducido", Decimal("0.005")),
        ("liva-art-161:recargo-rate-tabaco", Decimal("0.0175")),
    ),
)
def test_equivalence_surcharge_rates_before_their_first_window_read_it_as_a_backward_projection(
    fact_id: str,
    value: Decimal,
) -> None:
    """A date always has a rate: before the first window, the first redaction answers, marked as projected."""
    first = min(
        variant.valid_from for variant in _catalogue().facts[fact_id].variants if variant.valid_from is not None
    )

    before = _resolve(fact_id, first - timedelta(days=1))
    assert before.variant_id.endswith(first.isoformat())
    assert before.payload.value == value
    assert before.projection_direction is TemporalProjectionDirection.BACKWARD
    assert before.projected_from_date == first
    assert not before.published_on_date

    resolved = _resolve(fact_id, first)

    assert resolved.projection_direction is TemporalProjectionDirection.AUTHORED
    assert resolved.published_on_date
    assert resolved.variant_id.endswith(first.isoformat())
    assert resolved.payload.value == value
    assert resolved.payload.unit == "fraction"
    assert resolved.source_refs == (f"boe-liva-art-161-{first.isoformat()}",)


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
            if variant.valid_from == _replacement_start():
                assert _REPLACEMENT_SOURCE in variant.source_refs


def test_equivalence_surcharge_rates_cite_hash_pinned_boe_redactions() -> None:
    source_root = bundled_path()
    shared = load_shared_catalogues(source_root / "registry" / "aeat")
    catalogue = _catalogue()

    for source_ref, (sha256, byte_count) in _SOURCES.items():
        source = shared.sources[source_ref]
        assert source.sha256 == sha256
        assert source.bytes == byte_count
    assert {
        source_ref: (
            None if source.applies_from is None else source.applies_from.isoformat(),
            None if source.applies_to is None else source.applies_to.isoformat(),
        )
        for source_ref, source in ((ref, shared.sources[ref]) for ref in _SOURCES)
    } == {
        "boe-liva-art-161-1993-01-01": ("1993-01-01", "1996-12-31"),
        "boe-liva-art-161-1997-01-01": ("1997-01-01", "2012-08-31"),
        "boe-liva-art-161-2012-07-15": ("2012-09-01", None),
        _REPLACEMENT_SOURCE: ("2012-09-01", None),
    }
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
