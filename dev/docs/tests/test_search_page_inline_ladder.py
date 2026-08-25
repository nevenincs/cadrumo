"""Durable gate: the SHIPPED search page inherits the palette tier ladder.

The ratified search-surface decision retires the stock ``PagefindUI`` drop from
``docs/_templates/search.html`` and hosts the Ctrl-K palette's own search
controller inline on the page, so the page and the modal share ONE ranking
implementation. The whole point of that extraction is that the page stops
rendering Pagefind's flat relevance list and starts rendering the ratified tier
ladder -- term/casilla/LEGAL/CLI cards ABOVE full-text pages, with the PERF-003
exact-term tie-break inside the card tier.

This is the inline-host sibling of ``test_palette_ranking.py`` (which proves the
same ladder in the modal). It drives the REAL shipped ``search.html`` +
``cadrumo-docs.js`` in a real browser: build the page, inject the deliberately
narrowed approved-concept fixture into the Pagefind index, navigate to
``search.html?q=iva``, and
assert a concept CARD leads the rendered results -- proof the page inherited the
palette ranking rather than Pagefind's flat list (which would surface no
``--concept`` card class and would not float the exact-term concept first).

If this ever fails while ``test_palette_ranking.py`` passes, the extraction
regressed the inline host specifically; if both fail, the shared controller
regressed and BOTH search surfaces degraded at once.

Scope/cost: builds a Furo subset that renders the real search template + loads
the real controller, injects only the approved concept-card fixture (the
production funnel also carries casilla, LEGAL, and CLI records), indexes, and
drives one browser -- seconds, ``integration`` marked.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from ..._paths import REPO_ROOT
from ..pagefind_index import build_search_index
from ..pagefind_inject import _inject_records
from ._http_serve_support import serve_directory
from .test_palette_ranking import _approved_concept_records

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

_REPO_ROOT = REPO_ROOT
_DOCS = _REPO_ROOT / "docs"

_MOUNT = "#pagefind-search"
_INPUT_SELECTOR = f"{_MOUNT} input"
# The inline host reuses the palette's result-item classes verbatim, so the
# concept-card class is the same one test_palette_ranking asserts on -- proving
# the page renders the SAME tiered surface, not a look-alike.
_CONCEPT_TITLE = f"{_MOUNT} .cadrumo-palette-item--concept .cadrumo-palette-item-title"
_ANY_TITLE = f"{_MOUNT} .cadrumo-palette-item .cadrumo-palette-item-title"


def _build_search_site(out: Path) -> Path:
    """Build a Furo subset rendering the real search template + real controller."""
    src = out / "src"
    build = out / "html"
    src.mkdir(parents=True)
    static = src / "_static"
    static.mkdir(parents=True)
    for name in ("cadrumo-docs.js", "cadrumo-docs.css"):
        (static / name).write_bytes((_DOCS / "_static" / name).read_bytes())
    # templates_path points at the REAL docs/_templates so the shipped
    # search.html override renders; html_js_files wires the real controller
    # exactly as production conf.py does.
    (src / "conf.py").write_text(
        "project = 'cadrumo-inline-ladder'\n"
        "extensions = []\n"
        "html_theme = 'furo'\n"
        f"templates_path = [r'{_DOCS / '_templates'}']\n"
        "html_static_path = ['_static']\n"
        "html_js_files = ['cadrumo-docs.js']\n"
        "html_css_files = ['cadrumo-docs.css']\n",
        encoding="utf-8",
    )
    (src / "index.rst").write_text(
        "Home\n====\n\n.. toctree::\n\n   topics\n",
        encoding="utf-8",
    )
    (src / "topics.rst").write_text(
        "Topics\n======\n\nGeneral documentation content for the full-text index.\n",
        encoding="utf-8",
    )

    from sphinx.application import Sphinx

    app = Sphinx(
        str(src),
        str(src),
        str(build),
        str(out / "doctree"),
        "html",
        status=io.StringIO(),
        warning=io.StringIO(),
        freshenv=True,
    )
    app.build()
    return build


def test_search_page_renders_the_tier_ladder(tmp_path: Path) -> None:
    """``search.html?q=iva`` -> the IVA concept card leads the rendered results."""
    out = tmp_path / "site"
    out.mkdir()
    build = _build_search_site(out)
    (build / "pagefind.yml").write_bytes((_DOCS / "pagefind.yml").read_bytes())

    materialised = _approved_concept_records()

    async def inject(index: object) -> None:
        await _inject_records(index, materialised, {})  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]  # reason: pagefind index is dynamically typed

    build_search_index(build, inject=inject)

    with serve_directory(build) as (_httpd, port):
        base = f"http://127.0.0.1:{port}"
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page()
            # The ?q= seed drives the inline controller with no typing -- the same
            # path a casilla/palette handoff takes to this page.
            page.goto(f"{base}/search.html?q=iva", wait_until="networkidle")
            page.wait_for_selector(_INPUT_SELECTOR, timeout=15000)
            # The concept cards paint asynchronously once Pagefind resolves.
            page.wait_for_function(
                f"document.querySelectorAll({_CONCEPT_TITLE!r}).length > 0",
                timeout=15000,
            )
            seeded = page.input_value(_INPUT_SELECTOR)
            concept_titles = page.eval_on_selector_all(
                _CONCEPT_TITLE,
                "els => els.map(e => e.textContent.trim())",
            )
            first_row = page.eval_on_selector_all(
                _ANY_TITLE,
                "els => els.length ? els[0].textContent.trim() : ''",
            )
            # The per-class D7 icon must render on the inline host too: the
            # general-fact IVA concept ships display_class `doc`, so its row
            # carries the doc icon SVG -- read verbatim from the shipped meta,
            # never re-derived. Proves the icon lands on BOTH hosts (the shared
            # controller renders it once for the modal and the page).
            doc_icon_svgs = page.eval_on_selector_all(
                f"{_MOUNT} .cadrumo-palette-item--concept .cadrumo-palette-item-icon--doc svg",
                "els => els.length",
            )
            browser.close()

    assert seeded == "iva", f"input not seeded from ?q=, got {seeded!r}"
    assert concept_titles, "no concept cards rendered on the search page"
    # The tier ladder: a concept CARD leads the whole result list, above any
    # full-text page hit -- Pagefind's flat list would not do this.
    assert first_row == "IVA", f"expected the IVA concept card first, got {first_row!r}"
    # And the PERF-003 tie-break floats the exact-term concept ahead of VIES.
    if "VIES" in concept_titles:
        assert concept_titles.index("IVA") < concept_titles.index("VIES"), concept_titles
    # D7: the doc-class icon rendered on the inline host's concept rows.
    assert doc_icon_svgs > 0, "the doc class icon did not render on the search page"
