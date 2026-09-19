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
fail, and the Unión scheme is where that matters -- it carries three lines where
the other two carry one each, so an omission there is invisible in the total
alone.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.core.casilla_id import validated_casilla_id
from cadrumo.domain.calculations.registry.formula_runtime import calculate_registry_snapshot
from cadrumo.domain.calculations.registry.schema import ModeloRevision

from ._registry_schema_support import _committed_modelo, _committed_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODELO = "369"

#: Each scheme's revision and the one total it states.
_SCHEMES = (
    ("esquema-union", "iva.union.cuota-total"),
    ("esquema-exterior", "iva.exterior.cuota-total"),
    ("esquema-importacion", "iva.importacion.cuota-total"),
)


def _declared_cuota_lines(revision: ModeloRevision, total_casilla_id: str) -> tuple[str, ...]:
    """The per-destination cuota casillas this scheme declares, excluding its total."""
    return tuple(
        sorted(
            str(casilla.id)
            for casilla in revision.casillas
            if str(casilla.id).endswith("-cuota") and str(casilla.id) != total_casilla_id
        ),
    )


@pytest.mark.parametrize(("revision_id", "total_casilla_id"), _SCHEMES)
def test_the_scheme_total_sums_every_destination_line_the_scheme_declares(
    revision_id: str,
    total_casilla_id: str,
) -> None:
    """The formula's operands are exactly the scheme's declared cuota lines.

    This is the omission check. A total is still arithmetically correct over a
    short operand list, so the defect that matters -- a destination line the
    total forgets -- shows up here and nowhere in the value.
    """
    revision = _committed_modelo(_MODELO).revisions[revision_id]
    formula = next(item for item in revision.formulas if str(item.target_casilla_id) == total_casilla_id)

    operands = tuple(sorted(str(arg.casilla_id) for arg in formula.expression.args))

    assert formula.expression.op == "add", f"{revision_id}: the scheme total is not a sum"
    assert operands == _declared_cuota_lines(revision, total_casilla_id), (
        f"{revision_id}: the total sums {operands!r} while the scheme declares "
        f"{_declared_cuota_lines(revision, total_casilla_id)!r}"
    )
    assert operands, f"{revision_id}: the scheme declares no destination line, so its total proves nothing"


def test_the_union_scheme_totals_its_three_destination_lines() -> None:
    """The worked case, through the real formula runtime rather than the declaration.

    Modelo 369's Unión scheme is the multi-line one, and distinct values are used
    per line so a total that double-counted or dropped one cannot land on the
    right answer by coincidence.
    """
    revision_id = "esquema-union"
    revision = _committed_modelo(_MODELO).revisions[revision_id]
    lines = _declared_cuota_lines(revision, "iva.union.cuota-total")
    assert len(lines) > 1, "the multi-line worked example needs a scheme with more than one destination"

    amounts = [Decimal("100.00") * (index + 1) for index in range(len(lines))]
    inputs = {
        validated_casilla_id(line, surface="test_modelo_369_registry"): amount
        for line, amount in zip(lines, amounts, strict=True)
    }

    snapshot = _committed_snapshot(_MODELO, 2025, "1T")
    result = calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        date_context={"filing_period": date(2025, 3, 31)},
    )

    assert result.values["iva.union.cuota-total"] == sum(amounts)
