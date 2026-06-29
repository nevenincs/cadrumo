"""Registry contract for operator-supplied local observation errors."""

from __future__ import annotations

import pytest

from ....core.errors import ERROR_REGISTRY, AeatError, ErrorCategory, build_error_envelope, get_registered_error_code
from ....domain.modelos._errors import ModeloError
from .._action_errors import ModeloLocalObservationError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_modelo_local_observation_error_is_registered_and_envelopes() -> None:
    assert issubclass(ModeloLocalObservationError, ModeloError)
    assert issubclass(ModeloLocalObservationError, AeatError)

    code = get_registered_error_code(ModeloLocalObservationError)

    assert code.code == "REFUSED_MODELO_LOCAL_OBSERVATION"
    assert code.category is ErrorCategory.REFUSED
    assert code.default_suggestion == "aeat app modelo filing-record observe-local --help"
    assert ERROR_REGISTRY[code.code] is code

    envelope = build_error_envelope(
        ModeloLocalObservationError(
            "local observation requires at least one --set CASILLA=DECIMAL value",
        ),
    )

    assert envelope.code == "REFUSED_MODELO_LOCAL_OBSERVATION"
    assert envelope.category == "REFUSED"
    assert envelope.suggestion == "aeat app modelo filing-record observe-local --help"
    assert envelope.message == "local observation requires at least one --set CASILLA=DECIMAL value"
