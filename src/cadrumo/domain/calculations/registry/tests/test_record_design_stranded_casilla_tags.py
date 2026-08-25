"""A casilla reference emitted on a line of its own is folded back onto its row.

AEAT prints the casilla in a far-right column, and the plain text extractor
breaks the line before it. The tag then arrives alone -- ``[194]`` on its own
line -- and nothing downstream recovers it, so the field it belongs to reaches
the registry with no casilla number at all.

WHAT THE PAGE ACTUALLY SHOWS, and why folding onto the PRECEDING line is right
rather than a guess. Modelo 200's 2012 edition lays the row out as two physical
lines: the description ``Balance: ... Acciones y participaciones en patrimonio
propias`` on one, and its columns plus the casilla -- ``15 164 17 N [194]`` --
on the next. Extraction joins the columns onto the description and drops the
tag, so the tag's own line is the tail of the row immediately above it.

Checked against page geometry across the seven bundled designs that strand a
tag: of 791 stranded tags, 766 are confirmed by the PDF's own word coordinates
to belong to the row the fold attaches them to, one is physically alone on its
row so geometry cannot speak, and the remaining 22 carry a casilla number that
repeats two to five times in the same document, which the positional tie cannot
disambiguate. None was shown to be attached to a foreign row.
"""

from __future__ import annotations

import re

import pytest

from .....core.resources import bundled_path
from .. import extract_record_design
from ..record_design import (
    _clean_pdf_line,
    _collapse_stuttered_row_prefix,
    _extract_pdf_text_lines,
    _join_wrapped_row_descriptions,
    _pdf_page_name,
    _reattach_stranded_casilla_tags,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_STRANDED = re.compile(r"^\s*\[\d+\]\s*$")

_MODELO_200 = bundled_path("corpus", "aeat_official", "disenos_registro", "modelo_200", "files")
#: The edition whose layout is quoted above. Its ``Pág. 50`` carries the row.
_STRANDING_DESIGN = "04-200-ejercicio-2012-actualizado-a-28-06-2013-539-kb-pdf.pdf"
_SHEET = "Pág. 50"
_ORDINAL, _OFFSET, _CASILLA = "15", 164, "194"


def _prepared_lines(name: str) -> tuple[str, ...]:
    """The line stream as the reader sees it just before the fold."""
    design = _MODELO_200 / name
    return _collapse_stuttered_row_prefix(
        _join_wrapped_row_descriptions(
            _extract_pdf_text_lines(design.read_bytes(), source_label=name),
        ),
    )


def test_the_stranded_tag_reaches_the_field_it_belongs_to() -> None:
    extraction = extract_record_design(_MODELO_200 / _STRANDING_DESIGN)

    sheet = next(s for s in extraction.sheets if s.name == _SHEET)
    field = next(f for f in sheet.fields if f.offset == _OFFSET and f.ordinal == _ORDINAL)

    assert f"[{_CASILLA}]" in (field.description or ""), (
        f"the casilla AEAT prints on this row is missing: {field.description!r}"
    )


def test_that_tag_is_stranded_before_the_fold_runs() -> None:
    """Anti-vacuity: without the fold the tag is a line of its own, not a field's.

    Without this, the assertion above would pass just as well against a design
    that never stranded anything, and would be pinning nothing.
    """
    prepared = _prepared_lines(_STRANDING_DESIGN)

    stranded = [line.strip() for line in prepared if _STRANDED.match(line)]

    assert f"[{_CASILLA}]" in stranded, "this design no longer strands the tag under test"

    remaining = [line.strip() for line in _reattach_stranded_casilla_tags(prepared) if _STRANDED.match(line)]

    assert f"[{_CASILLA}]" not in remaining, "the fold left the tag under test stranded"
    assert len(remaining) < len(stranded), "the fold recovered nothing at all"


def test_the_fold_declines_a_neighbour_that_is_not_field_shaped() -> None:
    """A tag beside a heading or prose stays stranded and is reported as lost.

    This is the failure the fold could otherwise cause: a casilla number
    declared on bytes AEAT never put it on, which a tiling mis-attribution has
    already been shown to pass quietly through the contiguity check.
    """
    design = bundled_path(
        "corpus",
        "aeat_official",
        "disenos_registro",
        "modelo_390",
        "files",
        "08-390-ejercicio-2015-103-kb-pdf.pdf",
    )
    heading = next(
        line.strip()
        for line in _extract_pdf_text_lines(design.read_bytes(), source_label=design.name)
        if _pdf_page_name(_clean_pdf_line(line)) is not None
    )

    assert _reattach_stranded_casilla_tags((heading, "[523]")) == (heading, "[523]")
    assert _reattach_stranded_casilla_tags(("Datos adicionales", "[523]")) == (
        "Datos adicionales",
        "[523]",
    )
    assert _reattach_stranded_casilla_tags(("[523]",)) == ("[523]",)


def test_the_fold_does_not_append_a_tag_to_a_row_that_already_closes_with_one() -> None:
    """A row already carrying its casilla is left alone.

    The neighbouring line is then a different row's tag, and appending it here
    would both invent a second casilla for this row and consume the real one.
    """
    row = "15 164 17 N Balance - Otras reservas [193]"

    assert _reattach_stranded_casilla_tags((row, "[194]")) == (row, "[194]")
