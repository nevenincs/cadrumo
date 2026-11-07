"""BOE-redaction grounding and closure for administrator-retention facts."""

from __future__ import annotations

from datetime import date, timedelta
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
from cadrumo.domain.calculations.registry.schema_base import DateAxis
from cadrumo.domain.calculations.registry.schema_references import TemporalProjectionDirection

from ..compiler.fact_validation import governed_fact_catalogue_failures
from ..compiler.loader import load_shared_catalogues
from .profile_schema_support import authored_fact_catalogue, authored_history_supported_filing_years

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_FACT_IDS = frozenset(
    {
        "lirpf-art-101:retencion-administrador-general",
        "lirpf-art-101:retencion-administrador-reducida",
        "lirpf-art-101:retencion-administrador-incn-umbral-eur",
    }
)


def _catalogue() -> GovernedFactCatalogue:
    return authored_fact_catalogue(_FACT_IDS)


def _first_valid_from(fact_id: str) -> date:
    return min(variant.valid_from for variant in _catalogue().facts[fact_id].variants if variant.valid_from is not None)


def _resolve(fact_id: str, effective_date: date) -> ResolvedScalarFact:
    resolved = resolve_governed_fact(
        _catalogue(),
        ScalarFactQuery(
            fact_id=fact_id,
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date,
        ),
        authority_digest="a" * 64,
        support=authored_history_supported_filing_years(),
    )
    assert isinstance(resolved, ResolvedScalarFact)
    return resolved


def test_administrator_facts_are_authored_once() -> None:
    authored_ids = set(_catalogue().facts)

    assert authored_ids == _FACT_IDS


def _redaction_boundaries(fact_id: str) -> tuple[date, ...]:
    """Every BOE redaction boundary the catalogue authors for one fact, oldest first."""
    return tuple(
        sorted(variant.valid_from for variant in _catalogue().facts[fact_id].variants if variant.valid_from is not None)
    )


@pytest.mark.parametrize(
    "effective_date",
    _redaction_boundaries("lirpf-art-101:retencion-administrador-reducida"),
    ids=date.isoformat,
)
def test_each_boe_redaction_boundary_selects_the_exact_variant(effective_date: date) -> None:
    variant_suffix = effective_date.isoformat()
    resolved = _resolve("lirpf-art-101:retencion-administrador-reducida", effective_date)

    assert resolved.variant_id.endswith(variant_suffix)
    assert resolved.payload.value == Decimal("0.19")
    assert resolved.valid_from == effective_date
    assert resolved.source_refs == (f"boe-lirpf-art-101-administrator-{variant_suffix}",)


def test_the_administrator_reduced_rate_before_its_first_variant_reads_it_as_a_backward_projection() -> None:
    """A standing rate reads its first variant before it began, and says so; a threshold does not.

    The turnover threshold declares no standing rate, so its first variant's start
    is a legal boundary and the day before it resolves to nothing.
    """
    first = _first_valid_from("lirpf-art-101:retencion-administrador-reducida")

    before = _resolve("lirpf-art-101:retencion-administrador-reducida", first - timedelta(days=1))
    assert before.variant_id.endswith(first.isoformat())
    assert before.payload.value == Decimal("0.19")
    assert before.projection_direction is TemporalProjectionDirection.BACKWARD
    assert before.projected_from_date == first
    assert not before.published_on_date

    threshold = "lirpf-art-101:retencion-administrador-incn-umbral-eur"
    with pytest.raises(RegistryValidationError, match="has no variant for the exact query context"):
        _resolve(threshold, _first_valid_from(threshold) - timedelta(days=1))

    resolved = _resolve("lirpf-art-101:retencion-administrador-reducida", first)

    assert resolved.projection_direction is TemporalProjectionDirection.AUTHORED
    assert resolved.variant_id.endswith(first.isoformat())
    assert resolved.payload.value == Decimal("0.19")
    assert resolved.payload.unit == "fraction"
    assert resolved.source_refs == (f"boe-lirpf-art-101-administrator-{first.isoformat()}",)


def test_authored_facts_preserve_units_values_and_exact_source_windows() -> None:
    reduction_start = _first_valid_from("lirpf-art-101:retencion-administrador-reducida")
    general = _resolve("lirpf-art-101:retencion-administrador-general", reduction_start)
    reduced = _resolve("lirpf-art-101:retencion-administrador-reducida", reduction_start)
    threshold = _resolve("lirpf-art-101:retencion-administrador-incn-umbral-eur", reduction_start)
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
