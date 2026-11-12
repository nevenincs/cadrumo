"""A Modelo edit refused at its commit point names the door of its refusal family.

Each refusal is built the way the edit boundary builds it, from the typed
refusal it settles under or bare where the command line raises it, and read
through the reader the operation error detail uses.
"""

from __future__ import annotations

import pytest

from ....core.errors.error_codes import resolve_error_message
from ....core.operator_action_enums import NoRecoveryOutcome
from ...cli_exception_preconditions import nested_terminal_precondition_verdict
from ..action_errors import (
    ModeloEditBaselineStaleError,
    ModeloEditContractIncompatibleError,
    ModeloEditIntentUnsupportedError,
    ModeloEditRefusedError,
    modelo_edit_refusal_error,
)
from ..edit_models import ModeloEditParseReason, ModeloEditParseRefusalV1, ModeloEditScalarAddressV1

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_LOCALES = ("es", "ca", "en", "hu")


def test_a_refused_value_opens_set_value_leaving_the_work_unit_box_and_value_to_the_operator() -> None:
    refusal = ModeloEditParseRefusalV1(
        address=ModeloEditScalarAddressV1(casilla_id="0001"), reason=ModeloEditParseReason.CHANNEL_UNAVAILABLE
    )
    error = modelo_edit_refusal_error(refusal)

    assert type(error) is ModeloEditRefusedError
    verdict = nested_terminal_precondition_verdict(error)
    assert verdict is not None
    assert verdict.action is not None
    assert verdict.action.action_id == "operator.modelo.work.set_value"
    assert set(verdict.missing_argument_names) == {"work_unit_id", "casilla_id", "value"}


def test_a_stale_form_opens_the_work_status_to_read_it_again() -> None:
    verdict = nested_terminal_precondition_verdict(ModeloEditBaselineStaleError())

    assert verdict is not None
    assert verdict.action is not None
    assert verdict.action.action_id == "operator.modelo.work.status"
    assert set(verdict.missing_argument_names) == {"work_unit_id"}


@pytest.mark.parametrize(
    ("error", "outcome"),
    [
        (ModeloEditIntentUnsupportedError(), NoRecoveryOutcome.OPERATOR_DECISION),
        (ModeloEditContractIncompatibleError(), NoRecoveryOutcome.TERMINAL),
    ],
    ids=["intent_unsupported", "contract_incompatible"],
)
def test_a_refusal_no_action_repairs_names_its_outcome(
    error: ModeloEditRefusedError, outcome: NoRecoveryOutcome
) -> None:
    verdict = nested_terminal_precondition_verdict(error)

    assert verdict is not None
    assert verdict.action is None
    assert verdict.no_recovery_outcome is outcome


@pytest.mark.parametrize(
    "error_type",
    [
        ModeloEditRefusedError,
        ModeloEditBaselineStaleError,
        ModeloEditIntentUnsupportedError,
        ModeloEditContractIncompatibleError,
    ],
)
def test_every_edit_refusal_keeps_its_served_words(error_type: type[ModeloEditRefusedError]) -> None:
    error = error_type()
    for locale in _LOCALES:
        message = resolve_error_message(error, locale=locale)
        assert message
        assert "%{" not in message
