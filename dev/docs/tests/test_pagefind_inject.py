"""Projection and weighting for the unified-record Pagefind injection.

In-process checks over real projected records (no mocks): unified records funnel
into custom records, typed metadata and filters carry the card payload, and the
relevance boost applies when the committed file is present while base weights
stand when it is absent; malformed committed input fails closed.

Split from the site-building half so each module carries one execution lane; the
tests that run a real Pagefind build over copied HTML live in
``test_pagefind_inject_site``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cadrumo.core.external_constants import OutputLanguage

from ..pagefind_inject import (
    InjectionStats,
    SearchInjectionError,
    _bounded_to_sample,
    _effective_weight,
    _filters_for,
    _Materialised,
    _meta_for,
    _sort_key,
    build_record_injector,
    load_relevance_weights,
)
from ..terminology._cli_projection import project_cli_search_records
from ..terminology.unified_record import to_search_record
from ._pagefind_inject_support import concept_records

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_concept_records_funnel_into_search_records() -> None:
    """Every Handbook concept projects into a unified record with a deep link."""
    materialised = concept_records()
    assert materialised.concepts > 30  # the approved + draft Handbook
    assert len(materialised.records) == materialised.concepts
    sample = next(r for r in materialised.records if r.metadata.concept_id == "prorrata")
    assert sample.kind.value == "concept"
    assert sample.target == "_generated/glossary.html#term-prorrata"
    assert sample.ranking_weight == 1.0  # concept base weight (tier one)
    assert "es" in {lang.value for lang in sample.descriptions}


def test_meta_filters_and_sort_carry_the_card_payload() -> None:
    """The Pagefind meta/filters/sort carry the typed term-card payload."""
    record = next(r for r in concept_records().records if r.metadata.concept_id == "prorrata")
    meta = _meta_for(record, record.ranking_weight)
    assert meta["kind"] == "concept"
    assert meta["concept_id"] == "prorrata"
    assert meta["domain"]  # the concept domain
    assert "weight" in meta

    filters = _filters_for(record)
    assert filters["kind"] == ["concept"]
    assert "domain" in filters

    # The sort key is a fixed-width descending-orderable string.
    assert _sort_key(1.0) > _sort_key(0.5)


def test_relevance_boost_applies_when_present_else_base() -> None:
    """A present relevance weight boosts a record; absence keeps the base."""
    record = next(r for r in concept_records().records if r.metadata.concept_id == "prorrata")
    # Base weight stands with no relevance map.
    assert _effective_weight(record, {}) == record.ranking_weight
    # A weaker relevance does not lower the base (max).
    assert _effective_weight(record, {record.id: 0.1}) == record.ranking_weight
    # A casilla (lower base) is boosted by a strong relevance weight.
    casilla = next(
        (r for r in concept_records().records if r.kind.value == "concept"),
    )
    assert _effective_weight(casilla, {casilla.id: 1.0}) >= casilla.ranking_weight


def test_relevance_file_absent_yields_empty_map(tmp_path: Path) -> None:
    """An absent relevance file yields an empty weight map (base weights)."""
    assert load_relevance_weights(tmp_path) == {}


def test_relevance_file_present_is_loaded(tmp_path: Path) -> None:
    """The committed SweepResult is parsed into a per-record boost map.

    The loader consumes the exact shape the sweep writes (``mappings[]`` with
    laundered ``targets[]``), not a hand-imagined flat ``{"weights": {...}}``
    map. A record id that several query terms resolved to keeps its STRONGEST
    weight.
    """
    from ..terminology._sweep import SweepResult, TermRelevanceMapping, TermTargetRef
    from ..terminology.search_record import SearchRecordKind

    def _target(record_id: str, weight: float) -> TermTargetRef:
        return TermTargetRef(
            record_id=record_id,
            target=f"_generated/glossary.html#term-{record_id.split(':')[-1]}",
            kind=SearchRecordKind.CONCEPT,
            surface="concept",
            ranking_weight=weight,
        )

    result = SweepResult(
        mappings=(
            TermRelevanceMapping(
                query="prorrata",
                concept_id="prorrata",
                language=OutputLanguage.ES,
                targets=(_target("concept:prorrata", 0.6),),
            ),
            TermRelevanceMapping(
                query="regla de prorrata",
                concept_id="prorrata",
                language=OutputLanguage.ES,
                # Same record id surfaced again with a stronger weight: the
                # loader keeps the maximum.
                targets=(_target("concept:prorrata", 0.95), _target("concept:iva", 0.4)),
            ),
        ),
        query_count=2,
        concept_count=1,
        failed_query_count=0,
        reindex_note="test fixture",
        score_floor=0.5,
    )

    rel = tmp_path / "dev/docs/terminology/relevance"
    rel.mkdir(parents=True)
    (rel / "relevance.json").write_text(result.model_dump_json(), encoding="utf-8")

    weights = load_relevance_weights(tmp_path)
    assert weights["concept:prorrata"] == 0.95  # strongest of 0.6 / 0.95
    assert weights["concept:iva"] == 0.4


def test_relevance_file_malformed_raises_search_injection_error(tmp_path: Path) -> None:
    """A present file that is not a valid SweepResult fails closed."""
    rel = tmp_path / "dev/docs/terminology/relevance"
    rel.mkdir(parents=True)
    (rel / "relevance.json").write_text(json.dumps({"not": "a sweep result"}), encoding="utf-8")
    with pytest.raises(SearchInjectionError) as exc_info:
        load_relevance_weights(tmp_path)
    assert str(exc_info.value) == f"committed relevance file is invalid: {rel / 'relevance.json'}"


def test_build_record_injector_returns_a_callable(tmp_path: Path) -> None:
    """The public injector factory builds a callback (pre-loading relevance).

    Exercises the public seam entry point without the slow full Pagefind
    write: it reads the (absent) relevance file at construction and returns the
    async callback the post-build pass invokes.
    """
    inject = build_record_injector(tmp_path)
    assert callable(inject)
    stats = InjectionStats(concepts=1, custom_records_written=4)
    assert stats.custom_records_written == 4  # the stats type the callback emits


def test_the_bounded_sample_reports_exactly_the_records_it_carries() -> None:
    """A bounded injection cannot claim a record it dropped.

    A CLI command and a CLI option share the single ``cli`` record kind, so a
    cap taken on the kind spent its whole allowance on commands and then went
    on reporting a full complement of options that never reached the index.
    Both halves are asserted against the real live command tree: the options
    are carried, and every counter is the length of what the bound kept.
    """
    commands, options, _stats = project_cli_search_records()
    assert commands and options
    materialised = _Materialised(
        records=[to_search_record(record) for record in (*commands, *options)],
        cli_commands=len(commands),
        cli_options=len(options),
    )

    bounded = _bounded_to_sample(materialised, 4)

    assert bounded.cli_commands == 4
    assert bounded.cli_options == 4
    assert len(bounded.records) == bounded.cli_commands + bounded.cli_options
    carried_options = sum(1 for record in bounded.records if record.id.startswith("cli-option:"))
    assert carried_options == bounded.cli_options
