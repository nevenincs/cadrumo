"""Store the language roots of one documentation build as one structure and each language's text.

A built root is one language's whole site. This module takes the same site in
every language and writes it once:

- ``structure/``: each page's structure (see :mod:`dev.docs.shared_structure`)
  and one copy of every other file that is the same bytes in every language;
- ``text/<language>.json``: that language's strings, a flat list indexed by slot;
- ``languages/<language>/``: the files that differ by language and are not
  pages, such as the search index;
- ``layout.json``: which of the three each path is.

:func:`compose_root` writes one language's site back from that, and
:func:`differences` is the gate: it reports every file of a built root the stored
form does not give back byte for byte.
"""

from __future__ import annotations

import json
import os
import zlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Final

from .compile_slots import (
    MARK,
    MARK_CLOSE,
    MARK_OPEN,
    CompileSlots,
    Rendering,
    read_escaped_marks,
    refuse_escaped_marks,
    refuse_stray_delimiters,
)
from .compile_slots import cache_key_slots as _cache_key_slots
from .compile_slots import factor_page as _factor_compiled_page
from .shared_structure import SLOT_CLOSE, SLOT_OPEN, LanguageText, compose_page, factor_page

STRUCTURE_DIRECTORY: Final[str] = "structure"
TEXT_DIRECTORY: Final[str] = "text"
LANGUAGES_DIRECTORY: Final[str] = "languages"
LAYOUT_FILE: Final[str] = "layout.json"
LAYOUT_SCHEMA: Final[int] = 1
_PAGE_SUFFIX: Final[str] = ".html"
_UTF_8: Final[str] = "utf-8"


class LanguageRootsError(ValueError):
    """The language roots cannot be stored as one structure, or a stored form cannot be read."""


@dataclass(frozen=True)
class Layout:
    """How each path of the site is stored.

    Attributes:
        languages: The languages, in the order their strings were factored.
        pages: Paths stored as a structure and composed with a language's text.
        shared: Paths stored once because every language has the same bytes.
        language_files: For each language, the paths stored for it alone.
    """

    languages: tuple[str, ...]
    pages: tuple[str, ...]
    shared: tuple[str, ...]
    language_files: Mapping[str, tuple[str, ...]]

    def document(self) -> dict[str, object]:
        """Return the layout as the JSON document :func:`read_layout` reads."""
        return {
            "schema": LAYOUT_SCHEMA,
            "languages": list(self.languages),
            "pages": list(self.pages),
            "shared": list(self.shared),
            "language_files": {language: list(paths) for language, paths in self.language_files.items()},
        }


def text_file(language: str) -> str:
    """Return the path, inside the stored form, of one language's strings."""
    return f"{TEXT_DIRECTORY}/{language}.json"


def _inside(root: Path, relative: str) -> Path:
    """Return ``relative`` under ``root``, refusing a path that is absolute or climbs out."""
    path = PurePosixPath(relative)
    if path.is_absolute() or not path.parts or ".." in path.parts or "\\" in relative or ":" in path.parts[0]:
        raise LanguageRootsError(f"not a path inside a documentation root: {relative!r}")
    return root.joinpath(*path.parts)


def _write(target: Path, content: bytes) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)


def _page_text(content: bytes) -> str | None:
    """Return a page's text when storing it as text gives the same bytes back."""
    try:
        text = content.decode(_UTF_8)
    except UnicodeDecodeError:
        return None
    return text if text.encode(_UTF_8) == content else None


#: What a page's own build ends each of its lines with. Sphinx writes a page as
#: text, so the terminator is the one the writing platform uses.
_PLATFORM_TERMINATOR: Final[str] = os.linesep


def _without_terminators(page: str) -> str:
    """Return one page's text with the writing platform's line terminators taken off.

    The stored form has to be the same bytes whichever platform compiled it, and
    the terminator is the one thing in a page that is not: the same compile
    writes ``\\r\\n`` on Windows where it writes ``\\n`` on Linux. So a page is
    stored with one line feed per line and nothing of the platform that wrote
    it, and :func:`_with_terminators` puts the composing platform's own back.
    """
    return page.replace("\r\n", "\n")


def _with_terminators(page: str) -> str:
    """Return one page's text ended as this platform's own build ends its lines."""
    return page if _PLATFORM_TERMINATOR == "\n" else page.replace("\n", _PLATFORM_TERMINATOR)


def factor_roots(files: Mapping[str, Mapping[str, Path]], destination: Path) -> Layout:
    """Write the same site in every language as one structure and each language's text.

    Args:
        files: For each language, the site's files by their path inside the root.
            The first language is the one the others are compared with.
        destination: An empty or absent directory to write the stored form into.

    Returns:
        How each path was stored.

    Raises:
        LanguageRootsError: If no language is given, ``destination`` is not empty,
            or a page exists in some languages and not in others.
    """
    languages = tuple(files)
    if not languages:
        raise LanguageRootsError("no language root was given")
    if destination.exists() and any(destination.iterdir()):
        raise LanguageRootsError(f"the destination is not empty: {destination}")
    every_path = sorted({path for by_path in files.values() for path in by_path})
    text = LanguageText(languages)
    pages: list[str] = []
    shared: list[str] = []
    language_files: dict[str, list[str]] = {language: [] for language in languages}
    uneven: list[str] = []
    for path in every_path:
        sources = [files[language].get(path) for language in languages]
        present = [source for source in sources if source is not None]
        if len(present) < len(languages):
            if path.endswith(_PAGE_SUFFIX):
                uneven.append(path)
                continue
            for language, source in zip(languages, sources, strict=True):
                if source is not None:
                    _write(_inside(destination / LANGUAGES_DIRECTORY / language, path), source.read_bytes())
                    language_files[language].append(path)
            continue
        contents = [source.read_bytes() for source in present]
        texts = [_page_text(content) for content in contents] if path.endswith(_PAGE_SUFFIX) else []
        page_texts = [_without_terminators(page) for page in texts if page is not None]
        if page_texts and len(page_texts) == len(contents):
            if all(page == page_texts[0] for page in page_texts[1:]):
                _write(_inside(destination / STRUCTURE_DIRECTORY, path), page_texts[0].encode(_UTF_8))
                shared.append(path)
                continue
            structure = text.structure(factor_page(page_texts))
            _write(_inside(destination / STRUCTURE_DIRECTORY, path), structure.encode(_UTF_8))
            pages.append(path)
            continue
        if all(content == contents[0] for content in contents[1:]):
            _write(_inside(destination / STRUCTURE_DIRECTORY, path), contents[0])
            shared.append(path)
            continue
        for language, content in zip(languages, contents, strict=True):
            _write(_inside(destination / LANGUAGES_DIRECTORY / language, path), content)
            language_files[language].append(path)
    if uneven:
        raise LanguageRootsError(
            f"{len(uneven)} page(s) exist in some languages and not in others, first {uneven[0]}; "
            "every language is built from the same pages"
        )
    for language in languages:
        strings = json.dumps(text.strings[language], ensure_ascii=False, separators=(",", ":"))
        _write(destination / text_file(language), strings.encode(_UTF_8))
    layout = Layout(
        languages=languages,
        pages=tuple(pages),
        shared=tuple(shared),
        language_files={language: tuple(paths) for language, paths in language_files.items()},
    )
    _write(destination / LAYOUT_FILE, (json.dumps(layout.document(), indent=1) + "\n").encode(_UTF_8))
    return layout


def asset_cache_key(content: bytes) -> str:
    """Return the cache key a built page carries for an asset of these bytes.

    The same key Sphinx appends to every asset reference
    (``sphinx.builders.html._assets``): a CRC-32 of the file's bytes with
    carriage returns removed, and empty for empty content. A file stored once
    per language has one key per language, so the key in a page is a string
    that depends on the language exactly as a translated label does.
    """
    stripped = content.translate(None, b"\r")
    return f"{zlib.crc32(stripped):08x}" if stripped else ""


def _rendered_language_file(content: bytes, slots: CompileSlots, language_index: int, path: str) -> bytes:
    """Return one language's bytes for a compiled file that is not a page.

    A file that is not a page has no markup for a position to be read from, so
    only a mark whose strings are placed as they were recorded can appear in
    one: a creation site that wrote them for that file's syntax, or a template
    that interpolated them without escaping, which is how Sphinx renders the
    theme's own files.
    """
    text = content.decode(_UTF_8)
    refuse_stray_delimiters(text, path)
    pieces: list[str] = []
    position = 0
    for mark in MARK.finditer(text):
        rendering, values = slots.strings(int(mark.group(1), 36))
        if rendering not in {Rendering.VERBATIM, Rendering.TEMPLATE}:
            raise LanguageRootsError(
                f"{path} is not a page and carries a mark whose strings a docutils writer owns; "
                "a file written outside a page must record its strings in its own syntax"
            )
        pieces.extend((text[position : mark.start()], values[language_index]))
        position = mark.end()
    pieces.append(text[position:])
    return "".join(pieces).encode(_UTF_8)


def store_compiled_root(
    compiled: Mapping[str, Path],
    slots: CompileSlots,
    destination: Path,
    *,
    language_files: Mapping[str, Mapping[str, Path]] | None = None,
) -> Layout:
    """Write one compiled site as the structure and each language's text.

    The stored form is the same one :func:`factor_roots` writes from several
    built roots, and :func:`compose_root` reads either without knowing which
    wrote it. What differs is where the slots come from: here each is a mark the
    one compile recorded (:mod:`dev.docs.compile_slots`), so no alignment is
    guessed and a slot's strings are what the compile resolved.

    Args:
        compiled: The compiled site's files by their path inside the root.
        slots: The marks the compile recorded, naming the languages in the
            order their strings are stored.
        destination: An empty or absent directory to write the stored form into.
        language_files: For each language, files that belong to that language
            alone and are not pages, such as its search index. A path given
            here is stored per language even when the compile also wrote it.

    Returns:
        How each path was stored.

    Raises:
        LanguageRootsError: If ``destination`` is not empty, a file that is not
            a page carries a mark it cannot answer, or a page carries a slot
            delimiter of its own.
    """
    languages = slots.languages
    if destination.exists() and any(destination.iterdir()):
        raise LanguageRootsError(f"the destination is not empty: {destination}")
    extra = language_files or {language: {} for language in languages}
    if set(extra) != set(languages):
        raise LanguageRootsError(f"the per-language files must name exactly {list(languages)}")
    text = LanguageText(languages)
    own: dict[str, list[str]] = {language: [] for language in languages}
    keys: dict[str, tuple[str, ...]] = {}
    for path in sorted({name for language in languages for name in extra[language]}):
        written: list[str] = []
        for language in languages:
            source = extra[language].get(path)
            if source is None:
                continue
            content = source.read_bytes()
            _write(_inside(destination / LANGUAGES_DIRECTORY / language, path), content)
            own[language].append(path)
            written.append(asset_cache_key(content))
        if len(written) == len(languages) and path in compiled:
            name = PurePosixPath(path).name
            keys[f"{name}?v={asset_cache_key(compiled[path].read_bytes())}"] = tuple(written)
    per_language = {path for language in languages for path in own[language]}
    pages: list[str] = []
    shared: list[str] = []
    # Every file that is not a page is stored first, and the pages after it. A
    # page links such a file by the cache key of the bytes the compile wrote, so
    # each key the pages have to answer with one per language has to be known
    # before the first page is factored.
    page_paths: list[str] = []
    for path in sorted(compiled):
        if path in per_language:
            continue
        content = compiled[path].read_bytes()
        if path.endswith(_PAGE_SUFFIX) and _page_text(content) is not None:
            page_paths.append(path)
            continue
        decoded = content.decode(_UTF_8, errors="replace")
        if MARK_OPEN not in decoded:
            refuse_escaped_marks(decoded, path)
            _write(_inside(destination / STRUCTURE_DIRECTORY, path), content)
            shared.append(path)
            continue
        written = []
        for index, language in enumerate(languages):
            rendered = _rendered_language_file(content, slots, index, path)
            _write(_inside(destination / LANGUAGES_DIRECTORY / language, path), rendered)
            own[language].append(path)
            written.append(asset_cache_key(rendered))
        keys[f"{PurePosixPath(path).name}?v={asset_cache_key(content)}"] = tuple(written)
    for path in page_paths:
        content = compiled[path].read_bytes()
        text_of_page = _page_text(content)
        if text_of_page is None:  # pragma: no cover - the page text was read once already
            raise LanguageRootsError(f"{path} stopped being a page between the two passes")
        # A mark a creation site wrote into JavaScript reaches the written page
        # as its own escape, which is the delimiter and has to be read as one
        # before the page is factored (:func:`read_escaped_marks`).
        page = read_escaped_marks(_without_terminators(text_of_page))
        factored: list[str | tuple[str, ...]] = []
        for part in _factor_compiled_page(page, slots, path=path):
            factored.extend(_cache_key_slots(part, keys) if isinstance(part, str) else [part])
        if not any(isinstance(part, tuple) for part in factored):
            _write(_inside(destination / STRUCTURE_DIRECTORY, path), page.encode(_UTF_8))
            shared.append(path)
            continue
        structure = text.structure(factored)
        _write(_inside(destination / STRUCTURE_DIRECTORY, path), structure.encode(_UTF_8))
        pages.append(path)
    for language in languages:
        strings = json.dumps(text.strings[language], ensure_ascii=False, separators=(",", ":"))
        _write(destination / text_file(language), strings.encode(_UTF_8))
    layout = Layout(
        languages=languages,
        pages=tuple(pages),
        shared=tuple(shared),
        language_files={language: tuple(sorted(paths)) for language, paths in own.items()},
    )
    _write(destination / LAYOUT_FILE, (json.dumps(layout.document(), indent=1) + "\n").encode(_UTF_8))
    return layout


def _string_list(value: object, where: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise LanguageRootsError(f"{where} must be a list of strings")
    strings = tuple(item for item in value if isinstance(item, str))
    if len(strings) != len(value):
        raise LanguageRootsError(f"{where} must be a list of strings")
    return strings


def read_layout(stored: Path) -> Layout:
    """Read how each path is stored from a stored form's layout file."""
    try:
        document = json.loads((stored / LAYOUT_FILE).read_text(encoding=_UTF_8))
    except (OSError, ValueError) as error:
        raise LanguageRootsError(f"no readable layout in {stored}: {error}") from None
    if not isinstance(document, dict) or document.get("schema") != LAYOUT_SCHEMA:
        raise LanguageRootsError(f"{stored / LAYOUT_FILE} is not a schema {LAYOUT_SCHEMA} layout")
    languages = _string_list(document.get("languages"), "languages")
    per_language = document.get("language_files")
    if not isinstance(per_language, dict) or set(per_language) != set(languages):
        raise LanguageRootsError("language_files must name exactly the layout's languages")
    return Layout(
        languages=languages,
        pages=_string_list(document.get("pages"), "pages"),
        shared=_string_list(document.get("shared"), "shared"),
        language_files={language: _string_list(per_language[language], language) for language in languages},
    )


def read_text(stored: Path, language: str) -> Sequence[str]:
    """Read one language's strings from a stored form."""
    try:
        strings = json.loads((stored / text_file(language)).read_text(encoding=_UTF_8))
    except (OSError, ValueError) as error:
        raise LanguageRootsError(f"no readable text for {language} in {stored}: {error}") from None
    return _string_list(strings, f"the text of {language}")


def _stored(stored: Path, kind: str, language: str, path: str, strings: Sequence[str]) -> bytes:
    if kind == LANGUAGES_DIRECTORY:
        return _inside(stored / LANGUAGES_DIRECTORY / language, path).read_bytes()
    content = _inside(stored / STRUCTURE_DIRECTORY, path).read_bytes()
    if kind == TEXT_DIRECTORY:
        return _with_terminators(compose_page(content.decode(_UTF_8), strings)).encode(_UTF_8)
    # A page every language has the same bytes of is stored once, and stored as
    # a page: without the terminators of the platform that wrote it.
    page = _page_text(content) if path.endswith(_PAGE_SUFFIX) else None
    return content if page is None else _with_terminators(page).encode(_UTF_8)


def _kinds(layout: Layout, language: str) -> dict[str, str]:
    """Return how each path of one language's site is stored: composed, stored once, or its own."""
    return {
        **dict.fromkeys(layout.pages, TEXT_DIRECTORY),
        **dict.fromkeys(layout.shared, STRUCTURE_DIRECTORY),
        **dict.fromkeys(layout.language_files[language], LANGUAGES_DIRECTORY),
    }


#: Every private-use character the compile's own artefacts are delimited by: a
#: structure's slots and a compiled page's marks. A composed page is what a
#: reader is served, so none of them may still be in it.
_RESERVED: Final[tuple[tuple[str, str], ...]] = (
    (SLOT_OPEN, "an opening slot"),
    (SLOT_CLOSE, "a closing slot"),
    (MARK_OPEN, "an opening mark"),
    (MARK_CLOSE, "a closing mark"),
)


def _refuse_reserved(language: str, path: str, content: bytes) -> None:
    """Refuse a composed page still carrying a slot or mark delimiter.

    Composition replaces every slot the structure names with one language's
    string, and the strings were factored out of a page whose marks were all
    read. So a delimiter left in a composed page means one of the two was not:
    the page would reach a reader carrying a private-use character where its
    text belongs, which is the one failure of this mechanism nothing downstream
    could notice.

    Raises:
        LanguageRootsError: If the page carries any of them.
    """
    text = content.decode(_UTF_8, errors="replace")
    for delimiter, name in _RESERVED:
        at = text.find(delimiter)
        if at >= 0:
            raise LanguageRootsError(
                f"the composed {language} page {path} still carries {name} delimiter, "
                f"around {text[max(at - 60, 0) : at + 20]!r}"
            )


def compose_root(stored: Path, language: str, destination: Path) -> None:
    """Write one language's whole site from the stored form into ``destination``.

    Raises:
        LanguageRootsError: If the stored form holds no such language, or a
            composed page still carries a slot or mark delimiter.
    """
    layout = read_layout(stored)
    if language not in layout.languages:
        raise LanguageRootsError(f"the stored form holds {list(layout.languages)}, not {language}")
    strings = read_text(stored, language)
    for path, kind in _kinds(layout, language).items():
        content = _stored(stored, kind, language, path, strings)
        if path.endswith(_PAGE_SUFFIX):
            _refuse_reserved(language, path, content)
        _write(_inside(destination, path), content)


def differences(stored: Path, files: Mapping[str, Mapping[str, Path]]) -> list[str]:
    """Return every built file the stored form does not give back byte for byte.

    Args:
        stored: The stored form :func:`factor_roots` wrote.
        files: For each language, the built site's files by their path inside the root.

    Returns:
        One line per language and path that is missing from the stored form,
        extra in it, or composed to different bytes. Empty when the stored form
        is exactly the built roots.
    """
    layout = read_layout(stored)
    found: list[str] = []
    if set(files) != set(layout.languages):
        found.append(f"languages: stored {sorted(layout.languages)}, built {sorted(files)}")
    for language in layout.languages:
        built = files.get(language, {})
        strings = read_text(stored, language)
        kinds = _kinds(layout, language)
        found.extend(f"{language}/{path}: built but not stored" for path in sorted(set(built) - set(kinds)))
        found.extend(f"{language}/{path}: stored but not built" for path in sorted(set(kinds) - set(built)))
        for path in sorted(set(kinds) & set(built)):
            if _stored(stored, kinds[path], language, path, strings) != built[path].read_bytes():
                found.append(f"{language}/{path}: composed bytes differ from the built file")
    return found
