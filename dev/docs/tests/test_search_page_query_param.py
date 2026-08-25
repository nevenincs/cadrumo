"""Durable ``?q=`` handoff gate: the SHIPPED search page, in a browser.

``docs/_templates/search.html`` is the landing surface every full-text handoff
targets: the Ctrl-K palette's always-present "Search the docs for ..." row
(``docs/_static/cadrumo-docs.js``, ``fullSearchEntry``) and the casilla search
records both navigate here with the reader's query in ``?q=``. The template
once rendered a search box that never read the parameter, so every handoff
landed on an empty box -- the query was received and silently dropped.

The gate is written against OBSERVABLE behaviour, not the surface internals:
navigate to ``search.html?q=<term>``, assert the query is visible in an input
and results for ``<term>`` are on screen without typing. It queries a plain
``input`` value and the page's own rendered text (the indexed page title), NOT
any surface-specific result class, so the assertions held across the
retirement of the stock ``PagefindUI`` drop in favour of the palette-hosted
inline controller -- the ``?q=`` contract is the same either way. The page is
now a bare ``#pagefind-search`` mount that the globally-loaded
``cadrumo-docs.js`` (``initSearchPage``) renders the shared search controller
into; this build wires that asset exactly as the production ``conf.py`` does.

Both encodings that reach the page are locked: the palette emits ``%20`` for
spaces via ``encodeURIComponent``, the casilla records emit ``+``.
``URLSearchParams`` decodes both; the ``decodeURIComponent`` that does NOT
decode ``+`` is the regression this asserts against (the reported failure was
``search.html?q=130+10``).

Scope/cost: builds a two-page Furo subset, indexes it, and drives one browser --
seconds, ``integration`` marked. Sibling of ``test_palette_ranking.py`` (the
palette's compose ladder); this one owns the page the palette hands off to.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from ..._paths import REPO_ROOT
from ..pagefind_index import build_search_index
from ._http_serve_support import serve_directory

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

_REPO_ROOT = REPO_ROOT
_DOCS = _REPO_ROOT / "docs"

# The indexed target. Its title carries both terms of the "130 10" query so the
# +-encoded case resolves to a real hit rather than an empty result set, and
# asserting the title text is on screen is surface-agnostic (it is the indexed
# page's own content, not a result-widget class).
_TARGET_TITLE = "Modelo 130 casilla 10"
_TARGET_PAGE = f"""{_TARGET_TITLE}
=====================

The modelo 130 pago fraccionado declares casilla 10 as the rendimiento neto
of the period. Casilla 10 carries the cumulative figure for modelo 130.
"""

_OTHER_PAGE = """Prorrata
========

The prorrata rule apportions deducible IVA and is unrelated to pagos
fraccionados.
"""

# The search page mounts its surface into this container (the template's own
# element in search.html, NOT a PagefindUI internal). Scoping queries to it
# excludes the Furo theme chrome -- its own header search box and its sidebar
# nav, which lists every page title and would otherwise pollute a body-text
# assertion. The input and results are read from within this container, so the
# assertions track "the search surface", whichever surface renders there.
_MOUNT = "#pagefind-search"
_INPUT_SELECTOR = f"{_MOUNT} input"


def _build_search_site(out: Path) -> Path:
    """Build a Furo subset that renders the real shipped search template."""
    src = out / "src"
    build = out / "html"
    src.mkdir(parents=True)
    # The shipped search.html is a bare mount; the globally-loaded
    # cadrumo-docs.js hosts the search controller inline. Copy the real
    # shipped asset in and wire it exactly as production conf.py does
    # (html_js_files / html_css_files), so the built page loads the same
    # controller the real site does -- not a stub.
    static = src / "_static"
    static.mkdir(parents=True)
    for name in ("cadrumo-docs.js", "cadrumo-docs.css"):
        (static / name).write_bytes((_DOCS / "_static" / name).read_bytes())
    # templates_path points at the REAL docs/_templates, so Sphinx renders the
    # shipped search.html override -- not a copy that could drift from it.
    (src / "conf.py").write_text(
        "project = 'cadrumo-search'\n"
        "extensions = []\n"
        "html_theme = 'furo'\n"
        f"templates_path = [r'{_DOCS / '_templates'}']\n"
        "html_static_path = ['_static']\n"
        "html_js_files = ['cadrumo-docs.js']\n"
        "html_css_files = ['cadrumo-docs.css']\n",
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


@pytest.fixture(scope="module")
def search_site(tmp_path_factory: pytest.TempPathFactory) -> object:
    """The built, indexed, served search site. Built once for every case."""
    out = tmp_path_factory.mktemp("search-site")
    build = _build_search_site(out)
    (build / "pagefind.yml").write_bytes((_DOCS / "pagefind.yml").read_bytes())
    build_search_index(build)

    with serve_directory(build) as (_httpd, port):
        yield f"http://127.0.0.1:{port}"


def _read_search_page(base: str, query_string: str) -> tuple[str, str]:
    """Open search.html with ``query_string``; return input value and body text.

    When a query is seeded, waits for the indexed target's own text to appear
    on screen (surface-agnostic proof that results rendered). The no-query case
    skips that wait so it can assert emptiness without racing a result that
    never comes.
    """
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()
        page.goto(f"{base}/search.html{query_string}", wait_until="networkidle")
        # The search box renders asynchronously after the surface constructs.
        page.wait_for_selector(_INPUT_SELECTOR, timeout=15000)
        value = page.input_value(_INPUT_SELECTOR)
        if value:
            # Results are "on screen" == the indexed page's title text appears
            # inside the search surface (not the Furo nav, which always lists it).
            page.wait_for_function(
                f"document.querySelector({_MOUNT!r}).innerText.includes({_TARGET_TITLE!r})",
                timeout=15000,
            )
        surface_text = page.inner_text(_MOUNT)
        browser.close()
    return value, surface_text


def test_percent_encoded_query_seeds_results(search_site: str) -> None:
    """The palette's %20-encoded handoff renders results without typing."""
    # encodeURIComponent("modelo 130") -- exactly what fullSearchEntry emits.
    value, body_text = _read_search_page(search_site, "?q=modelo%20130")

    assert value == "modelo 130", f"input not seeded, got {value!r}"
    assert _TARGET_TITLE in body_text, "seeded query rendered no results on screen"


def test_plus_encoded_query_seeds_results(search_site: str) -> None:
    """The reported failure: ``?q=130+10`` -- ``+`` is a space, not a literal.

    ``decodeURIComponent("130+10")`` yields the literal ``"130+10"``, which
    matches nothing. This is the regression the gate exists for.
    """
    value, body_text = _read_search_page(search_site, "?q=130+10")

    assert value == "130 10", f"`+` not decoded as space, got {value!r}"
    assert _TARGET_TITLE in body_text, "+-encoded query rendered no results on screen"


def test_no_query_leaves_the_plain_search_page(search_site: str) -> None:
    """A bare search.html stays the plain "open search page" path."""
    value, body_text = _read_search_page(search_site, "")

    assert value == "", f"input should be empty with no ?q=, got {value!r}"
    assert _TARGET_TITLE not in body_text, "results should not render unprompted"
