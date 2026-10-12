"""The Operations run screen says why the runtime's request model refused a request, field by field."""

from __future__ import annotations

import pytest

from ....adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from ....application.user_profile.automation_custody_port import AutomationCustodyCode
from ....core.request_faults import RequestFault
from ..operations.run_screen import OperationRunScreen

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_FAULTS = (
    RequestFault(location=("patch", "taxable_base"), type="value_error", message="a synthetic rule about a decimal"),
    RequestFault(location=("lines", 2), type="missing", message="Field required"),
    RequestFault(location=(), type="value_error", message="synthetic action 'list' takes no reference; use 'add'"),
)


def test_each_fault_the_runtime_returned_is_shown_under_the_refusal_as_the_form_spells_its_own() -> None:
    refused = RuntimeFrontendRefusedError(AutomationCustodyCode.INVALID.value, request_faults=_FAULTS)

    assert OperationRunScreen._failure_text(refused).splitlines() == [
        "invalid",
        "patch.taxable_base: a synthetic rule about a decimal",
        "lines.2: Field required",
        "synthetic action 'list' takes no reference; use 'add'",
    ]


def test_a_refusal_without_faults_is_shown_as_it_was() -> None:
    assert OperationRunScreen._failure_text(RuntimeFrontendRefusedError("operation_denied")) == "operation_denied"
