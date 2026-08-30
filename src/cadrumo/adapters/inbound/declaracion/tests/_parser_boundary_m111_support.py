"""Shared Modelo 111 parser boundary corpus expectations."""

from __future__ import annotations

from .....core.casilla_id import validated_casilla_id
from ._parser_boundary_support import CasillaId, Decimal

_M111_CASILLA_07: CasillaId = validated_casilla_id("07", surface="declaracion_parser_boundary.casilla")
_M111_CASILLA_08: CasillaId = validated_casilla_id("08", surface="declaracion_parser_boundary.casilla")
_M111_CASILLA_09: CasillaId = validated_casilla_id("09", surface="declaracion_parser_boundary.casilla")
_M111_CASILLA_28: CasillaId = validated_casilla_id("28", surface="declaracion_parser_boundary.casilla")
_M111_CASILLA_30: CasillaId = validated_casilla_id("30", surface="declaracion_parser_boundary.casilla")
_M111_CORPUS_PARAMS: tuple[tuple[str, int, str], ...] = (
    ("2024-1T", 2024, "1T"),
    ("2024-2T", 2024, "2T"),
    ("2024-3T", 2024, "3T"),
    ("2024-4T", 2024, "4T"),
)
_M111_CORPUS_IDS: tuple[str, ...] = tuple(stem for stem, _year, _period in _M111_CORPUS_PARAMS)

_M111_FORM_TIED_CASILLAS: frozenset[CasillaId] = frozenset(
    {_M111_CASILLA_09, _M111_CASILLA_28, _M111_CASILLA_30},
)
"""Casillas whose printed values the FORM ties together on these renders.

With one epigrafe filled and no prior autoliquidacion, ``28`` is the sum that
reduces to ``09`` and ``30 = 28 - 29`` reduces to ``28``. They are therefore
expected to repeat, and a distinctness guard must exempt them rather than
demanding a form that contradicts its own stated formula. Named here so the
exemption is a declared property of the form and not a literal in an assertion.
"""

_M111_EXPECTED_VALUES_BY_STEM: dict[str, dict[CasillaId, Decimal]] = {
    "2024-1T": {
        _M111_CASILLA_07: Decimal("3"),
        _M111_CASILLA_08: Decimal("12480.00"),
        _M111_CASILLA_09: Decimal("2371.20"),
        _M111_CASILLA_28: Decimal("2371.20"),
        _M111_CASILLA_30: Decimal("2371.20"),
    },
    "2024-2T": {
        _M111_CASILLA_07: Decimal("4"),
        _M111_CASILLA_08: Decimal("15630.50"),
        _M111_CASILLA_09: Decimal("2969.80"),
        _M111_CASILLA_28: Decimal("2969.80"),
        _M111_CASILLA_30: Decimal("2969.80"),
    },
    "2024-3T": {
        _M111_CASILLA_07: Decimal("2"),
        _M111_CASILLA_08: Decimal("9145.25"),
        _M111_CASILLA_09: Decimal("1737.60"),
        _M111_CASILLA_28: Decimal("1737.60"),
        _M111_CASILLA_30: Decimal("1737.60"),
    },
    "2024-4T": {
        _M111_CASILLA_30: Decimal("4208.15"),
    },
}
"""Exactly what each committed M111 render prints, per quarter.

Every quarter carries DIFFERENT amounts, and within a quarter the perceptor
count, the base and the retencion differ from one another. The renders these
replace printed the sanitiser's single ``1000.00`` into every money box of all
four files, so no assertion over them could tell a cross-column misread from a
cross-QUARTER one.

Casillas 09, 28 and 30 do repeat within a quarter. That is the form's own
arithmetic rather than a weakness: with only epigrafe 3 filled and no prior
autoliquidacion, ``28 = 03+06+...+27`` reduces to ``09`` and ``30 = 28 - 29``
reduces to ``28``. Printing three different numbers there would render a form
that contradicts its own stated formula.

Mirrored from the stamped amounts in
``tests/fixtures/justificantes/_generate_modelo_111.py``, the same arrangement
the M100 and current-year fixtures use. The generator is not the code under
test -- the parser is -- so this is the printed document's own authority.
"""
