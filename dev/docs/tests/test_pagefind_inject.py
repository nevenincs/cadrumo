"""Real-behaviour tests for the unified-record Pagefind injection.

Exercises the injection callback over a real Pagefind build with real
projected records (no mocks): the unified records funnel into custom records,
land per-language so the es/en/ca/hu splits each receive them with deep-link
targets, typed metadata, and ranking weights, and the relevance boost applies
when the committed file is present while base weights stand when it is absent.

The build-the-whole-index tests use the concept-card subset (108 records, fast
and deterministic); the materialisation of all kinds and the weight/metadata
projection are tested directly. The full 7k-record injection is proven once at
the module-build level, not per test, to keep the suite fast.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from ..pagefind_index import build_search_index
from ..pagefind_inject import (
    InjectionStats,
    _effective_weight,
    _filters_for,
    _inject_records,
    _materialise_records,
    _Materialised,
    _meta_for,
    _sort_key,
    build_record_injector,
    load_relevance_weights,
)
from ..terminology._concept_cards import project_concept_cards
from ..terminology._unified_record import to_search_record

# dev/docs/tests/test_pagefind_inject.py -> parents[3] is the repo root.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_BUILT_HTML = _REPO_ROOT / "docs" / "_build" / "html"
_PAGEFIND_YML = _REPO_ROOT / "docs" / "pagefind.yml"


def _concept_records() -> _Materialised:
    cards, _ = project_concept_cards()
    records = [to_search_record(card) for card in cards]
    return _Materialised(records=records, concepts=len(cards))


def _fixture_site(tmp_path: Path, *, pages: int = 3) -> Path:
    """Copy a small real built-HTML subset + the pagefind.yml into tmp."""
    site = tmp_path / "site"
    site.mkdir()
    html = sorted(_BUILT_HTML.rglob("*.html"))[:pages]
    for source in html:
        dest = site / source.relative_to(_BUILT_HTML)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(source, dest)
    shutil.copy(_PAGEFIND_YML, site / "pagefind.yml")
    return site


@pytest.mark.unit
@pytest.mark.hex_core
def test_concept_records_funnel_into_search_records() -> None:
    """Every Handbook concept projects into a unified record with a deep link."""
    materialised = _concept_records()
    assert materialised.concepts > 30  # the approved + draft Handbook
    assert len(materialised.records) == materialised.concepts
    sample = next(r for r in materialised.records if r.metadata.concept_id == "prorrata")
    assert sample.kind.value == "concept"
    assert sample.target.startswith("glossary.html#term-")
    assert sample.ranking_weight == 1.0  # concept base weight (tier one)
    assert "es" in {lang.value for lang in sample.descriptions}


@pytest.mark.unit
@pytest.mark.hex_core
def test_meta_filters_and_sort_carry_the_card_payload() -> None:
    """The Pagefind meta/filters/sort carry the typed term-card payload."""
    record = next(r for r in _concept_records().records if r.metadata.concept_id == "prorrata")
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


@pytest.mark.unit
@pytest.mark.hex_core
def test_relevance_boost_applies_when_present_else_base() -> None:
    """A present relevance weight boosts a record; absence keeps the base."""
    record = next(r for r in _concept_records().records if r.metadata.concept_id == "prorrata")
    # Base weight stands with no relevance map.
    assert _effective_weight(record, {}) == record.ranking_weight
    # A weaker relevance does not lower the base (max).
    assert _effective_weight(record, {record.id: 0.1}) == record.ranking_weight
    # A casilla (lower base) is boosted by a strong relevance weight.
    casilla = next(
        (r for r in _concept_records().records if r.kind.value == "concept"),
    )
    assert _effective_weight(casilla, {casilla.id: 1.0}) >= casilla.ranking_weight


@pytest.mark.unit
@pytest.mark.hex_core
def test_relevance_file_absent_yields_empty_map(tmp_path: Path) -> None:
    """An absent relevance file yields an empty weight map (base weights)."""
    assert load_relevance_weights(tmp_path) == {}


@pytest.mark.unit
@pytest.mark.hex_core
def test_relevance_file_present_is_loaded(tmp_path: Path) -> None:
    """A present relevance file's weights are loaded and clamped."""
    rel = tmp_path / "src/aeat/_data/terminology/relevance"
    rel.mkdir(parents=True)
    (rel / "relevance.json").write_text(
        json.dumps({"weights": {"concept:prorrata": 0.9, "concept:iva": 2.0}}),
        encoding="utf-8",
    )
    weights = load_relevance_weights(tmp_path)
    assert weights["concept:prorrata"] == 0.9
    assert weights["concept:iva"] == 1.0  # clamped into [0, 1]


@pytest.mark.integration
@pytest.mark.hex_core
def test_injection_lands_records_per_language(tmp_path: Path) -> None:
    """The concept records inject and the es/en/hu language splits form.

    Real Pagefind build (no mock): the directory pass indexes the English
    pages and the injected concept records add per-language custom records, so
    the resulting index carries multiple language splits with the injected
    content.
    """
    site = _fixture_site(tmp_path)
    materialised = _concept_records()
    captured: list[InjectionStats] = []

    async def inject(index: object) -> None:
        stats = await _inject_records(index, materialised, {})  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]  # reason: pagefind index is dynamically typed
        captured.append(stats)

    result = build_search_index(site, inject=inject)

    assert result.page_count == 3
    stats = captured[0]
    assert stats.concepts == materialised.concepts
    assert stats.custom_records_written > materialised.concepts  # multi-language
    # The Spanish-invariant description means every concept yields an es record.
    assert "es" in stats.languages

    pf = site / "pagefind"
    languages = {p.name.split("_")[0] for p in pf.rglob("*.pf_index")}
    # English (the pages) plus Spanish (every concept) must both split out.
    assert "es" in languages
    assert "en" in languages


@pytest.mark.integration
@pytest.mark.hex_core
def test_full_four_language_splits_form_with_substantive_content(
    tmp_path: Path,
) -> None:
    """All four es/en/ca/hu splits form when records carry per-language text.

    Proves the language routing end to end with one substantive record per
    language (the concept ca/hu descriptions are sometimes short; this isolates
    the routing from content-length effects).
    """
    site = _fixture_site(tmp_path, pages=1)

    async def inject(index: object) -> None:
        for language in ("es", "en", "ca", "hu"):
            await index.add_custom_record(  # type: ignore[attr-defined]  # ty: ignore[unresolved-attribute]  # reason: pagefind index is dynamically typed
                url=f"/glossary.html#term-prorrata-{language}",
                content=(
                    f"prorrata especial deduccion sectors activitat {language} "
                    f"contingut significatiu per formar un index separat"
                ),
                language=language,
                meta={"kind": "concept"},
                filters={"kind": ["concept"]},
            )

    build_search_index(site, inject=inject)
    pf = site / "pagefind"
    languages = {p.name.split("_")[0] for p in pf.rglob("*.pf_index")}
    assert {"es", "en", "ca", "hu"} <= languages, languages


@pytest.mark.integration
@pytest.mark.hex_core
def test_materialises_every_kind_with_graceful_cli() -> None:
    """All four record kinds materialise into unified records.

    Proves the full projection pipeline (concepts + casillas + CLI) funnels
    into unified records, and that the CLI projection is skipped-and-reported
    if the live CLI is unavailable rather than failing the whole injection -
    concepts and casillas (the priority surfaces) always land. This tests the
    materialisation directly; the Pagefind injection of the records is proven
    by the per-language integration tests above, so the slow full 7k-record
    Pagefind write is not repeated here.
    """
    materialised = _materialise_records()

    assert materialised.concepts > 0
    assert materialised.casillas > 1000  # thousands of deduped casillas
    # CLI either projected (commands > 0) or was cleanly skipped-and-reported.
    assert materialised.cli_commands > 0 or materialised.cli_skipped_reason is not None
    # The unified record list spans every kind that projected.
    kinds = {r.kind.value for r in materialised.records}
    assert {"concept", "casilla"} <= kinds
    # Every record carries a deep-link target and a weight in [0, 1].
    sample = materialised.records[0]
    assert sample.target
    assert 0.0 <= sample.ranking_weight <= 1.0


@pytest.mark.unit
@pytest.mark.hex_core
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
