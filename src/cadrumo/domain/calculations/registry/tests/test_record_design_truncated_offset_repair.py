"""A row whose position lost a digit is restored from the pair restating it below.

Modelo 200's 2011 design loses one row of its ``Pág. 44`` record this way::

    17 198 17 N  Inst. inversión colectiva - Cuenta pérdidas y ganancias ...
    18 21 17 N   Inst. inversión colectiva - Cuenta pérdidas y ganancias ...
    18 215
    19 232 17 N  Inst. inversión colectiva - Cuenta pérdidas y ganancias ...

WHY THIS ONE IS DIFFERENT FROM THE OTHER READ REPAIRS. Every other row this
module rescues fails to parse, so the damage announces itself. This one PARSES.
It reads as ordinal 18 at position 21, seventeen bytes, and nothing downstream
doubts it -- so position 215 becomes a hole that skips the record, while the row
silently claims bytes 21-37 that belong to other fields.

WHAT SETTLES IT. The neighbours, three ways at once: the stranded pair repeats
the parsed row's OWN ordinal; the position it states resumes exactly where the
row above ends; and the position the row currently claims does NOT. The third
condition is what keeps this away from a healthy row that merely sits above a
stray pair of numbers.

MEASURED BEFORE BEING TRUSTED, because unlike the other repairs this one MUTATES
a row rather than rescuing one. Across all 218 bundled designs it rewrites
EXACTLY ONE LINE -- the one above. A repair that silently moved a field would
not show up in any skipped-record count, so the count of rewrites is the control
that matters and it is pinned here.
"""

from __future__ import annotations

import pytest

from .....core.resources._boundary import bundled_path
from ..record_design import extract_record_design
from ..record_design_pdf_repairs import _repair_truncated_offset_rows

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_DESIGN = bundled_path(
    "corpus",
    "aeat_official",
    "disenos_registro",
    "modelo_200",
    "files",
    "03-200-ejercicio-2011-522-kb-pdf.pdf",
)


def test_the_design_now_reads_without_skipping_a_record() -> None:
    extraction = extract_record_design(_DESIGN)

    assert not extraction.skipped, [(s.name, s.reason) for s in extraction.skipped]


def test_the_recovered_record_carries_the_row_at_its_true_position() -> None:
    extraction = extract_record_design(_DESIGN)
    sheet = next(s for s in extraction.sheets if s.name.strip().endswith(" 44"))

    field = next((f for f in sheet.fields if f.offset == 215), None)
    assert field is not None, "position 215 is still unread"
    assert field.ordinal == "18"
    assert field.length == 17

    assert not [f for f in sheet.fields if f.offset == 21], "the row is still also claiming the truncated position 21"


def test_the_recovered_record_tiles_without_a_hole() -> None:
    extraction = extract_record_design(_DESIGN)
    sheet = next(s for s in extraction.sheets if s.name.strip().endswith(" 44"))

    occupied: set[int] = set()
    for field in sheet.fields:
        occupied |= set(range(field.offset, field.offset + field.length))
    unwritten = sorted(set(range(1, (sheet.total_positions or 0) + 1)) - occupied)

    assert not unwritten, unwritten[:8]


def test_the_row_is_restored_when_all_three_conditions_hold() -> None:
    lines = (
        "17 198 17 N Inst. inversion colectiva.",
        "18 21 17 N Inst. inversion colectiva.",
        "18 215",
        "19 232 17 N Inst. inversion colectiva.",
    )

    repaired = _repair_truncated_offset_rows(lines)

    assert repaired == (
        "17 198 17 N Inst. inversion colectiva.",
        "18 215 17 N Inst. inversion colectiva.",
        "19 232 17 N Inst. inversion colectiva.",
    )


def test_a_row_already_at_the_resuming_position_is_left_alone() -> None:
    """The third condition: a HEALTHY row above a stray pair must not be touched.

    Here the row already resumes correctly at 215, so whatever the pair below
    says, there is no damage to repair.
    """
    lines = (
        "17 198 17 N Inst. inversion colectiva.",
        "18 215 17 N Inst. inversion colectiva.",
        "18 215",
    )

    assert _repair_truncated_offset_rows(lines) == lines


def test_a_pair_naming_another_ordinal_is_left_alone() -> None:
    """The first condition: the pair must restate the row's OWN ordinal."""
    lines = (
        "17 198 17 N Inst. inversion colectiva.",
        "18 21 17 N Inst. inversion colectiva.",
        "19 215",
    )

    assert _repair_truncated_offset_rows(lines) == lines


def test_a_pair_that_does_not_resume_the_previous_row_is_left_alone() -> None:
    """The second condition: the stated position must continue the row above."""
    lines = (
        "17 198 17 N Inst. inversion colectiva.",
        "18 21 17 N Inst. inversion colectiva.",
        "18 999",
    )

    assert _repair_truncated_offset_rows(lines) == lines
