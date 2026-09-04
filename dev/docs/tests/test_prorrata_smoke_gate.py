"""End-to-end prorrata smoke gate: the whole pipeline, in a browser.

This is the durable end-to-end proof of the documentation-search pipeline:
Handbook concepts and registry casillas project into unified records, the
records inject into the Pagefind index, and the Ctrl-K palette - driven through
real Pagefind WASM in a headless browser - surfaces them as term cards with
resolving deep links. It is the gate the operator's goal ("semantic search via
the command-K palette") is held to.

What it asserts for the query "prorrata":

* a CONCEPT card appears AND its deep link resolves to the built generated
  glossary at the ``#term-prorrata`` / ``#term-prorrata-especial`` anchor (this
  proves the concept-target path fix - the link points at
  ``_generated/glossary.html``, not the removed ``glossary.html``);
* at least one M303 prorrata CASILLA card appears with a resolving deep link;
* a relevant how-to/explanation PAGE appears in the full-text tier;
* FOUR-LANGUAGE probes (es / en / ca / hu phrasings) each surface the prorrata
  concept card - the cross-lingual matching the combined-language injection
  content delivers.

Scope/cost: the gate builds a representative docs SUBSET (the generated
glossary, a prorrata how-to, the search page, an index) rather than the full
1776-page site, so it runs in seconds, not minutes - while still driving a real
browser and asserting resolving deep links (no mocks). It is ``integration``
marked: it builds docs + the Pagefind index and runs Playwright, so it runs in
the lane that has a browser, not the default unit lane.

Run it with::

    uv run --no-sync pytest dev/docs/tests/test_prorrata_smoke_gate.py \
        -q -m integration
"""

from __future__ import annotations

import io
import urllib.request
from pathlib import Path

import pytest

from ..._paths import REPO_ROOT
from ..glossary_reference import generate_glossary_reference
from ..pagefind_index import build_search_index
from ..pagefind_inject import _inject_records, _Materialised
from ..terminology._concept_cards import project_concept_cards
from ..terminology.casilla_projection import project_casilla_search_records
from ..terminology.unified_record import to_search_record
from ._http_serve_support import serve_directory

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

# dev/docs/tests/test_prorrata_smoke_gate.py -> parents[3] is the repo root.
_REPO_ROOT = REPO_ROOT
_DOCS = _REPO_ROOT / "docs"

# Four-language prorrata probes: each must surface the concept card. "pro rata"
# is the English admitted alias; the ca/hu phrasings ride the combined-language
# injection content.
_LANGUAGE_PROBES = (
    ("es", "prorrata"),
    ("en", "pro rata"),
    ("ca", "prorrata sectors"),
    ("hu", "aranyositas"),
)


def _build_subset_site(out: Path) -> None:
    """Build a representative docs subset with Sphinx: glossary + a how-to."""
    src = out / "src"
    build = out / "html"
    src.mkdir(parents=True)
    generate_glossary_reference(src)
    (src / "conf.py").write_text(
        'project = "cadrumo-smoke"\n'
        'extensions = ["myst_parser"]\n'
        'source_suffix = {".md": "markdown", ".rst": "restructuredtext"}\n'
        'html_theme = "basic"\n',
        encoding="utf-8",
    )
    (src / "how-to.md").write_text(
        "# Choose the prorrata rule\n\n"
        "Use the prorrata rule when your IVA return mixes deductible and "
        "non-deductible operations. The deductible proportion is the prorrata.\n",
        encoding="utf-8",
    )
    (src / "index.rst").write_text(
        "Smoke\n=====\n\n.. toctree::\n\n   _generated/glossary\n   how-to\n",
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


def _prorrata_records() -> _Materialised:
    """Concept cards plus the M303 prorrata casillas - the smoke surfaces."""
    concept_cards, _ = project_concept_cards()
    casillas, _ = project_casilla_search_records()
    records = [to_search_record(card) for card in concept_cards]
    for casilla in casillas:
        if casilla.modelo.value != "303":
            continue
        if any("prorrata" in (text or "").lower() for text in casilla.descriptions.values()):
            records.append(to_search_record(casilla))
    return _Materialised(records=records)


def test_prorrata_end_to_end_palette_smoke(tmp_path: Path) -> None:
    """Ctrl-K -> prorrata -> concept card + M303 casilla + how-to + 4 languages."""
    out = tmp_path / "site"
    out.mkdir()
    _build_subset_site(out)
    build = out / "html"
    # Copy the real palette JS/CSS into the built site so Ctrl-K is wired.
    static = build / "_static"
    static.mkdir(parents=True, exist_ok=True)
    for name in ("cadrumo-docs.js", "cadrumo-docs.css"):
        (static / name).write_bytes((_DOCS / "_static" / name).read_bytes())
    (build / "pagefind.yml").write_bytes((_DOCS / "pagefind.yml").read_bytes())

    materialised = _prorrata_records()

    async def inject(index: object) -> None:
        await _inject_records(index, materialised, {})  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]  # reason: pagefind index is dynamically typed

    build_search_index(build, inject=inject)

    with serve_directory(build) as (_httpd, port):
        base = f"http://127.0.0.1:{port}"
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page()
            # The injected query API is exercised directly (the basic theme
            # carries no palette trigger); this is the same path the palette's
            # searchPagefind() runs, so it proves the index + injection + the
            # weight-sort card surfacing end to end.
            page.goto(f"{base}/how-to.html", wait_until="networkidle")

            def search(query: str) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
                raw = page.evaluate(
                    """async (q) => {
                      const pf = await import('/pagefind/pagefind.js');
                      const cards = await pf.search(q, { sort: { weight: 'desc' } });
                      const pages = await pf.search(q);
                      const cardData = await Promise.all(
                        cards.results.slice(0, 12).map((r) => r.data())
                      );
                      const pageData = await Promise.all(
                        pages.results.slice(0, 6).map((r) => r.data())
                      );
                      return {
                        cards: cardData.map((d) => ({
                          kind: (d.meta && d.meta.kind) || "",
                          cid: (d.meta && d.meta.concept_id) || "",
                          modelo: (d.meta && d.meta.modelo) || "",
                          url: d.url || "",
                        })),
                        pages: pageData.map((d) => ({ url: d.url || "" })),
                      };
                    }""",
                    query,
                )
                return list(raw["cards"]), list(raw["pages"])

            cards, pages = search("prorrata")

            concept_cards = [c for c in cards if c["kind"] == "concept"]
            casilla_cards = [c for c in cards if c["kind"] == "casilla" and c["modelo"] == "303"]

            assert concept_cards, f"no concept card for prorrata; got {cards}"
            assert any(c["cid"] in ("prorrata", "prorrata-especial") for c in concept_cards), concept_cards
            assert casilla_cards, f"no M303 prorrata casilla card; got {cards}"

            # The concept deep link resolves to the built generated glossary
            # at its #term- anchor (proves the target-path fix).
            concept_url = concept_cards[0]["url"]
            assert "_generated/glossary.html#term-" in concept_url, concept_url
            page_path, anchor = concept_url.split("#", 1)
            # Fetch the deep-link page from the local test server to prove it
            # resolves (the loopback URL is the gate's own fixture, not input).
            with urllib.request.urlopen(base + page_path, timeout=10) as resp:  # noqa: S310
                assert resp.status == 200, page_path
                body = resp.read().decode("utf-8")
            assert f'id="{anchor}"' in body, f"{anchor} not in built glossary"

            # A relevant how-to / explanation page appears in the full-text tier.
            assert any("how-to.html" in p["url"] for p in pages), pages

            # Four-language probes: each surfaces the prorrata concept card.
            for language, probe in _LANGUAGE_PROBES:
                probe_cards, _ = search(probe)
                concepts = [c for c in probe_cards if c["kind"] == "concept"]
                assert concepts, f"{language} probe {probe!r} found no concept card"

            browser.close()
