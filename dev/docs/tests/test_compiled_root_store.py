"""One compiled site is stored as the structure and each language's text, and composes back.

A compiled site is written by hand: a page carrying marks, a page carrying none,
an asset every language shares, a script the compile wrote with marks in its own
syntax, and a search file given per language. The stored form is then composed
for every language and compared with the site each language's own build would
have produced, which is stated here.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from ..compile_slots import (
    BLOCK_CLOSE,
    BLOCK_MID,
    BLOCK_OPEN,
    MARK_CLOSE,
    MARK_OPEN,
    CompileSlots,
    CompileSlotsError,
    Rendering,
    activate,
    deactivate,
)
from ..language_roots import (
    LANGUAGES_DIRECTORY,
    STRUCTURE_DIRECTORY,
    LanguageRootsError,
    Layout,
    asset_cache_key,
    compose_root,
    read_layout,
    refuse_uneven_language_files,
    store_compiled_root,
)
from ..shared_structure import SLOT_CLOSE, SLOT_OPEN

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]

_LANGUAGES = ("en", "es")


@pytest.fixture
def slots() -> Iterator[CompileSlots]:
    """A compile recording two languages."""
    recorded = activate(_LANGUAGES)
    yield recorded
    deactivate()


def _written(root: Path, files: dict[str, bytes]) -> dict[str, Path]:
    for path, content in files.items():
        target = root.joinpath(*path.split("/"))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    return {path: root.joinpath(*path.split("/")) for path in files}


def test_a_compiled_site_composes_back_to_every_language(slots: CompileSlots, tmp_path: Path) -> None:
    """Every language's site comes out of one compile and one list of strings."""
    title = slots.mark(Rendering.DOCUTILS, ["Filing calendar", "Calendario fiscal"])
    chrome = slots.mark(Rendering.VERBATIM, ["Search docs", "Buscar"])
    strings_script = f'window.s={{"search":"{chrome}"}};\n'.encode()
    compiled = _written(
        tmp_path / "compiled",
        {
            "index.html": f"<head><title>{title}</title></head><body><h1>{title}</h1></body>".encode(),
            "notice.html": b"<body><p>Ley 37/1992</p></body>",
            "_static/app.css": b"body{margin:0}",
            "_static/chrome.js": strings_script,
        },
    )
    index = _written(tmp_path / "index-en", {"pagefind/index.pf_meta": b"\x00en"})
    index_es = _written(tmp_path / "index-es", {"pagefind/index.pf_meta": b"\x00es"})
    stored = tmp_path / "stored"
    layout = store_compiled_root(
        compiled,
        slots,
        stored,
        language_files={"en": index, "es": index_es},
    )

    assert layout.pages == ("index.html",)
    assert layout.shared == ("_static/app.css", "notice.html")
    assert layout.language_files == {
        "en": ("_static/chrome.js", "pagefind/index.pf_meta"),
        "es": ("_static/chrome.js", "pagefind/index.pf_meta"),
    }
    assert (stored / STRUCTURE_DIRECTORY / "notice.html").read_bytes() == b"<body><p>Ley 37/1992</p></body>"
    # The title stands in the ``<title>`` element and in the heading, and both
    # writers write this string the same way, so it is one stored string.
    assert json.loads((stored / "text" / "es.json").read_text(encoding="utf-8")) == ["Calendario fiscal"]

    for language, expected in (
        ("en", "<head><title>Filing calendar</title></head><body><h1>Filing calendar</h1></body>"),
        ("es", "<head><title>Calendario fiscal</title></head><body><h1>Calendario fiscal</h1></body>"),
    ):
        site = tmp_path / f"site-{language}"
        compose_root(stored, language, site)
        assert (site / "index.html").read_text(encoding="utf-8") == expected
        assert (site / "_static" / "app.css").read_bytes() == b"body{margin:0}"
        assert (site / "pagefind" / "index.pf_meta").read_bytes() == b"\x00" + language.encode()
    assert (tmp_path / "site-es" / "_static" / "chrome.js").read_text(
        encoding="utf-8"
    ) == 'window.s={"search":"Buscar"};\n'


def test_a_language_dependent_assets_key_in_a_page_becomes_a_slot(slots: CompileSlots, tmp_path: Path) -> None:
    """A page links each language's own file, so it carries that language's key."""
    compiled = _written(
        tmp_path / "compiled",
        {
            "index.html": b'<script src="_static/chrome.js?v=KEY"></script>',
            "_static/chrome.js": b"compiled",
        },
    )
    english = _written(tmp_path / "en", {"_static/chrome.js": b"en"})
    spanish = _written(tmp_path / "es", {"_static/chrome.js": b"es"})
    # The compiled page is written with the key of the compiled file, exactly as
    # Sphinx writes it, so the stored page can find the reference to replace.
    compiled_key = asset_cache_key(b"compiled")
    compiled["index.html"].write_bytes(f'<script src="_static/chrome.js?v={compiled_key}"></script>'.encode())
    stored = tmp_path / "stored"
    store_compiled_root(compiled, slots, stored, language_files={"en": english, "es": spanish})

    for language, content in (("en", b"en"), ("es", b"es")):
        site = tmp_path / f"site-{language}"
        compose_root(stored, language, site)
        assert (site / "index.html").read_text(encoding="utf-8") == (
            f'<script src="_static/chrome.js?v={asset_cache_key(content)}"></script>'
        )


#: One asset of a built root, and the key the pages of that root carry for it.
#: Taken from a desktop English root built on 2026-10-06, whose every page links
#: ``_static/documentation_options.js?v=037dbd9b``. The key is Sphinx's, not this
#: module's, which is what makes it evidence that the two agree.
_BUILT_ASSET: bytes = (
    b"const DOCUMENTATION_OPTIONS = {\n"
    b"    VERSION: '0.5.1',\n"
    b"    LANGUAGE: 'en',\n"
    b"    COLLAPSE_INDEX: false,\n"
    b"    BUILDER: 'html',\n"
    b"    FILE_SUFFIX: '.html',\n"
    b"    LINK_SUFFIX: '.html',\n"
    b"    HAS_SOURCE: false,\n"
    b"    SOURCELINK_SUFFIX: '.txt',\n"
    b"    NAVIGATION_WITH_KEYS: false,\n"
    b"    SHOW_SEARCH_SUMMARY: true,\n"
    b"    ENABLE_SEARCH_SHORTCUTS: true,\n"
    b"};"
)
_BUILT_ASSET_KEY = "037dbd9b"


def test_the_key_is_the_one_a_built_page_carries() -> None:
    """An asset of a built root hashes to the key that root's pages link it with."""
    assert asset_cache_key(_BUILT_ASSET) == _BUILT_ASSET_KEY
    assert asset_cache_key(_BUILT_ASSET.replace(b"\n", b"\r\n")) == _BUILT_ASSET_KEY
    assert asset_cache_key(b"") == ""


def test_a_file_that_is_not_a_page_cannot_answer_a_docutils_mark(slots: CompileSlots, tmp_path: Path) -> None:
    """Only the creation site knows how to write a string into something that is not markup."""
    mark = slots.mark(Rendering.DOCUTILS, ["a", "b"])
    compiled = _written(tmp_path / "compiled", {"_static/chrome.js": f"x={mark}".encode()})
    with pytest.raises(LanguageRootsError, match="not a page and carries a mark"):
        store_compiled_root(compiled, slots, tmp_path / "stored", language_files={"en": {}, "es": {}})


def test_the_stored_form_reads_the_same_however_it_was_written(slots: CompileSlots, tmp_path: Path) -> None:
    """The composer cannot tell a stored compile from stored roots, which is the point."""
    mark = slots.mark(Rendering.DOCUTILS, ["one", "uno"])
    compiled = _written(tmp_path / "compiled", {"page.html": f"<p>{mark}</p>".encode()})
    stored = tmp_path / "stored"
    store_compiled_root(compiled, slots, stored, language_files={"en": {}, "es": {}})
    assert read_layout(stored).languages == _LANGUAGES
    assert not (stored / LANGUAGES_DIRECTORY).exists()


@pytest.mark.parametrize(
    ("delimiter", "named"),
    [
        (MARK_OPEN, "an opening mark"),
        (MARK_CLOSE, "a closing mark"),
        (SLOT_OPEN, "an opening slot"),
        (SLOT_CLOSE, "a closing slot"),
        # A fragment document's own delimiters. Its written page is deleted
        # rather than composed, so nothing else would ever notice one that
        # reached a page the compile kept.
        (BLOCK_OPEN, "an opening translation block"),
        (BLOCK_MID, "a translation block's separator"),
        (BLOCK_CLOSE, "a closing translation block"),
    ],
)
@pytest.mark.parametrize("path", ["page.html", "_static/chrome.js"])
def test_a_composed_file_still_carrying_a_delimiter_is_refused(
    delimiter: str,
    named: str,
    path: str,
    tmp_path: Path,
) -> None:
    """A reader is served the composed root, so no private-use delimiter may reach any of it.

    The stored form is written by hand, because the refusal is about a
    structure or a string that something upstream left a delimiter in: a
    structure composed from strings this module factored itself would carry
    none, which is exactly what makes the check worth having.

    A script or a stylesheet is checked as a page is: a mark reaches one the
    same way, and such a file is stored once, so a delimiter left in it would
    be shipped to every language at once.
    """
    stored = tmp_path / "stored"
    _written(
        stored,
        {
            f"{STRUCTURE_DIRECTORY}/{path}": f"<p>cut{delimiter}</p>".encode(),
            "text/en.json": b"[]",
            "layout.json": json.dumps(
                {
                    "schema": 1,
                    "languages": ["en"],
                    "pages": [],
                    "shared": [path],
                    "language_files": {"en": []},
                }
            ).encode(),
        },
    )
    with pytest.raises(LanguageRootsError, match=f"composed en file {path} still carries {named} delimiter"):
        compose_root(stored, "en", tmp_path / "root")


def test_a_composed_file_whose_bytes_are_not_text_is_composed(tmp_path: Path) -> None:
    """An image carries no text for a delimiter to be in, and is not read as if it did."""
    stored = tmp_path / "stored"
    image = b"\x89PNG\r\n\x1a\n\xff\xfe\x00\x01"
    _written(
        stored,
        {
            f"{STRUCTURE_DIRECTORY}/_static/mark.png": image,
            "text/en.json": b"[]",
            "layout.json": json.dumps(
                {
                    "schema": 1,
                    "languages": ["en"],
                    "pages": [],
                    "shared": ["_static/mark.png"],
                    "language_files": {"en": []},
                }
            ).encode(),
        },
    )
    compose_root(stored, "en", tmp_path / "root")
    assert (tmp_path / "root" / "_static" / "mark.png").read_bytes() == image


def test_a_file_that_is_not_a_page_and_carries_a_lone_delimiter_is_refused(slots: CompileSlots, tmp_path: Path) -> None:
    """A mark whose opening was cut off leaves no mark to find, and the file is stored once.

    Nothing in the file looks language dependent, so the ordinary rule would
    store it as shared and ship the stray delimiter to every language.
    """
    compiled = _written(tmp_path / "compiled", {"_static/chrome.js": f'x="cut{MARK_CLOSE}";'.encode()})
    with pytest.raises(CompileSlotsError, match="not part of a whole mark"):
        store_compiled_root(compiled, slots, tmp_path / "stored", language_files={"en": {}, "es": {}})


@pytest.mark.parametrize(
    ("path", "content"),
    [
        ("index.html", b'<a href="/docs/%EE%80%82k%EE%80%83/index.html">x</a>'),
        ("_static/chrome.js", b'const root = "/docs/&#xE002;k&#xE003;/";'),
    ],
)
def test_a_file_carrying_a_re_encoded_mark_is_refused(
    slots: CompileSlots, tmp_path: Path, path: str, content: bytes
) -> None:
    """A mark whose delimiters were re-encoded is a mark the factoring never sees.

    The page and the script are written by hand with the delimiters as a URL
    quoter and an XML serialiser write them, because that is what the refusal is
    about: the factoring finds no mark, the file is stored as shared text, and
    every language is served the number the compile wrote.
    """
    compiled = _written(tmp_path / "compiled", {path: content})
    with pytest.raises(CompileSlotsError, match=f"{path} carries a re-encoded mark"):
        store_compiled_root(compiled, slots, tmp_path / "stored", language_files={"en": {}, "es": {}})


def _layout(language_files: dict[str, tuple[str, ...]]) -> Layout:
    """Return a layout whose only interesting fact is which files each language holds."""
    return Layout(languages=tuple(language_files), pages=(), shared=(), language_files=language_files)


def test_per_language_files_that_are_the_same_set_in_every_language_pass() -> None:
    """The baseline the three refusals below are refusals against."""
    refuse_uneven_language_files(
        _layout({"en": ("objects.inv",), "es": ("objects.inv", "_static/translations.js")}),
        absent={"en": ("_static/translations.js",)},
    )


def test_a_language_missing_a_file_its_peers_hold_is_refused() -> None:
    """A root short one file is a site missing a script, an index or an inventory.

    Pages cannot be uneven by construction; a file stored per language because
    its BYTES differ can be, and the root composed for that language is then
    served to a reader with the file simply absent.
    """
    with pytest.raises(LanguageRootsError, match=r"es/objects\.inv: held by another language and absent here"):
        refuse_uneven_language_files(_layout({"en": ("objects.inv",), "es": ()}), absent={})


def test_a_declared_absence_the_language_holds_all_the_same_is_refused() -> None:
    """A declaration that nothing matches is a standing permission for the next absence."""
    with pytest.raises(LanguageRootsError, match=r"en/_static/translations\.js: declared absent"):
        refuse_uneven_language_files(
            _layout({"en": ("_static/translations.js",), "es": ("_static/translations.js",)}),
            absent={"en": ("_static/translations.js",)},
        )


def test_a_declared_absence_of_a_file_no_language_holds_is_refused() -> None:
    """A stale declaration excuses an absence nobody is weighing any more."""
    with pytest.raises(LanguageRootsError, match=r"_static/retired\.js: declared absent, and no language"):
        refuse_uneven_language_files(
            _layout({"en": ("objects.inv",), "es": ("objects.inv",)}),
            absent={"en": ("_static/retired.js",)},
        )


def test_a_page_whose_bytes_are_not_text_is_refused(slots: CompileSlots, tmp_path: Path) -> None:
    """A page read with replacement characters is a page whose marks are lost.

    Stored whole, it would give every language the compile's own text; read
    with replacement characters, two different pages would read the same.
    """
    compiled = _written(tmp_path / "compiled", {"index.html": b"<p>\xff\xfe</p>"})
    with pytest.raises(LanguageRootsError, match=r"index\.html is a page whose bytes are not the UTF-8 text"):
        store_compiled_root(compiled, slots, tmp_path / "stored", language_files={"en": {}, "es": {}})
