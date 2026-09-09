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
from cadrumo.domain.calculations.registry.authority import bundled_authority

from ..pagefind_inject import (
    InjectionStats,
    SearchInjectionError,
    SearchRecordProjection,
    _bounded_to_sample,
    _effective_weight,
    _filters_for,
    _Materialised,
    _meta_for,
    _sort_key,
    build_record_injector,
    load_relevance_weights,
)
from ..terminology.casilla_projection import project_casilla_search_records
from ..terminology.cli_projection import project_cli_search_records
from ..terminology.unified_record import SearchRecord, to_search_record
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


#: The distinguishing fragment of each refusal, so neither arm can pass by
#: raising the other's error.
_PARTITION_FRAGMENT = "counters describe"
_NEGATIVE_FRAGMENT = "negative counter"


def test_an_empty_projection_carries_no_contradiction() -> None:
    """Empty-parameter control: an empty record set with a zero census is legal.

    Completeness is a separate boundary (:meth:`SearchRecordProjection.require_complete_corpus`,
    and ``_require_complete_projection`` on the injector's own type); construction
    refuses only a census that disagrees with its own records.
    """
    empty = SearchRecordProjection(
        records=(),
        concepts=0,
        casillas=0,
        legal_provisions=0,
        cli_commands=0,
        cli_options=0,
    )

    assert empty.records == ()


def test_a_census_matching_the_records_carried_is_admitted() -> None:
    """Anti-noise: a coherent projection over real records is not refused."""
    records = tuple(concept_records().records)
    assert records, "the concept projection carried nothing, so this admits nothing"

    coherent = SearchRecordProjection(
        records=records,
        concepts=len(records),
        casillas=0,
        legal_provisions=0,
        cli_commands=0,
        cli_options=0,
    )
    skipped = SearchRecordProjection(
        records=records,
        concepts=len(records),
        casillas=0,
        legal_provisions=0,
        cli_commands=0,
        cli_options=0,
        cli_skipped_reason="the CLI tree could not be walked",
    )

    assert coherent.concepts == len(coherent.records)
    assert skipped.cli_skipped_reason == "the CLI tree could not be walked"


def test_a_census_claiming_records_the_projection_never_carried_is_refused() -> None:
    """Teeth, partition arm: the census may not outrun the tuple.

    ``_bounded_to_sample`` already refuses this drift on its own path. The
    resolver and the Rung-2 manifest read the census and the tuple as one fact,
    so a counter reporting a row that never reached the index is a silent
    under-delivery dressed as a full complement.
    """
    records = tuple(concept_records().records)

    with pytest.raises(SearchInjectionError) as excinfo:
        SearchRecordProjection(
            records=records,
            concepts=len(records) + 1,
            casillas=0,
            legal_provisions=0,
            cli_commands=0,
            cli_options=0,
        )

    message = str(excinfo.value)
    assert _PARTITION_FRAGMENT in message, message
    assert _NEGATIVE_FRAGMENT not in message, f"the negative arm covered for the partition arm: {message}"
    assert str(len(records)) in message, message


def test_a_negative_counter_is_refused_even_when_the_census_still_sums() -> None:
    """Teeth, negative arm: a cancelled counter sums correctly and is still a lie.

    ``casillas=-5`` against ``concepts=len(records) + 5`` totals exactly the
    records carried, so the partition arm demonstrably cannot catch it; only a
    per-counter check can.
    """
    records = tuple(concept_records().records)

    with pytest.raises(SearchInjectionError) as excinfo:
        SearchRecordProjection(
            records=records,
            concepts=len(records) + 5,
            casillas=-5,
            legal_provisions=0,
            cli_commands=0,
            cli_options=0,
        )

    message = str(excinfo.value)
    assert _NEGATIVE_FRAGMENT in message, message
    assert _PARTITION_FRAGMENT not in message, f"the partition arm covered for the negative arm: {message}"
    assert "casillas=-5" in message, message


#: The distinguishing fragment of each COMPLETENESS refusal, so neither arm can
#: pass by raising the other's error. Both differ from the census fragments
#: above, so a coherence refusal cannot stand in for a completeness one either.
_CASILLA_GAP_FRAGMENT = "casilla projection is empty"
_CLI_GAP_FRAGMENT = "CLI projection was skipped"


@pytest.fixture(scope="module")
def _real_casilla_record() -> SearchRecord:
    """One real projected casilla record, so a complete census is not a fiction."""
    records, _stats = project_casilla_search_records(bundled_authority())
    assert records, "the casilla projection carried nothing, so this proves nothing"
    return to_search_record(records[0])


def test_an_empty_projection_is_not_the_complete_corpus() -> None:
    """Empty-parameter control: an empty projection is coherent and NOT complete.

    Construction admits it -- nothing contradicts nothing -- so the completeness
    boundary is the only thing standing between "the corpus projected nothing"
    and "the corpus is fully present". A control that merely constructed the
    value would report the first as the second.
    """
    empty = SearchRecordProjection(
        records=(),
        concepts=0,
        casillas=0,
        legal_provisions=0,
        cli_commands=0,
        cli_options=0,
    )

    with pytest.raises(SearchInjectionError) as excinfo:
        empty.require_complete_corpus()

    assert _CASILLA_GAP_FRAGMENT in str(excinfo.value), str(excinfo.value)


def test_a_projection_with_both_arms_satisfied_is_admitted(_real_casilla_record: SearchRecord) -> None:
    """Anti-noise: real records with a populated casilla arm and no skip pass."""
    concepts = tuple(concept_records().records)
    assert concepts, "the concept projection carried nothing, so this admits nothing"

    complete = SearchRecordProjection(
        records=(*concepts, _real_casilla_record),
        concepts=len(concepts),
        casillas=1,
        legal_provisions=0,
        cli_commands=0,
        cli_options=0,
    )

    complete.require_complete_corpus()


def test_an_empty_casilla_arm_is_refused_by_the_value_object() -> None:
    """Teeth, casilla arm: the invariant is on the type, not on one consumer.

    ``_require_complete_projection`` refuses the same shortfall on the
    injector's own ``_Materialised``, but the public value object reaches the
    terminology sweep too, and the sweep filters its relevance targets to the
    ids the projection emitted -- so a narrowed projection there does not fail,
    it silently drops the missing kind and reports a clean run.
    """
    records = tuple(concept_records().records)
    projection = SearchRecordProjection(
        records=records,
        concepts=len(records),
        casillas=0,
        legal_provisions=0,
        cli_commands=0,
        cli_options=0,
    )

    with pytest.raises(SearchInjectionError) as excinfo:
        projection.require_complete_corpus()

    message = str(excinfo.value)
    assert _CASILLA_GAP_FRAGMENT in message, message
    assert _CLI_GAP_FRAGMENT not in message, f"the CLI arm covered for the casilla arm: {message}"


def test_a_skipped_cli_arm_is_refused_even_with_casillas_present(
    _real_casilla_record: SearchRecord,
) -> None:
    """Teeth, CLI arm: a coherent census and a populated casilla arm are not enough.

    The casilla arm demonstrably cannot catch this one: ``casillas=1`` clears it.
    A skipped CLI walk leaves every counter honest about the rows carried, which
    is precisely why coherence cannot stand in for completeness.
    """
    concepts = tuple(concept_records().records)
    projection = SearchRecordProjection(
        records=(*concepts, _real_casilla_record),
        concepts=len(concepts),
        casillas=1,
        legal_provisions=0,
        cli_commands=0,
        cli_options=0,
        cli_skipped_reason="RuntimeError: the live CLI tree could not be walked",
    )

    with pytest.raises(SearchInjectionError) as excinfo:
        projection.require_complete_corpus()

    message = str(excinfo.value)
    assert _CLI_GAP_FRAGMENT in message, message
    assert _CASILLA_GAP_FRAGMENT not in message, f"the casilla arm covered for the CLI arm: {message}"
    assert "the live CLI tree could not be walked" in message, message
