"""The MCP adapter follows the person's sign-in, and never offers the agent the person's own acts.

A sign-in the person holds is followed only when that person approves the
exact connection.

With no stored sign-in and no configured key, the agent's server has one more
way in: it asks the person holding a live sign-in to the same profile, and the
person's approval admits that connection and nothing else. The ask carries no
secret. The adapter, the installed clients, the native transport, the runtime,
its attendance broker, the session authority and the profile worker are real;
the native login, the keychain and the wall clock are ports held by the test,
and the MCP SDK uses its memory transport.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path
from typing import Any

import pytest

from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import PROFILE_INPUT
from cadrumo.application.auth.auth_read_contracts import AUTH_READ_OPERATION_DEFINITION_ID
from cadrumo.application.operations.person_acts import ACCESS_ADMINISTRATION_OPERATIONS
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.access_contracts import ProfileAccessStatus
from cadrumo.application.user_profile.profile_operation_contracts import PROFILE_BUNDLE_EXPORT_OPERATION_DEFINITION_ID
from cadrumo.core.config import override_settings
from cadrumo.core.hashing import canonical_json_bytes
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.installed_client import open_installed_client
from cadrumo_harness.mcp.protocol_contract import PERSON_ACT_REMEDY, sign_in_remedy
from cadrumo_harness.mcp.runtime_adapter import RuntimeMcpAdapter
from cadrumo_harness.mcp.runtime_admission import McpAdmission
from cadrumo_harness.mcp.server import build_server
from cadrumo_harness.mcp.tests.agent_key_reads import edit_profile_and_read_back
from cadrumo_harness.mcp.tests.session import connected_server_and_client_session
from cadrumo_runtime.host.tests.stored_sign_in_runtime import StoredSignInRuntime, stored_sign_in_runtime

from ..proof_support import ProcessIdentity
from .attended_mcp_support import attended_status, holding_person, review_attendance

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows worker and protected pipes"),
    pytest.mark.usefixtures("authority_operation"),
]

_PROFILE_CALL: tuple[str, dict[str, object]] = ("search", {"family": AUTH_READ_OPERATION_DEFINITION_ID})
"""A read of the profile's own operations, answered only under a session."""
_PAGE = 50
"""A page small enough that reading its contracts stays well inside one call's budget."""
_SWEEPS = 2.0
"""Seconds that span several of the runtime's lease sweeps, which run at most twice a second."""


def _adapter() -> RuntimeMcpAdapter:
    """An adapter started with no credential reference and no profile named."""
    return RuntimeMcpAdapter(profile_id=None, client=None, requests_attendance=True)


async def _holding(runtime: StoredSignInRuntime) -> FrontendClient:
    """The person signs in at the command line, keeps no stored sign-in, and holds it for attendance."""
    holder = await open_installed_client(profile_id=runtime.profile_id, frontend=OperationFrontendProjection.CLI)
    await asyncio.to_thread(holder.login_password, bytearray(PROFILE_INPUT.encode()), timeout=120)
    await asyncio.to_thread(holder.attendance_inventory)
    return holder


def _decide_first_ask(holder: FrontendClient, *, approve: bool) -> None:
    """Wait for the agent's ask to reach the person, then decide it as the person."""
    identity = ProcessIdentity.capture(os.getpid())
    deadline = time.monotonic() + 60
    while review_attendance(holder, identity, approve=approve) is None:
        assert time.monotonic() < deadline, "the exact native agent ask never reached the person"
        time.sleep(0.05)


async def _status_while_deciding(
    sdk: Any, holder: FrontendClient, *, approve: bool, tool: str = "status", arguments: dict[str, object] | None = None
) -> Any:
    deciding = asyncio.create_task(asyncio.to_thread(_decide_first_ask, holder, approve=approve))
    try:
        return await sdk.call_tool(tool, {} if arguments is None else arguments)
    finally:
        await deciding


async def _every_listed_operation(sdk: Any) -> list[dict[str, Any]]:
    """Page an unfiltered search to its end, as an agent discovering what it may do would."""
    rows: list[dict[str, Any]] = []
    args: dict[str, Any] = {"limit": _PAGE}
    while True:
        page = await sdk.call_tool("search", args)
        assert page.is_error is False, page.structured_content
        assert page.structured_content["outcome"] == "found"
        rows.extend(page.structured_content["operations"])
        if "next_cursor" not in page.structured_content:
            return rows
        args = {"limit": _PAGE, "cursor": page.structured_content["next_cursor"]}


async def _discovery_offers_no_persons_act(sdk: Any) -> None:
    """Search lists the session's operations without the person's acts; describing one is refused, typed."""
    listed = {row["definition_id"]: row for row in await _every_listed_operation(sdk)}
    assert AUTH_READ_OPERATION_DEFINITION_ID in listed
    assert not ACCESS_ADMINISTRATION_OPERATIONS & listed.keys()
    assert PROFILE_BUNDLE_EXPORT_OPERATION_DEFINITION_ID not in listed
    assert not [identity for identity, row in listed.items() if row["ephemeral_secret_required"]]
    for persons_act in (PROFILE_BUNDLE_EXPORT_OPERATION_DEFINITION_ID, "user-profile.automation-inventory"):
        described = await sdk.call_tool("describe", {"definition_id": persons_act})
        assert described.is_error is True
        assert described.structured_content == {
            "outcome": "refused",
            "code": "person_act_required",
            "remedy": PERSON_ACT_REMEDY,
        }, persons_act


@pytest.mark.anyio
async def test_a_person_reviewed_attended_session_searches_every_operation_but_the_persons_acts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with (
        stored_sign_in_runtime(tmp_path, monkeypatch) as runtime,
        override_settings(cadrumo_active_profile=str(runtime.profile_id)),
    ):
        holder = holding_person(runtime)
        adapter = _adapter()
        try:
            await attended_status(runtime, holder, adapter)
            async with connected_server_and_client_session(build_server(adapter)) as sdk:
                await _discovery_offers_no_persons_act(sdk)
                assert adapter.admission is McpAdmission.ATTENDED
        finally:
            try:
                await adapter.close()
            finally:
                await asyncio.to_thread(holder.close)


@pytest.mark.anyio
async def test_an_approved_attended_connection_reads_the_profile_with_no_stored_sign_in_or_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with (
        stored_sign_in_runtime(tmp_path, monkeypatch, signed_in=False) as runtime,
        override_settings(cadrumo_active_profile=str(runtime.profile_id)),
    ):
        holder = await _holding(runtime)
        try:
            assert runtime.stored_sign_in() is None
            persons_session = holder.session_id
            # As on a Windows logon that holds no credentials: the automation store cannot be reached.
            # An attended session answers to the person's session, not to that store.
            runtime.enrollment.native.unavailable = True
            adapter = _adapter()
            try:
                async with connected_server_and_client_session(build_server(adapter)) as sdk:
                    status = await _status_while_deciding(sdk, holder, approve=True)
                    private = await sdk.call_tool(*_PROFILE_CALL)
                    assert adapter.admission is McpAdmission.ATTENDED
                    await asyncio.sleep(_SWEEPS)
                    swept = await sdk.call_tool("status", {})
                    await _discovery_offers_no_persons_act(sdk)
            finally:
                await adapter.close()
        finally:
            await asyncio.to_thread(holder.close)

        assert status.is_error is False
        reply = status.structured_content
        assert reply["outcome"] == "status" and reply["session"] == McpAdmission.ATTENDED.value, reply
        admitted = ProfileAccessStatus.model_validate_json(canonical_json_bytes(reply["status"]))
        assert admitted.profile_id == runtime.profile_id and admitted.denial is None
        assert admitted.session_id is not None and admitted.session_id != persons_session
        # The lease sweeps that ran while the automation store was unavailable left the attended session in place.
        assert swept.structured_content["session"] == McpAdmission.ATTENDED.value, swept.structured_content
        assert swept.structured_content["status"]["session_id"] == str(admitted.session_id)
        # The authenticated read the attended session admits.
        assert private.is_error is False, private.structured_content
        assert private.structured_content["outcome"] == "found"


@pytest.mark.anyio
async def test_a_declined_ask_leaves_only_status_and_sends_the_agent_to_the_person(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with (
        stored_sign_in_runtime(tmp_path, monkeypatch, signed_in=False) as runtime,
        override_settings(cadrumo_active_profile=str(runtime.profile_id)),
    ):
        holder = await _holding(runtime)
        try:
            adapter = _adapter()
            try:
                async with connected_server_and_client_session(build_server(adapter)) as sdk:
                    status = await _status_while_deciding(sdk, holder, approve=False)
                    private = await _status_while_deciding(
                        sdk, holder, approve=False, tool=_PROFILE_CALL[0], arguments=_PROFILE_CALL[1]
                    )
                    assert adapter.client is None
            finally:
                await adapter.close()
        finally:
            await asyncio.to_thread(holder.close)

        remedy = sign_in_remedy("authentication_required")
        assert status.is_error is False
        assert status.structured_content["session"] == "none"
        assert status.structured_content["authenticated"] is False
        assert status.structured_content["denial"] == "authentication_required"
        assert status.structured_content["remedy"] == remedy
        assert private.is_error is True
        assert private.structured_content["code"] == "authentication_required"
        assert private.structured_content["remedy"] == remedy


@pytest.mark.anyio
async def test_an_approved_attended_connection_edits_the_profile_and_reads_each_change_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An agent inside the person's held sign-in patches the profile, mutates a field and edits rows."""
    with (
        stored_sign_in_runtime(tmp_path, monkeypatch, signed_in=False) as runtime,
        override_settings(cadrumo_active_profile=str(runtime.profile_id)),
    ):
        holder = await _holding(runtime)
        try:
            adapter = _adapter()
            try:
                async with connected_server_and_client_session(build_server(adapter)) as sdk:
                    status = await _status_while_deciding(sdk, holder, approve=True)
                    assert status.structured_content["session"] == McpAdmission.ATTENDED.value, status
                    await edit_profile_and_read_back(sdk, runtime.profile_id)
            finally:
                await adapter.close()
        finally:
            await asyncio.to_thread(holder.close)
