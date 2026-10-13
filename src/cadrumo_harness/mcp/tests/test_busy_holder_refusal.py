"""An agent refused for a busy subject is told which operation holds it, to report to the person."""

from __future__ import annotations

import pytest

from cadrumo.adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from cadrumo.application.user_profile.access_contracts import AccessDenialCode

from ..protocol_contract import refusal_facts

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_HOLDER = "cd" * 32


def test_a_busy_refusal_names_its_holder_to_the_agent() -> None:
    refused = RuntimeFrontendRefusedError(AccessDenialCode.SUBJECT_BUSY.value, holder_operation_id=_HOLDER)

    assert refusal_facts(refused) == {"holder_operation_id": _HOLDER}


def test_a_refusal_without_a_holder_adds_nothing() -> None:
    assert refusal_facts(RuntimeFrontendRefusedError(AccessDenialCode.OPERATION_DENIED.value)) == {}
