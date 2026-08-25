"""Modelo 193's records reach the 500 positions AEAT declares, and their gaps are AEAT's own.

A fixed-width record is written into a buffer sized by its LAST field, and every
position no field claims is emitted as a space. That makes two different things
look alike from a distance: a record that stops short of the design (a genuinely
truncated line) and a record that spans the design but leaves AEAT's declared
filler runs unwritten (a correct line).

Modelo 193 was raised as the first. It is the second. All three records --
declarante, perceptor, gastos -- span exactly 500 positions in both revisions,
matching what their design sheets declare, and every unwritten run coincides
byte-for-byte with a design field AEAT itself labels ``BLANCOS``.

THE AUTHORITY IS THE DESIGN, NOT THE LAYOUT. The extent is checked against the
sheet's ``total_positions`` rather than against the layout's own arithmetic,
which would restate the same numbers and prove nothing. The gap check is what
distinguishes correct-and-sparse from truncated: a gap that fell over a design
field carrying a description would be an unwritten DATA position, which is the
defect this shape is mistaken for.
"""

from __future__ import annotations

import pytest

from .....core.resources import bundled_path
from .. import extract_record_design
from ._registry_schema_support import _committed_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: AEAT's own word for a filler run in a Diseño de Registros.
_FILLER = "BLANCOS"

#: Record id -> the design sheet that governs it.
_SHEET_FOR_RECORD = {
    "modelo-193-declarante": "Tipo 1 - Registro De Declarante",
    "modelo-193-perceptor": "Tipo 2 - Registro De Perceptor",
    "modelo-193-gastos": "Tipo 2 - Registro De Perceptor  Relaci\xf3n De Gastos",
}


def _gap_runs(positions: list[int]) -> list[tuple[int, int]]:
    runs: list[tuple[int, int]] = []
    start = previous = None
    for position in positions:
        if start is None:
            start = previous = position
        elif position == previous + 1:
            previous = position
        else:
            runs.append((start, previous))
            start = previous = position
    if start is not None:
        runs.append((start, previous))
    return runs


def _modelo_193_cases():
    modelos, catalogues = _committed_registry_tree()
    modelo = next(candidate for candidate in modelos if candidate.id == "193")
    for revision_id, revision in modelo.revisions.items():
        design_refs = [ref for ref in revision.source_refs if catalogues.sources[ref].kind == "record_design"]
        assert design_refs, f"193/{revision_id} declares no record design to check against"
        design = extract_record_design(bundled_path() / catalogues.sources[design_refs[0]].corpus_path)
        sheets = {sheet.name: sheet for sheet in design.sheets}
        for layout in revision.export_layouts or ():
            for record in layout.records:
                yield revision_id, record, sheets[_SHEET_FOR_RECORD[record.id]]


def test_every_record_spans_the_positions_its_design_sheet_declares() -> None:
    """Truncation is the defect this rules out, and the design is the ruler."""
    checked = 0
    for revision_id, record, sheet in _modelo_193_cases():
        extent = max(field.offset + field.length - 1 for field in record.fields)
        assert extent == sheet.total_positions, (
            f"193/{revision_id} record {record.id} spans {extent} positions but its design "
            f"sheet {sheet.name!r} declares {sheet.total_positions}"
        )
        checked += 1
    assert checked, "no modelo 193 records were checked, so this asserts nothing"


def test_every_unwritten_run_is_a_filler_the_design_declares() -> None:
    """The check that separates correct-and-sparse from silently-unwritten.

    A gap falling over a design field with a real description would be a DATA
    position the layout never writes -- a blank slot behind a valid-looking
    line. Every modelo 193 gap falls over a ``BLANCOS`` field instead.
    """
    checked = 0
    for revision_id, record, sheet in _modelo_193_cases():
        occupied: set[int] = set()
        for field in record.fields:
            occupied |= set(range(field.offset, field.offset + field.length))
        for low, high in _gap_runs(sorted(set(range(1, sheet.total_positions + 1)) - occupied)):
            covering = [
                design_field
                for design_field in sheet.fields
                if design_field.offset <= high and design_field.offset + design_field.length - 1 >= low
            ]
            assert covering, (
                f"193/{revision_id} record {record.id} leaves {low}-{high} unwritten and the "
                "design declares no field there at all"
            )
            for design_field in covering:
                description = (design_field.description or "").strip().rstrip(".").upper()
                assert description == _FILLER, (
                    f"193/{revision_id} record {record.id} leaves {low}-{high} unwritten, but the "
                    f"design carries {description!r} there, so a data position is going out blank"
                )
            checked += 1
    assert checked, "no gaps were examined, so the filler property is untested"
