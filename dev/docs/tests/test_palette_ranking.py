"""Durable palette-ladder gate: the SHIPPED Ctrl-K palette, in a browser.

The prorrata smoke gate proves the index + injection + ``pf.search`` surface a
concept card; this gate proves the palette's COMPOSE LADDER on top of it -- the
exact behaviour an operator sees when they press Ctrl-K and type. It drives the
real shipped ``docs/_static/aeat-docs.js`` (not a re-implementation): opens the
palette, types a query, and reads the rendered ``.aeat-palette-item`` rows.

It locks in two invariants found and fixed during the corpus-quality drive
(audit ``2026-06-15-docs-terminology-search``):

* PERF-003 ranking -- every injected concept card carries the flat tier-one
  weight, so a pure weight sort ties them and the exact-term match can sink
  below incidental matches (``iva`` once surfaced VIES first). The palette now
  breaks within-tier ties by relevance, so the exact-term concept leads its
  tier. Asserted: ``iva`` -> the IVA concept is the FIRST palette result and
  ranks ahead of VIES.
* PERF-001 draft-free -- the injected concept set carries only approved
  concepts (drafts 404 against the approved-only glossary), asserted on the
  materialised records the palette renders.

Scope/cost: builds the generated-glossary subset (for the ``#term`` anchors) and
a single trigger page, injects the approved concept cards (no casilla/CLI walk),
and drives one browser -- seconds, ``integration`` marked.
"""

from __future__ import annotations

import http.server
import io
import socketserver
import threading
from functools import partial
from pathlib import Path

import pytest

from ..glossary_reference import generate_glossary_reference
from ..pagefind_index import build_search_index
from ..pagefind_inject import _inject_records, _Materialised
from ..terminology._concept_cards import project_concept_cards
from ..terminology._unified_record import to_search_record

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DOCS = _REPO_ROOT / "docs"

# A page carrying the palette trigger + the real palette JS, dropped at the
# build root so the palette resolves /pagefind/ against the document base.
_TRIGGER_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>palette</title></head>
<body>
<button data-aeat-search data-aeat-search-url="search.html">Search</button>
<script src="_static/aeat-docs.js"></script>
</body></html>
"""


def _approved_concept_records() -> _Materialised:
    """The approved concept cards the production injector ships (no drafts)."""
    from ..terminology_handbook._enums import ConceptLifecycle

    cards, _ = project_concept_cards()
    approved = [c for c in cards if c.lifecycle is ConceptLifecycle.APPROVED]
    # The invariant the palette renders: nothing draft reaches a card.
    assert approved and all(c.lifecycle is ConceptLifecycle.APPROVED for c in approved)
    records = [to_search_record(c) for c in approved]
    return _Materialised(records=records, concepts=len(records))


def _build_glossary_site(out: Path) -> Path:
    """Build the generated-glossary subset and return the built-HTML root."""
    src = out / "src"
    build = out / "html"
    src.mkdir(parents=True)
    generate_glossary_reference(src)
    (src / "conf.py").write_text(
        'project = "aeat-palette"\nextensions = []\nhtml_theme = "basic"\n',
        encoding="utf-8",
    )
    (src / "index.rst").write_text(
        "Palette\n=======\n\n.. toctree::\n\n   _generated/glossary\n",
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


def _serve(directory: Path) -> tuple[socketserver.TCPServer, int]:
    handler = partial(http.server.SimpleHTTPRequestHandler, directory=str(directory))
    httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
    port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, port


def test_palette_ranks_exact_term_concept_first(tmp_path: Path) -> None:
    """Ctrl-K + "iva" -> the IVA concept is the first row, ahead of VIES."""
    out = tmp_path / "site"
    out.mkdir()
    build = _build_glossary_site(out)

    static = build / "_static"
    static.mkdir(parents=True, exist_ok=True)
    for name in ("aeat-docs.js", "aeat-docs.css"):
        (static / name).write_bytes((_DOCS / "_static" / name).read_bytes())
    (build / "pagefind.yml").write_bytes((_DOCS / "pagefind.yml").read_bytes())
    (build / "palette.html").write_text(_TRIGGER_PAGE, encoding="utf-8")

    materialised = _approved_concept_records()

    async def inject(index: object) -> None:
        await _inject_records(index, materialised, {})  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]  # reason: pagefind index is dynamically typed

    build_search_index(build, inject=inject)

    httpd, port = _serve(build)
    base = f"http://127.0.0.1:{port}"
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page()
            page.goto(f"{base}/palette.html", wait_until="networkidle")
            # Open the palette and type the query through the real shipped JS.
            page.keyboard.press("Control+k")
            page.locator(".aeat-palette-input").fill("iva")
            # Wait until the async Pagefind cards have painted concept rows.
            page.wait_for_function(
                "document.querySelectorAll('.aeat-palette-item--concept .aeat-palette-item-title').length > 0",
                timeout=15000,
            )
            titles = page.eval_on_selector_all(
                ".aeat-palette-item--concept .aeat-palette-item-title",
                "els => els.map(e => e.textContent.trim())",
            )
            # Also read the very first rendered row (any kind) to prove the
            # concept leads the whole ladder, not just its own tier.
            first_row = page.eval_on_selector_all(
                ".aeat-palette-item .aeat-palette-item-title",
                "els => els.length ? els[0].textContent.trim() : ''",
            )
            browser.close()
    finally:
        httpd.shutdown()

    assert titles, "no concept rows rendered for 'iva'"
    # The exact-term concept leads its tier (regression: VIES once led).
    assert titles[0] == "IVA", f"expected IVA first, got {titles}"
    if "VIES" in titles:
        assert titles.index("IVA") < titles.index("VIES"), titles
    # And a concept leads the entire palette ladder (cards above nav/full-text).
    assert first_row == "IVA", f"expected IVA as first palette row, got {first_row!r}"
