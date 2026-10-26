"""Fail-fast checks for typed casilla operand provenance."""

from __future__ import annotations

import pytest

from .....core.casilla_id import validated_casilla_id
from ..binding_value_contract import (
    BindingDataType,
    BindingValueChannel,
    BindingValueContract,
)
from ..errors import RegistryValidationError
from ..manual_input_selector import ManualInputProvider
from ..schema import BindingDefinition, FormulaDefinition
from ..schema_formula import FormulaExpression
from ..schema_input_kind import InputKind
from ._referential_integrity_support import (
    REFERENCE_LEGAL_ID,
    REFERENCE_SOURCE_ID,
    build_minimal_snapshot,
    minimal_revision,
    segmented_casilla,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


_SOURCE_CASILLA = validated_casilla_id("01")
_TARGET_CASILLA = validated_casilla_id("02")


def test_snapshot_build_fails_when_non_casilla_operand_ref_collides_with_casilla_id() -> None:
    """Snapshot publication refuses a token that is both casilla.id and binding id."""
    source_casilla = segmented_casilla(_SOURCE_CASILLA, "01", None)
    target_casilla_def = segmented_casilla(_TARGET_CASILLA, "02", None).model_copy(
        update={"input_kind": InputKind.COMPUTED, "formula": "test.binding-collision"},
    )
    formula = FormulaDefinition(
        id="test.binding-collision",
        target_casilla_id=_TARGET_CASILLA,
        expression=FormulaExpression(binding="01"),
        legal_refs=(REFERENCE_LEGAL_ID,),
        source_refs=(REFERENCE_SOURCE_ID,),
    )
    binding = BindingDefinition(
        id="01",
        provider=ManualInputProvider.model_validate(
            {
                "record": "DPA",
                "field": "test",
                "offset": 1,
                "length": 1,
                "data_type": "integer",
            },
        ),
        value=BindingValueContract(data_type=BindingDataType.INTEGER, channel=BindingValueChannel.INTEGER),
        legal_refs=(REFERENCE_LEGAL_ID,),
        source_refs=(REFERENCE_SOURCE_ID,),
    )

    with pytest.raises(RegistryValidationError, match="duplicate registry id '01' shared by casilla, binding"):
        build_minimal_snapshot(
            minimal_revision(casillas=(source_casilla, target_casilla_def), formulas=(formula,), bindings=(binding,)),
        )
