"""BOE-redaction grounding and adapter retirement for RIRPF art. 95 rates."""

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

from ..compiler.fact_validation import governed_fact_catalogue_failures
from ..compiler.loader import load_shared_catalogues
from .profile_schema_support import authored_fact_catalogue, authored_history_supported_filing_years

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_RATE_IDS = frozenset(
    {
        "rirpf-art-95:retencion-actividades-profesionales-general",
        "rirpf-art-95:retencion-actividades-profesionales-inicio",
        "rirpf-art-95:retencion-actividades-profesionales-colectivos-especificos",
        "rirpf-art-95:retencion-actividades-agricolas-ganaderas-general",
        "rirpf-art-95:retencion-actividades-ganaderas-engorde-porcino-avicultura",
        "rirpf-art-95:retencion-actividades-forestales",
        "rirpf-art-95:retencion-actividades-estimacion-objetiva",
    }
)
_EXPECTED_RATE_VALUES = {
    "rirpf-art-95:retencion-actividades-profesionales-general": ("0.15", "0.18", "0.15", "0.15", "0.15"),
    "rirpf-art-95:retencion-actividades-profesionales-inicio": ("0.07", "0.09", "0.07", "0.07", "0.07"),
    "rirpf-art-95:retencion-actividades-profesionales-colectivos-especificos": (
        "0.07",
        "0.09",
        "0.07",
        "0.07",
        "0.07",
    ),
    "rirpf-art-95:retencion-actividades-agricolas-ganaderas-general": ("0.02",) * 5,
    "rirpf-art-95:retencion-actividades-ganaderas-engorde-porcino-avicultura": ("0.01",) * 5,
    "rirpf-art-95:retencion-actividades-forestales": ("0.02",) * 5,
    "rirpf-art-95:retencion-actividades-estimacion-objetiva": ("0.01",) * 5,
}


def _catalogue() -> GovernedFactCatalogue:
    return authored_fact_catalogue(_RATE_IDS)


@cache
def _redaction_starts() -> tuple[date, ...]:
    """Return the days the BOE redactions take effect, as the authored variants of the general rate start."""
    variants = _catalogue().facts["rirpf-art-95:retencion-actividades-profesionales-general"].variants
    return tuple(variant.valid_from for variant in variants if variant.valid_from is not None)


def _resolve(fact_id: str, effective_date: date) -> ResolvedScalarFact:
    resolved = resolve_governed_fact(
        _catalogue(),
        ScalarFactQuery(fact_id=fact_id, date_axis=DateAxis.FILING_PERIOD, effective_date=effective_date),
        authority_digest="9" * 64,
        support=authored_history_supported_filing_years(),
    )
    assert isinstance(resolved, ResolvedScalarFact)
    return resolved


def test_article_95_rates_are_authored_once() -> None:
    assert set(_catalogue().facts) == _RATE_IDS


def test_article_95_redactions_take_effect_on_their_boe_dates() -> None:
    assert [start.isoformat() for start in _redaction_starts()] == [
        "2007-04-01",
        "2015-01-01",
        "2015-07-12",
        "2018-12-23",
        "2023-01-26",
    ]


@pytest.mark.parametrize(
    ("fact_id", "redaction", "value"),
    tuple(
        (fact_id, redaction, value)
        for fact_id, values in _EXPECTED_RATE_VALUES.items()
        for redaction, value in enumerate(values)
    ),
)
def test_article_95_rate_boundaries_select_the_boe_redaction_value(fact_id: str, redaction: int, value: str) -> None:
    effective_date = _redaction_starts()[redaction]
    resolved = _resolve(fact_id, effective_date)

    assert resolved.payload.value == Decimal(value)
    assert resolved.variant_id.endswith(effective_date.isoformat())
    assert resolved.source_refs == (f"boe-rirpf-art-95-{effective_date.isoformat()}",)


def test_article_95_rates_before_the_first_redaction_read_it_as_a_backward_projection() -> None:
    """A date always has a rate: before the first redaction in force, that redaction answers, marked as projected."""
    fact_id = "rirpf-art-95:retencion-actividades-profesionales-general"
    first = min(
        variant.valid_from for variant in _catalogue().facts[fact_id].variants if variant.valid_from is not None
    )

    before = _resolve(fact_id, first - timedelta(days=1))
    assert before.payload.value == Decimal("0.15")
    assert before.variant_id.endswith(first.isoformat())
    assert before.projection_direction is TemporalProjectionDirection.BACKWARD
    assert before.projected_from_date == first
    assert not before.published_on_date

    resolved = _resolve("rirpf-art-95:retencion-actividades-profesionales-general", first)
    assert resolved.projection_direction is TemporalProjectionDirection.AUTHORED
    assert resolved.payload.value == Decimal("0.15")
    assert resolved.payload.unit == "fraction"
    assert resolved.source_refs == (f"boe-rirpf-art-95-{first.isoformat()}",)


def test_each_authored_rate_variant_has_its_own_hash_pinned_boe_window() -> None:
    source_root = bundled_path()
    shared = load_shared_catalogues(source_root / "registry" / "aeat")

    for fact in _catalogue().facts.values():
        assert tuple(variant.valid_from for variant in fact.variants) == _redaction_starts()
        published: list[str] = []
        for variant in fact.variants:
            source = shared.sources[variant.source_refs[0]]
            assert source.applies_from == variant.valid_from
            assert source.applies_to == variant.valid_to
            assert source.published_at is not None
            published.append(source.published_at.isoformat())
            assert variant.source_citations[0].source_ref == source.id
        assert published == ["2007-03-31", "2014-12-06", "2015-07-11", "2018-12-22", "2023-01-25"]

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
