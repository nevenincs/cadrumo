"""A design's ``Tipo`` column renders as AEAT prints it, not as the sheet stores it.

A spreadsheet hands a whole-number cell back as a ``float``, so a ``Tipo`` of
``6`` arrives as ``6.0``. Rendering that verbatim produces a type code
(``"6.0"``) that appears nowhere in any diseño de registro, and the artifact is
reader-dependent rather than a property of the design: modelo 100's 2016 design
read from its ``.xls`` yielded ``"6.0"`` where the ``.xlsx`` conversion of the
SAME file yielded ``"6"``.

That divergence is how this surfaced and it is also the sharpest available
control, so it is the test: the two encodings of one design must agree field for
field. A reader that renders the type column differently depending on which
copy it opened is describing the reader, not the modelo.

:func:`~domain.calculations.registry.extract_record_design` is the read path
under test; the sibling ordinal column already carried this coercion, with a
docstring naming the same hazard.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .....core.resources import bundled_path
from .....core.tabular import coerce_cell_text
from ..record_design import extract_record_design

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_FILES = Path("corpus/aeat_official/disenos_registro/modelo_100/files")
#: The one design that shipped both encodings AND disagreed between them.
_STEM = "21-100-ejercicio-2016-1-90-mb-xls"


def _rows(path: Path):
    sheets = extract_record_design(path).require_complete()
    return [
        (sheet.name, field.offset, field.length, field.description, field.type_code)
        for sheet in sheets
        for field in sheet.fields
    ]


def test_the_coercion_is_what_renders_an_integral_float_as_an_integer() -> None:
    """Anti-vacuity: without the flag the artifact is real, with it the value is right.

    If this ever reads the same both ways, the test below would pass whether or
    not the read path coerces anything, and would be measuring nothing.
    """
    assert coerce_cell_text(6.0) == "6.0"
    assert coerce_cell_text(6.0, integral_floats_as_int=True) == "6"


#: The dual-encoding control needs a design that ships BOTH binaries, and the
#: modelo 100 design above is not one: only its .xls binary ships, beside
#: .xlsx.extracted sidecars whose own binary never did. Exactly one design in
#: the bundled corpus ships both, so the control reads that one rather than
#: asserting about a file that is not there.
_DUAL_ENCODING_FILES = Path("corpus/aeat_official/disenos_registro/modelo_200/files")
_DUAL_ENCODING_STEM = "01-200-ejercicio-2025-10-9-mb-xls"


def test_both_encodings_of_one_design_are_read_identically() -> None:
    xls = bundled_path() / _DUAL_ENCODING_FILES / f"{_DUAL_ENCODING_STEM}.xls"
    xlsx = bundled_path() / _DUAL_ENCODING_FILES / f"{_DUAL_ENCODING_STEM}.xlsx"
    if not (xls.is_file() and xlsx.is_file()):
        raise AssertionError(
            f"both encodings of {_DUAL_ENCODING_STEM} must ship for this control to mean anything",
        )

    from_xls, from_xlsx = _rows(xls), _rows(xlsx)

    assert len(from_xls) == len(from_xlsx), (
        f"the two encodings read a different number of fields ({len(from_xls)} against "
        f"{len(from_xlsx)}), which is a corpus divergence rather than a rendering one"
    )
    divergent = [(left, right) for left, right in zip(from_xls, from_xlsx, strict=True) if left != right]
    assert not divergent, (
        "the two encodings of one design disagree, so the reader is describing itself rather than "
        f"the modelo; first: {divergent[:2]}"
    )


def test_no_type_code_is_rendered_as_a_float() -> None:
    """The property, stated over the whole design rather than one field.

    Pinned as a shape rather than a count: a design gaining or losing rows must
    not make this pass vacuously, and no float-rendered type code is acceptable
    at any tally.
    """
    rows = _rows(bundled_path() / _FILES / f"{_STEM}.xls")
    floated = sorted({row[4] for row in rows if row[4] and row[4].replace(".", "", 1).isdigit() and "." in row[4]})

    assert not floated, f"type codes rendered with a decimal point: {floated}"
