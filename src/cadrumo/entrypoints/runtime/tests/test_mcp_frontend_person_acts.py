"""The runtime refuses the person's own acts to the MCP frontend, and to it alone.

The MCP harness offers no tool that sends any of these requests. A client of
the same account can still declare the MCP frontend and send one itself, so the
runtime refuses each, keyed on the act, with the one code that sends the agent
to the person: signing in by password, requesting a key, listing, locking or
denying sessions, signing the person out, resetting a password, resuming a
locked profile, installation acts, and every operation whose contract needs a
secret. A key the person configured and a resumed sign-in still admit the MCP
frontend, and the command line keeps every one of these acts.

The runtime, the native transport, the session authority, the profile worker
and the profile's custody are real. The native login the runtime observes, the
keychain holding the proof and the runtime's wall clock are ports held by the
test.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from uuid import uuid4

import pytest

from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from cadrumo.adapters.local_runtime.installation_client import RuntimeInstallationClient
from cadrumo.adapters.persistence.storage.custody.automation_store_composition import installed_automation_secret_store
from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import PROFILE_INPUT
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.installation_requests import RuntimeProfileListReply, RuntimeProfileListRequest
from cadrumo.application.runtime.operation_access import RuntimeOperationSubmit
from cadrumo.application.runtime.profile_access import RuntimeAccessRefusal
from cadrumo.application.user_profile.access_contracts import AccessDenialCode
from cadrumo.application.user_profile.automation_lifecycle import AutomationDenialKind
from cadrumo.application.user_profile.profile_operation_contracts import PROFILE_BUNDLE_EXPORT_OPERATION_DEFINITION_ID

from .stored_sign_in_runtime import StoredSignInRuntime, stored_sign_in_runtime

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows worker and protected pipes"),
    pytest.mark.usefixtures("authority_operation"),
]

_CLI = OperationFrontendProjection.CLI
_MCP = OperationFrontendProjection.MCP
_PERSON = AccessDenialCode.PERSON_ACT_REQUIRED.value


def _resumed(runtime: StoredSignInRuntime, frontend: OperationFrontendProjection) -> RuntimeFrontendClient:
    """A client holding the person's resumed sign-in on the frontend it declares."""
    client = RuntimeFrontendClient(runtime.connect(), profile_id=runtime.profile_id, frontend=frontend)
    client.resume_receipt()
    return client


def _persons_act(act: object) -> None:
    """The act is refused with the code that sends the agent to the person."""
    assert isinstance(act, RuntimeFrontendRefusedError), repr(act)
    assert act.reason == _PERSON, (act.reason, act.request_faults)


def _refusal_of(call: object) -> object:
    try:
        return call() if callable(call) else call
    except RuntimeFrontendRefusedError as refused:
        return refused


def test_the_mcp_frontend_is_refused_every_sign_in_session_and_key_act_and_keeps_its_resumed_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with stored_sign_in_runtime(tmp_path, monkeypatch) as runtime:
        password = runtime.login(runtime.connect(), "password", bytearray(PROFILE_INPUT.encode()), frontend=_MCP)
        assert isinstance(password, RuntimeAccessRefusal) and password.code.value == _PERSON

        agent = _resumed(runtime, _MCP)
        own = agent.session_id
        _persons_act(_refusal_of(agent.sessions))
        _persons_act(_refusal_of(agent.lock))
        _persons_act(_refusal_of(agent.human_sign_out))
        _persons_act(_refusal_of(lambda: agent.deny_automation(AutomationDenialKind.ALL)))
        unadmitted = RuntimeFrontendClient(runtime.connect(), profile_id=runtime.profile_id, frontend=_MCP)
        _persons_act(_refusal_of(lambda: unadmitted.prepare_enrollment(installed_automation_secret_store())))
        recovering = RuntimeFrontendClient(runtime.connect(), profile_id=runtime.profile_id, frontend=_MCP)
        _persons_act(
            _refusal_of(lambda: recovering.recover_profile(bytearray(PROFILE_INPUT.encode()), grants=frozenset()))
        )
        resetting = RuntimeFrontendClient(runtime.connect(), profile_id=runtime.profile_id, frontend=_MCP)
        replacement = bytearray(b"synthetic-replacement-password-77c1")
        _persons_act(
            _refusal_of(
                lambda: resetting.reset_password(
                    recovery_code=bytearray(b"synthetic-recovery-code"),
                    new_passphrase=replacement,
                    new_passphrase_confirmation=bytearray(replacement),
                )
            )
        )
        # The operation that needs a secret is not offered to the agent at all.
        _persons_act(
            _refusal_of(
                lambda: agent.describe(PROFILE_BUNDLE_EXPORT_OPERATION_DEFINITION_ID, deadline=time.monotonic() + 30)
            )
        )

        submitted = RuntimeOperationSubmit(
            request_id=uuid4(),
            profile_id=runtime.profile_id,
            session_id=own,
            definition_id=PROFILE_BUNDLE_EXPORT_OPERATION_DEFINITION_ID,
            subject_ref=f"profile:{runtime.profile_id}",
            payload_json=json.dumps(
                {"profile_id": str(runtime.profile_id), "destination": str(tmp_path / "x.bundle"), "purpose": "portable_transfer"}
            ),
        )
        _persons_act(_refusal_of(lambda: agent.operation(submitted, deadline=time.monotonic() + 30)))

        # None of it took the agent's own session away, and the stored sign-in stands.
        assert agent.status().status.denial is None
        assert runtime.stored_sign_in() is not None

        # The person keeps every one of these acts on the command line.
        person = _resumed(runtime, _CLI)
        assert {item.session_id for item in person.sessions()} >= {own, person.session_id}
        described = person.describe(PROFILE_BUNDLE_EXPORT_OPERATION_DEFINITION_ID, deadline=time.monotonic() + 30)
        assert described.contract.ephemeral_secret_required
        signed_out = person.human_sign_out()
        assert own in signed_out.session_ids


def test_an_installation_act_declared_by_the_mcp_frontend_is_refused_and_the_command_lines_is_served(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with stored_sign_in_runtime(tmp_path, monkeypatch) as runtime:

        def listed(frontend: OperationFrontendProjection) -> object:
            request = RuntimeProfileListRequest(request_id=uuid4(), frontend=frontend)
            client = RuntimeInstallationClient(runtime.connect())
            try:
                return _refusal_of(lambda: client.perform(request, RuntimeProfileListReply))
            finally:
                client.close()

        answers = {frontend: listed(frontend) for frontend in (_MCP, _CLI)}

    _persons_act(answers[_MCP])
    assert isinstance(answers[_CLI], RuntimeProfileListReply), answers[_CLI]
