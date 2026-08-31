"""A row whose coordinate column was damaged is rebuilt from the stutter restating it.

Modelo 200's 2010 and 2011 editions lose the coordinate column on some rows and
then restate it on the following line. The damage takes two forms and both cost
a whole record:

* the coordinates vanish, leaving ``17 N <description>`` with no position; or
* they survive mangled, so ``54 827`` arrives as ``4 82`` and parses as a real
  but WRONG row at ordinal 4, position 82.

Either way the true pair appears on the next line -- ``54 827 Ajustes por
valoracion [380]`` -- which is not itself a row, because it carries no length
and no naturaleza. Read together the two halves are one row; read apart, the
sheet has a hole and is skipped entirely.

WHAT THE GUARD IS. The coordinates are admitted only when OVER-DETERMINED
against the last undamaged row: the ordinal must follow by one AND the position
must resume where that row ended. The length and naturaleza are never inferred
-- a donor half must state them. That requirement is what makes this a recovery
rather than a reconstruction, and it is why the same two editions keep three
sites this declines: ``6 11 [213]`` states coordinates and a casilla and
nothing else, so recovering it would mean inventing a naturaleza and truncating
a description.
"""

from __future__ import annotations

import pytest

from .....core.resources.bundled_data import bundled_path
from ..record_design import extract_record_design
from ..record_design_pdf_repairs import _recover_coordinate_stutter_rows

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODELO_200 = bundled_path("corpus", "aeat_official", "disenos_registro", "modelo_200", "files")
_REPAIRED_DESIGN = "02-200-ejercicio-2010-472-kb-pdf.pdf"

#: The run this recovers, and the width AEAT gives every monetary field in it.
_RUN_OFFSETS = (776, 793, 810, 827, 844, 861)
_FIELD_WIDTH = 17


def _sheet_named(extraction, suffix: str):
    return next((sheet for sheet in extraction.sheets if sheet.name.strip().endswith(suffix)), None)


def test_the_recovered_record_is_no_longer_skipped() -> None:
    """The hole this closes, stated as the record it costs.

    This assertion once carried a second half naming the two records that were
    STILL skipped -- the position-10 pair on ``Pag. 21`` and ``Pag. 22`` -- and
    described them as carrying no numbers at all. That reading was wrong and
    both have since been recovered by their own repairs: the numbers were there,
    split across lines in three different ways. The design now reads whole, so
    the honest assertion is that nothing is skipped rather than that a
    particular remainder is.
    """
    extraction = extract_record_design(_MODELO_200 / _REPAIRED_DESIGN)

    assert not extraction.skipped, [(s.name, s.reason) for s in extraction.skipped]


def test_the_recovered_record_tiles_its_run_without_a_hole() -> None:
    """The recovered row is checked by the geometry it has to satisfy.

    Six consecutive ordinals, each 17 bytes, each starting where the last ended.
    A rebuilt row with the wrong ordinal or the wrong position cannot satisfy
    both, which is the same over-determination the repair admits it on.
    """
    extraction = extract_record_design(_MODELO_200 / _REPAIRED_DESIGN)
    sheet = _sheet_named(extraction, "31")
    assert sheet is not None, "the record is absent, so the recovery did not happen"

    by_offset = {field.offset: field for field in sheet.fields}
    for position, offset in enumerate(_RUN_OFFSETS, start=51):
        assert offset in by_offset, f"@{offset} is missing from the recovered run"
        field = by_offset[offset]
        assert field.ordinal == str(position), f"@{offset} carries ordinal {field.ordinal!r}"
        assert field.length == _FIELD_WIDTH, f"@{offset} is {field.length} bytes wide"


def test_the_sibling_record_no_longer_reports_an_empty_ordinal_cell() -> None:
    """The quieter half of the same damage, on a record that was never skipped.

    ``Pág. 30`` read whole throughout, but its position 844 came back with no
    ordinal. The schema states that an absent ordinal means AEAT LEFT THE CELL
    BLANK, never that the parser could not read it -- so this position was
    making a false declaration about the source document, and no contiguity
    check could see it because the bytes tiled.
    """
    extraction = extract_record_design(_MODELO_200 / _REPAIRED_DESIGN)
    sheet = _sheet_named(extraction, "30")
    assert sheet is not None

    field = next(candidate for candidate in sheet.fields if candidate.offset == 844)

    assert field.ordinal == "55"


def test_a_stutter_with_no_donor_half_is_declined() -> None:
    """The guard that keeps this a recovery rather than a reconstruction.

    This is the shape of the three sites left standing in these same two
    editions. The coordinates are over-determined and would be admitted, but no
    neighbouring line states a length or a naturaleza, so there is nothing to
    recover them from.
    """
    lines = (
        "12 500 17 N Something AEAT prints [100] ",
        "Modelo 200 Diseno de registro",
        "13 517 [101] ",
        "14 534 17 N The next row [102] ",
    )

    assert _recover_coordinate_stutter_rows(lines) == lines


def test_a_stutter_whose_coordinates_do_not_resume_is_declined() -> None:
    """The over-determination proved by breaking it.

    The donor half is present and well-formed; only the stated position is
    wrong -- it does not resume where the previous row ended. One disagreeing
    fact is enough to refuse, which is what stops this admitting prose that
    happens to open with two numbers.
    """
    lines = (
        "12 500 17 N Something AEAT prints [100] ",
        "17 N A description with no coordinates",
        "13 999 a tail fragment [101] ",
    )

    assert _recover_coordinate_stutter_rows(lines) == lines


def test_the_same_shape_is_recovered_when_the_position_does_resume() -> None:
    """The companion to the refusal above: only the position differs.

    Without this, the refusal could pass because the repair never fires on this
    shape at all rather than because the guard rejected it.
    """
    lines = (
        "12 500 17 N Something AEAT prints [100] ",
        "17 N A description with no coordinates",
        "13 517 a tail fragment [101] ",
    )

    recovered = _recover_coordinate_stutter_rows(lines)

    assert recovered == (
        "12 500 17 N Something AEAT prints [100] ",
        "13 517 17 N A description with no coordinates a tail fragment [101] ",
    )
