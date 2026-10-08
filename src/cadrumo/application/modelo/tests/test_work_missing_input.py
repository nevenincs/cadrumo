"""Classification of calculation input refusals before revision publication."""

from __future__ import annotations

import pytest

from ....domain.calculations.registry.errors import RegistryValidationError
from ..work_missing_input import ModeloWorkMissingInputError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.mark.parametrize(
    "message",
    [
        "errors.calc.binding_value_missing",
        "errors.calc.bound_casilla_binding_value_missing",
        "errors.calc.date_binding_value_missing",
        "errors.calc.enum_binding_value_missing",
    ],
)
def test_supported_engine_refusal_retains_renderer_fields_and_source(message: str) -> None:
    source = RegistryValidationError(
        "binding 'synthetic.binding' has no supplied value",
        translated_message=message,
        context={"binding_id": "synthetic.binding", "op": "synthetic_op"},
    )

    classified = ModeloWorkMissingInputError.from_registry_error(source)

    assert isinstance(classified, RegistryValidationError)
    assert classified.binding_id == "synthetic.binding"
    assert classified.args == source.args
    assert str(classified) == str(source)
    assert classified.translated_message == source.translated_message
    assert classified.context == source.context
    assert classified.context is not source.context
    assert classified.__cause__ is source


@pytest.mark.parametrize(
    ("message", "binding_id"),
    [
        ("errors.calc.relation_value_missing", "synthetic.binding"),
        ("errors.calc.binding_value_missing", None),
        ("errors.calc.binding_value_missing", ""),
        ("errors.calc.binding_value_missing", " synthetic.binding "),
        ("errors.calc.binding_value_missing", "first,second"),
        ("errors.calc.date_binding_value_missing", 123),
        ("errors.calc.bound_casilla_binding_value_missing", "first,second"),
    ],
)
def test_unsupported_or_malformed_refusal_stays_unclassified(message: str, binding_id: object) -> None:
    source = RegistryValidationError(
        "original refusal",
        translated_message=message,
        context={"binding_id": binding_id},
    )

    assert ModeloWorkMissingInputError.from_registry_error(source) is None
    assert str(source) == "original refusal"
    assert source.translated_message == message


def test_missing_context_stays_unclassified() -> None:
    source = RegistryValidationError("original refusal", translated_message="errors.calc.binding_value_missing")

    assert ModeloWorkMissingInputError.from_registry_error(source) is None
