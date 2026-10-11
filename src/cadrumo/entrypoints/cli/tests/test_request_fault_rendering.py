"""A refusal that carries the request model's faults reaches the command line's error with them."""

from __future__ import annotations

import json
import sys
from typing import cast

import pytest
import typer

from ....adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ....adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from ....application.user_profile.automation_custody_port import AutomationCustodyCode
from ....core.config import override_settings
from ....core.request_faults import RequestFault
from ..errors import CliRefusedBoundaryError, emit_error_and_exit
from ..registered_operation_contracts import RegisteredOperationProgress
from ..registered_operation_errors import map_registered_transport_failure

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_OPERATION = "a" * 64
_FAULTS = (
    RequestFault(location=("patch", "taxable_base"), type="value_error", message="a synthetic rule about a decimal"),
    RequestFault(location=("patch_fields",), type="value_error", message="a synthetic rule about an order"),
)


class _NoTransport:
    """Stands where the client is passed; a refusal that owns no transport cleanup never asks it anything."""


def _mapped(error: Exception) -> CliRefusedBoundaryError:
    client = cast(RuntimeFrontendClient, _NoTransport())
    return map_registered_transport_failure(client, _OPERATION, error, RegisteredOperationProgress())


def test_the_faults_the_runtime_returned_are_printed_in_the_error_context(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    refused = RuntimeFrontendRefusedError(AutomationCustodyCode.INVALID.value, request_faults=_FAULTS)
    assert refused.request_faults == _FAULTS

    monkeypatch.setattr(sys, "argv", ["aeat", "--format", "json"])
    with override_settings(cadrumo_output_language="en"), pytest.raises(typer.Exit):
        emit_error_and_exit(_mapped(refused))

    context = json.loads(capsys.readouterr().err)["error"]["context"]
    assert context["reason"] == "invalid"
    assert context["request_faults"] == (
        "patch.taxable_base: a synthetic rule about a decimal; patch_fields: a synthetic rule about an order"
    )


def test_a_refusal_without_faults_is_printed_as_it_was(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "argv", ["aeat", "--format", "json"])
    with override_settings(cadrumo_output_language="en"), pytest.raises(typer.Exit):
        emit_error_and_exit(_mapped(RuntimeFrontendRefusedError(AutomationCustodyCode.INVALID.value)))

    context = json.loads(capsys.readouterr().err)["error"]["context"]
    assert context["reason"] == "invalid"
    assert "request_faults" not in context
