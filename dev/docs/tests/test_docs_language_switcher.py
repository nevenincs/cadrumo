"""Language-switcher rendering and configuration contracts.

The header language switcher (:mod:`dev.docs.language_switcher`, placed by
``docs/_templates/cadrumo-language-switcher.html``) is a native
``<details>/<summary>`` dropdown linking every page to its counterpart under
each per-language deploy root. These gates prove, with a real Furo build (no
mocks), that the switcher computes the correct relative hrefs in each of the two
layouts the product publishes, that the closed state keeps a fixed footprint
(current language code only, so the header cannot overflow on narrow viewports),
and that ``docs/conf.py`` populates the switcher context from the single
``OutputLanguage`` authority and the single layout authority.

The two layouts differ in where the roots sit, and the switcher's links are
relative, so each layout has its own expected hrefs. The desktop package serves
one language at its apex and the rest under their own code; the website serves
every language under its own code and nothing at the apex. Both are stated here
by hand, from a page at a root and from a nested page, because a switcher
assuming one layout writes links into nothing in the other.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from cadrumo.core.external_constants import OutputLanguage
from dev._paths import REPO_ROOT

from ..language_switcher import (
    carries_switcher,
    page_in_other_roots,
    switcher_markup,
    unresolved_cross_root_links,
)
from ..site_chrome import site_chrome

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]

_REPO_ROOT = REPO_ROOT
_DOCS = _REPO_ROOT / "docs"
_TEMPLATES = _DOCS / "_templates"

_LANGUAGE_LABELS = {"en": "English", "es": "Español", "ca": "Català", "hu": "Magyar"}

#: Where each root is served in the desktop package's layout: English at the
#: apex of the site, every other language in a directory of its own.
_APEX_LAYOUT = {"en": "", "es": "es/", "ca": "ca/", "hu": "hu/"}

#: Where each root is served in the website's layout: every language under its
#: own code, and no root at the apex.
_PER_LANGUAGE_LAYOUT = {"en": "en/", "es": "es/", "ca": "ca/", "hu": "hu/"}


#: The pages only the English root publishes, written as the production
#: configuration writes them.
_ENGLISH_ONLY_PAGES = ("api/**", "_modules/**", "technical/**", "py-modindex")


def _switcher_context(language: str, prefixes: dict[str, str]) -> dict[str, object]:
    """Return the switcher html_context for one build language in one layout."""
    order = ["en", *[member.value for member in OutputLanguage if member is not OutputLanguage.EN]]
    return {
        "cadrumo_docs_site_prefixes": prefixes,
        "cadrumo_docs_english_only_pages": _ENGLISH_ONLY_PAGES,
        "cadrumo_docs_languages": [{"code": code, "label": _LANGUAGE_LABELS[code]} for code in order],
        # The switcher's accessible name is resolved chrome, so the real mapping
        # the build hands the template is supplied here rather than a stub.
        "cadrumo_chrome": site_chrome(OutputLanguage(language), language_endonym=_LANGUAGE_LABELS[language]),
    }


def _build_switcher_site(tmp_path: Path, language: str, prefixes: dict[str, str]) -> dict[str, str]:
    """Build a three-page Furo site with the real switcher template; return each page's HTML.

    A page at the root and a page one directory down, because the links are
    relative to the page carrying them: the two resolve the same counterpart
    through different paths, and only one of them would catch a switcher that
    counted the wrong number of directories. And a page of the API reference,
    which no other language's root holds.
    """
    site = tmp_path / "site"
    (site / "how-to").mkdir(parents=True)
    (site / "api").mkdir()
    context = _switcher_context(language, prefixes)
    conf = (
        "import sys\n"
        f"sys.path.insert(0, r'{_REPO_ROOT}')\n"
        'extensions = ["myst_parser"]\n'
        'html_theme = "furo"\n'
        f"templates_path = [r'{_TEMPLATES}']\n"
        # The custom cadrumo header (which hosts the switcher) lives in Furo's
        # announcement block, which Furo only emits when an announcement is set -
        # exactly as the production docs config sets it.
        'html_theme_options = {"announcement": "x"}\n'
        f'language = "{language}"\n'
        f"html_context = {context!r}\n"
        # The element is built by the module that owns it, registered exactly as
        # the production configuration registers it, so the build under test
        # exercises the shipped code and not a copy of it. The shared base
        # template asks for the interface-strings tag too, so the module that
        # answers it is registered as well: the template is the shipped one.
        "from dev.docs.language_switcher import register as _switcher\n"
        "from dev.docs.translations_js import register as _translations_js\n"
        "def setup(app):\n"
        "    _switcher(app)\n"
        "    _translations_js(app)\n"
    )
    (site / "conf.py").write_text(conf, encoding="utf-8")
    (site / "index.md").write_text("# Home\n\n```{toctree}\nhow-to/quickstart\napi/ledger\n```\n", encoding="utf-8")
    (site / "how-to" / "quickstart.md").write_text("# Quickstart\n\nBody text.\n", encoding="utf-8")
    (site / "api" / "ledger.md").write_text("# Ledger module\n\nReference text.\n", encoding="utf-8")
    out = tmp_path / "out"
    result = subprocess.run(
        [sys.executable, "-m", "sphinx", "-b", "html", "-j", "1", str(site), str(out)],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return {
        "index.html": (out / "index.html").read_text(encoding="utf-8"),
        "how-to/quickstart.html": (out / "how-to" / "quickstart.html").read_text(encoding="utf-8"),
        "api/ledger.html": (out / "api" / "ledger.html").read_text(encoding="utf-8"),
    }


def _switcher_block(html: str) -> str:
    """Return the switcher's ``<details>`` dropdown block from the rendered header."""
    match = re.search(r'<details class="cadrumo-header-lang"[^>]*>.*?</details>', html, re.DOTALL)
    assert match is not None, "language switcher <details> dropdown is absent from the rendered header"
    return match.group(0)


def _switcher_summary(html: str) -> str:
    """Return the switcher's ``<summary>`` (the closed-state trigger)."""
    match = re.search(r"<summary.*?</summary>", _switcher_block(html), re.DOTALL)
    assert match is not None, "language switcher <summary> is absent"
    return match.group(0)


def _switcher_hrefs(html: str) -> dict[str, str]:
    """Extract the dropdown menu's per-language option hrefs keyed by BCP-47 code."""
    hrefs: dict[str, str] = {}
    for match in re.finditer(
        r'<a class="cadrumo-header-lang-item" href="([^"]+)"[^>]*lang="([a-z]+)"', _switcher_block(html)
    ):
        hrefs[match.group(2)] = match.group(1)
    return hrefs


def _assert_dropdown_shape(html: str, language: str) -> None:
    """Closed state shows only the current language code; the open menu lists every language."""
    summary = _switcher_summary(html)
    # Fixed-footprint trigger: the current code, no anchors, no other language.
    assert f'lang="{language}">{language.upper()}</span>' in summary
    # The trigger's accessible name is this root's own chrome, not English.
    accessible_name = re.search(r'<summary[^>]*aria-label="([^"]*)"', summary)
    assert accessible_name is not None, "the switcher trigger carries no accessible name"
    expected_chrome = site_chrome(OutputLanguage(language), language_endonym=_LANGUAGE_LABELS[language])
    assert accessible_name.group(1) == expected_chrome["aria_language"]
    assert "<a" not in summary
    assert all(f'lang="{other}"' not in summary for other in _LANGUAGE_LABELS if other != language)
    # Open panel: every language present, the current one a non-link current marker.
    block = _switcher_block(html)
    menu_langs = set(re.findall(r'class="cadrumo-header-lang-item[^"]*"[^>]*\blang="([a-z]+)"', block))
    assert menu_langs == set(_LANGUAGE_LABELS)
    assert f'aria-current="true" lang="{language}"' in block


@pytest.mark.parametrize(
    ("layout", "language", "expected"),
    [
        # The desktop package's layout, from the root English serves at the
        # site's apex: each localized counterpart is one level up from the page
        # and then into its own segment.
        (
            _APEX_LAYOUT,
            "en",
            {
                "index.html": {"es": "es/index.html", "ca": "ca/index.html", "hu": "hu/index.html"},
                "how-to/quickstart.html": {
                    "es": "../es/how-to/quickstart.html",
                    "ca": "../ca/how-to/quickstart.html",
                    "hu": "../hu/how-to/quickstart.html",
                },
                "api/ledger.html": {"es": "../es/index.html", "ca": "../ca/index.html", "hu": "../hu/index.html"},
            },
        ),
        # The same layout from a root in a directory of its own: the base is one
        # level above this root, where English is served and the other segments
        # sit.
        (
            _APEX_LAYOUT,
            "es",
            {
                "index.html": {"en": "../index.html", "ca": "../ca/index.html", "hu": "../hu/index.html"},
                "how-to/quickstart.html": {
                    "en": "../../how-to/quickstart.html",
                    "ca": "../../ca/how-to/quickstart.html",
                    "hu": "../../hu/how-to/quickstart.html",
                },
                "api/ledger.html": {"en": "../../index.html", "ca": "../../ca/index.html", "hu": "../../hu/index.html"},
            },
        ),
        # The website's layout, where English is a directory like every other:
        # the English root no longer stands at the base, so every link walks out
        # of it first and the apex holds no page to link to at all.
        (
            _PER_LANGUAGE_LAYOUT,
            "en",
            {
                "index.html": {"es": "../es/index.html", "ca": "../ca/index.html", "hu": "../hu/index.html"},
                "how-to/quickstart.html": {
                    "es": "../../es/how-to/quickstart.html",
                    "ca": "../../ca/how-to/quickstart.html",
                    "hu": "../../hu/how-to/quickstart.html",
                },
                # What the published English root really carries: an API page,
                # whose Spanish link opens the Spanish entry page, because the
                # Spanish root holds no API reference to open instead.
                "api/ledger.html": {
                    "es": "../../es/index.html",
                    "ca": "../../ca/index.html",
                    "hu": "../../hu/index.html",
                },
            },
        ),
        (
            _PER_LANGUAGE_LAYOUT,
            "es",
            {
                "index.html": {"en": "../en/index.html", "ca": "../ca/index.html", "hu": "../hu/index.html"},
                "how-to/quickstart.html": {
                    "en": "../../en/how-to/quickstart.html",
                    "ca": "../../ca/how-to/quickstart.html",
                    "hu": "../../hu/how-to/quickstart.html",
                },
                "api/ledger.html": {
                    "en": "../../en/index.html",
                    "ca": "../../ca/index.html",
                    "hu": "../../hu/index.html",
                },
            },
        ),
    ],
    ids=["apex-layout-en", "apex-layout-es", "per-language-layout-en", "per-language-layout-es"],
)
def test_the_switcher_links_each_root_where_the_layout_serves_it(
    tmp_path: Path,
    layout: dict[str, str],
    language: str,
    expected: dict[str, dict[str, str]],
) -> None:
    """Every link resolves to the counterpart page in the layout being built.

    Stated by hand for both layouts and for a page at a root as well as a
    nested one. The hrefs are relative, so the only thing that makes them right
    is how many directories this root sits in and which directory each other
    root sits in -- both facts of the layout, neither of the language.
    """
    pages = _build_switcher_site(tmp_path, language, layout)
    assert {page: _switcher_hrefs(html) for page, html in pages.items()} == expected
    for html in pages.values():
        _assert_dropdown_shape(html, language)


@pytest.mark.parametrize(
    ("pagename", "opened"),
    [
        ("how-to/quickstart", "how-to/quickstart"),
        ("index", "index"),
        ("api/cadrumo.core.casilla_id", "index"),
        ("api/index", "index"),
        ("_modules/cadrumo/core/casilla_id", "index"),
        ("technical/architecture/overview", "index"),
        ("py-modindex", "index"),
        # A page that merely starts with the same letters is everyone's page.
        ("apidocs-notes", "apidocs-notes"),
        ("genindex", "genindex"),
    ],
)
def test_a_page_only_the_english_root_publishes_opens_the_entry_page_elsewhere(pagename: str, opened: str) -> None:
    """The API reference and the technical collection exist in English only."""
    assert page_in_other_roots(pagename, entry_page="index", english_only=_ENGLISH_ONLY_PAGES) == opened


def test_conf_names_the_pages_only_the_english_root_publishes() -> None:
    """The switcher reads the same list the user scope leaves out, plus the module index."""
    context = _conf_switcher_context("en")

    assert context["english_only"] == ["api/**", "_modules/**", "technical/**", "py-modindex"]


def _conf_switcher_context(
    language: str,
    *,
    site_prefix: str | None = None,
    base_url: str | None = None,
) -> dict[str, object]:
    """Evaluate docs/conf.py under one build configuration and return its switcher context.

    ``site_prefix`` is the root's own directory in the layout being produced and
    ``base_url`` the address the site is served from; together they are what
    says which layout this build is one root of.
    """
    conf = _DOCS / "conf.py"
    script = (
        "import json, runpy;"
        f"ns = runpy.run_path(r'{conf}');"
        "ctx = ns['html_context'];"
        "print('SWITCHER=' + json.dumps({"
        "'language': ctx['language'],"
        "'prefixes': ctx['cadrumo_docs_site_prefixes'],"
        "'english_only': list(ctx['cadrumo_docs_english_only_pages']),"
        "'languages': ctx['cadrumo_docs_languages']}))"
    )
    with tempfile.TemporaryDirectory(prefix="cadrumo-switcher-ctx-") as storage_root:
        env = {
            **os.environ,
            "CADRUMO_DOCS_PROJECT_ROOT": str(_REPO_ROOT),
            "CADRUMO_DOCS_LANGUAGE": language,
            "CADRUMO_LOCAL_STORAGE_ROOT": storage_root,
        }
        for key, value in (("CADRUMO_DOCS_SITE_PREFIX", site_prefix), ("CADRUMO_DOCS_BASE_URL", base_url)):
            if value is None:
                env.pop(key, None)
            else:
                env[key] = value
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
    assert result.returncode == 0, result.stdout + result.stderr
    line = next(row for row in result.stdout.splitlines() if row.startswith("SWITCHER="))
    payload = json.loads(line[len("SWITCHER=") :])
    if not isinstance(payload, dict) or not all(isinstance(key, str) for key in payload):
        raise AssertionError("switcher context must contain a JSON object with string keys")
    return {key: value for key, value in payload.items() if isinstance(key, str)}


def test_conf_populates_switcher_context_from_output_language() -> None:
    """conf.py builds the switcher context from OutputLanguage: English first, then targets, with endonyms."""
    context = _conf_switcher_context("ca")
    assert context["language"] == "ca"
    raw_languages = context.get("languages")
    assert isinstance(raw_languages, list)
    languages: list[dict[str, object]] = []
    for raw_entry in raw_languages:
        if not isinstance(raw_entry, dict) or not all(isinstance(key, str) for key in raw_entry):
            raise AssertionError("switcher language entries must be JSON objects with string keys")
        languages.append({key: value for key, value in raw_entry.items() if isinstance(key, str)})
    codes = [entry["code"] for entry in languages]
    assert codes[0] == "en"
    assert set(codes) == {member.value for member in OutputLanguage}
    labels = {entry["code"]: entry["label"] for entry in languages}
    assert labels == _LANGUAGE_LABELS


def test_conf_hands_the_switcher_the_layout_the_build_is_producing() -> None:
    """The switcher links each root where the layout serves it, so conf.py carries the layout.

    The packaged desktop site is compiled in English and has no address of its
    own, so English stands at its apex; the website is served from an address
    of its own and puts every language under its code. Both mappings are stated
    here, because reading them off the authority under test would assert
    nothing.
    """
    assert _conf_switcher_context("en")["prefixes"] == _APEX_LAYOUT
    assert (
        _conf_switcher_context("ca", site_prefix="ca", base_url="https://example.test/docs")["prefixes"]
        == _PER_LANGUAGE_LAYOUT
    )


#: What each root of the site holds, for the resolution gates below: three pages
#: in English, and the two every language publishes in each other root.
_ROOT_FILES = {
    "en": {"index.html", "how-to/quickstart.html", "api/ledger.html"},
    "es": {"index.html", "how-to/quickstart.html"},
    "ca": {"index.html", "how-to/quickstart.html"},
    "hu": {"index.html", "how-to/quickstart.html"},
}

#: Every language the site publishes, as the switcher takes them.
_SWITCHER_LANGUAGES = [{"code": code, "label": label} for code, label in _LANGUAGE_LABELS.items()]


#: The path the site is served under in the gates below, above the language
#: directories: the shape the error page's own absolute links are resolved from.
_SITE_PATH = "/docs"


def _element(
    layout: dict[str, str],
    language: str,
    page: str,
    *,
    pagename: str | None = None,
    root_uri: str | None = None,
) -> str:
    """Return the switcher one page of one root carries, from the real renderer.

    *pagename* overrides the page each other language's link opens, which is
    :func:`page_in_other_roots`' answer by default. *root_uri* overrides the
    path back to this page's own root, which the error page states absolutely.
    """
    docname = page.removesuffix(".html")
    return switcher_markup(
        _SWITCHER_LANGUAGES,
        build_language=language,
        prefixes=layout,
        root_uri=root_uri if root_uri is not None else "../" * docname.count("/"),
        pagename=pagename
        if pagename is not None
        else page_in_other_roots(docname, entry_page="index", english_only=_ENGLISH_ONLY_PAGES),
        aria_label="Language",
        newline="\n",
    )


@pytest.mark.parametrize("layout", [_APEX_LAYOUT, _PER_LANGUAGE_LAYOUT], ids=["apex-layout", "per-language-layout"])
@pytest.mark.parametrize("language", sorted(_ROOT_FILES))
@pytest.mark.parametrize("page", ["index.html", "how-to/quickstart.html"])
def test_every_switcher_link_resolves_to_a_page_the_root_it_names_holds(
    layout: dict[str, str], language: str, page: str
) -> None:
    """The baseline: the real renderer's links all land on a file in the root they name.

    The element comes from the renderer the pages carry and the resolution from
    the checker the compile runs, so neither side is the other's expectation.
    """
    assert (
        unresolved_cross_root_links(
            _element(layout, language, page),
            language=language,
            page=page,
            prefixes=layout,
            files=_ROOT_FILES,
        )
        == []
    )


@pytest.mark.parametrize("layout", [_APEX_LAYOUT, _PER_LANGUAGE_LAYOUT], ids=["apex-layout", "per-language-layout"])
def test_a_link_to_a_page_only_the_english_root_publishes_is_reported(layout: dict[str, str]) -> None:
    """Detector teeth: the defect :func:`page_in_other_roots` exists to prevent.

    An English-only page named in the other roots' links is the exact wrong
    answer, and nothing else notices it: the links are relative, so no build
    warns and a reader finds the 404 page. The element is rendered with that
    substitution suppressed, which is what the switcher wrote before the
    substitution existed.
    """
    found = unresolved_cross_root_links(
        _element(layout, "en", "api/ledger.html", pagename="api/ledger"),
        language="en",
        page="api/ledger.html",
        prefixes=layout,
        files=_ROOT_FILES,
    )

    assert len(found) == 3, found
    assert all("does not hold" in message for message in found), found
    assert any("es/api/ledger.html" in message for message in found), found


def test_a_link_that_climbs_out_of_the_served_site_is_reported() -> None:
    """A link written for a deeper root than the page sits in leaves the site entirely.

    Written by hand, because what produces it is a root_uri and a prefix that
    disagree about how deep the page is -- the defect that put a Spanish link
    relative to the English root rather than to the base above it.
    """
    element = _element(_PER_LANGUAGE_LAYOUT, "en", "index.html", pagename="index").replace("../", "../../")

    found = unresolved_cross_root_links(
        element,
        language="en",
        page="index.html",
        prefixes=_PER_LANGUAGE_LAYOUT,
        files=_ROOT_FILES,
    )

    assert len(found) == 3, found
    assert all("outside the served site" in message for message in found), found


def test_a_link_into_a_language_the_site_publishes_no_root_for_is_reported() -> None:
    """A switcher naming a retired language addresses a directory nothing serves."""
    element = _element(_PER_LANGUAGE_LAYOUT, "en", "index.html").replace('lang="hu"', 'lang="fr"', 1)

    found = unresolved_cross_root_links(
        element,
        language="en",
        page="index.html",
        prefixes=_PER_LANGUAGE_LAYOUT,
        files=_ROOT_FILES,
    )

    assert found == ["en/index.html -> ../hu/index.html: names 'fr', which the site publishes no root for"]


def test_the_error_pages_absolute_links_resolve_from_the_path_the_site_is_served_under() -> None:
    """The error page is served for an address that does not exist, so its links are absolute.

    It therefore states the path the site is served under, which a relative
    link never has to: ``/docs/es/../ca/404.html``. Resolved against the page's
    own directory that address would land outside every root, which is why the
    served path is a fact of the check rather than of the page.
    """
    files = {language: {*pages, "404.html"} for language, pages in _ROOT_FILES.items()}

    assert (
        unresolved_cross_root_links(
            _element(_PER_LANGUAGE_LAYOUT, "es", "404.html", root_uri=f"{_SITE_PATH}/es/"),
            language="es",
            page="404.html",
            prefixes=_PER_LANGUAGE_LAYOUT,
            files=files,
            site_path=_SITE_PATH,
        )
        == []
    )


def test_an_absolute_link_outside_the_path_the_site_is_served_under_is_reported() -> None:
    """An absolute link built from the wrong served path leaves the site entirely.

    Nothing on the page says where the site is served, so a link that states it
    wrongly points at another site's address and resolves to nothing here.
    """
    files = {language: {*pages, "404.html"} for language, pages in _ROOT_FILES.items()}

    found = unresolved_cross_root_links(
        _element(_PER_LANGUAGE_LAYOUT, "es", "404.html", root_uri="/handbook/es/"),
        language="es",
        page="404.html",
        prefixes=_PER_LANGUAGE_LAYOUT,
        files=files,
        site_path=_SITE_PATH,
    )

    assert len(found) == 3, found
    assert all(f"outside the site served at {_SITE_PATH}/" in message for message in found), found


def test_a_recorded_string_is_recognised_as_a_switcher_only_when_it_is_one() -> None:
    """The compile reads only the few strings that carry the element, so it has to know them."""
    assert carries_switcher(_element(_PER_LANGUAGE_LAYOUT, "en", "index.html"))
    assert not carries_switcher('<a class="reference internal" href="../ca/index.html">Català</a>')
