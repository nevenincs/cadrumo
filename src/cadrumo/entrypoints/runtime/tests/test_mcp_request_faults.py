"""A payload the runtime refuses as invalid comes back to an MCP client in the validators' own words.

A fault's message is the validator's message, the text the command line shows
for the same refusal, and no fault attaches the refused input.

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
from cadrumo.application.modelo.action_errors import WorkUnitNotFoundError
from cadrumo.application.modelo.operation_definitions import MODELO_WORK_RENAME_OPERATION_DEFINITION_ID
from cadrumo.application.modelo.query_read_contracts import ModeloBindingsListRequest
from cadrumo.application.modelo.query_read_operation import MODELO_BINDINGS_LIST_OPERATION_DEFINITION_ID
from cadrumo.core.config import override_settings
from cadrumo.core.errors.error_codes import build_error_envelope
from cadrumo.core.period import PeriodError
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
async def test_a_value_that_breaks_a_rule_is_answered_with_its_location_and_the_validators_message(
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
    # The whole patch was refused input; no fault attaches it.
    assert _PRIVATE_NOTE not in json.dumps(refused)


@pytest.mark.anyio
async def test_a_missing_and_an_unknown_member_are_named_by_the_model_and_the_refused_input_is_not_attached(
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
async def test_a_validators_message_that_quotes_what_it_refused_reaches_the_caller_as_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with (
        stored_sign_in_runtime(tmp_path, monkeypatch) as runtime,
        override_settings(cadrumo_active_profile=str(runtime.profile_id)),
    ):
        adapter = _adapter()
        try:
            # The model's wording for this rule names the action it was given.
            refused = await _execute(
                adapter, runtime, LEDGER_OWN_ACCOUNT_OPERATION_DEFINITION_ID, action="list", own_account_id="acc-4242"
            )
        finally:
            await adapter.close()

    assert _faults(refused) == {(): ("value_error", "Value error, own account action 'list' takes no account id")}


@pytest.mark.anyio
async def test_a_registered_refusal_raised_while_a_request_is_read_reaches_the_caller_as_the_command_line_prints_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    members: dict[str, Any] = {"modelo": "210", "year": 2025, "period_code": "evento", "missing": True}
    with (
        stored_sign_in_runtime(tmp_path, monkeypatch) as runtime,
        override_settings(cadrumo_active_profile=str(runtime.profile_id)),
    ):
        adapter = _adapter()
        try:
            refused = await _execute(adapter, runtime, MODELO_BINDINGS_LIST_OPERATION_DEFINITION_ID, **members)
            # The worker that refused it still serves the session.
            again = await _execute(adapter, runtime, MODELO_BINDINGS_LIST_OPERATION_DEFINITION_ID, **members)
        finally:
            await adapter.close()
        # The command builds this same request, and prints the error it raises through this envelope.
        with pytest.raises(PeriodError) as raised:
            ModeloBindingsListRequest(profile_id=runtime.profile_id, **members)
    printed = build_error_envelope(raised.value)

    assert (printed.code, "EVENT-N" in printed.message) == ("INTEGRITY_PERIOD", True)
    assert _faults(refused) == {(): (printed.code, printed.message)}
    assert again == refused


@pytest.mark.anyio
async def test_a_registered_refusal_about_what_a_request_names_is_answered_and_the_session_serves_on(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    unknown = "synthetic-unit-that-does-not-exist"
    with (
        stored_sign_in_runtime(tmp_path, monkeypatch) as runtime,
        override_settings(cadrumo_active_profile=str(runtime.profile_id)),
    ):
        adapter = _adapter()
        try:
            # The request fits its model; resolving whose work it names is what refuses it.
            refused = await adapter.call(
                "execute",
                {
                    "definition_id": MODELO_WORK_RENAME_OPERATION_DEFINITION_ID,
                    "payload": {
                        "work_unit_id": unknown,
                        "new_name": "synthetic new name",
                        "observed_name": "synthetic old name",
                        "observed_updated_at": "2026-01-01T00:00:00Z",
                        "actor": "synthetic-actor",
                    },
                },
            )
            served = await _execute(adapter, runtime, MODELO_BINDINGS_LIST_OPERATION_DEFINITION_ID, catalogue_only=True)
        finally:
            await adapter.close()
        printed = build_error_envelope(
            WorkUnitNotFoundError(
                translated_message="application.modelo.errors.work_unit_not_found", context={"work_unit_id": unknown}
            )
        )

    assert printed.code == "ERROR_MODELO_WORK_UNIT_NOT_FOUND"
    assert _faults(refused) == {(): (printed.code, printed.message)}
    assert served["outcome"] == "submitted", served


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
