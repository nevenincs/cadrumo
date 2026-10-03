"""The shared command boundary preserves recorded failures and transport coordinates."""

from __future__ import annotations

import json
import sys

import pytest
import typer

from ....application.operations.models import OperationId
from ....core.config import override_settings
from ....core.errors.error_codes import get_error_exit_code, get_registered_error_code_by_code
from ....core.operations import OperationEffect, OperationTerminalCondition
from ..errors import CliRefusedBoundaryError, emit_error_and_exit
from ..registered_operation_errors import submitted_operation_error

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


@pytest.mark.parametrize(
    "code,condition",
    [
        ("REFUSED_EVIDENCE_BUNDLE_NOT_FOUND", OperationTerminalCondition.REFUSED),
        ("FAIL_PROFILE_EXPORT", OperationTerminalCondition.FAILED),
    ],
)
def test_recorded_failure_uses_the_original_category_exit_code_and_operation_receipt(
    code: str,
    condition: OperationTerminalCondition,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    operation_id: OperationId = "a" * 64
    error = submitted_operation_error(operation_id, code, terminal_condition=condition, effect=OperationEffect.NONE)
    assert isinstance(error, CliRefusedBoundaryError)
    monkeypatch.setattr(sys, "argv", ["aeat", "--format", "json"])
    with override_settings(cadrumo_output_language="en"), pytest.raises(typer.Exit) as caught:
        emit_error_and_exit(error)
    captured = capsys.readouterr()
    document = json.loads(captured.err)
    registered = get_registered_error_code_by_code(code)
    assert caught.value.exit_code == get_error_exit_code(registered.category)
    assert document["error"]["code"] == code
    assert document["error"]["category"] == registered.category.value
    assert document["error"]["context"] == {
        "operation_id": str(operation_id),
        "reason": code,
        "effect": "none",
        "terminal_condition": condition.value,
    }
    assert document["error"]["message"] != code
    assert captured.out == ""


def test_unknown_transport_reason_retains_the_original_boundary() -> None:
    error = submitted_operation_error("a" * 64, "runtime_invalid_frame", terminal_condition=None, effect=None)
    assert type(error) is CliRefusedBoundaryError
    assert error.context is not None and error.context["effect"] == "unknown"
