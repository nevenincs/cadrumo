"""A row split between a bare coordinate line and its naturaleza half is rebuilt.

Modelo 200's ``17-200-orden-eha-1338-2010`` design emits the ``Indicador de
página complementaria`` row of its ``Pág. 21`` and ``Pág. 22`` records with the
three coordinate numbers alone on one line and the naturaleza, description and
wrapped content below::

    5 10 1
    An C Indicador de página complementaria.
    Blanco (No
    complementaria) o
    "C" (Complementaria)
    6 11 1 A C Operaciones fusión, escisión, canje valores - ...

Position 10 was then the ONLY hole on either record, and a record read with a
hole is skipped whole, so one split row cost two sheets.

WHY THE ANCHOR LOOKS FORWARD. Everywhere else in this module an ordinal is
admitted by continuing from the row ABOVE. That is impossible here: on these
pages ordinals 2, 3 and 4 are emitted with their ordinal and position FUSED
(``23 3 Num``, ``36 3 An``, ``49 1 An``) and are not recovered until record
assembly, so at line-repair time the nearest parsed row above is ordinal 1. The
row BELOW is intact, and anchoring on it is the same two independent facts in
the other direction: the successor's ordinal must be one more, and its position
must resume exactly where the rebuilt row ends.

THE NATURALEZA HALF SITS ON EITHER SIDE. The 2010 update prints it BELOW the
triple; the 2010 and 2011 designs print it ABOVE, separated from the triple by
the wrapped Contenido cell and a page break's running furniture -- the modelo
name, the version and the two-line subtitle. Same row, mirrored, so the search
tries the line below first and then looks back a bounded distance.

THE PATTERN IS ANCHORED END TO END on purpose. An earlier attempt at this shape
allowed a trailing fragment after the three numbers and was measured claiming
FORTY lines on one design where two were real. A bare triple is a triple and
nothing else.
"""

from __future__ import annotations

import pytest

from .....core.resources.bundled_data import bundled_path
from ..record_design import extract_record_design
from ..record_design_pdf_repairs import _BARE_COORDINATE_TRIPLE_RE, rejoin_bare_coordinate_rows

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_DESIGN = bundled_path(
    "corpus",
    "aeat_official",
    "disenos_registro",
    "modelo_200",
    "files",
    "17-200-orden-eha-1338-2010-actualizado-a-11-06-2010-283-kb-pdf.pdf",
)
#: The two records the split row used to cost.
_RECOVERED_SHEETS = ("21", "22")


def test_the_design_now_reads_without_skipping_a_record() -> None:
    extraction = extract_record_design(_DESIGN)

    assert not extraction.skipped, [(s.name, s.reason) for s in extraction.skipped]


@pytest.mark.parametrize("suffix", _RECOVERED_SHEETS)
def test_the_recovered_record_carries_the_rebuilt_row(suffix: str) -> None:
    """The row itself, at the position that used to be the record's only hole."""
    extraction = extract_record_design(_DESIGN)
    sheet = next((s for s in extraction.sheets if s.name.strip().endswith(f" {suffix}")), None)
    assert sheet is not None, f"record ending {suffix!r} is absent"

    field = next((f for f in sheet.fields if f.offset == 10), None)
    assert field is not None, "position 10 is still unread"
    assert field.ordinal == "5"
    assert field.length == 1
    assert "complementaria" in (field.description or "").casefold()


@pytest.mark.parametrize("suffix", _RECOVERED_SHEETS)
def test_the_recovered_record_tiles_without_a_hole(suffix: str) -> None:
    """A rebuilt row with the wrong position would leave the record holed."""
    extraction = extract_record_design(_DESIGN)
    sheet = next(s for s in extraction.sheets if s.name.strip().endswith(f" {suffix}"))

    occupied: set[int] = set()
    for field in sheet.fields:
        occupied |= set(range(field.offset, field.offset + field.length))
    unwritten = sorted(set(range(1, (sheet.total_positions or 0) + 1)) - occupied)

    assert not unwritten, unwritten[:8]


def test_a_triple_carrying_a_trailing_fragment_is_not_a_bare_triple() -> None:
    """The narrowing that keeps this from claiming ordinary content lines.

    ``5 10 1 "C" (Complementaria)`` opens a quoted Contenido value; a pattern
    that accepted it matched forty lines on one design. The anchored pattern
    rejects it.
    """
    assert _BARE_COORDINATE_TRIPLE_RE.match("5 10 1") is not None
    assert _BARE_COORDINATE_TRIPLE_RE.match('5 10 1 "C" (Complementaria)') is None
    assert _BARE_COORDINATE_TRIPLE_RE.match("5 10 1 An Something") is None


def test_a_triple_whose_successor_does_not_resume_is_declined() -> None:
    """The over-determination, proved by breaking one half of it.

    The successor here is ordinal 7 rather than 6, so the ordinal no longer
    follows even though the position still resumes.
    """
    lines = (
        "5 10 1",
        "An C Indicador de pagina complementaria.",
        "7 11 1 A C The row below",
    )

    assert rejoin_bare_coordinate_rows(lines) == lines


def test_the_same_shape_is_rebuilt_when_the_successor_does_resume() -> None:
    """The companion, so the refusal above cannot pass by the repair never firing."""
    lines = (
        "5 10 1",
        "An C Indicador de pagina complementaria.",
        "6 11 1 A C The row below",
    )

    rebuilt = rejoin_bare_coordinate_rows(lines)

    assert rebuilt == (
        "5 10 1 An C Indicador de pagina complementaria.",
        "6 11 1 A C The row below",
    )


def test_the_mirrored_shape_is_rebuilt_when_the_naturaleza_half_sits_above() -> None:
    """Modelo 200's 2010 and 2011 designs print the halves in the other order.

    The triple lands after a page break, so its naturaleza half is several lines
    above with running furniture in between. The successor anchor is unchanged.
    """
    lines = (
        "4 9 1 An C Fin de identificador de modelo.",
        "An C Indicador de pagina complementaria.",
        "Blanco (No",
        "Modelo 200",
        "vers. 1.0",
        "5 10 1",
        '"C" (Complementaria)',
        "6 11 1 A C The row below",
    )

    rebuilt = rejoin_bare_coordinate_rows(lines)

    assert rebuilt[0] == "4 9 1 An C Fin de identificador de modelo."
    assert rebuilt[1].startswith("5 10 1 An C Indicador de pagina complementaria.")
    assert rebuilt[-1] == "6 11 1 A C The row below"
    assert len(rebuilt) == 3


def test_both_of_the_mirrored_designs_recover_their_first_record() -> None:
    """The two designs that print the halves above now read their Pag. 21."""
    for name in (
        "02-200-ejercicio-2010-472-kb-pdf.pdf",
        "03-200-ejercicio-2011-522-kb-pdf.pdf",
    ):
        design = bundled_path("corpus", "aeat_official", "disenos_registro", "modelo_200", "files", name)
        extraction = extract_record_design(design)
        skipped = {sheet.name.strip()[-2:] for sheet in extraction.skipped}
        assert "21" not in skipped, (name, sorted(skipped))
        sheet = next(s for s in extraction.sheets if s.name.strip().endswith(" 21"))
        field = next((f for f in sheet.fields if f.offset == 10), None)
        assert field is not None and field.ordinal == "5", name
