"""Bundled user-documentation staging: shippable subset, manifest and refusal gates."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ..native.docs_stage import (
    DocsPackagingError,
    csp_hash,
    declared_languages,
    package_prefix,
    scan_page,
    served_media_types,
    stage_roots,
    verified_stage,
)
from ..native.layout import load_layout

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

THEME_SNIPPET = "document.documentElement.dataset.theme = localStorage.getItem('theme') || 'auto';"
PAGE = f"""<!doctype html><html><head>
<script src="_static/furo.js"></script>
<script type="application/json" id="strings">{{"a": 1}}</script>
<script>{THEME_SNIPPET}</script>
</head><body><a href="https://example.org/page.html">external prose link</a></body></html>
"""


def _build(tmp_path: Path) -> Path:
    paths = {
        "user_docs_build": "user-docs/build",
        "user_docs_work": "user-docs/work",
        "user_docs_stage": "user-docs/stage",
    }
    (tmp_path / "build-paths.json").write_text(json.dumps({"paths": paths}), encoding="utf-8")
    return tmp_path


def _root(build: Path, language: str, page: str = PAGE, *, search: bool = True) -> Path:
    root = build / "user-docs/build/html" / language
    (root / "how-to").mkdir(parents=True)
    (root / "index.html").write_text(page, encoding="utf-8")
    (root / "how-to/modelo-303.html").write_text(page, encoding="utf-8")
    if search:
        (root / "pagefind").mkdir()
        (root / "pagefind/pagefind.js").write_text("export {};", encoding="utf-8")
    for state in (".doctrees", "_sources"):
        (root / state).mkdir()
        (root / state / "index.doctree").write_bytes(b"state")
    (root / ".buildinfo").write_text("# Sphinx build info", encoding="utf-8")
    return root


def _languages() -> tuple[str, ...]:
    return declared_languages(load_layout())


def test_csp_hash_matches_the_specification_example_and_html_newline_normalization() -> None:
    # The CSP specification's worked example for an inline script body.
    assert csp_hash("alert('Hello, world.');") == "sha256-qznLcsROx4GACP2dm0UCKCzCG+HiZ1guq6ZZDob/Tng="
    assert csp_hash("alert(1);\r\nalert(2);\r") == csp_hash("alert(1);\nalert(2);\n")


def test_scan_counts_only_executing_inline_scripts() -> None:
    page = PAGE + '<script type="module">import "./a.js";</script><script type="text/plain">x</script>'
    findings = scan_page(page, served_media_types(load_layout()["user_docs"]))
    assert findings.inline_scripts == [THEME_SNIPPET, 'import "./a.js";']
    assert findings.refused == []


def test_staging_ships_the_apex_layout_without_build_state(tmp_path: Path) -> None:
    build = _build(tmp_path)
    for language in _languages():
        _root(build, language)
    stage_roots(build)
    payload = verified_stage(build / "user-docs/stage", load_layout()["user_docs"])
    manifest = json.loads((payload / "manifest.json").read_text(encoding="utf-8"))
    localized = [language for language in _languages() if language != "en"]
    assert manifest["languages"] == list(_languages())
    assert manifest["apex_language"] == "en"
    assert manifest["entries"] == {"en": "index.html"} | {language: f"{language}/index.html" for language in localized}
    assert manifest["search"] == {"en": "pagefind/pagefind.js"} | {
        language: f"{language}/pagefind/pagefind.js" for language in localized
    }
    assert manifest["script_hashes"] == [csp_hash(THEME_SNIPPET)]
    pages = ("index.html", "how-to/modelo-303.html", "pagefind/pagefind.js")
    expected = {page for page in pages} | {f"{language}/{page}" for language in localized for page in pages}
    assert set(manifest["files"]) == expected
    shipped = {path.relative_to(payload).as_posix() for path in payload.rglob("*") if path.is_file()}
    assert shipped == {"manifest.json", *expected}


def test_nested_language_roots_in_the_apex_source_are_not_staged_twice(tmp_path: Path) -> None:
    build = _build(tmp_path)
    apex = _root(build, "en")
    for language in _languages():
        if language != "en":
            _root(build, language, PAGE.replace("<body>", f"<body><p>{language} root</p>"))
            nested = apex / language
            nested.mkdir()
            (nested / "index.html").write_text("nested copy inside the apex source", encoding="utf-8")
    stage_roots(build)
    payload = verified_stage(build / "user-docs/stage", load_layout()["user_docs"])
    manifest = json.loads((payload / "manifest.json").read_text(encoding="utf-8"))
    for language in _languages():
        if language != "en":
            staged = (payload / language / "index.html").read_text(encoding="utf-8")
            assert f"<p>{language} root</p>" in staged
    assert len(manifest["files"]) == 3 * len(_languages())


def test_staged_payload_detects_a_changed_file(tmp_path: Path) -> None:
    build = _build(tmp_path)
    for language in _languages():
        _root(build, language)
    stage_roots(build)
    (build / "user-docs/stage/user" / package_prefix(_languages()[-1]) / "index.html").write_text("x", encoding="utf-8")
    with pytest.raises(DocsPackagingError, match="changed after staging"):
        verified_stage(build / "user-docs/stage", load_layout()["user_docs"])


def test_staging_refuses_remote_resources_and_names_each_offender(tmp_path: Path) -> None:
    build = _build(tmp_path)
    remote = PAGE.replace(
        "</head>",
        '<script async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>'
        '<link rel="stylesheet" href="//fonts.example.net/a.css"></head>',
    )
    languages = _languages()
    _root(build, languages[0], remote)
    for language in languages[1:]:
        _root(build, language)
    with pytest.raises(DocsPackagingError) as refusal:
        stage_roots(build)
    message = str(refusal.value)
    assert "<script src> https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js: 2 location(s)" in message
    assert "<link href> //fonts.example.net/a.css: 2 location(s)" in message
    assert f"first {package_prefix(languages[0])}how-to/modelo-303.html:5" in message
    assert not (build / "user-docs/stage/ready").exists()


def test_staging_refuses_inline_event_handlers(tmp_path: Path) -> None:
    build = _build(tmp_path)
    languages = _languages()
    _root(build, languages[0], PAGE.replace("<body>", '<body onload="start()">'))
    for language in languages[1:]:
        _root(build, language)
    with pytest.raises(DocsPackagingError, match="<body onload> inline event handler"):
        stage_roots(build)


def test_staging_refuses_a_language_without_its_search_index(tmp_path: Path) -> None:
    build = _build(tmp_path)
    languages = _languages()
    _root(build, languages[0], search=False)
    for language in languages[1:]:
        _root(build, language)
    with pytest.raises(DocsPackagingError, match=f"{languages[0]}: missing pagefind/pagefind.js"):
        stage_roots(build)


@pytest.mark.parametrize("languages", [[], ["en", "en"], ["en", "xx"], "en", ["es", "ca"]])
def test_language_declaration_must_be_unique_supported_languages(languages: object) -> None:
    with pytest.raises(DocsPackagingError):
        declared_languages({"user_docs": {"languages": languages}})


def test_assembly_with_documentation_refuses_a_missing_stage_and_names_the_remedy(tmp_path: Path) -> None:
    with pytest.raises(DocsPackagingError, match="has not run for this CMake binary directory"):
        verified_stage(tmp_path / "user-docs/stage", load_layout()["user_docs"])
