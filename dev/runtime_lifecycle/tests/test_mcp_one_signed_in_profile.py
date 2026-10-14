"""An agent works inside the one profile the person signed in to, and nowhere else.

Against a running runtime with synthetic encrypted profiles, one connection of
the MCP adapter works under a reviewed attended child of the person's sign-in, is refused
the person's own acts, and loses its way in when the person signs out before
moving to another profile: the connection is never
moved to the second. The adapter, the installed clients, the native
transport, the runtime, the session authority, the profile workers and both
profiles' custody are real; the native login, the keychain and the wall clock
are ports held by the test. The configured-key route is proven against the
same runtime by the credential-reference test of the sign-in adapter suite.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from uuid import UUID

import pytest

from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import PROFILE_INPUT
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import profile_authority_contexts
from cadrumo.application.auth.auth_read_contracts import AUTH_READ_OPERATION_DEFINITION_ID
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.profile_operation_contracts import PROFILE_BUNDLE_EXPORT_OPERATION_DEFINITION_ID
from cadrumo.application.user_profile.registration import register_profile_with_credentials
from cadrumo.core.config import override_settings
from cadrumo_client.transport.installed_client import open_installed_client
from cadrumo_harness.mcp.protocol_contract import PERSON_ACT_REMEDY, PROFILE_CHANGED_REMEDY, SIGN_IN_REMEDY
from cadrumo_harness.mcp.runtime_adapter import RuntimeMcpAdapter
from cadrumo_harness.mcp.runtime_admission import McpAdmission
from cadrumo_runtime.host.tests.stored_sign_in_runtime import stored_sign_in_runtime

from .attended_mcp_support import attended_status, holding_person

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows worker and protected pipes"),
    pytest.mark.usefixtures("authority_operation"),
]

_READ = {"family": AUTH_READ_OPERATION_DEFINITION_ID}


def _another_profile() -> UUID:
    """Create a second synthetic encrypted profile beside the runtime's own."""
    create, decode = profile_authority_contexts()
    registered = register_profile_with_credentials(
        label="Second profile",
        passphrase=PROFILE_INPUT,
        profile_create_context=create,
        profile_decode_context=decode,
    )
    return UUID(registered.profile_id)


@pytest.mark.anyio
async def test_mcp_works_only_inside_the_profile_the_person_is_signed_in_to(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with stored_sign_in_runtime(tmp_path, monkeypatch) as runtime:
        other = _another_profile()
        holder = holding_person(runtime)
        adapter = RuntimeMcpAdapter(profile_id=None, client=None, requests_attendance=True)
        try:
            with override_settings(cadrumo_active_profile=str(runtime.profile_id)):
                # Inside the signed-in profile the agent works.
                inside = await attended_status(runtime, holder, adapter)
                found = await adapter.call("search", _READ)
                # The person's own acts stay the person's.
                persons_act = await adapter.call(
                    "describe", {"definition_id": PROFILE_BUNDLE_EXPORT_OPERATION_DEFINITION_ID}
                )

                # The person retires the first sign-in before moving to another profile.
                assert adapter.client is not None
                attended_id = adapter.client.session_id
                retired = await asyncio.to_thread(holder.human_sign_out)
                assert attended_id in retired.session_ids
                person = await open_installed_client(profile_id=other, frontend=OperationFrontendProjection.CLI)
                try:
                    await asyncio.to_thread(person.login_password, bytearray(PROFILE_INPUT.encode()), timeout=120)
                    signed_out = await adapter.call("search", _READ)
                    status_signed_out = await adapter.call("status", {})

                    with override_settings(cadrumo_active_profile=str(other)):
                        # The connection was made for the first profile and is never moved to the second.
                        moved = await adapter.call("search", _READ)
                finally:
                    await asyncio.to_thread(person.close)
        finally:
            try:
                await adapter.close()
            finally:
                holder.close()

    assert inside["session"] == McpAdmission.ATTENDED.value, inside
    assert found["outcome"] == "found", found
    assert persons_act == {"outcome": "refused", "code": "person_act_required", "remedy": PERSON_ACT_REMEDY}

    assert signed_out["outcome"] == "refused", signed_out
    assert signed_out["remedy"] == SIGN_IN_REMEDY, signed_out
    assert status_signed_out["session"] == "none" and status_signed_out["authenticated"] is False
    assert status_signed_out["profile_id"] == str(runtime.profile_id)
    assert status_signed_out["remedy"] == SIGN_IN_REMEDY

    assert moved == {"outcome": "refused", "code": "profile_mismatch", "remedy": PROFILE_CHANGED_REMEDY}, moved
