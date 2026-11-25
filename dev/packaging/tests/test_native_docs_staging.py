"""Bundled user-documentation staging: one stored structure, each language's text, manifest and refusal gates."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import pytest

from dev.docs.shared_structure import compose_page

from ..native.docs_errors import DocsPackagingError
from ..native.docs_scan import csp_hash, scan_page, served_media_types
from ..native.docs_stage import declared_languages, package_prefix, stage_roots, verified_stage
from ..native.layout import load_layout

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

THEME_SNIPPET = "document.documentElement.dataset.theme = localStorage.getItem('theme') || 'auto';"
PAGE = f"""<!doctype html><html><head>
<script src="_static/furo.js"></script>
<script type="application/json" id="strings">{{"a": 1}}</script>
<script>{THEME_SNIPPET}</script>
</head><body><a href="https://example.org/page.html">external prose link</a></body></html>
"""
STYLESHEET = "body{margin:0}"


def _build(tmp_path: Path) -> Path:
    paths = {
        "user_docs_build": "user-docs/build",
        "user_docs_work": "user-docs/work",
        "user_docs_stage": "user-docs/stage",
    }
    (tmp_path / "build-paths.json").write_text(json.dumps({"paths": paths}), encoding="utf-8")
    return tmp_path


def _page(language: str, page: str = PAGE) -> str:
    """The page as one language's build writes it: the same markup, its own text."""
    return page.replace("<html>", f'<html lang="{language}">').replace("external prose link", f"{language} prose")


def _root(build: Path, language: str, page: str = PAGE, *, search: bool | None = None) -> Path:
    """Write one language's built root; only the apex language carries the search index unless told otherwise."""
    root = build / "user-docs/build/html" / language
    (root / "how-to").mkdir(parents=True)
    (root / "_static").mkdir()
    (root / "index.html").write_text(_page(language, page), encoding="utf-8")
    (root / "how-to/modelo-303.html").write_text(_page(language, page), encoding="utf-8")
    (root / "_static/site.css").write_text(STYLESHEET, encoding="utf-8")
    if language == "en" if search is None else search:
        (root / "pagefind").mkdir()
        (root / "pagefind/pagefind.js").write_text("export {};", encoding="utf-8")
    for state in (".doctrees", "_sources"):
        (root / state).mkdir()
        (root / state / "index.doctree").write_bytes(b"state")
    (root / ".buildinfo").write_text("# Sphinx build info", encoding="utf-8")
    return root


def _languages() -> tuple[str, ...]:
    return declared_languages(load_layout())


def _staged(build: Path) -> tuple[Path, dict[str, Any]]:
    payload = verified_stage(build / "user-docs/stage", load_layout()["user_docs"])
    return payload, json.loads((payload / "manifest.json").read_text(encoding="utf-8"))


def _composed(payload: Path, language: str, page: str) -> str:
    structure = (payload / "structure" / page).read_text(encoding="utf-8", newline="")
    text = compose_page(structure, json.loads((payload / "text" / f"{language}.json").read_text(encoding="utf-8")))
    # The stored page omits platform line terminators; composition restores
    # them just as the documentation producer does when writing its output.
    return text.replace("\n", os.linesep)


def test_csp_hash_matches_the_specification_example_and_html_newline_normalization() -> None:
    # The CSP specification's worked example for an inline script body.
    assert csp_hash("alert('Hello, world.');") == "sha256-qznLcsROx4GACP2dm0UCKCzCG+HiZ1guq6ZZDob/Tng="
    assert csp_hash("alert(1);\r\nalert(2);\r") == csp_hash("alert(1);\nalert(2);\n")


def test_scan_counts_only_executing_inline_scripts() -> None:
    page = PAGE + '<script type="module">import "./a.js";</script><script type="text/plain">x</script>'
    findings = scan_page(page, served_media_types(load_layout()["user_docs"]))
    assert findings.inline_scripts == [THEME_SNIPPET, 'import "./a.js";']
    assert findings.refused == []


def test_staging_stores_one_structure_each_language_text_and_no_build_state(tmp_path: Path) -> None:
    build = _build(tmp_path)
    for language in _languages():
        _root(build, language)
    stage_roots(build)
    payload, manifest = _staged(build)
    localized = [language for language in _languages() if language != "en"]
    assert manifest["schema"] == 2
    assert manifest["languages"] == list(_languages())
    assert manifest["apex_language"] == "en"
    assert manifest["entries"] == {"en": "index.html"} | {language: f"{language}/index.html" for language in localized}
    assert manifest["search"] == "pagefind/pagefind.js"
    assert manifest["script_hashes"] == [csp_hash(THEME_SNIPPET)]
    assert manifest["stored"] == {
        "structure": "structure",
        "languages": "languages",
        "text": {language: f"text/{language}.json" for language in _languages()},
    }
    assert manifest["pages"] == ["how-to/modelo-303.html", "index.html"]
    expected = {
        "structure/index.html",
        "structure/how-to/modelo-303.html",
        "structure/_static/site.css",
        "languages/en/pagefind/pagefind.js",
        *(f"text/{language}.json" for language in _languages()),
    }
    assert set(manifest["files"]) == expected
    shipped = {path.relative_to(payload).as_posix() for path in payload.rglob("*") if path.is_file()}
    assert shipped == {"manifest.json", *expected}


def test_every_language_page_comes_back_from_the_structure_and_its_text(tmp_path: Path) -> None:
    build = _build(tmp_path)
    for language in _languages():
        _root(build, language)
    stage_roots(build)
    payload, _ = _staged(build)
    structure = (payload / "structure/index.html").read_text(encoding="utf-8")
    assert THEME_SNIPPET in structure
    for language in _languages():
        assert f"{language} prose" not in structure
        for page in ("index.html", "how-to/modelo-303.html"):
            built = (build / "user-docs/build/html" / language / page).read_text(encoding="utf-8", newline="")
            assert f"{language} prose" in built
            assert _composed(payload, language, page) == built
    assert (payload / "structure/_static/site.css").read_text(encoding="utf-8") == STYLESHEET


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
    payload, manifest = _staged(build)
    for language in _languages():
        if language != "en":
            assert f"<p>{language} root</p>" in _composed(payload, language, "index.html")
    assert not [path for path in manifest["files"] if path.startswith(("languages/", "structure/")) and "/es/" in path]
    assert len(manifest["files"]) == 4 + len(_languages())


def test_staged_payload_detects_a_changed_file(tmp_path: Path) -> None:
    build = _build(tmp_path)
    for language in _languages():
        _root(build, language)
    stage_roots(build)
    (build / "user-docs/stage/user/text" / f"{_languages()[-1]}.json").write_text("[]", encoding="utf-8")
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


def test_staging_refuses_an_apex_without_the_search_index(tmp_path: Path) -> None:
    build = _build(tmp_path)
    for language in _languages():
        _root(build, language, search=False)
    with pytest.raises(DocsPackagingError, match=re.escape("en: missing pagefind/pagefind.js")):
        stage_roots(build)


def test_staging_refuses_a_second_search_index(tmp_path: Path) -> None:
    build = _build(tmp_path)
    for language in _languages():
        _root(build, language, search=True)
    with pytest.raises(DocsPackagingError, match=re.escape("es: holds its own pagefind/pagefind.js; the one")):
        stage_roots(build)


def test_staging_refuses_a_page_one_language_lacks(tmp_path: Path) -> None:
    build = _build(tmp_path)
    for language in _languages():
        _root(build, language)
    (build / "user-docs/build/html/hu/how-to/modelo-303.html").unlink()
    with pytest.raises(DocsPackagingError, match=r"1 page\(s\) exist in some languages and not in others"):
        stage_roots(build)
    assert not (build / "user-docs/stage/ready").exists()


@pytest.mark.parametrize("languages", [[], ["en", "en"], ["en", "xx"], "en", ["es", "ca"]])
def test_language_declaration_must_be_unique_supported_languages(languages: object) -> None:
    with pytest.raises(DocsPackagingError):
        declared_languages({"user_docs": {"languages": languages}})


def test_assembly_with_documentation_refuses_a_missing_stage_and_names_the_remedy(tmp_path: Path) -> None:
    with pytest.raises(DocsPackagingError, match="has not run for this CMake binary directory"):
        verified_stage(tmp_path / "user-docs/stage", load_layout()["user_docs"])


def _identity(path: Path) -> tuple[int, int]:
    """The file's identity and last write: equal only when the file was neither replaced nor rewritten."""
    status = path.stat()
    return status.st_ino, status.st_mtime_ns


def test_restaging_keeps_unchanged_files_replaces_changed_ones_and_prunes_removed_ones(tmp_path: Path) -> None:
    build = _build(tmp_path)
    for language in _languages():
        _root(build, language)
    stage_roots(build)
    payload, _ = _staged(build)
    edited = _languages()[-1]
    stylesheet, structure = payload / "structure/_static/site.css", payload / "structure/index.html"
    text, removed = payload / "text" / f"{edited}.json", payload / "structure/how-to/modelo-303.html"
    before = {path: _identity(path) for path in (stylesheet, structure, text)}
    for language in _languages():
        root = build / "user-docs/build/html" / language
        # The build rewrites every file; only one language's prose and one page set change.
        (root / "_static/site.css").write_text(STYLESHEET, encoding="utf-8")
        (root / "index.html").write_text(
            _page(language).replace(f"{edited} prose", f"{edited} revised prose"), encoding="utf-8"
        )
        (root / "how-to/modelo-303.html").unlink()

    stage_roots(build)

    payload, manifest = _staged(build)
    assert _identity(stylesheet) == before[stylesheet], "an unchanged stored file is not copied again"
    assert _identity(structure) == before[structure], "the structure every language shares did not change"
    assert _identity(text) != before[text]
    assert _composed(payload, edited, "index.html").count(f"{edited} revised prose") == 1
    assert not removed.exists() and not removed.parent.exists()
    assert "structure/how-to/modelo-303.html" not in manifest["files"]
    assert not (build / "user-docs/stage/next").exists()


def test_restaging_scans_only_pages_whose_bytes_changed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from ..native import docs_stage

    build = _build(tmp_path)
    for language in _languages():
        _root(build, language)
    stage_roots(build)
    scanned: list[str] = []
    real_scan = docs_stage.scan_page

    def counted(text: str, media_types: Any) -> Any:
        scanned.append(text)
        return real_scan(text, media_types)

    monkeypatch.setattr(docs_stage, "scan_page", counted)
    edited = build / "user-docs/build/html" / _languages()[0] / "index.html"
    edited.write_text(_page(_languages()[0]).replace("prose", "changed prose"), encoding="utf-8")

    stage_roots(build)

    assert [text for text in scanned if "changed prose" in text] == scanned and len(scanned) == 1
    _, manifest = _staged(build)
    assert manifest["script_hashes"] == [csp_hash(THEME_SNIPPET)], "remembered pages still contribute their hashes"


def test_a_remembered_page_is_refused_again_without_rescanning(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from ..native import docs_stage

    build = _build(tmp_path)
    languages = _languages()
    _root(build, languages[0], PAGE.replace("<body>", '<body onload="start()">'))
    for language in languages[1:]:
        _root(build, language)
    with pytest.raises(DocsPackagingError, match="<body onload> inline event handler") as first:
        stage_roots(build)

    def refused_rescan(text: str, media_types: Any) -> Any:
        raise AssertionError("an unchanged page was scanned again")

    monkeypatch.setattr(docs_stage, "scan_page", refused_rescan)
    with pytest.raises(DocsPackagingError, match="<body onload> inline event handler") as second:
        stage_roots(build)
    assert str(second.value) == str(first.value)
    assert not (build / "user-docs/stage/ready").exists()


def test_malformed_cached_findings_are_rescanned_and_cannot_hide_refusals(tmp_path: Path) -> None:
    build = _build(tmp_path)
    languages = _languages()
    _root(build, languages[0], PAGE.replace("<body>", '<body onload="start()">'))
    for language in languages[1:]:
        _root(build, language)
    with pytest.raises(DocsPackagingError, match="<body onload> inline event handler"):
        stage_roots(build)

    cache_path = build / "user-docs/stage/scan-cache.json"
    cache = json.loads(cache_path.read_text(encoding="utf-8"))
    for key in cache["findings"]:
        if key.startswith("text/html:"):
            cache["findings"][key] = [[], [["invalid", "not a line number"]]]
    cache_path.write_text(json.dumps(cache), encoding="utf-8")

    with pytest.raises(DocsPackagingError, match="<body onload> inline event handler"):
        stage_roots(build)
    assert not (build / "user-docs/stage/ready").exists()
