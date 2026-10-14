"""The runtime refuses every change to a model provider's credential on an agent's frontend.

Setting, removing and resetting a provider's credential are the person's own
acts. Only setting carries a secret, so the secret rule alone would leave
removing and resetting to an agent. Each of the three is refused at dispatch
to MCP and to the agent host, whether described or submitted, and to MCP's
generic ``execute`` tool before anything reaches the runtime. The person's
command line keeps each act, and the masked status read stays open to an
agent.

The runtime, the native transport, the session authority, the profile worker,
the profile's custody and the MCP adapter are real. The native login the
runtime observes, the keychain holding the proof and the runtime's wall clock
are ports held by the test.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any, Final
from uuid import uuid4

import pytest

from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.provider_settings.registered_operations import (
    PROVIDER_SETTINGS_REMOVE_OPERATION_DEFINITION_ID,
    PROVIDER_SETTINGS_RESET_OPERATION_DEFINITION_ID,
    PROVIDER_SETTINGS_SET_OPERATION_DEFINITION_ID,
    PROVIDER_SETTINGS_STATUS_OPERATION_DEFINITION_ID,
    ProviderSettingsChangeRequest,
)
from cadrumo.application.runtime.operation_access import RuntimeOperationSubmit
from cadrumo.application.user_profile.access_contracts import AccessDenialCode
from cadrumo.core.config import override_settings
from cadrumo.core.secure_object_write import ABSENT_SECURE_OBJECT_REVISION_ID
from cadrumo_harness.mcp.runtime_adapter import RuntimeMcpAdapter
from cadrumo_harness.mcp.server import build_server
from cadrumo_harness.mcp.tests.session import connected_server_and_client_session

from .stored_sign_in_runtime import StoredSignInRuntime, stored_sign_in_runtime

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows worker and protected pipes"),
    pytest.mark.usefixtures("authority_operation"),
]

_CLI: Final = OperationFrontendProjection.CLI
_AGENTS: Final = (OperationFrontendProjection.MCP, OperationFrontendProjection.AGENT_HOST)
_PERSON: Final = AccessDenialCode.PERSON_ACT_REQUIRED.value
_LANE: Final = "synthetic-lane"
"""An invented lane id: the refusal is keyed on the act, before any catalog lookup."""

_CHANGES: Final = (
    PROVIDER_SETTINGS_SET_OPERATION_DEFINITION_ID,
    PROVIDER_SETTINGS_REMOVE_OPERATION_DEFINITION_ID,
    PROVIDER_SETTINGS_RESET_OPERATION_DEFINITION_ID,
)


def _resumed(runtime: StoredSignInRuntime, frontend: OperationFrontendProjection) -> RuntimeFrontendClient:
    """A client holding the person's resumed sign-in on the frontend it declares."""
    client = RuntimeFrontendClient(runtime.connect(), profile_id=runtime.profile_id, frontend=frontend)
    client.resume_receipt()
    return client


def _refusal_of(call: Any) -> object:
    try:
        return call()
    except RuntimeFrontendRefusedError as refused:
        return refused


def _persons_act(answer: object) -> None:
    assert isinstance(answer, RuntimeFrontendRefusedError), repr(answer)
    assert answer.reason == _PERSON, (answer.reason, answer.request_faults)


def _change(runtime: StoredSignInRuntime, client: RuntimeFrontendClient, definition_id: str) -> RuntimeOperationSubmit:
    payload = ProviderSettingsChangeRequest(
        profile_id=runtime.profile_id, provider_id=_LANE, expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID
    )
    return RuntimeOperationSubmit(
        request_id=uuid4(),
        profile_id=runtime.profile_id,
        session_id=client.session_id,
        definition_id=definition_id,
        subject_ref=f"profile:{runtime.profile_id}",
        payload_json=payload.model_dump_json(),
    )


def _refused_to_agent(runtime: StoredSignInRuntime, frontend: OperationFrontendProjection, definition_id: str) -> None:
    """The agent's frontend is refused the change described and submitted, and keeps its status read and session."""
    agent = _resumed(runtime, frontend)
    _persons_act(_refusal_of(lambda: agent.describe(definition_id, deadline=time.monotonic() + 30)))
    submitted = _change(runtime, agent, definition_id)
    _persons_act(_refusal_of(lambda: agent.operation(submitted, deadline=time.monotonic() + 30)))
    read = agent.describe(PROVIDER_SETTINGS_STATUS_OPERATION_DEFINITION_ID, deadline=time.monotonic() + 30)
    assert read.contract.definition_id == PROVIDER_SETTINGS_STATUS_OPERATION_DEFINITION_ID
    assert agent.status().status.denial is None, frontend


@pytest.mark.parametrize("definition_id", _CHANGES)
def test_an_agent_frontend_is_refused_the_change_at_dispatch_and_the_person_keeps_it(
    definition_id: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with stored_sign_in_runtime(tmp_path, monkeypatch) as runtime:
        for frontend in _AGENTS:
            _refused_to_agent(runtime, frontend, definition_id)

        person = _resumed(runtime, _CLI)
        described = person.describe(definition_id, deadline=time.monotonic() + 30)

    assert described.contract.definition_id == definition_id
    # Only setting carries a secret; removing and resetting are the person's acts without one.
    assert described.contract.ephemeral_secret_required is (
        definition_id == PROVIDER_SETTINGS_SET_OPERATION_DEFINITION_ID
    )


@pytest.mark.anyio
@pytest.mark.parametrize("definition_id", _CHANGES)
async def test_mcp_generic_execute_refuses_the_change_before_the_runtime_is_handed_it(
    definition_id: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with (
        stored_sign_in_runtime(tmp_path, monkeypatch) as runtime,
        override_settings(cadrumo_active_profile=str(runtime.profile_id)),
    ):
        handed: list[str] = []
        handle = runtime.profiles.operation

        def kept(context: Any, channel: Any, request: Any) -> Any:
            handed.append(request.action)
            return handle(context, channel, request)

        adapter = RuntimeMcpAdapter(profile_id=None, client=None, resumes_sign_in=True)
        try:
            async with connected_server_and_client_session(build_server(adapter)) as sdk:
                status = await sdk.call_tool("status", {})
                assert status.structured_content is not None
                monkeypatch.setattr(runtime.profiles, "operation", kept)
                answer = await sdk.call_tool(
                    "execute",
                    {
                        "definition_id": definition_id,
                        "payload": {
                            "profile_id": str(runtime.profile_id),
                            "provider_id": _LANE,
                            "expected_revision": ABSENT_SECURE_OBJECT_REVISION_ID,
                        },
                    },
                )
        finally:
            await adapter.close()

    assert answer.is_error is True
    assert answer.structured_content is not None
    assert answer.structured_content["outcome"] == "refused"
    assert answer.structured_content["code"] == _PERSON
    assert not any("submit" in action for action in handed), handed
