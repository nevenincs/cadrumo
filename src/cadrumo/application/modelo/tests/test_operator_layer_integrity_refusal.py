"""A stored operator layer that contradicts its builder's invariants is a terminal integrity refusal."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ....core.errors.error_codes import get_registered_error_code, resolve_error_message
from ....core.operator_action_enums import NoRecoveryOutcome
from ....domain.calculations.registry.tests.published_authority import published_supported_filing_years
from ....domain.modelos.calculation_revision_operator_layer import CalculationOperatorLayer, ValueAttestation
from ....domain.modelos.errors import ModeloOperatorLayerIntegrityError
from ...cli_exception_preconditions import nested_terminal_precondition_verdict

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BINDING = "modelo-100-carry-binding"


def _attestation() -> ValueAttestation:
    support = published_supported_filing_years()
    assert support is not None
    return ValueAttestation(source_modelo="100", source_filing_year=support.floor - 1, source_period="0A")


def _refused(layer: dict[str, object]) -> ModeloOperatorLayerIntegrityError:
    with pytest.raises(ValidationError) as refused:
        CalculationOperatorLayer.model_validate(layer)
    cause = refused.value.errors()[0]["ctx"]["error"]
    assert isinstance(cause, ValueError)
    registered = cause.__cause__
    assert isinstance(registered, ModeloOperatorLayerIntegrityError)
    return registered


@pytest.mark.parametrize("locale", ["es", "ca", "en", "hu"])
@pytest.mark.parametrize(
    "layer",
    [
        {"binding_overrides": {_BINDING: "1.50"}, "value_attestations": {_BINDING: _attestation()}},
        {
            "binding_overrides": {_BINDING: "0"},
            "attested_binding_ids": (_BINDING,),
            "value_attestations": {_BINDING: _attestation()},
        },
    ],
    ids=["value_not_canonical", "both_attestation_kinds"],
)
def test_a_contradictory_stored_layer_is_terminal_and_worded_in_every_locale(
    layer: dict[str, object], locale: str
) -> None:
    refusal = _refused(layer)

    verdict = nested_terminal_precondition_verdict(refusal)
    assert verdict is not None
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.TERMINAL
    assert get_registered_error_code(refusal).code == "INTEGRITY_MODELOS_OPERATOR_LAYER"
    message = resolve_error_message(refusal, locale=locale)
    assert _BINDING in message
    assert "%{" not in message
