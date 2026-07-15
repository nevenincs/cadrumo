"""Durable ``?q=`` handoff gate: the SHIPPED search page, in a browser.

``docs/_templates/search.html`` is the landing surface every full-text handoff
targets: the Ctrl-K palette's always-present "Search the docs for ..." row
(``docs/_static/cadrumo-docs.js``, ``fullSearchEntry``) and the casilla search
records both navigate here with the reader's query in ``?q=``. The template
once rendered a bare PagefindUI that never read the parameter, so every handoff
landed on an empty box -- the query was received and silently dropped.

This gate drives the real shipped template (rendered by a real Furo build, via
the same ``templates_path`` override production uses) against a real Pagefind
index in a real browser. It locks the contract in both encodings that reach the
page: the palette emits ``%20`` for spaces via ``encodeURIComponent``, the
casilla records emit ``+``. ``URLSearchParams`` decodes both; the
``decodeURIComponent`` that does NOT decode ``+`` is the regression this
asserts against (the reported failure was ``search.html?q=130+10``).

Scope/cost: builds a two-page Furo subset, indexes it, and drives one browser --
seconds, ``integration`` marked. Sibling of ``test_palette_ranking.py`` (the
palette's compose ladder); this one owns the page the palette hands off to.
"""

from __future__ import annotations

import http.server
import io
import socketserver
import threading
from functools import partial
from pathlib import Path

import pytest

from ..pagefind_index import build_search_index

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DOCS = _REPO_ROOT / "docs"

# The indexed target. Carries both terms of the "130 10" query so the
# +-encoded case resolves to a real hit rather than an empty result set.
_TARGET_PAGE = """Modelo 130 casilla 10
=====================

The modelo 130 pago fraccionado declares casilla 10 as the rendimiento neto
of the period. Casilla 10 carries the cumulative figure for modelo 130.
"""

_OTHER_PAGE = """Prorrata
========

The prorrata rule apportions deducible IVA and is unrelated to pagos
fraccionados.
"""


def _build_search_site(out: Path) -> Path:
    """Build a Furo subset that renders the real shipped search template."""
    src = out / "src"
    build = out / "html"
    src.mkdir(parents=True)
    # templates_path points at the REAL docs/_templates, so Sphinx renders the
    # shipped search.html override -- not a copy that could drift from it.
    (src / "conf.py").write_text(
        "project = 'cadrumo-search'\n"
        "extensions = []\n"
        "html_theme = 'furo'\n"
        f"templates_path = [r'{_DOCS / '_templates'}']\n",
        encoding="utf-8",
    )
    (src / "index.rst").write_text(
        "Search\n======\n\n.. toctree::\n\n   modelo\n   prorrata\n",
        encoding="utf-8",
    )
    (src / "modelo.rst").write_text(_TARGET_PAGE, encoding="utf-8")
    (src / "prorrata.rst").write_text(_OTHER_PAGE, encoding="utf-8")

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


@pytest.fixture(scope="module")
def search_site(tmp_path_factory: pytest.TempPathFactory) -> object:
    """The built, indexed, served search site. Built once for every case."""
    out = tmp_path_factory.mktemp("search-site")
    build = _build_search_site(out)
    (build / "pagefind.yml").write_bytes((_DOCS / "pagefind.yml").read_bytes())
    build_search_index(build)

    httpd, port = _serve(build)
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        httpd.shutdown()


def _read_search_page(base: str, query_string: str) -> tuple[str, list[str], str]:
    """Open search.html with ``query_string``; return input value, result titles, URL.

    Waits for the Pagefind UI to paint its input, then for results only when a
    query was seeded -- so the no-query case can assert emptiness without
    racing a result that never comes.
    """
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()
        page.goto(f"{base}/search.html{query_string}", wait_until="networkidle")
        # The UI renders its input asynchronously after construction.
        page.wait_for_selector(".pagefind-ui__search-input", timeout=15000)
        value = page.input_value(".pagefind-ui__search-input")
        if value:
            page.wait_for_function(
                "document.querySelectorAll('.pagefind-ui__result-link').length > 0",
                timeout=15000,
            )
        titles = page.eval_on_selector_all(
            ".pagefind-ui__result-link",
            "els => els.map(e => e.textContent.trim())",
        )
        url = page.url
        browser.close()
    return value, titles, url


def test_percent_encoded_query_seeds_results(search_site: str) -> None:
    """The palette's %20-encoded handoff renders results without typing."""
    # encodeURIComponent("modelo 130") -- exactly what fullSearchEntry emits.
    value, titles, _ = _read_search_page(search_site, "?q=modelo%20130")

    assert value == "modelo 130", f"input not seeded, got {value!r}"
    assert titles, "no results rendered for the seeded query"
    assert any("130" in t for t in titles), titles


def test_plus_encoded_query_seeds_results(search_site: str) -> None:
    """The reported failure: ``?q=130+10`` -- ``+`` is a space, not a literal.

    ``decodeURIComponent("130+10")`` yields the literal ``"130+10"``, which
    matches nothing. This is the regression the gate exists for.
    """
    value, titles, _ = _read_search_page(search_site, "?q=130+10")

    assert value == "130 10", f"`+` not decoded as space, got {value!r}"
    assert titles, "no results rendered for the +-encoded query"
    assert any("130" in t for t in titles), titles


def test_no_query_leaves_the_plain_search_page(search_site: str) -> None:
    """A bare search.html stays the plain "open search page" path."""
    value, titles, _ = _read_search_page(search_site, "")

    assert value == "", f"input should be empty with no ?q=, got {value!r}"
    assert titles == [], f"no results should render unprompted, got {titles}"


def test_typing_syncs_the_url_for_sharing(search_site: str) -> None:
    """The URL tracks the input, so a refined search is shareable.

    Asserted via replaceState semantics: the reader's own typing must not
    stack history entries, so one back step leaves the page entirely.
    """
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()
        page.goto(f"{search_site}/index.html", wait_until="networkidle")
        page.goto(f"{search_site}/search.html", wait_until="networkidle")
        page.wait_for_selector(".pagefind-ui__search-input", timeout=15000)
        page.locator(".pagefind-ui__search-input").fill("prorrata")
        page.wait_for_function(
            "new URL(window.location.href).searchParams.get('q') === 'prorrata'",
            timeout=15000,
        )
        # replaceState, not pushState: typing left no extra history entry, so
        # one back step returns to the page before the search.
        page.go_back(wait_until="networkidle")
        landed = page.url
        browser.close()

    assert landed.endswith("/index.html"), f"back button not sane, landed on {landed}"
