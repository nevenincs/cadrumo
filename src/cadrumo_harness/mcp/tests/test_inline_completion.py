"""Inline completion retains the same result, refusal and recovery semantics."""

from typing import Any

import pytest

from ..operation_guidance import operation_guidance
from ..protocol_contract import has_refusal, unknown_outcome_instruction, validate_tool_arguments

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _submitted(lifecycle: str = "terminal", disposition: str = "none") -> dict[str, Any]:
    return {
        "outcome": "submitted",
        "receipt": {"operation_id": "o"},
        "reply": {
            "observation": {
                "outcome": "success",
                "projection": {
                    "operation_id": "o",
                    "lifecycle": lifecycle,
                    "pending_interaction": {"disposition": disposition},
                    "definition_contract": {"large": "schema"},
                    "effect": "none",
                },
                "event_page": {"old": "events"},
            }
        },
    }


def test_completed_result_needs_no_further_read_and_retains_receipt() -> None:
    response = _submitted()
    response["completion"] = {"outcome": "reply", "document": {"outcome": "success", "projection": {"rows": []}}}
    guided = operation_guidance("execute", response)
    assert guided["completion"] == response["completion"]
    assert guided["receipt"] == response["receipt"]
    assert "next_call" not in guided
    assert "definition_contract" not in guided["reply"]["observation"]["projection"]
    assert not has_refusal(guided)


def test_incomplete_work_and_pending_review_do_not_resubmit_or_auto_respond() -> None:
    active = operation_guidance("execute", _submitted("running"))
    assert active["next_call"]["tool"] == "observe"
    pending = operation_guidance("execute", _submitted("running", "pending"))
    assert "next_call" not in pending
    assert pending["receipt"] == {"operation_id": "o"}


def test_inline_refusal_is_reported_and_lost_read_is_not_a_failed_write() -> None:
    response = _submitted()
    response["completion"] = {
        "outcome": "reply",
        "document": {"outcome": "refused", "code": "operation_not_successful"},
    }
    assert has_refusal(response)
    response["completion"] = {"outcome": "unresolved", "code": "connection_closed"}
    assert not has_refusal(response)
    instruction = unknown_outcome_instruction(response)
    assert instruction is not None
    assert "Do not repeat this call" in instruction
    assert operation_guidance("execute", response)["next_call"]["tool"] == "result"


@pytest.mark.parametrize("wait", [-1, 6, True, 0.5, "2"])
def test_wait_is_a_bounded_integer(wait: object) -> None:
    with pytest.raises(ValueError):
        validate_tool_arguments("execute", {"definition_id": "ledger.list", "payload": {}, "wait_seconds": wait})


def test_zero_wait_retains_the_existing_submission_contract() -> None:
    validate_tool_arguments("execute", {"definition_id": "ledger.list", "payload": {}, "wait_seconds": 0})
    response = {"outcome": "submitted", "receipt": {"operation_id": "o"}}
    assert operation_guidance("execute", response)["next_call"]["tool"] == "observe"
