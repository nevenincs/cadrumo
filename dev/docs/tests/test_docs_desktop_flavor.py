"""Desktop documentation flavor: the built page, for real.

The desktop application shows the documentation in a frame on its own origin,
under a policy that admits nothing from the network. These gates build a fixture
page through the real ``docs/conf.py`` in both flavors.

* The desktop page references nothing remote, loads the bridge before
  ``cadrumo-docs.js``, and names the application's window origins; the web page
  keeps exactly the scripts it shipped before the flavor existed.
* A translated desktop page loads its plural-form script and runs under the
  window's script policy without a violation.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, override

import pytest

from cadrumo.core.external_constants import OutputLanguage

from ..desktop_palette import theme_variables
from ..shared_page_assets import CHROME_STRINGS_GLOBAL, CHROME_STRINGS_SCRIPT, THEME_VARIABLES_STYLESHEET
from ..site_chrome import site_chrome
from ._docs_desktop_support import DOCS, build_fixture_site, built_site
from ._http_serve_support import serve_directory

pytestmark = [pytest.mark.integration, pytest.mark.hex_core, pytest.mark.docs]

#: The scripts the web flavor renders on this page, in order: what it shipped
#: before the desktop flavor existed, and the root's chrome strings ahead of the
#: page script that reads them. The web flavor must keep shipping exactly these.
_WEB_SCRIPTS = [
    "_static/jquery.js",
    "_static/_sphinx_javascript_frameworks_compat.js",
    "_static/documentation_options.js",
    "_static/doctools.js",
    "_static/sphinx_highlight.js",
    "_static/scripts/furo.js",
    "_static/clipboard.min.js",
    "_static/copybutton.js",
    "_static/js/hoverxref.js",
    "_static/js/tooltipster.bundle.min.js",
    "_static/js/micromodal.min.js",
    "_static/design-tabs.js",
    "https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js",
    "_static/cadrumo-chrome-strings.js",
    "_static/cadrumo-docs.js",
]


def _script_tags(page: str) -> list[dict[str, str]]:
    """Return every ``<script src=...>`` element's attributes, in document order."""
    from html.parser import HTMLParser

    tags: list[dict[str, str]] = []

    class _Collector(HTMLParser):
        @override
        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            if tag == "script":
                values = {name: value or "" for name, value in attrs}
                if "src" in values:
                    tags.append(values)

    _Collector().feed(page)
    return tags


def _loaded_resource_urls(page: str) -> list[str]:
    """Return the URL of every element the browser fetches on load, excluding anchors."""
    from html.parser import HTMLParser

    urls: list[str] = []

    class _Collector(HTMLParser):
        @override
        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            values = {name: value or "" for name, value in attrs}
            if tag in {"script", "img", "iframe", "source", "audio", "video", "embed"} and bool(values.get("src")):
                urls.append(values["src"])
            elif tag == "link" and bool(values.get("href")):
                urls.append(values["href"])
            elif tag == "object" and bool(values.get("data")):
                urls.append(values["data"])

    _Collector().feed(page)
    return urls


def _without_version(src: str) -> str:
    return src.split("?", 1)[0]


@pytest.fixture(scope="module")
def flavor_sites(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    """The fixture site built once per flavor with the default configuration."""
    return {
        "web": built_site(tmp_path_factory.mktemp("web-flavor")),
        "desktop": built_site(tmp_path_factory.mktemp("desktop-flavor"), CADRUMO_DOCS_FLAVOR="desktop"),
    }


@pytest.fixture(scope="module")
def flavor_pages(flavor_sites: dict[str, Path]) -> dict[str, str]:
    """The fixture page of each flavor's site."""
    return {flavor: (site / "fixture.html").read_text(encoding="utf-8") for flavor, site in flavor_sites.items()}


def test_desktop_page_loads_nothing_remote(flavor_pages: dict[str, str]) -> None:
    """No script, stylesheet, image or frame on the desktop page comes from the network."""
    urls = _loaded_resource_urls(flavor_pages["desktop"])
    assert urls, "the parser found no loaded resource at all; the check would pass vacuously"
    remote = [url for url in urls if url.lower().startswith(("http:", "https:", "//"))]
    assert remote == []
    sources = [_without_version(tag["src"]) for tag in _script_tags(flavor_pages["desktop"])]
    assert "_static/js/hoverxref.js" not in sources
    assert "_static/jquery.js" not in sources


def test_desktop_page_loads_the_bridge_before_the_page_script(flavor_pages: dict[str, str]) -> None:
    """The bridge is a plain classic script ahead of ``cadrumo-docs.js`` and names no origin itself."""
    tags = _script_tags(flavor_pages["desktop"])
    sources = [_without_version(tag["src"]) for tag in tags]
    bridge = sources.index("_static/cadrumo-desktop-bridge.js")
    assert bridge < sources.index("_static/cadrumo-docs.js")
    assert set(tags[bridge]) == {"src"}


def test_web_page_keeps_its_scripts(flavor_pages: dict[str, str]) -> None:
    """The published flavor still ships the scripts it did before, and no bridge."""
    sources = [_without_version(tag["src"]) for tag in _script_tags(flavor_pages["web"])]
    assert sources == _WEB_SCRIPTS


@pytest.mark.parametrize("flavor", ["web", "desktop"])
def test_theme_variables_are_one_stylesheet_not_a_block_in_every_page(
    flavor_sites: dict[str, Path], flavor_pages: dict[str, str], flavor: str
) -> None:
    """Every variable ``docs/conf.py`` sets reaches the page through one linked sheet, last in the cascade."""
    page = flavor_pages[flavor]
    head = page[: page.index("</head>")]
    assert "<style" not in head, "the head still declares styles inline"
    sheets = [_without_version(url) for url in _loaded_resource_urls(head) if ".css" in url]
    assert sheets[-1] == f"_static/{THEME_VARIABLES_STYLESHEET}", sheets
    light_rule, print_guard, dark_rule, dark_preference_rule, closing = (
        (flavor_sites[flavor] / "_static" / THEME_VARIABLES_STYLESHEET).read_text(encoding="utf-8").splitlines()
    )
    assert (print_guard, closing) == ("@media not print{", "}")
    assert light_rule.startswith("body{")
    assert dark_rule.startswith('body[data-theme="dark"]{')
    assert dark_preference_rule.startswith('@media (prefers-color-scheme:dark){body:not([data-theme="light"]){')
    expected = theme_variables((DOCS / "conf.py").read_text(encoding="utf-8"))
    assert expected.light and expected.dark, "the configuration declares no theme variable; the check would be vacuous"
    for rule, variables in (
        (light_rule, expected.light),
        (dark_rule, expected.dark),
        (dark_preference_rule, expected.dark),
    ):
        missing = [name for name, value in variables.items() if f"--{name}:{value};" not in rule]
        assert missing == []
        assert "--color-code-background:" in rule
        assert "--color-code-foreground:" in rule


@pytest.mark.parametrize("flavor", ["web", "desktop"])
def test_chrome_strings_are_published_once_ahead_of_the_page_script(
    flavor_sites: dict[str, Path], flavor_pages: dict[str, str], flavor: str
) -> None:
    """The root's chrome strings are one script the page loads, not a payload inside it."""
    page = flavor_pages[flavor]
    assert "cadrumo-chrome-strings" not in page.replace(f"_static/{CHROME_STRINGS_SCRIPT}", "")
    sources = [_without_version(tag["src"]) for tag in _script_tags(page)]
    assert sources.index(f"_static/{CHROME_STRINGS_SCRIPT}") < sources.index("_static/cadrumo-docs.js")
    script = (flavor_sites[flavor] / "_static" / CHROME_STRINGS_SCRIPT).read_text(encoding="utf-8")
    prefix, suffix = f"window.{CHROME_STRINGS_GLOBAL}=", ";\n"
    assert script.startswith(prefix)
    assert script.endswith(suffix)
    assert json.loads(script[len(prefix) : -len(suffix)]) == site_chrome(OutputLanguage.EN, language_endonym="English")


def test_only_the_published_flavor_describes_its_pages_to_link_previews(flavor_pages: dict[str, str]) -> None:
    """A packaged page has no address to share, so it carries no Open Graph tag."""
    assert 'property="og:' in flavor_pages["web"]
    assert 'property="og:' not in flavor_pages["desktop"]


@pytest.mark.parametrize("flavor", ["web", "desktop"])
def test_a_site_carries_its_search_page_and_none_of_the_unread_build_products(
    flavor_sites: dict[str, Path], flavor: str
) -> None:
    """Search is Pagefind and sources are linked in the repository; Sphinx's own copies are not built."""
    site = flavor_sites[flavor]
    assert 'id="pagefind-search"' in (site / "search.html").read_text(encoding="utf-8")
    assert not (site / "searchindex.js").exists()
    assert not [path for path in (site / "_sources").rglob("*") if path.is_file()]


#: The head declaration the search controller reads to place a page in its site.
_SITE_PREFIX_META = 'name="cadrumo-docs-site-prefix" content="{prefix}"'


@pytest.mark.parametrize("flavor", ["web", "desktop"])
def test_a_root_that_is_the_whole_site_declares_no_prefix(flavor_pages: dict[str, str], flavor: str) -> None:
    """Every built page declares where its root sits in the served site.

    The site carries ONE search index, at the apex above the language roots, so
    the controller cannot find it or open a shared result inside the right root
    without knowing how far back the apex is. The default build is a root that
    IS the whole site, which declares an empty prefix -- declared rather than
    absent, because an absent declaration and an apex root would then read the
    same, and the first is a misconfiguration.
    """
    assert _SITE_PREFIX_META.format(prefix="") in flavor_pages[flavor]


def test_a_root_under_a_directory_declares_its_directory(tmp_path: Path) -> None:
    """A root the layout nests carries that one segment into every page's head.

    This is the only link in the chain from the build's declared layout to the
    reader's resolved address that a page itself can show, so it is read off a
    real build through the real templates rather than from the context key.
    """
    page = (built_site(tmp_path, CADRUMO_DOCS_SITE_PREFIX="en") / "fixture.html").read_text(encoding="utf-8")

    assert _SITE_PREFIX_META.format(prefix="en/") in page


def test_configuration_refuses_an_unknown_flavor(tmp_path: Path) -> None:
    """``docs/conf.py`` fails the build rather than guess a flavor."""
    _, result = build_fixture_site(tmp_path, CADRUMO_DOCS_FLAVOR="mobile")
    assert result.returncode != 0
    assert "CADRUMO_DOCS_FLAVOR must be 'web' or 'desktop'" in result.stdout + result.stderr


# ── A translated page under the window's script policy ─────────────────────

#: The script directive of the policy the application serves every documentation
#: response under (``content_security_policy`` in the shell's ``docs/policy.rs``),
#: less the digests of inline scripts, which the application computes per page.
#: The directives beside it in the test's policy are that function's, too.
_SCRIPT_POLICY = "script-src 'self' 'wasm-unsafe-eval'"
_PLURAL_SCRIPT = "_static/cadrumo-plural-expression.js"


def _inline_script_digests(page: str) -> str:
    """Return the policy source list entries admitting the page's own inline scripts."""
    import base64
    import hashlib
    import re

    bodies = re.findall(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", page, flags=re.DOTALL)
    return "".join(
        f" 'sha256-{base64.b64encode(hashlib.sha256(body.encode()).digest()).decode()}'" for body in bodies if body
    )


@pytest.fixture(scope="module")
def spanish_desktop_site(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The fixture page built in Spanish for the desktop flavor, which loads Sphinx's ``translations.js``."""
    return built_site(
        tmp_path_factory.mktemp("spanish-desktop"),
        CADRUMO_DOCS_FLAVOR="desktop",
        CADRUMO_DOCS_LANGUAGE="es",
    )


def _load_under_script_policy(
    site: Path, *, replace: dict[str, bytes] | None = None
) -> tuple[list[str], list[str], Any]:
    """Open the page under the application's script policy; return its errors, violations and plural form.

    ``replace`` serves other bytes for the named site files, for the control
    that removes the fix.
    """
    from playwright.sync_api import sync_playwright

    page_text = (site / "fixture.html").read_text(encoding="utf-8")
    policy = (
        f"default-src 'self'; {_SCRIPT_POLICY}{_inline_script_digests(page_text)}; worker-src 'self'; "
        "style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; "
        "object-src 'none'; base-uri 'self'; form-action 'self'"
    )
    with serve_directory(site) as (_, port), sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page()
            errors: list[str] = []
            page.on("pageerror", lambda error: errors.append(error.message))

            def _serve(route: Any) -> None:
                name = route.request.url.removeprefix(f"http://127.0.0.1:{port}/").split("?", 1)[0]
                if replace is not None and name in replace:
                    route.fulfill(body=replace[name], content_type="text/javascript")
                    return
                response = route.fetch()
                headers = dict(response.headers)
                if name == "fixture.html":
                    headers["content-security-policy"] = policy
                route.fulfill(response=response, headers=headers)

            page.route(f"http://127.0.0.1:{port}/**", _serve)
            page.add_init_script(
                "window.__violations = [];"
                "document.addEventListener('securitypolicyviolation', (event) =>"
                " window.__violations.push(event.violatedDirective + ' ' + event.sourceFile));"
            )
            page.goto(f"http://127.0.0.1:{port}/fixture.html", wait_until="load")
            violations = list(page.evaluate("window.__violations"))
            plural = page.evaluate(
                "[Documentation.LOCALE, typeof Documentation.PLURAL_EXPR === 'function'"
                " ? [0, 1, 2, 5, 1000000].map((n) => Documentation.PLURAL_EXPR(n)) : null]"
            )
            return errors, violations, plural
        finally:
            browser.close()


def test_translated_desktop_page_loads_the_plural_form_script_before_the_catalog(
    spanish_desktop_site: Path,
) -> None:
    """The evaluator replaces ``addTranslations`` after Sphinx defines it and before ``translations.js`` calls it."""
    page = (spanish_desktop_site / "fixture.html").read_text(encoding="utf-8")
    sources = [_without_version(tag["src"]) for tag in _script_tags(page)]
    assert "_static/translations.js" in sources
    sequence = [sources.index(name) for name in ("_static/doctools.js", _PLURAL_SCRIPT, "_static/translations.js")]
    assert sequence == sorted(sequence)


def test_translated_desktop_page_runs_under_the_script_policy_without_a_violation(
    spanish_desktop_site: Path,
) -> None:
    """Under a script policy that refuses string evaluation, the Spanish page loads its catalog cleanly."""
    errors, violations, (locale, forms) = _load_under_script_policy(spanish_desktop_site)
    assert errors == []
    assert violations == []
    assert locale == "es"
    # Spanish: one, then the million-multiple form, then every other count.
    assert forms == [2, 0, 2, 2, 1]


def test_the_policy_gate_detects_sphinx_building_a_function_from_the_plural_expression(
    spanish_desktop_site: Path,
) -> None:
    """Without the evaluator the same page raises the policy's EvalError, so the gate above can fail."""
    errors, violations, _ = _load_under_script_policy(spanish_desktop_site, replace={_PLURAL_SCRIPT: b""})
    assert any("unsafe-eval" in error for error in errors)
    assert any(violation.startswith("script-src") for violation in violations)
