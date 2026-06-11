"""Real-behavior coverage for localized modelo calculation input errors."""

from __future__ import annotations

import pytest

from ....core.errors import AeatError, build_error_envelope, resolve_error_message
from .._calculate_input import ModeloCalculateDecimalInputError, _decimal
from .._selectors import ModeloCalculationRevisionSelector
from .._work_addressing import ModeloRevisionPick, ModeloRevisionPickError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_decimal_override_error_is_typed_registered_and_localized() -> None:
    with pytest.raises(ModeloCalculateDecimalInputError) as exc_info:
        _decimal("not-decimal", flag="--relation", key="iva_base")

    error = exc_info.value
    assert isinstance(error, AeatError)
    assert error.translated_message == "application.modelo.errors.calculate_decimal_input_invalid"
    assert error.context == {"flag": "--relation", "key": "iva_base", "value": "not-decimal"}
    assert build_error_envelope(error).code
    assert "iva_base" in resolve_error_message(error)


def test_revision_pick_error_is_typed_registered_and_localized() -> None:
    with pytest.raises(ModeloRevisionPickError) as exc_info:
        ModeloRevisionPick(selector=ModeloCalculationRevisionSelector.EXPLICIT)

    error = exc_info.value
    assert isinstance(error, AeatError)
    assert error.translated_message == "application.modelo.errors.revision_pick_explicit_id_required"
    assert build_error_envelope(error).code
    assert "calculation_revision_id" in resolve_error_message(error)
