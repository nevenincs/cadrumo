"""The printed pages of an official form a revision cites, read from the text extracted beside it.

A form published as a PDF -- a BOE annex, an AEAT model -- prints its own page
labels (``Pág. 2 bis``), the apartado ordinals that open its sections
(``5. Operaciones realizadas en régimen general``) and its box numbers. The
corpus keeps one extracted text unit per PDF page beside the binary, written by
the canonical PDF extractor. This module reads those pages after hashing the
binary against its catalogue entry, so a statement about a page is a statement
about the file the revision cites.

Reading is deliberately literal. A box is printed on a page when its number
stands there as a whole token; an apartado is printed when its ordinal opens a
heading. Three kinds of number are set aside first because they are not that
page's boxes: the lines a publisher repeats on most pages of the document (its
running head and foot, with their issue number and date), the arithmetic a
caption restates (``(84 + 659 - 85 - 112)``), which cites other boxes, and a
number following an abbreviation (``Pág. 2``, ``art. 80``), which is a
reference.
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from cadrumo.domain.calculations.registry.schema_base import RegistrySourceKind
from cadrumo.domain.calculations.registry.schema_form_layouts import FormDesignSource
from cadrumo.domain.calculations.registry.schema_references import SourceReference
from dev.docs.preprocess.schema import SourceDocumentKind
from dev.docs.preprocess.sidecar import PreprocessSidecarError, load_sidecar, sidecar_paths_for

__all__ = [
    "OfficialFormPages",
    "OfficialFormUnavailableError",
    "PrintedPage",
    "apartado_ordinal",
    "read_official_form_pages",
]

#: A caption restating other boxes' arithmetic: two or more numbers joined by operators.
_ARITHMETIC_CAPTION: Final = re.compile(r"\(\s*\d+(?:\s*[-+x×*/]\s*\d+)+\s*\)")
#: An apartado ordinal opening a heading: ``5. Operaciones``, never ``9.1`` or ``80.Tres``.
_APARTADO: Final = re.compile(r"(?<!\S)(\d{1,3})\.\s+(?=[^\W\d_])")
_DIGITS: Final = re.compile(r"\d+")
#: A line is the publisher's running head or foot when it recurs, digits aside,
#: on more than this share of the document's pages.
_RUNNING_SHARE: Final[float] = 0.5
_RUNNING_MINIMUM_PAGES: Final[int] = 3


class OfficialFormUnavailableError(Exception):
    """A form the revision cites cannot be trusted, so no page may be read from it."""


def _folded(text: str) -> str:
    return " ".join(text.split()).casefold()


def apartado_ordinal(heading: str | None) -> str | None:
    """Return the apartado ordinal a heading opens with (``"5"`` for ``5. Operaciones ...``), or ``None``."""
    if not heading:
        return None
    match = _APARTADO.match(heading.strip())
    return None if match is None else str(match.group(1))


@dataclass(frozen=True, slots=True)
class PrintedPage:
    """One PDF page of an official form: its raw text, and the box numbers and apartados it prints."""

    source_ref: str
    title: str
    text: str
    numbers: frozenset[str]
    apartados: frozenset[str]

    def labels(self, candidates: Iterable[str]) -> frozenset[str]:
        """Return the candidate page labels this page prints, the longest winning at each position.

        ``Pág. 2`` is not printed by a page that prints only ``Pág. 2 bis``,
        and ``Pág. 1`` is not printed by a running head reading ``Pág. 12135``.
        """
        ordered = sorted(
            {_folded(label): label for label in candidates if label.strip()}.items(), key=lambda item: -len(item[0])
        )
        if not ordered:
            return frozenset[str]()
        pattern = re.compile(r"(?<!\w)(" + "|".join(re.escape(folded) for folded, _label in ordered) + r")(?!\w)")
        spelled = dict(ordered)
        return frozenset(spelled[match.group(1)] for match in pattern.finditer(_folded(self.text)))

    def prints_box(self, box: str) -> bool:
        """Whether the box number stands on this page as a whole token."""
        return box in self.numbers

    def prints_apartado(self, ordinal: str) -> bool:
        """Whether an apartado heading with this ordinal is printed on this page."""
        return ordinal in self.apartados


@dataclass(frozen=True, slots=True)
class OfficialFormPages:
    """Every printed page of the paginated forms one revision cites, with the files read pinned."""

    pages: tuple[PrintedPage, ...]
    pins: tuple[FormDesignSource, ...]

    def page_labelled(self, label: str, *, labels: Iterable[str]) -> PrintedPage | None:
        """Return the one page printing ``label`` among ``labels``, or ``None`` when no page or several do."""
        candidates = (*labels, label)
        printing = [page for page in self.pages if label in page.labels(candidates)]
        return printing[0] if len(printing) == 1 else None


def _running_keys(pages: Sequence[str]) -> frozenset[str]:
    """Return the digit-blind lines recurring on most pages: the publisher's running head and foot."""
    if len(pages) < _RUNNING_MINIMUM_PAGES:
        return frozenset[str]()
    counts: Counter[str] = Counter()
    for text in pages:
        counts.update({_DIGITS.sub("#", _folded(line)) for line in text.splitlines() if line.strip()})
    return frozenset(key for key, count in counts.items() if count > len(pages) * _RUNNING_SHARE)


def _printed_page(ref: str, title: str, text: str, running: frozenset[str]) -> PrintedPage:
    """Read a page's box numbers and apartados from what it prints of its own.

    A number standing after an abbreviation (``Pág. 2``, ``art. 80``,
    ``Núm. 23``) is a reference, not a box.
    """
    kept = "\n".join(line for line in text.splitlines() if _DIGITS.sub("#", _folded(line)) not in running)
    body = _ARITHMETIC_CAPTION.sub(" ", kept)
    tokens = body.split()
    numbers = frozenset(
        token
        for index, token in enumerate(tokens)
        if token.isdigit() and not (index and tokens[index - 1].endswith(".") and tokens[index - 1][:-1].isalpha())
    )
    apartados = frozenset(str(match.group(1)) for match in _APARTADO.finditer(body))
    return PrintedPage(source_ref=ref, title=title, text=text, numbers=numbers, apartados=apartados)


def _form_pages(
    ref: str, source: SourceReference, data_root: Path
) -> tuple[list[PrintedPage], FormDesignSource] | None:
    binary = data_root / source.corpus_path
    if not binary.is_file():
        raise OfficialFormUnavailableError(f"source {ref!r}: {source.corpus_path} is not present")
    actual = hashlib.sha256(binary.read_bytes()).hexdigest()
    if actual != source.sha256:
        raise OfficialFormUnavailableError(
            f"source {ref!r}: {source.corpus_path} hashes {actual}, not the catalogued {source.sha256}"
        )
    text_path, json_path = sidecar_paths_for(binary)
    if not json_path.is_file():
        return None
    try:
        extracted = load_sidecar(binary)
    except PreprocessSidecarError as error:
        raise OfficialFormUnavailableError(f"source {ref!r}: {error}") from error
    if extracted.source_kind is not SourceDocumentKind.CORPUS_PDF:
        return None
    texts = [unit.text for unit in extracted.units]
    running = _running_keys(texts)
    pages = [_printed_page(ref, unit.title or "", unit.text, running) for unit in extracted.units]
    pin = FormDesignSource(source_ref=ref, sha256=hashlib.sha256(text_path.read_bytes()).hexdigest())
    return pages, pin


def read_official_form_pages(
    source_refs: Sequence[str],
    sources: Mapping[str, SourceReference],
    data_root: Path,
) -> OfficialFormPages:
    """Return the printed pages of every paginated ``form_spec`` source among ``source_refs``, in citation order.

    A cited form whose extracted text is not paginated (an HTML orden, or a
    PDF never extracted) contributes no page.

    Raises:
        OfficialFormUnavailableError: When a cited form's binary is missing,
            does not hash to its catalogue entry, or its extracted text is stale.
    """
    pages: list[PrintedPage] = []
    pins: list[FormDesignSource] = []
    for ref in dict.fromkeys(str(item) for item in source_refs):
        source = sources.get(ref)
        if source is None or source.kind is not RegistrySourceKind.FORM_SPEC:
            continue
        read = _form_pages(ref, source, data_root)
        if read is None:
            continue
        pages.extend(read[0])
        pins.append(read[1])
    return OfficialFormPages(pages=tuple(pages), pins=tuple(pins))
