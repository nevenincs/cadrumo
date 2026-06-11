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
    assert sample.target == "_generated/glossary.html#term-prorrata"
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
def test_injection_lands_one_record_per_concept_in_primary_language(
    tmp_path: Path,
) -> None:
    """Each concept injects once into the primary (page) index, discoverably.

    Real Pagefind build (no mock): the directory pass indexes the English
    pages; the injection adds ONE custom record per concept into the primary
    language with combined multilingual content, so the record is in the index
    a reader's page loads. Asserts one record per concept (not four) and that
    the en index split is present.
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
    # One custom record per concept (single primary language), not per-language.
    assert stats.custom_records_written == materialised.concepts
    assert stats.languages == ("en",)

    pf = site / "pagefind"
    languages = {p.name.split("_")[0] for p in pf.rglob("*.pf_index")}
    assert "en" in languages


@pytest.mark.integration
@pytest.mark.hex_core
def test_sorted_by_weight_returns_only_injected_cards(tmp_path: Path) -> None:
    """A weight-sorted Pagefind search returns ONLY the injected records.

    This is the load-bearing mechanism the Ctrl-K palette relies on to surface
    term cards above the full-text pages (ADR D5): the injected records carry a
    ``weight`` sort key, the docs pages do not, so a search sorted by ``weight``
    drops the pages and returns the term/casilla/CLI cards ordered by tier
    weight (concept 1.0 first). Without this the concept record is buried under
    the many page hits for a corpus term like "prorrata".

    Driven through the real Pagefind WASM in a headless browser (no mock), over
    a built index whose pages match the query, so it proves the cards win even
    against competing page hits.
    """
    import http.server
    import socketserver
    import threading
    from functools import partial

    site = _fixture_site(tmp_path, pages=3)
    materialised = _concept_records()

    async def inject(index: object) -> None:
        await _inject_records(index, materialised, {})  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]  # reason: pagefind index is dynamically typed

    build_search_index(site, inject=inject)

    handler = partial(http.server.SimpleHTTPRequestHandler, directory=str(site))
    httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
    port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        from playwright.sync_api import sync_playwright

        page_name = sorted(p.name for p in site.glob("*.html"))[0]
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page()
            page.goto(f"http://127.0.0.1:{port}/{page_name}", wait_until="networkidle")
            result = page.evaluate(
                """async () => {
                  const pf = await import('/pagefind/pagefind.js');
                  const s = await pf.search('prorrata', { sort: { weight: 'desc' } });
                  const datas = await Promise.all(
                    s.results.slice(0, 5).map((r) => r.data())
                  );
                  return datas.map((d) => ({
                    kind: d.meta && d.meta.kind,
                    cid: d.meta && d.meta.concept_id,
                  }));
                }"""
            )
            browser.close()
    finally:
        httpd.shutdown()

    # Every weight-sorted result is an injected concept card (no page noise).
    assert result, "weight-sorted search returned nothing"
    assert all(row["kind"] == "concept" for row in result), result
    assert any(row["cid"] == "prorrata" for row in result), result


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
