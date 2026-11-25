"""Modelo 369 totals every destination line its own scheme declares.

The Ventanilla Única return is filed under three schemes -- Unión, exterior and
importación -- and each states one total: the cuota repercutida summed over the
per-destination lines that scheme carries. Orden HAC/610/2021 approves the form
and its record design, and the totals are the arithmetic those lines exist for.

THE OPERAND SET IS DERIVED, NOT COPIED. The expectation here comes from the
revision's own declared cuota lines rather than from the formula under test: a
formula that dropped a destination would still sum its remaining operands
correctly and would pass any check that read the expectation off it. Comparing
the operands against the declared lines is what makes a dropped destination
fail. Each scheme settles one line per destination: those lines read the fixed
rows of the return, which the live export test exercises with real rows.
"""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.schema import ModeloRevision

from .registry_schema_support import committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODELO = "369"

#: Each scheme's revision and the one total it states.
_SCHEMES = (
    ("esquema-union", "iva.union.cuota-total", ".total-periodo"),
    ("esquema-exterior", "iva.exterior.cuota-total", ".servicios"),
    ("esquema-importacion", "iva.importacion.cuota-total", ".importaciones"),
)


def _declared_settlement_lines(revision: ModeloRevision, line_suffix: str) -> tuple[str, ...]:
    """The per-destination settlement casillas this scheme declares."""
    return tuple(
        sorted(
            str(casilla.id)
            for casilla in revision.casillas
            if ".resultado." in str(casilla.id) and str(casilla.id).endswith(line_suffix)
        ),
    )


@pytest.mark.parametrize(("revision_id", "total_casilla_id", "line_suffix"), _SCHEMES)
def test_the_scheme_total_sums_every_destination_line_the_scheme_declares(
    revision_id: str,
    total_casilla_id: str,
    line_suffix: str,
) -> None:
    """The formula's operands are exactly the scheme's declared settlement lines.

    This is the omission check. A total is still arithmetically correct over a
    short operand list, so the defect that matters -- a destination line the
    total forgets -- shows up here and nowhere in the value.
    """
    revision = committed_modelo(_MODELO).revisions[revision_id]
    formula = next(item for item in revision.formulas if str(item.target_casilla_id) == total_casilla_id)

    operands = tuple(sorted(str(arg.casilla_id) for arg in formula.expression.args))
    declared = _declared_settlement_lines(revision, line_suffix)

    assert formula.expression.op == "add", f"{revision_id}: the scheme total is not a sum"
    assert operands == declared, f"{revision_id}: the total sums {operands!r} while the scheme declares {declared!r}"
    assert operands, f"{revision_id}: the scheme declares no destination line, so its total proves nothing"
