"""A refused edit value or binding value names the door of its refusal family.

Each error is built bare, the way its raising sites build it, and read through
the reader the operation error detail uses.
"""

from __future__ import annotations

import pytest

from ....core.external_constants import OutputLanguage
from ....core.operator_action_enums import NoRecoveryOutcome
from ...cli_exception_preconditions import nested_terminal_precondition_verdict
from ..edit_models import ModeloEditParseReason
from ..edit_number_parsing import read_edit_number_lexeme
from ..edit_parse_errors import ModeloEditParseRefusedError
from ..typed_query_contracts import ModeloBindingValueContractUnsupportedError, ModeloBindingValueInvalidError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.mark.parametrize("reason", list(ModeloEditParseReason))
def test_an_unparseable_edit_value_opens_set_value_leaving_the_work_unit_box_and_value_to_the_operator(
    reason: ModeloEditParseReason,
) -> None:
    verdict = nested_terminal_precondition_verdict(ModeloEditParseRefusedError(reason))

    assert verdict is not None
    assert verdict.action is not None
    assert verdict.action.action_id == "operator.modelo.work.set_value"
    assert set(verdict.missing_argument_names) == {"work_unit_id", "casilla_id", "value"}


def test_the_door_survives_a_refusal_raised_by_the_real_number_parser() -> None:
    with pytest.raises(ModeloEditParseRefusedError) as raised:
        read_edit_number_lexeme("1e5", OutputLanguage.EN, [])

    verdict = nested_terminal_precondition_verdict(raised.value)
    assert verdict is not None
    assert verdict.action is not None
    assert verdict.action.action_id == "operator.modelo.work.set_value"


def test_a_refused_binding_value_is_the_operators_to_state_again() -> None:
    verdict = nested_terminal_precondition_verdict(ModeloBindingValueInvalidError())

    assert verdict is not None
    assert verdict.action is None
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.OPERATOR_DECISION


def test_a_binding_without_an_official_value_grammar_is_terminal() -> None:
    verdict = nested_terminal_precondition_verdict(ModeloBindingValueContractUnsupportedError())

    assert verdict is not None
    assert verdict.action is None
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.TERMINAL
