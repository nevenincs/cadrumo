"""Fail-fast checks for typed casilla operand provenance."""

from __future__ import annotations

import pytest

from .....core import BindingSourceKind
from .._errors import RegistryValidationError
from .._ids import CasillaId, validated_casilla_id
from .._schema import DataBindingDefinition, FormulaDefinition, FormulaExpression, InputKind
from ._referential_integrity_support import (
    _DUMMY_LEGAL_ID,
    _DUMMY_SOURCE_ID,
    _build_minimal_snapshot,
    _minimal_revision,
    _segmented_casilla,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _casilla_id(value: object) -> CasillaId:
    try:
        return validated_casilla_id(value, surface="test casilla id")
    except ValueError as exc:
        raise AssertionError(f"test fixture {value!r} is not a CasillaId") from exc


_SOURCE_CASILLA = _casilla_id("01")
_TARGET_CASILLA = _casilla_id("02")


def test_snapshot_build_fails_when_non_casilla_operand_ref_collides_with_casilla_id() -> None:
    """Snapshot publication refuses a token that is both casilla.id and binding id."""
    source_casilla = _segmented_casilla(_SOURCE_CASILLA, "01", None)
    target_casilla_def = _segmented_casilla(_TARGET_CASILLA, "02", None).model_copy(
        update={"input_kind": InputKind.COMPUTED, "formula": "test.binding-collision"},
    )
    formula = FormulaDefinition(
        id="test.binding-collision",
        target_casilla_id=_TARGET_CASILLA,
        expression=FormulaExpression(binding="01"),
        legal_refs=(_DUMMY_LEGAL_ID,),
        source_refs=(_DUMMY_SOURCE_ID,),
    )
    binding = DataBindingDefinition(
        id="01",
        source=BindingSourceKind.MANUAL_INPUT,
        selector={
            "record": "DPA",
            "field": "test",
            "offset": 1,
            "length": 1,
            "data_type": "integer",
        },
        legal_refs=(_DUMMY_LEGAL_ID,),
        source_refs=(_DUMMY_SOURCE_ID,),
    )

    with pytest.raises(RegistryValidationError, match="duplicate registry id '01' shared by casilla, binding"):
        _build_minimal_snapshot(
            _minimal_revision(casillas=(source_casilla, target_casilla_def), formulas=(formula,), bindings=(binding,)),
        )
