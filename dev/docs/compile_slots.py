"""Carry every language's text through one documentation compile.

The documentation is compiled once, and a language costs only the rendering of
its own text. Wherever a string depends on the language, the compile writes a
*mark* in place of one language's text and records every language's string for
it. A finishing pass then turns the compiled site into the stored form
:mod:`dev.docs.language_roots` writes: each mark becomes a slot of
:mod:`dev.docs.shared_structure`, and the slot's strings are what the mark
recorded.

A mark is delimited by its own private-use characters, never the stored form's,
so the two never meet: a compiled page carries marks and no slots, and a stored
structure carries slots and no marks. A compiled page that already contains a
mark delimiter is refused, exactly as a page containing a slot delimiter is.

Where a mark lands decides how its strings are written, because the bytes of a
page come from writers that escape differently. A mark therefore declares which
writer owns it rather than leaving the finishing pass to infer it from
surrounding markup, which cannot be done: ``title="d'IVA"`` written by a
generator into a raw HTML block and the same attribute written by the docutils
writer are the same bytes and need different strings.

- :attr:`Rendering.DOCUTILS` is plain text that a docutils writer will escape.
  The finishing pass renders it as that writer does at the position the mark
  reached: a text node, an attribute value, or the ``<title>`` element the
  theme's template fills through Jinja.
- :attr:`Rendering.VERBATIM` is text already in the form the creation site
  wrote it for -- a generator's own ``.. raw:: html`` block, a JSON literal --
  and is placed as it was recorded.
"""

from __future__ import annotations

import bisect
import html
import json
import re
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Final

#: Private-use characters delimiting a mark's number inside a compiled page.
#: Adjacent to, and deliberately distinct from, the stored form's slot
#: delimiters, so one artefact can never be read as the other.
MARK_OPEN: Final[str] = ""
MARK_CLOSE: Final[str] = ""

MARK: Final[re.Pattern[str]] = re.compile(f"{MARK_OPEN}([0-9a-z]+){MARK_CLOSE}")
_DIGITS: Final[str] = "0123456789abcdefghijklmnopqrstuvwxyz"

#: The characters a docutils HTML writer replaces in text and in attribute
#: values (``docutils.writers._html_base.HTMLTranslator.special_characters``).
_DOCUTILS_SPECIAL: Final[dict[int, str]] = {
    ord("&"): "&amp;",
    ord("<"): "&lt;",
    ord('"'): "&quot;",
    ord(">"): "&gt;",
    ord("@"): "&#64;",
}
#: The whitespace a docutils HTML writer folds into a space inside an attribute
#: value (``HTMLTranslator.attval``).
_ATTRIBUTE_WHITESPACE: Final[re.Pattern[str]] = re.compile("[\n\r\t\v\f]")

#: One piece of a page: a comment, a tag, or the text between two tags.
_PIECE: Final[re.Pattern[str]] = re.compile(r"<!--.*?-->|<[^>]*>|[^<]+", re.DOTALL)
#: An attribute's name and its double-quoted value inside one tag.
_ATTRIBUTE: Final[re.Pattern[str]] = re.compile(r'(\s[^\s"=<>/]+=")([^"]*)')
_TAG_NAME: Final[re.Pattern[str]] = re.compile(r"</?([A-Za-z][^\s/>]*)")


class CompileSlotsError(ValueError):
    """A mark cannot be recorded, or a compiled page cannot be factored."""


class Rendering(StrEnum):
    """Which writer owns a mark's strings, and therefore how they are written."""

    DOCUTILS = "docutils"
    VERBATIM = "verbatim"


class Position(StrEnum):
    """Where in a page's markup one mark occurrence sits."""

    TEXT = "text"
    ATTRIBUTE = "attribute"
    TITLE = "title"
    MARKUP = "markup"


def _number(value: int) -> str:
    """Return a mark or slot number in the compact base the delimiters carry."""
    digits = ""
    while True:
        value, remainder = divmod(value, len(_DIGITS))
        digits = _DIGITS[remainder] + digits
        if not value:
            return digits


def _docutils_text(value: str) -> str:
    """Return one string as a docutils writer writes it into a text node."""
    return value.translate(_DOCUTILS_SPECIAL)


def _docutils_attribute(value: str) -> str:
    """Return one string as a docutils writer writes it into an attribute value."""
    return _ATTRIBUTE_WHITESPACE.sub(" ", value).translate(_DOCUTILS_SPECIAL)


def _template_title(value: str) -> str:
    """Return one string as the theme's ``<title>`` carries it.

    The template is handed the title already written as HTML, then strips its
    tags and escapes the result through Jinja. Stripping unescapes what the
    docutils writer escaped and folds runs of whitespace, so what reaches the
    page is the plain string, whitespace folded, escaped the way
    ``markupsafe`` escapes rather than the way docutils does.
    """
    return html.escape(" ".join(value.split()), quote=False).replace('"', "&#34;").replace("'", "&#39;")


#: What the docutils smart-quotes transform is asked to educate: quotation
#: marks, dashes and ellipses (``docutils.transforms.universal.SmartQuotes``'s
#: own ``smartquotes_action``, which Sphinx leaves at its default).
_SMARTQUOTES_ACTION: Final[str] = "qDe"


def _educated(value: str, language: str) -> str:
    """Return one string with the typography the language's own build gives it.

    Sphinx educates quotation marks, dashes and ellipses in every text block
    before the writer sees it, and which quotation marks it uses depends on the
    language: a language's build writes its own. A mark holds no quotation mark
    for that transform to find, so each language's string is educated here
    instead, in its own language. Without this an apostrophe reaches the page as
    ``'`` where the build wrote ``’``, which was 1,847 of the differences the
    first measured compile reported in English alone.

    A string recorded verbatim is not educated: it is already in the form its
    creation site wrote, and a generator's own raw HTML never met the transform.
    """
    from docutils.utils import smartquotes

    educated = smartquotes.educate_tokens([("text", value)], attr=_SMARTQUOTES_ACTION, language=language)
    return "".join(str(piece) for piece in educated)


def _written(rendering: Rendering, position: Position, value: str, language: str) -> str:
    """Return one language's string as the page carries it at *position*."""
    if rendering is Rendering.VERBATIM:
        return value
    educated = _educated(value, language)
    if position is Position.TEXT:
        return _docutils_text(educated)
    if position is Position.ATTRIBUTE:
        return _docutils_attribute(educated)
    if position is Position.TITLE:
        return _template_title(educated)
    raise CompileSlotsError(
        f"a mark whose strings docutils owns reached page markup rather than text: {value!r}. "
        "A creation site writing markup itself must record its strings verbatim."
    )


@dataclass
class CompileSlots:
    """Every mark one compile recorded, and each language's string for it.

    Attributes:
        languages: The languages the compile carries, in the order their
            strings are stored.
        renderings: Which writer owns each mark's strings, by mark number.
        values: Each mark's string in every language, by mark number.
    """

    languages: tuple[str, ...]
    renderings: list[Rendering] = field(default_factory=list)
    values: list[tuple[str, ...]] = field(default_factory=list)
    _numbers: dict[tuple[Rendering, tuple[str, ...]], int] = field(default_factory=dict)

    def mark(self, rendering: Rendering, values: Sequence[str]) -> str:
        """Return the mark that reads *values* across the languages, recording it once.

        Args:
            rendering: Which writer owns the strings.
            values: One string per language, in :attr:`languages` order.

        Returns:
            The mark to write in place of the language's text.

        Raises:
            CompileSlotsError: If a string is given for the wrong number of
                languages, or itself contains a mark delimiter.
        """
        if len(values) != len(self.languages):
            raise CompileSlotsError(
                f"a mark needs one string per language; got {len(values)} for {len(self.languages)}"
            )
        strings = tuple(values)
        for value in strings:
            if MARK_OPEN in value or MARK_CLOSE in value:
                raise CompileSlotsError("a recorded string contains a character reserved for mark delimiters")
        key = (rendering, strings)
        number = self._numbers.get(key)
        if number is None:
            number = self._numbers[key] = len(self.values)
            self.renderings.append(rendering)
            self.values.append(strings)
        return f"{MARK_OPEN}{_number(number)}{MARK_CLOSE}"

    def derive(self, mark: str, rendering: Rendering, transform: Callable[[str], str]) -> str:
        """Return a mark reading each string of *mark* put through *transform*.

        What a creation site does to a resolved string -- escaping it for the
        syntax it writes, folding its whitespace, wrapping it -- has to happen
        to every language's string rather than to the mark, which the
        transformation would leave untouched.

        Args:
            mark: A mark this compile recorded.
            rendering: Which writer owns the transformed strings.
            transform: A callable from one string to one string.

        Returns:
            The new mark.

        Raises:
            CompileSlotsError: If *mark* is not one whole mark of this compile.
        """
        matched = MARK.fullmatch(mark)
        if matched is None:
            raise CompileSlotsError(f"not one whole mark: {mark!r}")
        number = int(matched.group(1), len(_DIGITS))
        if number >= len(self.values):
            raise CompileSlotsError(f"mark {number} was never recorded by this compile")
        return self.mark(rendering, tuple(str(transform(value)) for value in self.values[number]))

    def resolved(self, value: str, language: int) -> str:
        """Return *value* with every mark inside it read in one language.

        A string a mark is built from can itself hold marks: a chrome string
        takes the name of a command family as an argument, and a fragment
        rendered per language carries that language's chrome inside it. Such a
        string is not a mark, so it cannot stand on a page, and it cannot be
        recorded as one language's string either while it still names the other
        languages. Reading its marks in the language being recorded is what
        makes composition one operation rather than a special case per site.

        Args:
            value: A string that may contain marks.
            language: The language's index in :attr:`languages`.

        Returns:
            The string with each mark replaced by that language's string.
        """
        if MARK_OPEN not in value:
            return value
        return MARK.sub(lambda found: self.strings(int(found.group(1), len(_DIGITS)))[1][language], value)

    def strings(self, number: int) -> tuple[Rendering, tuple[str, ...]]:
        """Return one mark's owning writer and its string in every language."""
        if number >= len(self.values):
            raise CompileSlotsError(f"the compile recorded {len(self.values)} mark(s), not {number + 1}")
        return self.renderings[number], self.values[number]

    def document(self) -> dict[str, object]:
        """Return the marks as the JSON document :func:`read_slots` reads."""
        return {
            "schema": SLOTS_SCHEMA,
            "languages": list(self.languages),
            "marks": [
                {"rendering": rendering.value, "values": list(values)}
                for rendering, values in zip(self.renderings, self.values, strict=True)
            ],
        }

    def write(self, path: Path) -> None:
        """Write the marks where the finishing pass reads them."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.document(), ensure_ascii=False), encoding="utf-8")


#: The schema of the recorded marks, which the compile writes and the finishing
#: pass reads. They run in different processes: the marks are created inside the
#: ``sphinx-build`` child, and the site is factored by the driver that ran it.
SLOTS_SCHEMA: Final[int] = 1

#: Where inside the compiled site the compile leaves its recorded marks.
SLOTS_FILE: Final[str] = ".compile-slots.json"


def read_slots(path: Path) -> CompileSlots:
    """Read the marks one compile recorded.

    Raises:
        CompileSlotsError: If the document is absent, unreadable, or not of
            this schema.
    """
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise CompileSlotsError(f"no readable compile marks at {path}: {error}") from None
    if not isinstance(document, dict) or document.get("schema") != SLOTS_SCHEMA:
        raise CompileSlotsError(f"{path} is not a schema {SLOTS_SCHEMA} mark record")
    languages = document.get("languages")
    marks = document.get("marks")
    if not isinstance(languages, list) or not all(isinstance(item, str) for item in languages):
        raise CompileSlotsError(f"{path} must declare its languages")
    if not isinstance(marks, list):
        raise CompileSlotsError(f"{path} must declare its marks")
    slots = CompileSlots(tuple(str(language) for language in languages))
    for entry in marks:
        if not isinstance(entry, dict) or not isinstance(entry.get("values"), list):
            raise CompileSlotsError(f"{path} holds a mark with no strings")
        slots.mark(Rendering(entry.get("rendering")), [str(value) for value in entry["values"]])
    return slots


# ── The compile's one active record ──────────────────────────────────────────
# The resolvers that put a language's text on a page -- the chrome resolver, the
# generated references, the site chrome -- are called from deep inside Sphinx's
# own call stack, through configuration values and builder hooks that carry no
# argument of ours. One active record, set for the compile and cleared after it,
# is how they reach it; outside a multilingual compile there is none and every
# resolver renders one language exactly as it does today.
_ACTIVE: CompileSlots | None = None


def activate(languages: Sequence[str]) -> CompileSlots:
    """Record every language's text for this compile, and return the record."""
    global _ACTIVE
    if not languages:
        raise CompileSlotsError("a multilingual compile needs at least one language")
    _ACTIVE = CompileSlots(tuple(languages))
    return _ACTIVE


def deactivate() -> None:
    """Stop recording, so later work in this process renders one language."""
    global _ACTIVE
    _ACTIVE = None


def active() -> CompileSlots | None:
    """Return this compile's mark record, or None outside a multilingual compile."""
    return _ACTIVE


def escape(value: str, *, quote: bool = True) -> str:
    """Return *value* escaped for a generator's own HTML, marks included.

    A generator that writes HTML escapes what it puts in it. Escaping a mark
    does nothing, because a mark holds no character HTML reserves, so the
    escaping has to reach the strings instead. This is :func:`html.escape` for
    ordinary text and the same escaping applied to every language's string for a
    mark, recorded as the generator's own verbatim markup.

    ``quote`` defaults as :func:`html.escape` defaults, because every call site
    is a call to :func:`html.escape` that had to become slot-aware: a different
    default here silently un-escapes an apostrophe at each of them.
    """
    slots = _ACTIVE
    if slots is None or MARK_OPEN not in value:
        return html.escape(value, quote=quote)
    return "".join(
        slots.derive(piece, Rendering.VERBATIM, lambda text: html.escape(text, quote=quote))
        if MARK.fullmatch(piece)
        else html.escape(piece, quote=quote)
        for piece in _split_marks(value)
    )


def _split_marks(value: str) -> Iterator[str]:
    """Yield *value* as its marks and the text between them."""
    position = 0
    for found in MARK.finditer(value):
        if found.start() > position:
            yield value[position : found.start()]
        yield found.group()
        position = found.end()
    if position < len(value):
        yield value[position:]


# ── The finishing pass ───────────────────────────────────────────────────────


def markup_contexts(page: str) -> list[tuple[int, str]]:
    """Return where each stretch of one page's markup begins, and what kind it is.

    The kinds are the ones a difference is read in: ``text:<element>`` for a
    text node, ``title-text`` for the ``<title>`` element's own text,
    ``attr:<element>.<name>`` for a double-quoted attribute value, and
    ``markup:<element>`` for a tag's own bytes. Starts are in order, so a
    position is found by the last start at or before it.
    """
    spans: list[tuple[int, str]] = []
    in_title = False
    element = ""
    for piece in _PIECE.finditer(page):
        text = piece.group()
        if text[0] != "<":
            spans.append((piece.start(), "title-text" if in_title else f"text:{element}"))
            continue
        name = _TAG_NAME.match(text)
        tag = name.group(1).lower() if name is not None else "?"
        if tag == "title":
            in_title = not text.startswith("</")
        if not text.startswith("</"):
            element = tag
        last = piece.start()
        for attribute in _ATTRIBUTE.finditer(text):
            spans.append((piece.start() + attribute.start(2), f"attr:{tag}.{attribute.group(1).strip()[:-2]}"))
            last = piece.start() + attribute.end()
        spans.append((last, f"markup:{tag}"))
    return spans


def context_at(starts: Sequence[int], contexts: Sequence[tuple[int, str]], offset: int) -> str:
    """Return the kind of markup one offset of a page sits in.

    ``starts`` is ``[start for start, _ in contexts]``, taken once by the
    caller: a page of thirty megabytes is asked about tens of thousands of
    offsets, and rebuilding the list per question is what made the first
    measurement of the four roots take longer than the builds.
    """
    index = bisect.bisect_right(starts, offset) - 1
    return contexts[index][1] if index >= 0 else "unknown"


def mark_positions(page: str) -> list[tuple[re.Match[str], Position]]:
    """Return every mark one compiled page carries, and where in its markup it sits.

    Args:
        page: One compiled page.

    Returns:
        Each mark's match, in order, with the position whose writer decides how
        its strings are written.
    """
    found: list[tuple[re.Match[str], Position]] = []
    in_title = False
    for piece in _PIECE.finditer(page):
        text = piece.group()
        if text[0] != "<":
            found.extend(
                (mark, Position.TITLE if in_title else Position.TEXT)
                for mark in MARK.finditer(page, piece.start(), piece.end())
            )
            continue
        if (name := _TAG_NAME.match(text)) is not None and name.group(1).lower() == "title":
            in_title = not text.startswith("</")
        spans = [
            (piece.start() + attribute.start(2), piece.start() + attribute.end(2))
            for attribute in _ATTRIBUTE.finditer(text)
        ]
        for mark in MARK.finditer(page, piece.start(), piece.end()):
            inside = any(start <= mark.start() and mark.end() <= end for start, end in spans)
            found.append((mark, Position.ATTRIBUTE if inside else Position.MARKUP))
    return found


def factor_page(page: str, slots: CompileSlots) -> list[str | tuple[str, ...]]:
    """Return one compiled page as shared text and, per slot, each language's string.

    Args:
        page: One compiled page, carrying the compile's marks.
        slots: The marks the compile recorded.

    Returns:
        The page in order: a ``str`` is text every language shares, a tuple
        holds what each language reads at that point.

    Raises:
        CompileSlotsError: If the page names a mark the compile never recorded,
            or a mark reached a position its writer cannot write.
    """
    factored: list[str | tuple[str, ...]] = []
    position = 0
    for mark, where in mark_positions(page):
        if mark.start() > position:
            factored.append(page[position : mark.start()])
        rendering, values = slots.strings(int(mark.group(1), len(_DIGITS)))
        factored.append(
            tuple(
                _written(rendering, where, value, language)
                for language, value in zip(slots.languages, values, strict=True)
            )
        )
        position = mark.end()
    if position < len(page):
        factored.append(page[position:])
    return factored


def cache_key_slots(page: str, keys: Mapping[str, Sequence[str]]) -> list[str | tuple[str, ...]]:
    """Return one page with each language-dependent asset's cache key as a slot.

    A file whose content depends on the language is stored once per language
    under one path, and every page links it with the cache key of the bytes the
    compile wrote. Each language's bytes have their own key, so the key in the
    page is a slot like any other translated string -- there is nothing a single
    compile could have written there, because the keys only exist once the
    per-language files do.

    Args:
        page: The page, or a stretch of one, to replace keys in.
        keys: For each ``<name>?v=<key>`` reference the compiled page carries,
            that reference's key in every language, in the stored order.

    Returns:
        The page in order, as :func:`factor_page` returns it.
    """
    pattern = re.compile("|".join(re.escape(reference) for reference in sorted(keys))) if keys else None
    if pattern is None:
        return [page]
    factored: list[str | tuple[str, ...]] = []
    position = 0
    for found in pattern.finditer(page):
        if found.start() > position:
            factored.append(page[position : found.start()])
        reference = found.group()
        name = reference.partition("?v=")[0]
        factored.append(tuple(f"{name}?v={key}" for key in keys[reference]))
        position = found.end()
    if position < len(page):
        factored.append(page[position:])
    return factored
