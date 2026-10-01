"""Official headings a reviewer quotes for layout parts the design names in no readable form.

Some designs do not print their page, section and column titles where the
generator can read them: Renta's dictionaries name XML containers, and a record
design extracted from a PDF loses its table. A reviewer quotes the official
words from a source the revision itself cites, with the line they stand on, in
``official_headings.toml``. The generator applies each quote to the part it
names and refuses a quote whose words do not stand on the cited line, whose
source the revision does not cite or no longer hashes to its catalogue entry,
or whose part the layout does not have.

Letter case is not compared: AEAT designs print field names in capitals, and a
heading quotes the words, not the typesetting. Nothing else is normalised.

Parts that keep no official heading are listed in the same file with the
reason, so the file states the whole heading state of a modelo and a test can
hold it total.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Final

from cadrumo.core.toml import load_toml
from cadrumo.domain.calculations.registry.schema_form_layouts import FormDesignSource
from cadrumo.domain.calculations.registry.schema_references import SourceReference

from .official_text import clean_official_text

__all__ = [
    "OFFICIAL_HEADINGS",
    "QUOTE_LINE_SPAN",
    "OfficialHeadingRefusedError",
    "OfficialHeadings",
    "QuotedHeading",
    "UnheadedPart",
    "quoted_source_lines",
    "read_official_headings",
    "verify_quote",
]

OFFICIAL_HEADINGS: Final[Path] = Path(__file__).with_name("official_headings.toml")

#: A quoted heading may wrap onto the lines after the one it starts on, as a
#: design's long field name does in a PDF extraction.
QUOTE_LINE_SPAN: Final[int] = 3


class OfficialHeadingRefusedError(ValueError):
    """A quoted heading that is not grounded where it says it is, or names no part of the layout."""


@dataclass(frozen=True, slots=True)
class QuotedHeading:
    """One official heading quoted for a page, a section of it, or a column of one of its blocks."""

    modelo: str
    revision: str
    page: str
    section: str | None
    column: str | None
    text: str
    source_ref: str
    line: int

    def describe(self) -> str:
        """Name the quoted part for a refusal message."""
        parts = [self.modelo, self.revision, self.page]
        parts.extend(part for part in (self.section, self.column) if part is not None)
        return "/".join(parts)


@dataclass(frozen=True, slots=True)
class UnheadedPart:
    """A page or section that keeps no official heading, with the reviewed reason."""

    modelo: str
    page: str
    section: str | None
    revisions: tuple[str, ...]
    reason: str

    def covers(self, modelo: str, revision: str, page: str, section: str | None) -> bool:
        """Whether this entry accounts for the named part of the named revision."""
        return (
            self.modelo == modelo
            and self.page == page
            and self.section == section
            and (not self.revisions or revision in self.revisions)
        )


@dataclass(frozen=True, slots=True)
class OfficialHeadings:
    """Every quoted heading and every reasoned absence the reviewer recorded."""

    quotes: tuple[QuotedHeading, ...]
    unheaded: tuple[UnheadedPart, ...]

    def for_revision(self, modelo: str, revision: str) -> tuple[QuotedHeading, ...]:
        """The quotes that apply to one revision's layout."""
        return tuple(quote for quote in self.quotes if quote.modelo == modelo and quote.revision == revision)


def _optional(entry: Mapping[str, object], key: str) -> str | None:
    value = entry.get(key)
    return None if value is None else str(value)


def _quote(entry: Mapping[str, object]) -> QuotedHeading:
    line = entry["line"]
    if not isinstance(line, int) or line < 1:
        raise OfficialHeadingRefusedError(f"quoted heading {entry!r} cites no line number")
    return QuotedHeading(
        modelo=str(entry["modelo"]),
        revision=str(entry["revision"]),
        page=str(entry["page"]),
        section=_optional(entry, "section"),
        column=_optional(entry, "column"),
        text=str(entry["text"]),
        source_ref=str(entry["source"]),
        line=line,
    )


def _unheaded(entry: Mapping[str, object]) -> UnheadedPart:
    revisions = entry.get("revisions", [])
    reason = str(entry.get("reason", "")).strip()
    if not reason:
        raise OfficialHeadingRefusedError(f"unheaded part {entry!r} states no reason")
    return UnheadedPart(
        modelo=str(entry["modelo"]),
        page=str(entry["page"]),
        section=_optional(entry, "section"),
        revisions=tuple(str(item) for item in revisions) if isinstance(revisions, list) else (),
        reason=reason,
    )


@cache
def read_official_headings(path: Path = OFFICIAL_HEADINGS) -> OfficialHeadings:
    """Return the quoted headings and reasoned absences recorded at ``path``."""
    if not path.is_file():
        return OfficialHeadings((), ())
    with path.open("rb") as handle:
        document = load_toml(handle)
    quotes = document.get("quotes", [])
    unheaded = document.get("unheaded", [])
    return OfficialHeadings(
        quotes=tuple(_quote(entry) for entry in quotes) if isinstance(quotes, list) else (),
        unheaded=tuple(_unheaded(entry) for entry in unheaded) if isinstance(unheaded, list) else (),
    )


def _decoded(payload: bytes) -> str:
    try:
        return payload.decode("utf-8")
    except UnicodeDecodeError:
        return payload.decode("cp1252")


def quoted_source_lines(source: SourceReference, data_root: Path) -> tuple[tuple[str, ...], FormDesignSource]:
    """Return the lines a quote from ``source`` is read against, and the file pinned as read.

    The binary is hashed against the catalogue first, so a line read from the
    extracted text beside a PDF is a statement about the file the revision
    cites. A source with an extracted text beside it is read there; any other
    is read as the text it is.
    """
    binary = data_root / source.corpus_path
    if not binary.is_file():
        raise OfficialHeadingRefusedError(f"source {source.id!r}: {source.corpus_path} is not present")
    payload = binary.read_bytes()
    actual = hashlib.sha256(payload).hexdigest()
    if actual != source.sha256:
        raise OfficialHeadingRefusedError(
            f"source {source.id!r}: {source.corpus_path} hashes {actual}, not the catalogued {source.sha256}"
        )
    extracted = binary.with_name(binary.name + ".extracted.md")
    read = extracted if extracted.is_file() else binary
    text = _decoded(read.read_bytes())
    pinned = FormDesignSource(source_ref=str(source.id), sha256=hashlib.sha256(read.read_bytes()).hexdigest())
    return tuple(text.splitlines()), pinned


def _folded(text: str) -> str:
    return " ".join(clean_official_text(text).casefold().split())


def verify_quote(
    quote: QuotedHeading,
    *,
    cited: Sequence[str],
    sources: Mapping[str, SourceReference],
    data_root: Path,
) -> FormDesignSource:
    """Return the pinned source of a quote whose words stand on its cited line, or refuse it.

    ``cited`` is the source ids the revision itself cites: a heading is quoted
    from the revision's own evidence, never from a neighbouring edition's.
    """
    if quote.source_ref not in cited:
        raise OfficialHeadingRefusedError(f"{quote.describe()}: the revision does not cite {quote.source_ref!r}")
    source = sources.get(quote.source_ref)
    if source is None:
        raise OfficialHeadingRefusedError(f"{quote.describe()}: source {quote.source_ref!r} is not catalogued")
    lines, pinned = quoted_source_lines(source, data_root)
    if quote.line > len(lines):
        raise OfficialHeadingRefusedError(f"{quote.describe()}: {quote.source_ref!r} has no line {quote.line}")
    if not quote.text.strip():
        raise OfficialHeadingRefusedError(f"{quote.describe()}: the quoted heading is empty")
    window = " ".join(lines[quote.line - 1 : quote.line - 1 + QUOTE_LINE_SPAN])
    if _folded(quote.text) not in _folded(window):
        raise OfficialHeadingRefusedError(
            f"{quote.describe()}: {quote.text!r} does not stand on line {quote.line} of {quote.source_ref!r}"
        )
    return pinned
