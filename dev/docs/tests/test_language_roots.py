"""Language roots stored as one structure and each language's text come back exactly.

Three small roots are written by hand with every kind of file a built root
holds: a page that differs by language, a page and an asset that do not, a
script only the translated roots carry, a search file that differs, and a page
that is not text. The expected layout and the expected stored bytes are stated
here, and the composed roots are compared with the files that were written.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from ..language_roots import (
    LANGUAGES_DIRECTORY,
    LAYOUT_FILE,
    STRUCTURE_DIRECTORY,
    LanguageRootsError,
    Layout,
    compose_root,
    differences,
    factor_roots,
    read_layout,
    read_text,
    text_file,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]

_SITES: dict[str, dict[str, bytes]] = {
    "en": {
        "index.html": b'<html lang="en"><body><h1>Filing calendar</h1><p>ley:art-1</p></body></html>',
        "legal/notice.html": b"<html><body><p>Texto oficial</p></body></html>",
        "_static/app.css": b"body{margin:0}",
        "pagefind/index.pf_meta": b"\x00en-index",
        "scan.html": b"\xff\xfe not text en",
    },
    "es": {
        "index.html": b'<html lang="es"><body><h1>Calendario fiscal</h1><p>ley:art-1</p></body></html>',
        "legal/notice.html": b"<html><body><p>Texto oficial</p></body></html>",
        "_static/app.css": b"body{margin:0}",
        "_static/translations.js": b"es();",
        "pagefind/index.pf_meta": b"\x00es-index",
        "scan.html": b"\xff\xfe not text es",
    },
    "ca": {
        "index.html": b'<html lang="ca"><body><h1>Calendari fiscal</h1><p>ley:art-1</p></body></html>',
        "legal/notice.html": b"<html><body><p>Texto oficial</p></body></html>",
        "_static/app.css": b"body{margin:0}",
        "_static/translations.js": b"ca();",
        "pagefind/index.pf_meta": b"\x00ca-index",
        "scan.html": b"\xff\xfe not text ca",
    },
}


def _built(root: Path, sites: dict[str, dict[str, bytes]] | None = None) -> dict[str, dict[str, Path]]:
    files: dict[str, dict[str, Path]] = {}
    for language, site in (sites or _SITES).items():
        files[language] = {}
        for path, content in site.items():
            target = root / language / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            files[language][path] = target
    return files


def _tree(root: Path) -> dict[str, bytes]:
    return {path.relative_to(root).as_posix(): path.read_bytes() for path in root.rglob("*") if path.is_file()}


def test_each_path_is_stored_by_what_the_languages_share(tmp_path: Path) -> None:
    layout = factor_roots(_built(tmp_path / "built"), tmp_path / "stored")
    assert layout == Layout(
        languages=("en", "es", "ca"),
        pages=("index.html",),
        shared=("_static/app.css", "legal/notice.html"),
        language_files={
            "en": ("pagefind/index.pf_meta", "scan.html"),
            "es": ("_static/translations.js", "pagefind/index.pf_meta", "scan.html"),
            "ca": ("_static/translations.js", "pagefind/index.pf_meta", "scan.html"),
        },
    )
    assert read_layout(tmp_path / "stored") == layout


def test_the_structure_holds_no_language_and_the_text_holds_only_strings(tmp_path: Path) -> None:
    stored = tmp_path / "stored"
    factor_roots(_built(tmp_path / "built"), stored)
    structure = (stored / STRUCTURE_DIRECTORY / "index.html").read_text(encoding="utf-8")
    assert "<p>ley:art-1</p></body></html>" in structure
    for translated in ("Filing calendar", "Calendario fiscal", "Calendari fiscal", 'lang="es"'):
        assert translated not in structure
    assert sorted(read_text(stored, "es")) == ["Calendario fiscal", "es"]
    assert sorted(read_text(stored, "ca")) == ["Calendari fiscal", "ca"]
    assert (stored / STRUCTURE_DIRECTORY / "legal" / "notice.html").read_bytes() == _SITES["en"]["legal/notice.html"]
    assert not (stored / LANGUAGES_DIRECTORY / "en" / "_static").exists()


@pytest.mark.parametrize("language", ["en", "es", "ca"])
def test_a_language_site_is_composed_back_exactly(tmp_path: Path, language: str) -> None:
    stored = tmp_path / "stored"
    factor_roots(_built(tmp_path / "built"), stored)
    compose_root(stored, language, tmp_path / "composed")
    assert _tree(tmp_path / "composed") == _SITES[language]


def test_the_gate_is_silent_on_the_roots_it_stored_and_names_what_no_longer_matches(tmp_path: Path) -> None:
    built = _built(tmp_path / "built")
    stored = tmp_path / "stored"
    factor_roots(built, stored)
    assert differences(stored, built) == []

    renamed = [string.replace("fiscal", "tributario") for string in read_text(stored, "es")]
    (stored / text_file("es")).write_text(json.dumps(renamed), encoding="utf-8")
    built["ca"]["_static/app.css"].write_bytes(b"body{margin:1px}")
    built["en"]["extra.html"] = built["en"]["index.html"]
    assert differences(stored, built) == [
        "en/extra.html: built but not stored",
        "es/index.html: composed bytes differ from the built file",
        "ca/_static/app.css: composed bytes differ from the built file",
    ]


def test_a_page_missing_from_one_language_is_refused(tmp_path: Path) -> None:
    sites = {language: dict(site) for language, site in _SITES.items()}
    del sites["ca"]["index.html"]
    with pytest.raises(LanguageRootsError, match=r"1 page\(s\) exist in some languages and not in others, first index"):
        factor_roots(_built(tmp_path / "built", sites), tmp_path / "stored")


def test_a_destination_that_holds_anything_is_refused(tmp_path: Path) -> None:
    (tmp_path / "stored").mkdir()
    (tmp_path / "stored" / "old.txt").write_text("old", encoding="utf-8")
    with pytest.raises(LanguageRootsError, match="not empty"):
        factor_roots(_built(tmp_path / "built"), tmp_path / "stored")


@pytest.mark.parametrize("path", ["../outside.css", "/absolute.css", "C:/drive.css", "a\\b.css"])
def test_a_path_that_leaves_the_root_is_refused(tmp_path: Path, path: str) -> None:
    source = tmp_path / "source.css"
    source.write_bytes(b"x")
    with pytest.raises(LanguageRootsError, match="not a path inside a documentation root"):
        factor_roots({"en": {path: source}, "es": {path: source}}, tmp_path / "stored")


def test_a_layout_of_another_schema_or_another_language_set_is_refused(tmp_path: Path) -> None:
    stored = tmp_path / "stored"
    factor_roots(_built(tmp_path / "built"), stored)
    with pytest.raises(LanguageRootsError, match="holds"):
        compose_root(stored, "hu", tmp_path / "composed")
    document = json.loads((stored / LAYOUT_FILE).read_text(encoding="utf-8"))
    (stored / LAYOUT_FILE).write_text(json.dumps({**document, "schema": 2}), encoding="utf-8")
    with pytest.raises(LanguageRootsError, match="not a schema 1 layout"):
        read_layout(stored)


#: One page in three languages, written as its lines rather than as one string.
#: A page's own build ends each line with the terminator of the platform that
#: writes it, and the stored form must carry neither platform's.
_LINES: dict[str, tuple[str, ...]] = {
    "en": ("<html>", "<h1>Filing calendar</h1>", "<p>ley:art-1</p>", "</html>"),
    "es": ("<html>", "<h1>Calendario fiscal</h1>", "<p>ley:art-1</p>", "</html>"),
    "ca": ("<html>", "<h1>Calendari fiscal</h1>", "<p>ley:art-1</p>", "</html>"),
}


def _terminated(terminator: str) -> dict[str, dict[str, bytes]]:
    """Return one site per language whose pages end their lines with *terminator*.

    A page that differs by language, a page every language shares, and an asset
    whose line terminators are its author's rather than the writer's.
    """
    shared = terminator.join(("<html>", "<p>Texto oficial</p>", "</html>"))
    return {
        language: {
            "index.html": (terminator.join(lines) + terminator).encode("utf-8"),
            "legal/notice.html": shared.encode("utf-8"),
            "_static/app.css": b"body{\r\n  margin:0\r\n}",
        }
        for language, lines in _LINES.items()
    }


def test_a_page_is_stored_without_the_terminators_of_the_platform_that_wrote_it(tmp_path: Path) -> None:
    """Neither a composed page's structure nor a shared page carries a carriage return."""
    stored = tmp_path / "stored"
    factor_roots(_built(tmp_path / "built", _terminated("\r\n")), stored)
    assert b"\r" not in (stored / STRUCTURE_DIRECTORY / "index.html").read_bytes()
    assert b"\r" not in (stored / STRUCTURE_DIRECTORY / "legal" / "notice.html").read_bytes()
    # An asset is not a page: its bytes are its author's, and are stored as they are.
    assert (stored / STRUCTURE_DIRECTORY / "_static" / "app.css").read_bytes() == b"body{\r\n  margin:0\r\n}"


def test_a_structure_stored_from_either_terminator_is_the_same_bytes(tmp_path: Path) -> None:
    """The same site stored on two platforms is the same stored form."""
    factor_roots(_built(tmp_path / "crlf-built", _terminated("\r\n")), tmp_path / "from-crlf")
    factor_roots(_built(tmp_path / "lf-built", _terminated("\n")), tmp_path / "from-lf")
    assert _tree(tmp_path / "from-crlf") == _tree(tmp_path / "from-lf")


@pytest.mark.parametrize("stored_from", ["\r\n", "\n"])
def test_a_page_is_composed_as_this_platform_ends_its_lines(tmp_path: Path, stored_from: str) -> None:
    """Whichever platform stored the pages, composing gives this platform's terminators."""
    stored = tmp_path / "stored"
    factor_roots(_built(tmp_path / "built", _terminated(stored_from)), stored)
    compose_root(stored, "es", tmp_path / "composed")
    assert _tree(tmp_path / "composed") == _terminated(os.linesep)["es"]


def test_the_gate_is_silent_on_a_structure_the_other_platform_stored(tmp_path: Path) -> None:
    """A stored form written where lines end otherwise still gives this platform's build back."""
    elsewhere = "\n" if os.linesep == "\r\n" else "\r\n"
    stored = tmp_path / "stored"
    factor_roots(_built(tmp_path / "elsewhere", _terminated(elsewhere)), stored)
    assert differences(stored, _built(tmp_path / "here", _terminated(os.linesep))) == []
