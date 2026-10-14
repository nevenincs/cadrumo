"""The Operations run screen says why the runtime's request model refused a request, field by field."""

from __future__ import annotations

import pytest

from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError

from ....application.user_profile.automation_custody_port import AutomationCustodyCode
from ....core.config import override_settings
from ....core.i18n.render import tr
from ....core.request_faults import RequestFault
from ..operations.run_screen import OperationRunScreen

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_FAULTS = (
    RequestFault(location=("patch", "taxable_base"), type="value_error", message="a synthetic rule about a decimal"),
    RequestFault(location=("lines", 2), type="missing", message="Field required"),
    RequestFault(location=(), type="value_error", message="synthetic action 'list' takes no reference; use 'add'"),
)


def test_each_fault_the_runtime_returned_is_shown_under_the_refusal_as_the_form_spells_its_own() -> None:
    refused = FrontendRefusedError(AutomationCustodyCode.INVALID.value, request_faults=_FAULTS)

    assert OperationRunScreen._failure_text(refused).splitlines() == [
        "invalid",
        "patch.taxable_base: a synthetic rule about a decimal",
        "lines.2: Field required",
        "synthetic action 'list' takes no reference; use 'add'",
    ]


def test_a_refusal_without_faults_is_shown_as_it_was() -> None:
    assert OperationRunScreen._failure_text(FrontendRefusedError("operation_denied")) == "operation_denied"


def test_a_busy_refusal_names_the_operation_holding_the_subject() -> None:
    holder = "ef" * 32
    refused = FrontendRefusedError("subject_busy", holder_operation_id=holder)

    with override_settings(cadrumo_output_language="en"):
        lines = OperationRunScreen._failure_text(refused).splitlines()
        assert lines == ["subject_busy", tr("tui.operations.run.busy_holder", operation_id=holder)]

    assert holder in lines[1]
