"""Factor the language roots of one documentation set into one structure and the text of each language.

A translated page is the English page with different text in it: the markup,
the identifiers, the legal texts, the recorded output and the layout are the
same bytes in every language. This module separates the two. Each page becomes
one *structure*, the bytes every language shares with a numbered slot wherever
the languages differ, and each language becomes one flat list of strings indexed
by slot number. Composing a structure with a language's strings gives that
language's page back byte for byte, which is what the factoring is verified by.

Pages are compared as markup pieces, attribute values and text runs. Where the
pieces line up, only the values and runs that differ become slots, so a string
is the translated label or sentence itself and one that recurs is stored once.
Where a language carries markup the others lack, the unmatched stretch becomes
a slot whole. A misjudged alignment therefore costs size, never correctness.
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Final

#: Private-use characters that delimit a slot number inside a structure. A page
#: that already contains either is refused, so a delimiter is never content.
SLOT_OPEN: Final[str] = ""
SLOT_CLOSE: Final[str] = ""

_SLOT: Final[re.Pattern[str]] = re.compile(f"{SLOT_OPEN}([0-9a-z]+){SLOT_CLOSE}")
_PIECE: Final[re.Pattern[str]] = re.compile(r"<!--.*?-->|<[^>]*>|[^<]+", re.DOTALL)
_ATTRIBUTE: Final[re.Pattern[str]] = re.compile(r'(\s[^\s"=<>/]+=")([^"]*)')
#: The shape of a piece that may differ between languages without the markup differing.
_VALUE: Final[str] = "\x00"
#: How far past a mismatch the two pages are searched for the point they agree again.
_RESYNC_WINDOW: Final[int] = 400
#: How many consecutive pieces must agree for the pages to count as lined up again.
_RESYNC_RUN: Final[int] = 4
_DIGITS: Final[str] = "0123456789abcdefghijklmnopqrstuvwxyz"


class SharedStructureError(ValueError):
    """Pages cannot be factored, or a structure cannot be composed."""


def _pieces(page: str) -> tuple[list[str], list[str]]:
    """Split a page into pieces and their shapes: markup is its own shape, a value is a wildcard."""
    pieces: list[str] = []
    shapes: list[str] = []
    for match in _PIECE.finditer(page):
        piece = match.group()
        if piece[0] != "<":
            pieces.append(piece)
            shapes.append(_VALUE)
            continue
        position = 0
        for attribute in _ATTRIBUTE.finditer(piece):
            markup = piece[position : attribute.end(1)]
            pieces.extend((markup, attribute.group(2)))
            shapes.extend((markup, _VALUE))
            position = attribute.end()
        pieces.append(piece[position:])
        shapes.append(piece[position:])
    return pieces, shapes


def _resync(base: Sequence[str], other: Sequence[str], i: int, j: int) -> tuple[int, int] | None:
    """Return the nearest offsets past a mismatch at which the two shape runs agree again.

    They agree when the next ``_RESYNC_RUN`` pieces match, or when fewer remain
    and both pages end on them together, which is how a page's closing tags
    are found after something one language adds just before them.
    """
    for total in range(1, 2 * _RESYNC_WINDOW + 1):
        for skipped in range(max(0, total - _RESYNC_WINDOW), min(total, _RESYNC_WINDOW) + 1):
            a, b = i + skipped, j + total - skipped
            left, other_left = len(base) - a, len(other) - b
            if left <= 0 or other_left <= 0:
                continue
            if (left < _RESYNC_RUN or other_left < _RESYNC_RUN) and left != other_left:
                continue
            if base[a : a + _RESYNC_RUN] == other[b : b + _RESYNC_RUN]:
                return a, b
    return None


def _differences(base: tuple[list[str], list[str]], other: tuple[list[str], list[str]]) -> list[tuple[int, int, str]]:
    """Return what ``other`` holds in place of each differing stretch of ``base`` pieces.

    Each entry is ``(start, end, text)``: the base pieces ``[start, end)`` read
    ``text`` in the other page. ``start == end`` is text the other page inserts
    before that piece. Entries are in order and never overlap.
    """
    (pieces, shapes), (other_pieces, other_shapes) = base, other
    found: list[tuple[int, int, str]] = []
    i = j = 0
    while i < len(shapes) and j < len(other_shapes):
        if shapes[i] == other_shapes[j]:
            if pieces[i] != other_pieces[j]:
                found.append((i, i + 1, other_pieces[j]))
            i += 1
            j += 1
            continue
        agreed = _resync(shapes, other_shapes, i, j)
        if agreed is None:
            break
        found.append((i, agreed[0], "".join(other_pieces[j : agreed[1]])))
        i, j = agreed
    if i < len(shapes) or j < len(other_pieces):
        found.append((i, len(shapes), "".join(other_pieces[j:])))
    return found


def _slots(differences: Sequence[Sequence[tuple[int, int, str]]]) -> Iterator[tuple[int, int]]:
    """Merge every language's differing stretches into the stretches that become slots."""
    stretches = sorted({(start, end) for language in differences for start, end, _ in language})
    if not stretches:
        return
    low, high = stretches[0]
    for start, end in stretches[1:]:
        if start <= high:
            high = max(high, end)
            continue
        yield low, high
        low, high = start, end
    yield low, high


@dataclass(frozen=True)
class Difference:
    """One stretch two renderings of the same page do not share.

    Attributes:
        offset: Where the stretch starts in the first page.
        base: What the first page reads there.
        other: What the second page reads in its place.
    """

    offset: int
    base: str
    other: str


def compare_page(base: str, other: str) -> list[Difference]:
    """Return every stretch of ``base`` that ``other`` reads differently.

    The same alignment :func:`factor_page` factors by, reported rather than
    stored: it is how a page composed from the stored form is measured against
    the page a language's own build produced while the two still differ, so the
    remaining work is a count per kind of difference instead of a yes or no.
    """
    pieces, shapes = _pieces(base)
    offsets: list[int] = []
    at = 0
    for piece in pieces:
        offsets.append(at)
        at += len(piece)
    offsets.append(at)
    return [
        Difference(offsets[start], "".join(pieces[start:end]), replacement)
        for start, end, replacement in _differences((pieces, shapes), _pieces(other))
    ]


def factor_page(pages: Sequence[str]) -> list[str | tuple[str, ...]]:
    """Return one page's structure as shared text and, per slot, each language's string.

    Args:
        pages: The same page in every language, in the order the strings are returned.

    Returns:
        The page in order: a ``str`` is text every language shares, a tuple holds
        what each language reads at that point.

    Raises:
        SharedStructureError: If a page already contains a slot delimiter.
    """
    for page in pages:
        if SLOT_OPEN in page or SLOT_CLOSE in page:
            raise SharedStructureError("a page contains a character reserved for slot delimiters")
    base = _pieces(pages[0])
    differences = [_differences(base, _pieces(page)) for page in pages[1:]]
    pieces = base[0]
    cursors = [0] * len(differences)
    structure: list[str | tuple[str, ...]] = []
    position = 0
    for start, end in _slots(differences):
        if start > position:
            structure.append("".join(pieces[position:start]))
        values = ["".join(pieces[start:end])]
        for index, language in enumerate(differences):
            text: list[str] = []
            at = start
            cursor = cursors[index]
            while cursor < len(language) and language[cursor][1] <= end and language[cursor][0] >= start:
                piece_start, piece_end, replacement = language[cursor]
                text.append("".join(pieces[at:piece_start]))
                text.append(replacement)
                at = piece_end
                cursor += 1
            cursors[index] = cursor
            text.append("".join(pieces[at:end]))
            values.append("".join(text))
        structure.append(tuple(values))
        position = end
    if position < len(pieces):
        structure.append("".join(pieces[position:]))
    return structure


def _number(value: int) -> str:
    digits = ""
    while True:
        value, remainder = divmod(value, len(_DIGITS))
        digits = _DIGITS[remainder] + digits
        if not value:
            return digits


@dataclass
class LanguageText:
    """The strings of every language, one list per language, indexed by slot number."""

    languages: tuple[str, ...]
    strings: dict[str, list[str]] = field(default_factory=dict)
    _numbers: dict[tuple[str, ...], int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Start each language with an empty list."""
        for language in self.languages:
            self.strings.setdefault(language, [])

    def slot(self, values: tuple[str, ...]) -> int:
        """Return the slot number that reads ``values`` across the languages, adding it once."""
        number = self._numbers.get(values)
        if number is None:
            number = self._numbers[values] = len(self._numbers)
            for language, value in zip(self.languages, values, strict=True):
                self.strings[language].append(value)
        return number

    def structure(self, factored: Sequence[str | tuple[str, ...]]) -> str:
        """Return a factored page as structure text, its slots replaced by their numbers."""
        return "".join(
            part if isinstance(part, str) else f"{SLOT_OPEN}{_number(self.slot(part))}{SLOT_CLOSE}" for part in factored
        )


def compose_page(structure: str, strings: Sequence[str]) -> str:
    """Return the page a structure reads as in the language ``strings`` belongs to.

    Raises:
        SharedStructureError: If the structure names a slot the language has no string for.
    """

    def text(match: re.Match[str]) -> str:
        number = int(match.group(1), len(_DIGITS))
        if number >= len(strings):
            raise SharedStructureError(f"the structure names slot {number}, past the language's {len(strings)} strings")
        return strings[number]

    return _SLOT.sub(text, structure)


def factor_pages(pages: Mapping[str, Sequence[str]], languages: Sequence[str]) -> tuple[dict[str, str], LanguageText]:
    """Factor a set of pages, each given in every language, into structures and one text per language.

    Args:
        pages: Each page's content in every language, keyed by the page's path.
        languages: The languages, in the order each page's contents are given.

    Returns:
        Each page's structure by path, and the strings of every language.
    """
    text = LanguageText(tuple(languages))
    return {path: text.structure(factor_page(contents)) for path, contents in sorted(pages.items())}, text
