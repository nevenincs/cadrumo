"""A row that kept its length and naturaleza but lost its position entirely.

A PDF page break can swallow a row's position half outright. Modelo 200's 2010
editions do it repeatedly: ``17 N Sociedades de garantia reciproca - Estado
total cambios patrimonio neto ...`` stands alone where AEAT declared ``6 11 17 N
...``, and the record then reports 11-27 as a dropped run.

THE POSITION IS NOT GUESSED FROM THAT LINE. It is taken from where the previous
row ends, and the candidate is then subject to the same containment test every
staged candidate faces: admitted only if the span it would occupy is one no read
row claims. Three independent facts must agree before the row appears -- the
position follows the previous row, the length is the one AEAT printed, and that
length lands exactly in a hole.

This is the mirror of ``fill_unread_gaps``'s existing case, which handles a row
that kept its position and lost its naturaleza. Both are admitted by the same
rule, because a fixed-width record is contiguous and an interior span no row
covers is a dropped row rather than something AEAT left undescribed.

It runs only in the repair pass, so a design whose records already tile is never
offered it -- the guard every row-adding change must apply
change.
"""

from __future__ import annotations

import pytest

from .._record_design import _EMPTY_CORRECTIONS, _PdfParseState

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_HEADER = (
    "N\u00ba Posic. Lon Tipo Descripci\u00f3n",
    "1 1 2 An Inicio del identificador",
    "2 3 3 Num Modelo",
    "3 6 3 An Pagina",
    "4 9 1 An Fin de identificador",
    "5 10 1 An Indicador de pagina complementaria",
)


def _read(lines: tuple[str, ...], *, repair: bool):
    state = _PdfParseState(source_label="probe.pdf", corrections=_EMPTY_CORRECTIONS, repair_glued_rows=repair)
    for number, line in enumerate(lines, start=1):
        state.feed(line, number)
    state._close_current_body()
    return state.results[0].sheet


def test_a_headless_row_is_placed_where_the_previous_row_ends() -> None:
    sheet = _read((*_HEADER, "17 N Saldo final del ejercicio", "7 28 3 An Cierre"), repair=True)
    placed = [f for f in sheet.fields if f.offset == 11]

    assert placed, [(f.offset, f.length) for f in sheet.fields]
    assert placed[0].length == 17


def test_the_record_then_tiles_its_declared_extent() -> None:
    sheet = _read((*_HEADER, "17 N Saldo final del ejercicio", "7 28 3 An Cierre"), repair=True)
    covered: set[int] = set()
    for parsed in sheet.fields:
        covered.update(range(parsed.offset, parsed.offset + parsed.length))

    assert not set(range(1, (sheet.total_positions or 0) + 1)) - covered


def test_a_headless_row_that_would_overlap_a_read_row_is_discarded() -> None:
    """The containment test, exercised where it actually bites.

    The fragment is staged BEFORE the intact row, so the position it would take
    -- 11 to 27, straight after the header -- is the very span the intact row
    then claims. Ordering it the other way round would place the candidate at 28
    instead and test nothing, which is how this case first passed vacuously.
    """
    lines = (*_HEADER, "17 N Fragmento que solaparia", "6 11 17 Num Fila intacta", "7 28 3 An Cierre")
    sheet = _read(lines, repair=True)
    at_eleven = [f for f in sheet.fields if f.offset == 11]

    assert len(at_eleven) == 1, [(f.offset, f.length, f.description[:24]) for f in sheet.fields]
    assert at_eleven[0].description.startswith("Fila intacta")


def test_nothing_is_staged_outside_the_repair_pass() -> None:
    """A design that reads cleanly is never offered this, by construction."""
    sheet = _read((*_HEADER, "17 N Saldo final del ejercicio", "7 28 3 An Cierre"), repair=False)

    assert not [f for f in sheet.fields if f.offset == 11]
