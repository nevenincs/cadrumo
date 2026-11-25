"""A refused work metadata operation reaches the command as the error its executor raised."""

from __future__ import annotations

import pytest

from cadrumo_client.commands.errors import CliRecordedOperationError, CliRefusedBoundaryError
from cadrumo_client.transport.modelo_metadata import ModeloMetadataRunError

from ....application.operations.error_detail import OperationErrorDetailKind, OperationErrorDetailV1
from ....application.operator_actions.preconditions import profile_required_facts_missing_verdict
from ....core.errors.error_codes import get_registered_error_code
from ....core.operations import OperationEffect, OperationTerminalCondition
from ..operation_modelo_metadata import _refuse

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_OPERATION_ID = "f" * 64


def test_recorded_detail_rebuilds_the_executor_error_with_its_verdict_and_settlement_facts() -> None:
    verdict = profile_required_facts_missing_verdict(modelo=None, field_paths=("identity.tax_id",))
    # The detail as the client decodes it from the worker's recorded document.
    detail = OperationErrorDetailV1.model_validate_json(
        OperationErrorDetailV1(
            kind=OperationErrorDetailKind.REGISTERED_ERROR,
            error_code="REFUSED_USER_PROFILE_VALIDATION",
            message_key="errors.refused.refused_user_profile_validation",
            context=(),
            precondition_verdict_json=verdict.model_dump_json(),
        ).model_dump_json()
    )

    error = _refuse(
        ModeloMetadataRunError(
            operation_id=_OPERATION_ID,
            code="REFUSED_USER_PROFILE_VALIDATION",
            terminal_condition=OperationTerminalCondition.REFUSED,
            effect=OperationEffect.NONE,
            detail=detail,
        )
    )

    assert isinstance(error, CliRecordedOperationError)
    assert get_registered_error_code(error).code == "REFUSED_USER_PROFILE_VALIDATION"
    assert error.terminal_precondition_verdict == verdict
    assert error.context is not None
    assert error.context["operation_id"] == _OPERATION_ID
    assert error.context["effect"] == OperationEffect.NONE.value
    assert error.context["terminal_condition"] == OperationTerminalCondition.REFUSED.value


def test_a_refusal_without_recorded_detail_keeps_the_settled_code() -> None:
    error = _refuse(
        ModeloMetadataRunError(
            operation_id=_OPERATION_ID,
            code="refusal:modelo.metadata.denied",
            terminal_condition=OperationTerminalCondition.REFUSED,
            effect=OperationEffect.NONE,
        )
    )

    assert type(error) is CliRefusedBoundaryError
    assert error.context is not None
    assert error.context["reason"] == "refusal:modelo.metadata.denied"
