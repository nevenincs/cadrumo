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
- :attr:`Rendering.TEMPLATE` is text the theme's Jinja templates write. Sphinx
  renders them without autoescaping, and nothing a template writes ever met the
  smart-quotes transform, so the string reaches the page as it was authored
  where a docutils writer would have escaped it and published a typographic
  apostrophe. The ``<title>`` element is the exception its template escapes.
- :attr:`Rendering.VERBATIM` is text already in the form the creation site
  wrote it for -- a generator's own ``.. raw:: html`` block, a JSON literal --
  and is placed as it was recorded.
- :attr:`Rendering.PLAIN` is plain text a docutils writer or the theme escapes
  where it lands and that no build ever educated, because it never stood in a
  text block for the smart-quotes transform to find. An explicit toctree entry
  title and a toctree caption are attributes of the toctree node; Sphinx's own
  translated words are put into a finished page by the HTML writer long after
  the transforms ran. Which strings those are is a property of the string and
  not of where it lands, because the regions a title reaches -- the navigation,
  a body toctree, the relation links -- also carry titles a page's own educated
  heading supplied.
- :attr:`Rendering.MESSAGE` is one translatable message of an authored page,
  whose translation carries inline markup, links and roles and is therefore
  recorded already rendered. One message reaches more than one writer -- a
  page title stands in its own heading, in the ``<title>`` element and in the
  navigation of every page -- so a message mark records two forms: the
  rendered markup, and the plain text that markup reads as. The position
  decides which form the page carries.
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
    TEMPLATE = "template"
    VERBATIM = "verbatim"
    MESSAGE = "message"
    PLAIN = "plain"


class Position(StrEnum):
    """Where in a page's markup one mark occurrence sits."""

    TEXT = "text"
    ATTRIBUTE = "attribute"
    TITLE = "title"
    MARKUP = "markup"
    #: Inside a toctree in a page's own body, written by the docutils writer.
    #: What stands there is a page's title and never a message's own markup,
    #: which is the one thing this position says that :attr:`TEXT` does not.
    ENTRY_TEXT = "entry-text"
    ENTRY_ATTRIBUTE = "entry-attribute"
    #: Inside the theme's navigation tree, which carries the same titles. Furo
    #: hands the writer's toctree HTML to BeautifulSoup and writes ``str(soup)``
    #: back, which unescapes what the writer escaped (``&quot;`` and ``&#64;``
    #: included) and escapes the result minimally.
    NAVIGATION_TEXT = "navigation-text"
    NAVIGATION_ATTRIBUTE = "navigation-attribute"


def _number(value: int) -> str:
    """Return a mark or slot number in the compact base the delimiters carry."""
    digits = ""
    while True:
        value, remainder = divmod(value, len(_DIGITS))
        digits = _DIGITS[remainder] + digits
        if not value:
            return digits


def mark_number(mark: str) -> int:
    """Return the number one whole mark carries.

    Raises:
        CompileSlotsError: If *mark* is not one whole mark.
    """
    matched = MARK.fullmatch(mark)
    if matched is None:
        raise CompileSlotsError(f"not one whole mark: {mark!r}")
    return int(matched.group(1), len(_DIGITS))


def _docutils_text(value: str) -> str:
    """Return one string as a docutils writer writes it into a text node."""
    return value.translate(_DOCUTILS_SPECIAL)


def _docutils_attribute(value: str) -> str:
    """Return one string as a docutils writer writes it into an attribute value."""
    return _ATTRIBUTE_WHITESPACE.sub(" ", value).translate(_DOCUTILS_SPECIAL)


def _jinja(value: str) -> str:
    """Return one string as Jinja escapes it into a template's output.

    ``markupsafe`` escapes ``&``, ``<`` and ``>`` like docutils does, leaves
    ``@`` alone, and writes both quotation marks as numeric references.
    """
    return html.escape(value, quote=False).replace('"', "&#34;").replace("'", "&#39;")


def _template_title(value: str) -> str:
    """Return one string as the theme's ``<title>`` carries it.

    The template is handed the title already written as HTML, then strips its
    tags and escapes the result through Jinja. Stripping unescapes what the
    docutils writer escaped and folds runs of whitespace, so what reaches the
    page is the plain string, whitespace folded, escaped the way
    ``markupsafe`` escapes rather than the way docutils does.
    """
    return _jinja(" ".join(value.split()))


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


def _minimal(value: str) -> str:
    """Return one string as BeautifulSoup's minimal formatter writes it.

    ``&``, ``<`` and ``>`` and nothing else, in text and in an attribute value
    alike (``bs4.formatter.HTMLFormatter`` at its default entity substitution).
    """
    return html.escape(value, quote=False)


def _resouped(markup: str) -> str:
    """Return one stretch of markup as BeautifulSoup writes it back.

    Furo hands the writer's toctree markup to BeautifulSoup and writes
    ``str(soup)``, which parses what the writer escaped and escapes the result
    minimally. For plain text that is :func:`_minimal` of the unescaped text;
    for a message carrying inline markup it is the only faithful answer,
    because the escaping has to be undone inside the elements and not around
    them. Running the same library the theme runs is what keeps the two equal.
    """
    from bs4 import BeautifulSoup

    return str(BeautifulSoup(markup, "html.parser"))


def plain_text(markup: str) -> str:
    """Return the plain text one stretch of rendered markup reads as.

    This is what ``markupsafe``'s ``striptags`` does to the title the theme's
    template is handed: drop the elements, unescape the text, fold the
    whitespace. It is applied to a message's rendered form so that the plain
    form is derived from the markup rather than recorded twice.
    """
    return " ".join(html.unescape(_TAGS.sub("", markup)).split())


#: One element's opening or closing tag inside a stretch of rendered markup.
_TAGS: Final[re.Pattern[str]] = re.compile(r"<[^>]*>")


def _message_written(position: Position, markup: str, plain: str) -> str:
    """Return one language's message as the page carries it at *position*.

    A message is recorded rendered, so the form the position wants is derived
    from the rendering rather than escaped from a string: the docutils writer's
    own output is already what a text node carries, the theme's ``<title>`` and
    every attribute carry the plain text, and the navigation carries the
    rendering as BeautifulSoup writes it back.
    """
    if position is Position.TEXT:
        return markup
    if position is Position.MARKUP:
        raise CompileSlotsError(f"a message reached page markup rather than text or an attribute: {plain!r}")
    if position is Position.TITLE:
        return _template_title(plain)
    if position is Position.NAVIGATION_TEXT:
        return _resouped(markup)
    if position is Position.NAVIGATION_ATTRIBUTE:
        return _minimal(plain)
    if position is Position.ENTRY_TEXT:
        return _docutils_text(plain)
    return _docutils_attribute(plain)


def _plain_written(position: Position, value: str) -> str:
    """Return one uneducated string as the page carries it at *position*.

    Escaped exactly as a docutils writer's own string is, and educated nowhere,
    because the string never stood in a text block: it is a toctree attribute,
    or a word of Sphinx's own that the writer put into a finished page.
    """
    if position in {Position.NAVIGATION_TEXT, Position.NAVIGATION_ATTRIBUTE}:
        return _minimal(value)
    if position in {Position.TEXT, Position.ENTRY_TEXT}:
        return _docutils_text(value)
    if position in {Position.ATTRIBUTE, Position.ENTRY_ATTRIBUTE}:
        return _docutils_attribute(value)
    if position is Position.TITLE:
        return _template_title(value)
    raise CompileSlotsError(f"an uneducated string reached page markup rather than text or an attribute: {value!r}")


def _written(rendering: Rendering, position: Position, value: str, plain: str | None, language: str) -> str:
    """Return one language's string as the page carries it at *position*."""
    if rendering is Rendering.VERBATIM:
        return value
    if rendering is Rendering.PLAIN:
        return _plain_written(position, value)
    if rendering is Rendering.MESSAGE:
        if plain is None:
            raise CompileSlotsError(f"a message mark reached the page with no plain form recorded: {value!r}")
        return _message_written(position, value, plain)
    if rendering is Rendering.TEMPLATE:
        if position is Position.TITLE:
            return _template_title(value)
        if position in {Position.TEXT, Position.ATTRIBUTE}:
            # Sphinx renders the theme's templates in an environment that does
            # not autoescape, so a chrome string a template interpolates reaches
            # the page as it was authored. Only the ``<title>``, which the
            # template escapes itself, is written otherwise.
            return value
        raise CompileSlotsError(
            f"a mark whose strings a Jinja template owns reached {position.value} markup: {value!r}. "
            "Only text and attribute values a template writes can be recorded that way."
        )
    educated = _educated(value, language)
    if position in {Position.TEXT, Position.ENTRY_TEXT}:
        return _docutils_text(educated)
    if position in {Position.ATTRIBUTE, Position.ENTRY_ATTRIBUTE}:
        return _docutils_attribute(educated)
    if position in {Position.NAVIGATION_TEXT, Position.NAVIGATION_ATTRIBUTE}:
        return _minimal(educated)
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
        plain: For a message mark, the plain text its rendering reads as in
            every language; None for every other mark, which has one form.
    """

    languages: tuple[str, ...]
    renderings: list[Rendering] = field(default_factory=list)
    values: list[tuple[str, ...]] = field(default_factory=list)
    plain: list[tuple[str, ...] | None] = field(default_factory=list)
    _numbers: dict[tuple[Rendering, tuple[str, ...]], int] = field(default_factory=dict)
    _reserved: set[int] = field(default_factory=set)

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
            self.plain.append(None)
        return f"{MARK_OPEN}{_number(number)}{MARK_CLOSE}"

    def reserve(self, rendering: Rendering) -> str:
        """Return a mark whose strings this compile will record later.

        A translatable message is rendered by the compile that carries it, so
        the mark has to exist before its strings do: the pseudo-catalogue that
        puts the mark on the page is written before Sphinx reads a document,
        and the rendering it stands for is read back when the build has
        written it (:mod:`dev.docs.message_marks`). A reserved mark is never
        shared with another string, so it is kept out of the record of marks
        taken by what they read.
        """
        number = len(self.values)
        self._reserved.add(number)
        self.renderings.append(rendering)
        self.values.append(())
        self.plain.append(None)
        return f"{MARK_OPEN}{_number(number)}{MARK_CLOSE}"

    def supply(
        self,
        mark: str,
        values: Sequence[str],
        plain: Sequence[str],
        *,
        rendering: Rendering | None = None,
    ) -> None:
        """Record what a mark reserved by :meth:`reserve` reads in every language.

        Args:
            mark: A mark this compile reserved.
            values: One rendering per language, in :attr:`languages` order.
            plain: The plain text each rendering reads as, in the same order.
            rendering: Which writer owns the strings, where that is settled
                only now. A marked message is reserved before Sphinx reads a
                document, and whether the message is an explicit toctree entry
                title -- which decides whether it ever met the smart-quotes
                transform -- is known from the read documents and not before.

        Raises:
            CompileSlotsError: If *mark* was not reserved by this compile, or
                the strings are not one per language.
        """
        matched = MARK.fullmatch(mark)
        if matched is None:
            raise CompileSlotsError(f"not one whole mark: {mark!r}")
        number = int(matched.group(1), len(_DIGITS))
        if number not in self._reserved:
            raise CompileSlotsError(f"mark {number} was not reserved by this compile")
        if len(values) != len(self.languages) or len(plain) != len(self.languages):
            raise CompileSlotsError(
                f"a mark needs one string per language; got {len(values)} rendered and "
                f"{len(plain)} plain for {len(self.languages)}"
            )
        for value in (*values, *plain):
            if MARK_OPEN in value or MARK_CLOSE in value:
                raise CompileSlotsError("a recorded string contains a character reserved for mark delimiters")
        if rendering is not None:
            self.renderings[number] = rendering
        self.values[number] = tuple(values)
        self.plain[number] = tuple(plain)
        self._reserved.discard(number)

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
        """Return one mark's owning writer and its string in every language.

        Raises:
            CompileSlotsError: If the compile recorded no such mark, or if its
                strings are still to come. A mark the compile will render later
                has no string yet, so it cannot be read as one -- which is what
                a string built from it would be asking for.
        """
        if number >= len(self.values):
            raise CompileSlotsError(f"the compile recorded {len(self.values)} mark(s), not {number + 1}")
        if number in self._reserved:
            raise CompileSlotsError(
                f"mark {number} is one this compile renders later, so it has no string to read yet; "
                "a string built from another is built from that one's own strings"
            )
        return self.renderings[number], self.values[number]

    def document(self) -> dict[str, object]:
        """Return the marks as the JSON document :func:`read_slots` reads.

        Raises:
            CompileSlotsError: If a mark was reserved and never supplied. Such
                a mark stands on a page with nothing to read, so the record is
                refused here rather than factored into an empty string.
        """
        if self._reserved:
            raise CompileSlotsError(
                f"{len(self._reserved)} mark(s) were reserved and never supplied, first {min(self._reserved)}"
            )
        return {
            "schema": SLOTS_SCHEMA,
            "languages": list(self.languages),
            "marks": [
                {"rendering": rendering.value, "values": list(values)}
                | ({} if plain is None else {"plain": list(plain)})
                for rendering, values, plain in zip(self.renderings, self.values, self.plain, strict=True)
            ],
        }

    def write(self, path: Path) -> None:
        """Write the marks where the finishing pass reads them."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.document(), ensure_ascii=False), encoding="utf-8")


#: The schema of the recorded marks, which the compile writes and the finishing
#: pass reads. They run in different processes: the marks are created inside the
#: ``sphinx-build`` child, and the site is factored by the driver that ran it.
SLOTS_SCHEMA: Final[int] = 2

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
        rendering = Rendering(entry.get("rendering"))
        values = [str(value) for value in entry["values"]]
        recorded = entry.get("plain")
        if recorded is None:
            slots.mark(rendering, values)
            continue
        if not isinstance(recorded, list):
            raise CompileSlotsError(f"{path} holds a mark whose plain form is not a list of strings")
        # A message mark is read back as it was reserved, because two marks
        # reading the same rendering can still be two messages.
        slots.supply(slots.reserve(rendering), values, [str(value) for value in recorded])
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


def language_text(
    value_of: Callable[[str], str],
    language: str,
    *,
    rendering: Rendering = Rendering.DOCUTILS,
) -> str:
    """Return one value per language as a mark, or the build language's value alone.

    The primitive for a creation site that can already say what every language
    reads and needs no rendering of its own:
    :func:`~dev.docs._locale_chrome.docs_chrome` for a catalogue string,
    :func:`~dev.docs._locale_chrome.docs_fragment` where the markup itself
    differs, and this where the value is simply looked up per language.

    Args:
        value_of: Returns the value for one language tag.
        language: The language a single-language build renders.
        rendering: Which writer owns the strings.

    Returns:
        The mark, or the build language's value outside the one compile.
    """
    slots = _ACTIVE
    if slots is None:
        return value_of(language)
    return slots.mark(rendering, [value_of(carried) for carried in slots.languages])


def widest(value: str) -> int:
    """Return how many characters *value* reads as in the language that reads it longest.

    An RST heading is underlined to the width of its own text, and a mark is
    four characters standing for a title of any length. Docutils accepts an
    underline longer than its title and the length never reaches the page, so
    the widest language's is the one that is safe for all of them.
    """
    slots = _ACTIVE
    if slots is None or MARK_OPEN not in value:
        return len(value)
    return max(len(slots.resolved(value, index)) for index in range(len(slots.languages)))


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


#: The regions that carry a page's title rather than a message's own markup,
#: keyed by the class the element carrying them declares: Furo's own navigation
#: wrapper, and the ``compound`` div docutils writes a body toctree inside.
#:
#: The region says which writer wrote the title and that the title is plain
#: text. It does not say whether the title was educated: a region carries both
#: a title a page's own heading supplied, which was, and an explicit toctree
#: entry title, which was not. That is a property of the string, and the mark
#: carries it as :attr:`Rendering.PLAIN`.
_TITLE_REGIONS: Final[dict[str, tuple[Position, Position]]] = {
    "sidebar-tree": (Position.NAVIGATION_TEXT, Position.NAVIGATION_ATTRIBUTE),
    "toctree-wrapper": (Position.ENTRY_TEXT, Position.ENTRY_ATTRIBUTE),
}

#: One tag's ``class`` attribute value.
_CLASSES: Final[re.Pattern[str]] = re.compile(r'\sclass="([^"]*)"')


def _region_entered(tag: str) -> tuple[Position, Position] | None:
    """Return the positions one opening tag's classes declare a region of, if any."""
    classes = _CLASSES.search(tag)
    if classes is None:
        return None
    for name in classes.group(1).split():
        found = _TITLE_REGIONS.get(name)
        if found is not None:
            return found
    return None


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
    region: tuple[Position, Position] | None = None
    depth = 0
    for piece in _PIECE.finditer(page):
        text = piece.group()
        if text[0] != "<":
            ordinary = Position.TITLE if in_title else Position.TEXT
            where = ordinary if region is None else region[0]
            found.extend((mark, where) for mark in MARK.finditer(page, piece.start(), piece.end()))
            continue
        name = _TAG_NAME.match(text)
        tag = name.group(1).lower() if name is not None else "?"
        closing = text.startswith("</")
        if tag == "title":
            in_title = not closing
        if region is None:
            # Both regions are written as a div, which is what makes the nesting
            # of divs enough to find where each one ends.
            region = _region_entered(text) if tag == "div" and not closing else None
            depth = 1 if region is not None else 0
        elif tag == "div":
            # The region ends with the element that opened it, so the nesting of
            # its own kind of element is what says where that is.
            depth += -1 if closing else 1
            if depth == 0:
                region = None
        spans = [
            (piece.start() + attribute.start(2), piece.start() + attribute.end(2))
            for attribute in _ATTRIBUTE.finditer(text)
        ]
        for mark in MARK.finditer(page, piece.start(), piece.end()):
            inside = any(start <= mark.start() and mark.end() <= end for start, end in spans)
            if not inside:
                found.append((mark, Position.MARKUP))
            else:
                found.append((mark, Position.ATTRIBUTE if region is None else region[1]))
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
        number = int(mark.group(1), len(_DIGITS))
        rendering, values = slots.strings(number)
        plain = slots.plain[number] or (None,) * len(values)
        factored.append(
            tuple(
                _written(rendering, where, value, text, language)
                for language, value, text in zip(slots.languages, values, plain, strict=True)
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
