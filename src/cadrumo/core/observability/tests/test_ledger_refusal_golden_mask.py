"""Finite invocation-id policy for the two registered ledger read refusals."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest

from ....tests.golden_comparison import differing_paths, mask_document

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_PAIRS = (
    ("ledger.view", "REFUSED_FINANCIAL_LEDGER_TRANSACTION_ID_PREFIX"),
    ("ledger.evidence.view", "REFUSED_LEDGER_EVIDENCE_NOT_FOUND"),
)


def _refusal(command: str, code: str, operation_id: object) -> dict[str, Any]:
    return {
        "command": command,
        "status": "error",
        "error": {
            "code": code,
            "category": "REFUSED",
            "context": {
                "operation_id": operation_id,
                "terminal_condition": "refused",
                "effect": "none",
                "refusal_code": code,
            },
            "action": {"evidence": [{"values": {"reference_resolves": False}}]},
        },
        "result": {"operation_id": "visible-result-id"},
    }


@pytest.mark.parametrize(("command", "code"), _PAIRS)
def test_only_the_invocation_id_residual_is_normalised(command: str, code: str) -> None:
    first = _refusal(command, code, "1" * 64)
    second = _refusal(command, code, "2" * 64)
    assert differing_paths(first, second) == {"error.context.operation_id"}
    assert mask_document(first) == mask_document(second)
    assert first["error"]["context"]["operation_id"] == "1" * 64


@pytest.mark.parametrize(("command", "code"), _PAIRS)
@pytest.mark.parametrize("invalid", (None, "", "a" * 63, "a" * 65, "A" * 64, "g" * 64, 7, {}))
def test_malformed_invocation_ids_remain_visible(command: str, code: str, invalid: object) -> None:
    valid = _refusal(command, code, "1" * 64)
    malformed = _refusal(command, code, invalid)
    assert differing_paths(mask_document(valid), mask_document(malformed)) == {"error.context.operation_id"}


@pytest.mark.parametrize(("command", "code"), _PAIRS)
def test_missing_invocation_id_remains_visible(command: str, code: str) -> None:
    valid = _refusal(command, code, "1" * 64)
    missing = deepcopy(valid)
    del missing["error"]["context"]["operation_id"]
    assert differing_paths(mask_document(valid), mask_document(missing)) == {"error.context.operation_id"}


@pytest.mark.parametrize(
    ("command", "code"),
    (
        ("ledger.view", "REFUSED_LEDGER_EVIDENCE_NOT_FOUND"),
        ("ledger.evidence.view", "REFUSED_FINANCIAL_LEDGER_TRANSACTION_ID_PREFIX"),
        ("ledger.update", "REFUSED_FINANCIAL_LEDGER_TRANSACTION_ID_PREFIX"),
        ("ledger.evidence.view", "CONFLICT_RUNTIME_OPERATION_INVALID_FRAME"),
    ),
)
def test_other_command_or_code_keeps_its_invocation_id(command: str, code: str) -> None:
    first = _refusal(command, code, "1" * 64)
    second = _refusal(command, code, "2" * 64)
    assert differing_paths(mask_document(first), mask_document(second)) == {"error.context.operation_id"}


@pytest.mark.parametrize(("command", "code"), _PAIRS)
def test_refusal_semantics_and_result_ids_cannot_be_hidden(command: str, code: str) -> None:
    first = _refusal(command, code, "1" * 64)
    second = _refusal(command, code, "2" * 64)
    second["error"]["context"]["effect"] = "committed"
    second["error"]["context"]["terminal_condition"] = "succeeded"
    second["error"]["action"]["evidence"][0]["values"]["reference_resolves"] = True
    second["result"]["operation_id"] = "other-result-id"
    assert differing_paths(mask_document(first), mask_document(second)) == {
        "error.context.effect",
        "error.context.terminal_condition",
        "error.action.evidence[0].values.reference_resolves",
        "result.operation_id",
    }
