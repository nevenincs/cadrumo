"""``ModeloValue`` enforces its documented provenance state matrix.

:class:`ModeloValue` documents three fields that are really one state matrix:
``value`` is absent exactly when ``kind`` is EMPTY, and
``formula_trace_casilla_ids`` is carried exactly when ``kind`` is COMPUTED.
Declared as independent pydantic fields with no cross-field validator, the model
accepted every contradictory combination — an EMPTY casilla holding a Decimal, a
COMPUTED casilla with no trace, a LITERAL casilla claiming a formula lineage —
and an encrypted draft round-trip preserved them, because the downstream formula
check only runs when a caller explicitly invokes the validator.

These tests pin the refusal at construction (which is also the rehydration path,
since pydantic runs the same validator on ``model_validate``) and confirm the
shapes the real builder emits still construct.
"""

from __future__ import annotations

import json
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ..schema import ModeloValue, ModeloValueKind

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_empty_kind_refuses_a_carried_value() -> None:
    """An EMPTY casilla must not carry a scalar: ``value is None`` iff EMPTY."""
    with pytest.raises(ValidationError, match=r"value is None only for kind EMPTY"):
        ModeloValue(
            casilla_id="03",
            value=Decimal("1"),
            kind=ModeloValueKind.EMPTY,
            source="registry schema",
        )


@pytest.mark.parametrize(
    "kind",
    [
        ModeloValueKind.LITERAL,
        ModeloValueKind.COMPUTED,
        ModeloValueKind.INHERITED,
        ModeloValueKind.DEFAULT,
    ],
)
def test_non_empty_kind_refuses_a_missing_value(kind: ModeloValueKind) -> None:
    """Only EMPTY may omit the value; every other provenance kind must carry one."""
    with pytest.raises(ValidationError, match=r"value is None only for kind EMPTY"):
        ModeloValue(
            casilla_id="03",
            value=None,
            kind=kind,
            source="registry input",
            # COMPUTED needs a trace to reach the value assertion rather than
            # tripping the trace rule first.
            formula_trace_casilla_ids=() if kind is ModeloValueKind.COMPUTED else None,
        )


def test_computed_kind_refuses_a_missing_formula_trace() -> None:
    """A COMPUTED value with no trace has no lineage to audit it against."""
    with pytest.raises(ValidationError, match=r"formula_trace_casilla_ids is carried only for kind"):
        ModeloValue(
            casilla_id="0604",
            value=Decimal("1520.00"),
            kind=ModeloValueKind.COMPUTED,
            source="registry formula renta-2024-pagos-fraccionados-ingresados",
        )


@pytest.mark.parametrize(
    "kind",
    [ModeloValueKind.LITERAL, ModeloValueKind.INHERITED, ModeloValueKind.DEFAULT],
)
def test_non_computed_kind_refuses_a_formula_trace(kind: ModeloValueKind) -> None:
    """A non-computed value must not claim a formula lineage it never had."""
    with pytest.raises(ValidationError, match=r"formula_trace_casilla_ids is carried only for kind"):
        ModeloValue(
            casilla_id="03",
            value=Decimal("10"),
            kind=kind,
            source="registry input",
            formula_trace_casilla_ids=("01", "02"),
        )


def test_computed_value_accepts_an_empty_declared_trace() -> None:
    """A formula over constants declares no casilla inputs; presence, not size, is the rule."""
    value = ModeloValue(
        casilla_id="0610",
        value=Decimal("2007.50"),
        kind=ModeloValueKind.COMPUTED,
        source="registry formula over constants",
        formula_trace_casilla_ids=(),
    )

    assert value.formula_trace_casilla_ids == ()


def test_builder_shapes_still_construct() -> None:
    """The four shapes ``build_draft`` emits remain valid under the matrix."""
    computed = ModeloValue(
        casilla_id="0604",
        value=Decimal("1520.00"),
        kind=ModeloValueKind.COMPUTED,
        source="registry formula renta-2024-pagos-fraccionados-ingresados",
        formula_trace_casilla_ids=("0601", "0602"),
    )
    inherited = ModeloValue(
        casilla_id="0596",
        value=Decimal("4500.00"),
        kind=ModeloValueKind.INHERITED,
        source="registry binding modelo-100-retenciones",
    )
    literal = ModeloValue(
        casilla_id="0003",
        value=Decimal("12000.25"),
        kind=ModeloValueKind.LITERAL,
        source="registry input",
    )
    empty = ModeloValue(
        casilla_id="0005",
        value=None,
        kind=ModeloValueKind.EMPTY,
        source="registry schema",
    )

    assert computed.formula_trace_casilla_ids == ("0601", "0602")
    assert inherited.formula_trace_casilla_ids is None
    assert literal.value == Decimal("12000.25")
    assert empty.value is None


def test_rehydration_refuses_a_contradictory_persisted_shape() -> None:
    """The matrix also runs on the JSON rehydration path a stored draft loads through.

    Enforcing only at construction would leave a draft already persisted with a
    contradictory shape readable; the storage boundary deserialises through
    ``model_validate_json``, which runs the same validator.
    """
    persisted = json.dumps(
        {
            "casilla_id": "03",
            "value": 1,
            "kind": "EMPTY",
            "source": "registry schema",
            "formula_trace_casilla_ids": None,
        },
    )

    with pytest.raises(ValidationError, match=r"value is None only for kind EMPTY"):
        ModeloValue.model_validate_json(persisted)
