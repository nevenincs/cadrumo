"""The site's ONE search index, over a two-language fixture site, in a browser.

The documentation is built in four languages and the site carries one Pagefind
index for all of them, at the apex above the language roots. That is one
mechanism with five properties a reader depends on, and no earlier gate could
see any of them, because every gate indexed a single root:

1. there is ONE index directory, and no language root holds another;
2. a query from one language's page answers with that language's pages and not
   with another language's;
3. a record every language shares -- a concept, casilla, legal or CLI record --
   is returned from every language;
4. that record opens INSIDE the root being read, so a Spanish reader who picks
   a casilla lands on the Spanish casilla page;
5. the summary rendered on its row is the one in the language being read.

Properties 2 to 5 are behaviour of the shipped search controller, so they are
read from ``docs/_static/cadrumo-docs.js`` driving the real index in a real
browser through ``window.CadrumoDocs.search`` -- the one entry point the Ctrl-K
palette, the inline search page and the desktop frame bridge all answer from.
Asserting them against a re-implementation would prove nothing about what a
reader gets.

The fixture site is hand-written HTML rather than a Sphinx build: what is under
test is the index and the controller, and two Sphinx builds would add ten
minutes to buy page chrome neither reads. The pages carry exactly the three
facts a built page carries -- ``<html lang>``, the theme's ``data-content_root``,
and the build's ``cadrumo-docs-site-prefix`` meta.

The fixture keeps the two layouts the real pipeline keeps apart, because the
whole point of the URL prefixes is that they differ. The index is built over the
roots as a build leaves them, each language its own directory BESIDE the others,
and is written into the apex language's root. The served site is then composed
the way staging composes it, the apex language at the top and the others under
their own directory, and that is what the browser reads. An index built over the
served layout instead would walk the apex pass into every other root.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from pydantic import TypeAdapter

from cadrumo.core.external_constants import OutputLanguage
from dev._paths import REPO_ROOT

from ..pagefind_index import SHARED_INDEX_LANGUAGE, IndexedRoot, build_shared_search_index
from ..pagefind_inject import _inject_records, _Materialised
from ..terminology.search_record import ResultDisplayClass, SearchRecordKind
from ..terminology.unified_record import (
    RankingTier,
    SearchRecord,
    SearchRecordMetadata,
    normalise_display_class_weight,
)
from ._http_serve_support import serve_directory

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

_REPO_ROOT = REPO_ROOT
_DOCS = _REPO_ROOT / "docs"

#: Words present in exactly one place each, so a result set reads unambiguously:
#: no page chrome, nav title or other record carries them.
_APEX_PAGE_WORD = "zzqapexpageonly"
_LOCALIZED_PAGE_WORD = "zzqlocalizedpageonly"
_SHARED_RECORD_WORD = "zzqsharedrecordeverywhere"
#: Words that sit only in what a page record must leave out, and one that sits
#: in recorded text output, which stays searchable.
_NAVIGATION_WORD = "zzqnavigationonly"
_FOOTER_WORD = "zzqfooteronly"
_JSON_OUTPUT_WORD = "zzqjsonoutputonly"
_TEXT_OUTPUT_WORD = "zzqtextoutputonly"

#: The shared record's destination, relative to a language root exactly as the
#: projections emit it: the page exists in every language's root.
_RECORD_TARGET = "_generated/casillas/303.html#casilla-00303"

_SUMMARIES = {
    OutputLanguage.EN: f"{_SHARED_RECORD_WORD} deductible input tax for the quarter",
    OutputLanguage.ES: f"{_SHARED_RECORD_WORD} cuota deducible del trimestre",
}

_PAGE = """<!doctype html>
<html lang="{language}" data-content_root="{content_root}">
<head>
<meta charset="utf-8">
<meta name="cadrumo-docs-site-prefix" content="{prefix}">
<title>{title}</title>
</head>
<body>
<aside class="sidebar-drawer"><a href="{content_root}index.html">{navigation}</a></aside>
<article role="main"><h1>{title}</h1><p>{body}</p>
<pre class="cadrumo-frame-output" data-format="json">{{"field": "{json_output}"}}</pre>
<pre class="cadrumo-frame-output" data-format="text">{text_output}</pre>
</article>
<footer><p>{footer}</p></footer>
<script src="{content_root}_static/cadrumo-docs.js"></script>
</body>
</html>
"""

_DESTINATION_PAGE = """<!doctype html>
<html lang="{language}" data-content_root="../../">
<head><meta charset="utf-8"><title>casillas 303</title></head>
<body><article role="main"><h2 id="casilla-00303">Casilla 00303</h2></article></body>
</html>
"""


def _write_root(root: Path, language: str, prefix: str, token: str) -> None:
    """Write one language root: an entry page, a page one level deep, a destination."""
    root.mkdir(parents=True, exist_ok=True)
    surroundings = {
        "navigation": _NAVIGATION_WORD,
        "footer": _FOOTER_WORD,
        "json_output": _JSON_OUTPUT_WORD,
        "text_output": _TEXT_OUTPUT_WORD,
    }
    (root / "index.html").write_text(
        _PAGE.format(
            language=language, content_root="./", prefix=prefix, title=f"Home {language}", body=token, **surroundings
        ),
        encoding="utf-8",
    )
    deep = root / "how-to"
    deep.mkdir(parents=True, exist_ok=True)
    (deep / "guide.html").write_text(
        _PAGE.format(
            language=language, content_root="../", prefix=prefix, title=f"Guide {language}", body=token, **surroundings
        ),
        encoding="utf-8",
    )
    destination = root / "_generated" / "casillas"
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "303.html").write_text(_DESTINATION_PAGE.format(language=language), encoding="utf-8")


def _shared_record() -> _Materialised:
    """One casilla record carrying both languages' text, as the projections emit it."""
    record = SearchRecord(
        id="casilla-record:sharedindextest",
        kind=SearchRecordKind.CASILLA,
        tier=RankingTier.NAVIGATION,
        title="Modelo 303 · casilla 00303",
        descriptions=dict(_SUMMARIES),
        target=_RECORD_TARGET,
        ranking_weight=normalise_display_class_weight(ResultDisplayClass.CASILLA),
        metadata=SearchRecordMetadata(modelo="303", number="00303"),
    )
    return _Materialised(records=[record], casillas=1)


@pytest.fixture(scope="module")
def shared_index_site(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Build the two roots, index them once, and compose the site that is served.

    Module-scoped: the index write and the Pagefind binary run are the cost
    here, and every assertion below reads the same artefact a reader would.
    """
    work = tmp_path_factory.mktemp("shared-index")
    built = work / "html"
    _write_root(built / "en", "en", "", _APEX_PAGE_WORD)
    _write_root(built / "es", "es", "es/", _LOCALIZED_PAGE_WORD)
    for language in ("en", "es"):
        static = built / language / "_static"
        static.mkdir(parents=True, exist_ok=True)
        (static / "cadrumo-docs.js").write_bytes((_DOCS / "_static" / "cadrumo-docs.js").read_bytes())
    materialised = _shared_record()

    async def inject(index: object) -> None:
        await _inject_records(index, materialised, {})  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]  # reason: pagefind index is dynamically typed

    outcome = build_shared_search_index(
        [
            IndexedRoot(html_root=built / "en", language="en", url_prefix=""),
            IndexedRoot(html_root=built / "es", language="es", url_prefix="es/"),
        ],
        built / "en",
        inject=inject,
    )
    # Six pages read, three per root. The count is what the directory pass READ,
    # so it includes the destination pages, which carry the ignore mark and reach
    # no index entry -- the same arithmetic the generated casilla pages give in
    # production. What landed is asserted on the written index below.
    assert outcome.page_count == 6, outcome

    # Compose the served site as staging does: the apex language at the top,
    # carrying the one index, and the other language under its own directory.
    site = work / "site"
    shutil.copytree(built / "en", site)
    shutil.copytree(built / "es", site / "es")
    return site


def test_the_site_has_exactly_one_index_at_its_apex(shared_index_site: Path) -> None:
    """One index directory, at the apex, and no language root holding another.

    The index is also ONE split rather than one per rendered ``<html lang>``,
    which is what lets a record shared by every language be indexed once: a
    reader's bundle loads a single split, so four splits would need four copies
    of the same record to keep it reachable.
    """
    assert (shared_index_site / "pagefind" / "pagefind-entry.json").is_file()
    assert not (shared_index_site / "es" / "pagefind").exists()

    entry = json.loads((shared_index_site / "pagefind" / "pagefind-entry.json").read_text(encoding="utf-8"))
    assert list(entry["languages"]) == [SHARED_INDEX_LANGUAGE], entry["languages"]
    # Every page of both roots is in that one split.
    assert entry["languages"][SHARED_INDEX_LANGUAGE]["page_count"] == 5, entry


def _search_from(site: Path, page: str, query: str) -> list[dict[str, str]]:
    """Return the shipped controller's ranked rows for ``query``, read in a browser."""
    with serve_directory(site) as (_httpd, port):
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            try:
                browser_page = browser.new_page()
                browser_page.goto(f"http://127.0.0.1:{port}/{page}", wait_until="networkidle")
                rows = browser_page.evaluate(
                    """async (query) => {
                      const rows = await window.CadrumoDocs.search(query);
                      return rows.map((row) => ({
                        title: row.title,
                        href: new URL(row.href, document.baseURI).pathname,
                        excerpt: row.excerpt,
                      }));
                    }""",
                    query,
                )
                return TypeAdapter(list[dict[str, str]]).validate_python(rows, strict=True)
            finally:
                browser.close()


@pytest.mark.parametrize(
    ("page", "own_word", "other_word", "own_pages"),
    [
        ("how-to/guide.html", _APEX_PAGE_WORD, _LOCALIZED_PAGE_WORD, ["/", "/how-to/guide.html"]),
        ("es/how-to/guide.html", _LOCALIZED_PAGE_WORD, _APEX_PAGE_WORD, ["/es/", "/es/how-to/guide.html"]),
    ],
)
def test_a_page_search_answers_in_the_language_being_read(
    shared_index_site: Path,
    page: str,
    own_word: str,
    other_word: str,
    own_pages: list[str],
) -> None:
    """One index, four languages' pages, and a reader who sees only their own.

    The index holds every language's pages, so nothing but the page's own
    ``language`` filter keeps a Spanish reader from being answered with English
    prose. Both directions are read, because a filter applied to one pass only
    would pass the first direction and fail the second.
    """
    own = _search_from(shared_index_site, page, own_word)
    assert sorted(row["href"] for row in own) == own_pages, own

    other = _search_from(shared_index_site, page, other_word)
    assert other == [], other


def test_a_page_is_found_by_what_it_says_and_not_by_what_surrounds_it(shared_index_site: Path) -> None:
    """Navigation, footer and recorded JSON are on the page and out of its record.

    Every page carries the same navigation and footer, so a word in them would
    answer with every page, and a JSON envelope's keys match almost any query.
    Recorded text output is prose a reader searches for, and stays findable.
    """
    for excluded in (_NAVIGATION_WORD, _FOOTER_WORD, _JSON_OUTPUT_WORD):
        assert _search_from(shared_index_site, "how-to/guide.html", excluded) == [], excluded
    found = _search_from(shared_index_site, "how-to/guide.html", _TEXT_OUTPUT_WORD)
    assert sorted(row["href"] for row in found) == ["/", "/how-to/guide.html"], found


@pytest.mark.parametrize(
    ("page", "language", "destination"),
    [
        ("index.html", OutputLanguage.EN, f"/{_RECORD_TARGET.split('#')[0]}"),
        ("how-to/guide.html", OutputLanguage.EN, f"/{_RECORD_TARGET.split('#')[0]}"),
        ("es/index.html", OutputLanguage.ES, f"/es/{_RECORD_TARGET.split('#')[0]}"),
        ("es/how-to/guide.html", OutputLanguage.ES, f"/es/{_RECORD_TARGET.split('#')[0]}"),
    ],
)
def test_a_shared_record_is_returned_in_every_language_and_opens_inside_it(
    shared_index_site: Path,
    page: str,
    language: OutputLanguage,
    destination: str,
) -> None:
    """The one copy of a shared record answers every language, in that language.

    Three properties of the single copy at once, because they are one behaviour:
    it is REACHED from both languages (its filter names them all), it OPENS
    inside the root being read (its target is relative to a language root, and
    the page's own prefix completes it), and it READS in the language being
    read (the row shows that language's summary, chosen by the controller rather
    than fixed when the record was injected).

    Both an entry page and a page one level deep are read per language: the
    destination is resolved against the site apex, so a page at a different
    depth would otherwise be the one that got a broken address.
    """
    rows = _search_from(shared_index_site, page, _SHARED_RECORD_WORD)

    assert len(rows) == 1, rows
    assert rows[0]["href"] == destination, rows[0]
    assert rows[0]["excerpt"] == _SUMMARIES[language], rows[0]
