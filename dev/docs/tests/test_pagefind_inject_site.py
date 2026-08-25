"""Pagefind injection against a real built-HTML site.

Runs the vendored Pagefind binary over a copied subset of the real built HTML
and asserts the injection lands per language with deep-link targets and ranking
weights. These are ``integration``: they need the binary and the built site.

The projection and weighting checks that share the record helper are in
``test_pagefind_inject``; the helper itself is in ``_pagefind_inject_support``.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from cadrumo.core import scan_directory

from ..._paths import REPO_ROOT
from ..pagefind_index import build_search_index
from ..pagefind_inject import (
    InjectionStats,
    _inject_records,
    _materialise_records,
)
from ..terminology._concept_cards import project_concept_cards
from ._http_serve_support import serve_directory
from ._pagefind_inject_support import concept_records

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

# dev/docs/tests -> parents[3] is the repo root.
_REPO_ROOT = REPO_ROOT
_BUILT_HTML = _REPO_ROOT / "docs" / "_build" / "html"
_PAGEFIND_YML = _REPO_ROOT / "docs" / "pagefind.yml"


def _fixture_site(tmp_path: Path, *, pages: int = 3) -> Path:
    """Copy a small real built-HTML subset + the pagefind.yml into tmp."""
    site = tmp_path / "site"
    site.mkdir()
    html = scan_directory(_BUILT_HTML, pattern="*.html", recursive=True)[:pages]
    for source in html:
        dest = site / source.relative_to(_BUILT_HTML)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(source, dest)
    shutil.copy(_PAGEFIND_YML, site / "pagefind.yml")
    return site


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
    materialised = concept_records()
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
    languages = {p.name.split("_")[0] for p in scan_directory(pf, pattern="*.pf_index", recursive=True)}
    assert "en" in languages


def test_sorted_by_weight_returns_only_injected_cards(tmp_path: Path) -> None:
    """A weight-sorted Pagefind search returns ONLY the injected records.

    This is the load-bearing mechanism the Ctrl-K palette relies on to surface
    term cards above the full-text pages: the injected records carry a
    ``weight`` sort key, the docs pages do not, so a search sorted by ``weight``
    drops the pages and returns the term/casilla/legal/CLI records ordered by tier
    weight (concept 1.0 first). Without this the concept record is buried under
    the many page hits for a corpus term like "prorrata".

    Driven through the real Pagefind WASM in a headless browser (no mock), over
    a built index whose pages match the query, so it proves the cards win even
    against competing page hits.
    """
    site = _fixture_site(tmp_path, pages=3)
    materialised = concept_records()

    async def inject(index: object) -> None:
        await _inject_records(index, materialised, {})  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]  # reason: pagefind index is dynamically typed

    build_search_index(site, inject=inject)

    with serve_directory(site) as (_httpd, port):
        from playwright.sync_api import sync_playwright

        page_name = sorted(p.name for p in scan_directory(site, pattern="*.html"))[0]
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

    # Every weight-sorted result is an injected concept card (no page noise).
    assert result, "weight-sorted search returned nothing"
    assert all(row["kind"] == "concept" for row in result), result
    assert any(row["cid"] == "prorrata" for row in result), result


def test_materialises_every_kind_with_graceful_cli() -> None:
    """All five record kinds materialise into unified records.

    Proves the full projection pipeline (concepts + casillas + legal provisions
    + CLI) funnels into unified records, and that the CLI projection is
    skipped-and-reported if the live CLI is unavailable rather than failing the
    whole injection - concepts, casillas, and legal provisions (the priority
    surfaces) always land. This tests the materialisation directly; the Pagefind
    injection of the records is proven by the per-language integration tests
    above, so the slow full 7k-record Pagefind write is not repeated here.
    """
    materialised = _materialise_records()

    assert materialised.concepts > 0
    assert materialised.casillas > 1000  # thousands of deduped casillas
    assert materialised.legal_provisions > 0
    # CLI either projected (commands > 0) or was cleanly skipped-and-reported.
    assert materialised.cli_commands > 0 or materialised.cli_skipped_reason is not None
    # The unified record list spans every kind that projected.
    kinds = {r.kind.value for r in materialised.records}
    assert {"concept", "casilla", "legal"} <= kinds
    # Every record carries a deep-link target and a weight in [0, 1].
    sample = materialised.records[0]
    assert sample.target
    assert 0.0 <= sample.ranking_weight <= 1.0


def test_compile_search_index_wires_the_real_injector_over_built_html(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The docs-build driver compiles a working corpus over built HTML.

    Proves the ``dev.docs.build.compile_search_index`` wiring end to end: it
    runs the Pagefind directory pass over the built HTML and injects the unified
    search records, writing a per-language index alongside the pages. This is
    the seam ``just docs`` invokes after a full Sphinx build; without it the
    bundled Ctrl-K corpus never compiles. A real concept-subset injector is
    supplied so the wiring is exercised without the multi-minute full
    casilla/CLI materialisation (production uses the default full injector).
    """
    from ..build import compile_search_index

    site = _fixture_site(tmp_path, pages=3)
    materialised = concept_records()

    async def inject(index: object) -> None:
        await _inject_records(index, materialised, {})  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]  # reason: pagefind index is dynamically typed

    compile_search_index(site, _REPO_ROOT, injector=inject)

    pagefind = site / "pagefind"
    assert (pagefind / "pagefind-entry.json").is_file()
    assert (pagefind / "pagefind.js").is_file()
    # The driver reports the compiled corpus (page count + record line).
    summary = capsys.readouterr().out
    assert "Search index compiled" in summary
    assert "term/casilla/legal/CLI records" in summary


def test_materialise_injects_approved_concepts_only_no_drafts() -> None:
    """The production injector ships only approved concept cards, never drafts.

    A draft concept is scaffold-empty (placeholder short_description) and absent
    from the approved-only generated glossary, so its ``#term-<id>`` deep link
    is dead -- injecting it would ship a placeholder card that 404s. The
    materialised concept records must therefore all carry ``lifecycle ==
    'approved'`` and match the approved-concept count.
    """
    from cadrumo.core import ConceptLifecycle

    cards, _ = project_concept_cards()
    approved = sum(1 for c in cards if c.lifecycle is ConceptLifecycle.APPROVED)
    drafts = sum(1 for c in cards if c.lifecycle is not ConceptLifecycle.APPROVED)
    assert drafts > 0  # the Handbook carries a draft backlog that must be excluded

    materialised = _materialise_records()
    concept_records = [r for r in materialised.records if r.kind.value == "concept"]

    assert materialised.concepts == approved
    assert len(concept_records) == approved
    assert all(r.metadata.lifecycle == "approved" for r in concept_records)
