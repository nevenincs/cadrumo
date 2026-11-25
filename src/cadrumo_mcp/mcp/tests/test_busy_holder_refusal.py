"""An agent refused for a busy subject is told which operation holds it, to report to the person."""

from __future__ import annotations

import pytest

from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.transport.frontend_client_contracts import (
    CustodyRecoveringEffectUnknownError,
    CustodyRecoveringError,
    FrontendRefusedError,
)

from ..protocol_contract import refusal_code, refusal_facts

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_HOLDER = "cd" * 32


def test_a_busy_refusal_names_its_holder_to_the_agent() -> None:
    refused = FrontendRefusedError(AccessDenialCode.SUBJECT_BUSY.value, holder_operation_id=_HOLDER)

    assert refusal_facts(refused) == {"holder_operation_id": _HOLDER}


def test_a_refusal_without_a_holder_adds_nothing() -> None:
    assert refusal_facts(FrontendRefusedError(AccessDenialCode.OPERATION_DENIED.value)) == {}


def test_a_change_the_lost_worker_was_serving_tells_the_agent_its_effect_is_unknown() -> None:
    refused = CustodyRecoveringEffectUnknownError(remaining_seconds=90, operation_id=_HOLDER)

    assert refusal_code(refused) == AccessDenialCode.CUSTODY_RECOVERING.value
    assert refusal_facts(refused) == {"effect": "unknown", "operation_id": _HOLDER}
    assert refusal_facts(CustodyRecoveringEffectUnknownError(remaining_seconds=None, operation_id=None)) == {
        "effect": "unknown"
    }
    # A session refused before anything reached the worker has nothing unknown to report.
    assert refusal_facts(CustodyRecoveringError(remaining_seconds=90)) == {}
