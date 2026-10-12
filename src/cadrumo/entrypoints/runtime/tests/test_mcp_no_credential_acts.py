"""The MCP adapter against the real runtime offers no credential, session or installation act.

The adapter, the installed client it opens, the native transport, the runtime,
the session authority, the profile worker and the stored sign-in are real. The
native login the runtime observes, the keychain holding the proof and the
runtime's wall clock are ports held by the test. An agent works only inside the
profile the person signed in to, so the acts that sign in, sign out, lock,
administer sessions or keys, carry a secret or act outside the profile have no
tool, and an operation whose contract needs a secret is refused as the
person's own act before anything reaches the runtime.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import PROFILE_INPUT
from cadrumo.application.user_profile.profile_operation_contracts import PROFILE_BUNDLE_EXPORT_OPERATION_DEFINITION_ID
from cadrumo.core.config import override_settings
from cadrumo_harness.mcp.protocol_contract import PERSON_ACT_REMEDY, PERSON_ACT_REQUIRED
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

_REMOVED_CALLS: tuple[tuple[str, dict[str, Any]], ...] = (
    ("session", {"action": "sign_in", "secret": PROFILE_INPUT}),
    ("session", {"action": "sign_out"}),
    ("session", {"action": "lock"}),
    ("session", {"action": "list"}),
    ("installation", {"action": "profile_list"}),
    ("authenticate", {"credential_reference": "00000000-0000-4000-8000-000000000000"}),
    ("authorization_prepare", {}),
    ("authorization_request", {"proposal": {}}),
    ("authorization_poll", {}),
)


def _submissions(runtime: StoredSignInRuntime, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Keep the action of every operation request the runtime is handed, and handle each as it would."""
    handed: list[str] = []
    handle = runtime.profiles.operation

    def kept(context: Any, channel: Any, request: Any) -> Any:
        handed.append(request.action)
        return handle(context, channel, request)

    monkeypatch.setattr(runtime.profiles, "operation", kept)
    return handed


def _logins(runtime: StoredSignInRuntime) -> list[tuple[str, str]]:
    """Every login the runtime was asked for, by method and frontend."""
    return [(item.method, item.frontend.value) for item in runtime.profiles.logins]


@pytest.mark.anyio
async def test_no_tool_signs_in_administers_sessions_or_carries_a_secret_and_the_runtime_is_asked_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with (
        stored_sign_in_runtime(tmp_path, monkeypatch) as runtime,
        override_settings(cadrumo_active_profile=str(runtime.profile_id)),
    ):
        stored = runtime.stored_sign_in()
        adapter = RuntimeMcpAdapter(profile_id=None, client=None, resumes_sign_in=True)
        try:
            async with connected_server_and_client_session(build_server(adapter)) as sdk:
                names = {tool.name for tool in (await sdk.list_tools()).tools}
                status = await sdk.call_tool("status", {})
                assert status.structured_content is not None
                assert status.structured_content["session"] == "sign_in"
                logins_before = _logins(runtime)
                handed = _submissions(runtime, monkeypatch)
                held = adapter.client
                answers = [await sdk.call_tool(name, args) for name, args in _REMOVED_CALLS]
                given = await sdk.call_tool(
                    "execute",
                    {
                        "definition_id": PROFILE_BUNDLE_EXPORT_OPERATION_DEFINITION_ID,
                        "payload": {},
                        "secret": PROFILE_INPUT,
                    },
                )
                export = await sdk.call_tool(
                    "execute",
                    {
                        "definition_id": PROFILE_BUNDLE_EXPORT_OPERATION_DEFINITION_ID,
                        "payload": {
                            "profile_id": str(runtime.profile_id),
                            "destination": "synthetic.bundle",
                            "purpose": "backup",
                        },
                    },
                )
                logins_after = _logins(runtime)
                stored_after = runtime.stored_sign_in()
        finally:
            await adapter.close()

    assert not names & {name for name, _args in _REMOVED_CALLS}
    for (name, _args), answer in zip(_REMOVED_CALLS, answers, strict=True):
        assert answer.is_error is True, name
        assert answer.structured_content == {"outcome": "refused", "code": "unknown_tool"}, name
    # A secret given to execute is refused at the wire, and the operation that needs one is the person's act.
    assert given.is_error is True
    assert given.structured_content == {"outcome": "refused", "code": "invalid_request"}
    assert export.is_error is True
    assert export.structured_content == {"outcome": "refused", "code": PERSON_ACT_REQUIRED, "remedy": PERSON_ACT_REMEDY}
    # None of them reached the runtime: no login was asked for, nothing was submitted, and the
    # session the person's sign-in admitted and the stored sign-in are as they were.
    assert logins_after == logins_before
    assert all(method != "password" for method, _frontend in logins_after)
    assert not any("submit" in action for action in handed), handed
    assert adapter.client is None and held is not None
    assert stored_after == stored
    assert PROFILE_INPUT not in repr([answer.structured_content for answer in answers])
