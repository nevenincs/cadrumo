"""Durable ranking gate: full-text PAGE hits rank user docs above dev machinery.

The ratified ranking decision extends the user-first ladder from the injected
result CARDS (concept / casilla / LEGAL / CLI) to the RAW full-text page hits. Before the
build-side page-meta stamping this was structurally impossible: Pagefind
directory-indexed pages carried no ranking meta, so the palette ordered them by
raw relevance alone and an ``api/`` dev-machinery page could out-rank a
``how-to/`` user-doc page whenever it was the stronger textual match.

The fix stamps a path-derived ``display_class`` meta on each indexed page
(``cli/`` -> ``cli``, ``api/`` -> ``technical``, everything else user-facing ->
``doc``) and the shipped palette JS consumes that class to order pages within the
full-text band. This gate proves the closed loop end to end: it builds two real
pages -- a ``how-to/`` page mentioning a query token ONCE and an ``api/`` page
repeating it FOUR times (so raw BM25 relevance would float the api page first) --
runs the REAL vendored Pagefind index pass (which stamps the classes) and drives
the REAL shipped ``cadrumo-docs.js`` in a browser. The assertion is the D8
invariant that could not hold before: the how-to page leads the api page despite
the api page being the stronger textual match.

If this fails, the page-meta stamping or its JS consumption regressed and the
full-text half of the user-first ladder is broken (dev-machinery pages can
surface above user docs). It is the full-text sibling of ``test_palette_ranking``
(injected-card ladder) and ``test_search_page_inline_ladder`` (the shared
controller on the search page).

Scope/cost: two hand-authored built-HTML fixtures (no Sphinx build) plus one
injected sort-keyed anchor record (so the card pass drops full-text pages exactly
as it does in production), indexed by the real Pagefind binary, one browser --
seconds, ``integration`` marked.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.core.external_constants import OutputLanguage

from ..._paths import REPO_ROOT
from ..pagefind_index import build_search_index
from ..pagefind_inject import _inject_records, _Materialised
from ..terminology import (
    RankingTier,
    ResultDisplayClass,
    SearchRecord,
    SearchRecordKind,
    SearchRecordMetadata,
    normalise_display_class_weight,
)
from ._http_serve_support import serve_directory

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

_REPO_ROOT = REPO_ROOT
_DOCS = _REPO_ROOT / "docs"

# A made-up token present ONLY in the two full-text pages, so the query returns
# exactly them and no injected card. The api page repeats it four times and the
# how-to page once, so pure BM25 relevance would rank the api page first -- the
# D8 class ordering must override that and lead with the how-to page.
_QUERY_TERM = "zzhowtoapitoken"

# A built page shaped like the real Furo output: content lives in
# ``article[role=main]`` (what pagefind.yml scopes indexing to), so the page is
# full-text indexed and the page-meta stamping tags its <body>.
_PAGE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>{title}</title></head>
<body>
  <nav class="sidebar-tree"><a href="/x">nav noise</a></nav>
  <article role="main" id="main-content">
    <h1>{title}</h1>
    <p>{body}</p>
  </article>
</body></html>
"""

# One injected weighted anchor record. Its ONLY job is to put the `weight` sort
# key into the index: the palette's card pass is `pf.search(q, {sort:{weight}})`,
# and Pagefind drops from a sort-keyed search every result lacking that key --
# but ONLY when the key exists somewhere in the index. In production the index
# always carries thousands of injected sort-keyed records (concepts / casillas /
# LEGAL / CLI), so full-text pages ALWAYS drop from the card pass and reach the palette
# only via the relevance pass (`fromCardPass=false`), where their `display_class`
# orders them. This anchor reproduces that production invariant with one record;
# it does NOT contain the query token, so the query still matches only the two
# full-text pages, isolating the page-band ordering under test.
_ANCHOR_CARD = SearchRecord(
    id="concept:fulltext-ladder-anchor",
    kind=SearchRecordKind.CONCEPT,
    tier=RankingTier.TERM,
    title="Anchor concept",
    descriptions={OutputLanguage.ES: "concepto ancla sin el token de la consulta"},
    target="_generated/glossary.html#term-anchor",
    ranking_weight=normalise_display_class_weight(ResultDisplayClass.DOC),
    metadata=SearchRecordMetadata(concept_id="fulltext-ladder-anchor", domain="concepto"),
)

# The palette host: the real trigger + the real controller, dropped at the build
# root so Pagefind resolves /pagefind/ against the document base. It carries none
# of the query token, so it is never itself a hit.
_TRIGGER_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>palette</title></head>
<body>
<button data-cadrumo-search data-cadrumo-search-url="search.html">Search</button>
<script src="_static/cadrumo-docs.js"></script>
</body></html>
"""


def _build_fulltext_site(build: Path) -> None:
    """Materialise a two-page built site: a how-to page and an api page."""
    howto = build / "how-to"
    api = build / "api"
    howto.mkdir(parents=True)
    api.mkdir(parents=True)
    (howto / "import.html").write_text(
        _PAGE.format(
            title="Import guide",
            body=f"This how-to guide mentions {_QUERY_TERM} once for the reader.",
        ),
        encoding="utf-8",
    )
    (api / "internal.html").write_text(
        _PAGE.format(
            title="Internal reference",
            # Four repeats: the api page is the STRONGER textual match, so raw
            # relevance alone would rank it above the how-to page. D8 must win.
            body=f"Internal machinery {_QUERY_TERM} {_QUERY_TERM} {_QUERY_TERM} {_QUERY_TERM} reference.",
        ),
        encoding="utf-8",
    )
    static = build / "_static"
    static.mkdir(parents=True, exist_ok=True)
    for name in ("cadrumo-docs.js", "cadrumo-docs.css"):
        (static / name).write_bytes((_DOCS / "_static" / name).read_bytes())
    (build / "pagefind.yml").write_bytes((_DOCS / "pagefind.yml").read_bytes())
    (build / "palette.html").write_text(_TRIGGER_PAGE, encoding="utf-8")


def test_fulltext_user_doc_ranks_above_dev_machinery(tmp_path: Path) -> None:
    """A ``how-to/`` page leads an ``api/`` page even though api matches stronger."""
    build = tmp_path / "html"
    build.mkdir()
    _build_fulltext_site(build)

    # Inject one weighted concept anchor as a deliberately narrowed card fixture
    # (production also injects casilla, LEGAL, and CLI records) so the index
    # carries the `weight` sort key that makes the card pass drop full-text pages.
    # The anchor does not match the query, so the query still returns only the two
    # pages, whose ordering is then decided purely by the page-band class rank.
    async def inject(index: object) -> None:
        await _inject_records(index, _Materialised(records=[_ANCHOR_CARD], concepts=1), {})  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]  # reason: pagefind index is dynamically typed

    build_search_index(build, inject=inject)

    with serve_directory(build) as (_httpd, port):
        base = f"http://127.0.0.1:{port}"
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page()
            page.goto(f"{base}/palette.html", wait_until="networkidle")
            page.keyboard.press("Control+k")
            page.locator(".cadrumo-palette-input").fill(_QUERY_TERM)
            # Wait until both full-text page rows have painted.
            page.wait_for_function(
                "document.querySelectorAll('.cadrumo-palette-item--page').length >= 2",
                timeout=15000,
            )
            page_hrefs = page.eval_on_selector_all(
                ".cadrumo-palette-item--page a",
                "els => els.map(e => e.getAttribute('href'))",
            )
            # The per-class D8 icon must render on full-text page rows now that
            # they ship a class: the how-to row is `doc`, the api row `technical`.
            doc_icons = page.eval_on_selector_all(
                ".cadrumo-palette-item--page .cadrumo-palette-item-icon--doc svg",
                "els => els.length",
            )
            technical_icons = page.eval_on_selector_all(
                ".cadrumo-palette-item--page .cadrumo-palette-item-icon--technical svg",
                "els => els.length",
            )
            browser.close()

    howto_index = next(
        (i for i, href in enumerate(page_hrefs) if href and "how-to/import.html" in href),
        None,
    )
    api_index = next(
        (i for i, href in enumerate(page_hrefs) if href and "api/internal.html" in href),
        None,
    )
    assert howto_index is not None, f"the how-to page did not render: {page_hrefs}"
    assert api_index is not None, f"the api page did not render: {page_hrefs}"
    # D8: the user-doc page ranks ABOVE the dev-machinery page even though the api
    # page is the stronger textual match -- the assertion that was structurally
    # impossible before the page-meta stamping landed.
    assert howto_index < api_index, f"how-to did not out-rank api: {page_hrefs}"
    # Full-text page hits now carry a path-derived class + its icon (D8/D7).
    assert doc_icons > 0, "the doc class icon did not render on the how-to page row"
    assert technical_icons > 0, "the technical class icon did not render on the api page row"
