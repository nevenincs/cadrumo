"""Reading the official design's own words into headings, box numbers and slugs.

An AEAT record-design description is a heading path joined by dashes --
``Liquidación (3) - Regimen General - IVA Devengado - Régimen general - Base
imponible [01]`` is apartado, block, row and column with the printed box. These
helpers split that path, find the box, and derive stable node ids. They quote
the design's words; they never invent or humanise text.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from typing import Final

__all__ = [
    "DescriptionPath",
    "clean_official_text",
    "description_box",
    "description_path",
    "node_slug",
]

_BOX: Final = re.compile(r"\[\s*(\d{1,5})\s*\]")
_FORMULA: Final = re.compile(r"\([^()]*\[[^()]*\)")
_SEGMENT_SPLIT: Final = re.compile(r"\s-\s+|\s-(?=\S)|(?<=\S)-\s+")
_C1_CONTROLS: Final = re.compile(r"[\x80-\x9f]")
_MAX_SLUG: Final = 48


def clean_official_text(text: str) -> str:
    """Return extracted design text with extraction artefacts removed and nothing else changed.

    Whitespace runs (including the line breaks a spreadsheet cell carries) become
    one space. A C1 control character is a Windows-1252 byte the extractor
    decoded as Latin-1 -- code point U+0096 is the design's en dash -- so it is decoded
    as the byte it was; any other control character is dropped.
    """
    repaired = _C1_CONTROLS.sub(lambda match: match.group(0).encode("latin-1").decode("cp1252", "ignore"), text)
    printable = "".join(char for char in repaired if unicodedata.category(char) != "Cc" or char in "\t\n\r")
    return " ".join(printable.split())


def description_box(description: str) -> str | None:
    """Return the one printed box number a description states, or ``None``.

    Boxes inside a parenthesised formula (``([01] - [02])``) are references to
    other boxes, not this row's own, so they are removed first. A description
    naming two or more boxes of its own does not identify one.
    """
    boxes = _BOX.findall(_FORMULA.sub(" ", description))
    return str(boxes[0]) if len(boxes) == 1 else None


@dataclass(frozen=True, slots=True)
class DescriptionPath:
    """A description split into its section path, row stem and column."""

    section: tuple[str, ...]
    stem: str | None
    column: str | None


def description_path(description: str | None) -> DescriptionPath:
    """Split a description on dash-with-whitespace, dropping box numbers and formulas.

    With three or more segments the last is the column, the one before it the
    row, and the rest the section. With two, the first is the section and the
    second the field. A single segment names only the field.
    """
    if not description:
        return DescriptionPath((), None, None)
    stripped = _BOX.sub(" ", _FORMULA.sub(" ", clean_official_text(description)))
    segments = tuple(
        segment
        for segment in (" ".join(part.split()).strip(" .:-") for part in _SEGMENT_SPLIT.split(stripped))
        if segment
    )
    if len(segments) >= 3:
        return DescriptionPath(segments[:-2], segments[-2], segments[-1])
    if len(segments) == 2:
        return DescriptionPath(segments[:1], None, segments[1])
    return DescriptionPath((), None, segments[0] if segments else None)


def node_slug(text: str) -> str:
    """Return a stable ASCII node id for ``text``, bounded in length.

    Accents fold, ordinal marks and ``%`` are written out, and every other run
    of punctuation becomes one dash. A slug longer than the bound keeps its
    prefix and gains a short digest of the full text, so two long headings that
    share a prefix still receive distinct ids.
    """
    spelled = text.replace("º", "o").replace("ª", "a").replace("%", " pct ")
    folded = unicodedata.normalize("NFKD", spelled).encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", folded).strip("-") or "x"
    if len(slug) <= _MAX_SLUG:
        return slug
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:6]
    return f"{slug[: _MAX_SLUG - 7].rstrip('-')}-{digest}"
