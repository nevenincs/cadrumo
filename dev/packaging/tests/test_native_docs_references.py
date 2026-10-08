"""Bundled documentation reference gate: remote loads and unserved file types in pages and stylesheets."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dev._paths import REPO_ROOT

from ..native.docs_stage import (
    DocsPackagingError,
    ServedMediaTypes,
    css_references,
    declared_languages,
    scan_page,
    scan_stylesheet,
    served_media_types,
    stage_roots,
    verified_stage,
)
from ..native.layout import load_layout

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

PAGE = """<!doctype html><html><head><link rel="stylesheet" href="_static/site.css"></head>
<body><a href="https://example.org/page.html">external prose link</a><a href="how-to/">section</a></body></html>
"""
STYLESHEET = "body { color: black; }\n"
# Files the documentation scheme answers with 404, as Sphinx and the theme emit them.
UNSERVED = ("_static/readme/demo.gif", "_static/fonts/Mono.ttf", "_static/LICENSE.txt", "_static/site.js.map")


def _media_types() -> ServedMediaTypes:
    return served_media_types(load_layout()["user_docs"])


def _refused(page: str) -> list[tuple[str, int]]:
    return [(refusal.reason, refusal.line) for refusal in scan_page(page, _media_types()).refused]


def _refused_stylesheet(text: str) -> list[tuple[str, int]]:
    return [(refusal.reason, refusal.line) for refusal in scan_stylesheet(text, _media_types())]


def _build(tmp_path: Path, files: dict[str, str] | None = None) -> Path:
    paths = {
        "user_docs_build": "user-docs/build",
        "user_docs_work": "user-docs/work",
        "user_docs_stage": "user-docs/stage",
    }
    (tmp_path / "build-paths.json").write_text(json.dumps({"paths": paths}), encoding="utf-8")
    for index, language in enumerate(declared_languages(load_layout())):
        root = tmp_path / "user-docs/build/html" / language
        # The site has one search index, in the apex language's root.
        search = {"pagefind/pagefind.js": "export {};", "pagefind/pagefind-entry.json": "{}"} if index == 0 else {}
        contents = {
            "index.html": PAGE,
            "how-to/index.html": PAGE,
            **search,
            "_static/site.css": STYLESHEET,
            **{name: "unserved" for name in UNSERVED},
            "objects.inv": "inventory",
            **(files if files is not None and index == 0 else {}),
        }
        for name, content in contents.items():
            (root / name).parent.mkdir(parents=True, exist_ok=True)
            (root / name).write_text(content, encoding="utf-8")
    return tmp_path


def _staging_refusal(tmp_path: Path, files: dict[str, str]) -> str:
    build = _build(tmp_path, files)
    with pytest.raises(DocsPackagingError) as refusal:
        stage_roots(build)
    assert not (build / "user-docs/stage/ready").exists()
    return str(refusal.value)


# One falsifier per vector the gate covers; each names the refusal and its line.
@pytest.mark.parametrize(
    ("page", "expected"),
    [
        pytest.param(
            '<div>\n<p style="color: red;\n background: url(https://cdn.example/a.png)">x</p></div>',
            ("<p style> url() https://cdn.example/a.png", 3),
            id="style-attribute",
        ),
        pytest.param(
            "<head>\n<style>\nbody { }\n@import '//fonts.example/a.css';\n</style></head>",
            ("<style> @import //fonts.example/a.css", 4),
            id="style-element",
        ),
        pytest.param(
            '<head>\n<meta http-equiv="Refresh" content="0; URL=\'https://example.org/moved\'"></head>',
            ("<meta refresh> https://example.org/moved", 2),
            id="meta-refresh",
        ),
        pytest.param(
            '<form method="get" action="https://search.example/q"><input name="q"></form>',
            ("<form action> https://search.example/q", 1),
            id="form-action",
        ),
        pytest.param(
            '<form action="search.html"><button formaction="HTTPS://search.example/q">go</button></form>',
            ("<button formaction> HTTPS://search.example/q", 1),
            id="button-formaction",
        ),
        pytest.param(
            '<link rel="preload" as="image" imagesrcset="_static/a.png 1x, https://cdn.example/a2.png 2x">',
            ("<link imagesrcset> https://cdn.example/a2.png", 1),
            id="link-imagesrcset",
        ),
        pytest.param(
            '<img src="_static/a.png" srcset="data:image/png;base64,AAAA,BBBB 1x,//cdn.example/b.png 2x">',
            ("<img srcset> //cdn.example/b.png", 1),
            id="img-srcset-after-a-comma-bearing-data-url",
        ),
        pytest.param(
            '<script src="\\\\cdn.example/a.js"></script>',
            ("<script src> \\\\cdn.example/a.js", 1),
            id="backslash-protocol-relative",
        ),
        pytest.param(
            '<img src="ht&#9;tps://cdn.example/a.png">',
            ("<img src> ht\ttps://cdn.example/a.png", 1),
            id="tab-inside-the-scheme",
        ),
    ],
)
def test_page_gate_refuses_each_remote_vector_with_its_line(page: str, expected: tuple[str, int]) -> None:
    assert _refused(page) == [expected]


@pytest.mark.parametrize(
    ("stylesheet", "expected"),
    [
        pytest.param(
            "a {}\nbody { background: url( https://cdn.example/a.png ) }",
            ("url() https://cdn.example/a.png", 2),
            id="unquoted-url",
        ),
        pytest.param(
            "body {\n  background: url('//cdn.example/a.png');\n}", ("url() //cdn.example/a.png", 2), id="quoted-url"
        ),
        pytest.param(
            '@import "https://fonts.example/a.css" screen;',
            ("@import https://fonts.example/a.css", 1),
            id="import-string",
        ),
        pytest.param(
            "@import url(https://fonts.example/a.css);", ("@import https://fonts.example/a.css", 1), id="import-url"
        ),
        pytest.param(
            'a { background: image-set("a.png" 1x, "https://cdn.example/a2.png" 2x) }',
            ("image-set() https://cdn.example/a2.png", 1),
            id="image-set-string",
        ),
        pytest.param(
            "a { background: \\75 rl(https://cdn.example/escaped.png) }",
            ("url() https://cdn.example/escaped.png", 1),
            id="escaped-function-name",
        ),
    ],
)
def test_stylesheet_gate_refuses_each_remote_vector_with_its_line(stylesheet: str, expected: tuple[str, int]) -> None:
    assert _refused_stylesheet(stylesheet) == [expected]


def test_stylesheet_tokens_that_load_nothing_are_not_references() -> None:
    stylesheet = """/* url(https://cdn.example/commented.png) @import "https://x.example/c.css"; */
@namespace svg url(http://www.w3.org/2000/svg);
@font-face { font-family: Mono; src: local("https://not-a-url"), url(_static/fonts/mono.woff2) format("woff2"); }
a::after { content: "url(https://cdn.example/in-a-string.png)"; }
a { background: url('data:image/svg+xml;charset=utf-8,<svg xmlns="http://www.w3.org/2000/svg"></svg>'); }
b { background: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg'/%3E") }
"""
    assert [(syntax, url) for syntax, url, _ in css_references(stylesheet)] == [
        ("url()", "_static/fonts/mono.woff2"),
        ("url()", """data:image/svg+xml;charset=utf-8,<svg xmlns="http://www.w3.org/2000/svg"></svg>"""),
        ("url()", "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg'/%3E"),
    ]
    assert _refused_stylesheet(stylesheet) == []


def test_followed_links_may_leave_the_package_but_loads_may_not() -> None:
    assert _refused('<a href="https://example.org/">x</a><area href="//example.org/">') == []
    assert _refused('<img src="https://example.org/a.png">') == [("<img src> https://example.org/a.png", 1)]


@pytest.mark.parametrize(
    ("page", "expected"),
    [
        ('<img src="_static/readme/demo.gif">', "<img src> _static/readme/demo.gif"),
        ('<a href="../objects.inv#x">inventory</a>', "<a href> ../objects.inv#x"),
        ('<a href="_static/LICENSE.txt?download">licence</a>', "<a href> _static/LICENSE.txt?download"),
        ('<p style="background: url(_static/fonts/Mono.ttf)">x</p>', "<p style> url() _static/fonts/Mono.ttf"),
    ],
)
def test_page_gate_refuses_references_to_unserved_file_types(page: str, expected: str) -> None:
    assert _refused(page) == [(f"{expected}: the documentation scheme does not serve this file type", 1)]


def test_references_to_served_files_directories_and_other_documents_pass() -> None:
    page = (
        '<a href="how-to/">a</a><a href="..">b</a><a href="#top">c</a><a href="?q=1">d</a>'
        '<a href="mailto:a@example.org">e</a><img src="data:image/png;base64,AAAA">'
        '<a href="pagefind/pagefind-entry.json">f</a><a href="how-to/modelo%2D303.html">g</a>'
    )
    assert _refused(page) == []


def test_staging_scans_stylesheets_and_names_the_file_and_line(tmp_path: Path) -> None:
    message = _staging_refusal(tmp_path, {"_static/site.css": "a {}\n@import url(https://fonts.example/a.css);\n"})
    assert "@import https://fonts.example/a.css: 1 location(s), first _static/site.css:2" in message


def test_staging_refuses_a_stylesheet_that_loads_an_unserved_font(tmp_path: Path) -> None:
    message = _staging_refusal(tmp_path, {"_static/site.css": "@font-face { src: url(fonts/Mono.ttf) }\n"})
    assert "url() fonts/Mono.ttf: the documentation scheme does not serve this file type" in message


def test_staging_excludes_unserved_file_types_from_the_package(tmp_path: Path) -> None:
    build = _build(tmp_path)
    stage_roots(build)
    payload = verified_stage(build / "user-docs/stage", load_layout()["user_docs"])
    manifest = json.loads((payload / "manifest.json").read_text(encoding="utf-8"))
    languages = declared_languages(load_layout())
    # Every language wrote the same bytes here, so each served file is stored once.
    assert set(manifest["files"]) == {
        "structure/index.html",
        "structure/how-to/index.html",
        "structure/_static/site.css",
        f"languages/{languages[0]}/pagefind/pagefind.js",
        f"languages/{languages[0]}/pagefind/pagefind-entry.json",
        *(f"text/{language}.json" for language in languages),
    }


# The desktop host's documentation scheme replays the same cases against its own parser.
SHARED_MEDIA_TYPE_CASES = json.loads(
    (REPO_ROOT / "native/desktop/src-tauri/src/docs/media_type_cases.json").read_text(encoding="utf-8")
)


@pytest.mark.parametrize("table", SHARED_MEDIA_TYPE_CASES["malformed"])
def test_media_type_declaration_must_be_a_closed_table(table: object) -> None:
    with pytest.raises(DocsPackagingError, match="media_types"):
        served_media_types({} if table is None else {"media_types": table})


@pytest.mark.parametrize(("name", "expected"), SHARED_MEDIA_TYPE_CASES["cases"])
def test_media_types_match_names_before_the_final_extension(name: str, expected: str | None) -> None:
    assert served_media_types({"media_types": SHARED_MEDIA_TYPE_CASES["table"]}).of(name) == expected
