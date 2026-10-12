"""A payload the runtime's request model refuses comes back to an MCP client with the model's reasons.

The adapter, the installed client it opens, the native transport, the runtime,
the session authority, the profile worker and the stored sign-in are real, and
the request models are the registered operations' own. The native login the
runtime observes, the keychain holding the proof and the runtime's wall clock
are ports held by the test. The MCP SDK is not involved: the adapter is called
as the server calls it.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from cadrumo.application.ledger.classify_requests import LEDGER_CLASSIFY_OPERATION_DEFINITION_ID
from cadrumo.application.ledger.own_account_operation import LEDGER_OWN_ACCOUNT_OPERATION_DEFINITION_ID
from cadrumo.core.config import override_settings
from cadrumo_harness.mcp.runtime_adapter import RuntimeMcpAdapter

from .stored_sign_in_runtime import StoredSignInRuntime, stored_sign_in_runtime

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows worker and protected pipes"),
    pytest.mark.usefixtures("authority_operation"),
]

_NON_CANONICAL = "1.50"
_PRIVATE_NOTE = "synthetic-private-note-7f3a"
_PRIVATE_ACCOUNT = "ES00SYNTHETICPRIVATEACCOUNT" + "9" * 48
"""Longer than an account number may be, so the model refuses the member that holds it."""


def _adapter() -> RuntimeMcpAdapter:
    """An adapter started with no credential reference and no profile named."""
    return RuntimeMcpAdapter(profile_id=None, client=None, resumes_sign_in=True)


async def _execute(
    adapter: RuntimeMcpAdapter, runtime: StoredSignInRuntime, definition_id: str, **members: object
) -> dict[str, Any]:
    payload = {"profile_id": str(runtime.profile_id), **members}
    return await adapter.call("execute", {"definition_id": definition_id, "payload": payload})


def _faults(reply: dict[str, Any]) -> dict[tuple[str | int, ...], tuple[str, str]]:
    """Index a refusal's faults by location, asserting the shape every fault has."""
    assert (reply["outcome"], reply["code"]) == ("refused", "invalid"), reply
    assert set(reply) == {"outcome", "code", "faults"}, reply
    indexed: dict[tuple[str | int, ...], tuple[str, str]] = {}
    for fault in reply["faults"]:
        assert set(fault) == {"location", "type", "message"}, fault
        indexed[tuple(fault["location"])] = (fault["type"], fault["message"])
    assert len(indexed) == len(reply["faults"])
    return indexed


@pytest.mark.anyio
async def test_a_value_that_breaks_a_rule_is_answered_with_its_location_and_rule_and_without_the_value(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with (
        stored_sign_in_runtime(tmp_path, monkeypatch) as runtime,
        override_settings(cadrumo_active_profile=str(runtime.profile_id)),
    ):
        adapter = _adapter()
        try:
            refused = await _execute(
                adapter,
                runtime,
                LEDGER_CLASSIFY_OPERATION_DEFINITION_ID,
                transaction_id="synthetic-transaction",
                patch={"business_classification": "BUSINESS", "taxable_base": _NON_CANONICAL, "notes": _PRIVATE_NOTE},
                patch_fields=["taxable_base", "notes", "business_classification"],
            )
        finally:
            await adapter.close()

    faults = _faults(refused)
    assert faults == {
        ("patch", "taxable_base"): (
            "value_error",
            "Value error, ledger classify taxable_base must use canonical decimal text",
        ),
        ("patch_fields",): ("value_error", "Value error, ledger classify fields must use canonical sorted order"),
    }
    written = json.dumps(refused)
    assert _NON_CANONICAL not in written
    assert _PRIVATE_NOTE not in written


@pytest.mark.anyio
async def test_a_missing_and_an_unknown_member_are_named_by_the_model_and_no_private_value_is_repeated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with (
        stored_sign_in_runtime(tmp_path, monkeypatch) as runtime,
        override_settings(cadrumo_active_profile=str(runtime.profile_id)),
    ):
        adapter = _adapter()
        try:
            refused = await _execute(
                adapter,
                runtime,
                LEDGER_OWN_ACCOUNT_OPERATION_DEFINITION_ID,
                iban=_PRIVATE_ACCOUNT,
                holder_note=_PRIVATE_NOTE,
            )
        finally:
            await adapter.close()

    faults = _faults(refused)
    assert faults[("action",)][0] == "missing"
    assert faults[("iban",)][0] == "string_too_long"
    assert faults[("holder_note",)][0] == "extra_forbidden"
    assert all(message for _kind, message in faults.values())
    written = json.dumps(refused)
    assert _PRIVATE_ACCOUNT not in written
    assert _PRIVATE_NOTE not in written


@pytest.mark.anyio
async def test_a_validators_wording_that_names_no_value_reaches_the_caller_with_its_location_and_kind(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    account = "acc-4242"
    with (
        stored_sign_in_runtime(tmp_path, monkeypatch) as runtime,
        override_settings(cadrumo_active_profile=str(runtime.profile_id)),
    ):
        adapter = _adapter()
        try:
            # The model refuses an account id given to an action that takes none, and says so without either.
            refused = await _execute(
                adapter, runtime, LEDGER_OWN_ACCOUNT_OPERATION_DEFINITION_ID, action="list", own_account_id=account
            )
        finally:
            await adapter.close()

    assert _faults(refused) == {(): ("value_error", "Value error, this own account action takes no account id")}
    assert account not in json.dumps(refused)


@pytest.mark.anyio
async def test_a_refusal_that_is_no_fault_of_the_payload_carries_no_faults(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with (
        stored_sign_in_runtime(tmp_path, monkeypatch) as runtime,
        override_settings(cadrumo_active_profile=str(runtime.profile_id)),
    ):
        adapter = _adapter()
        try:
            # A request its model accepts, for a profile this session was not admitted to.
            refused = await adapter.call(
                "execute",
                {
                    "definition_id": LEDGER_OWN_ACCOUNT_OPERATION_DEFINITION_ID,
                    "payload": {"profile_id": str(uuid4()), "action": "list"},
                },
            )
        finally:
            await adapter.close()

    assert refused["outcome"] == "refused", refused
    assert refused["code"] != "invalid", refused
    assert "faults" not in refused, refused
