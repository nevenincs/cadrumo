"""Every door of the runtime and every person's act, crossed with every frontend.

The command line and the terminal interface are the person's frontends. external client
and the automation host are an automation's, and neither reaches a person's act: signing
in by password, listing, locking or denying sessions, signing the person out,
requesting a key, recovering a profile, resetting a password, deciding who
follows the person's sign-in, installation acts, and every operation whose
contract needs a secret. Each is refused there with the one code that sends
the automation to the person, and each stays open on the person's frontends.

The admission doors differ by frontend as well. Every frontend resumes the
person's stored sign-in. Only external client asks to be attended, and the automation host is
admitted by nothing but the resumed sign-in: a key login on it is refused.

The frontends an automation works on are written out here rather than read from the
predicate under test, and a frontend added later fails this file until it is
placed on one side.

The runtime, the native transport, the session authority, the profile worker
and the profile's custody are real. The native login the runtime observes, the
keychain holding the proof and the runtime's wall clock are ports held by the
test.
"""

from __future__ import annotations

import json
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Final
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.persistence.storage.custody.automation_store_composition import installed_automation_secret_store
from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import PROFILE_INPUT
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.access_contracts import AccessDenialCode
from cadrumo.application.user_profile.automation_lifecycle import AutomationDenialKind
from cadrumo.application.user_profile.profile_operation_contracts import PROFILE_BUNDLE_EXPORT_OPERATION_DEFINITION_ID
from cadrumo.core.errors.hierarchy import CadrumoError
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.contracts.installation_requests import ProfileListReply, ProfileListRequest
from cadrumo_client.contracts.operation_access import OperationSubmit
from cadrumo_client.contracts.profile_access import AccessRefusal, ProfileStatus
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError
from cadrumo_client.transport.installation_client import InstallationClient

from .stored_sign_in_runtime import StoredSignInRuntime, stored_sign_in_runtime

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows worker and protected pipes"),
    pytest.mark.usefixtures("authority_operation"),
]

_CLI = OperationFrontendProjection.CLI
_TUI = OperationFrontendProjection.TUI
_EXTERNAL_CLIENT = OperationFrontendProjection.EXTERNAL_CLIENT
_AGENT_HOST = OperationFrontendProjection.INSTALLED_SERVICE

_PERSONS: Final = frozenset({_CLI, _TUI})
_AGENTS: Final = frozenset({_EXTERNAL_CLIENT, _AGENT_HOST})

_SERVED: Final = "served"
_PERSON: Final = AccessDenialCode.PERSON_ACT_REQUIRED.value
_INVALID_FRAME: Final = RefusalCode.INVALID_FRAME.value

_PERSONS_ACTS: Final = (
    "password_sign_in",
    "session_inventory",
    "deny_automation",
    "enrollment_prepare",
    "password_reset",
    "attendance_decide",
    "secret_operation_describe",
    "secret_operation_submit",
    "installation_profile_list",
    "session_lock",
    "human_sign_out",
    "profile_recovery",
)
"""Every person's act the runtime's doors receive, in the order a run takes them: the last three end sessions."""


def _answer(call: Callable[[], object]) -> str:
    """Name what a door answered: served, or the code it refused with."""
    try:
        reply = call()
    except FrontendRefusedError as refused:
        return refused.reason
    except RefusalError as refused:
        return str(refused.reason)
    except CadrumoError as refused:
        # A door that was reached and refused the synthetic input it was given.
        return f"error:{type(refused).__name__}"
    if isinstance(reply, AccessRefusal):
        return reply.code.value
    if isinstance(reply, ProfileStatus) and reply.status.denial is not None:
        return reply.status.denial.value
    return _SERVED


def _client(runtime: StoredSignInRuntime, frontend: OperationFrontendProjection) -> FrontendClient:
    return FrontendClient(runtime.connect(), profile_id=runtime.profile_id, frontend=frontend)


def _bundle_export(runtime: StoredSignInRuntime, session: UUID, destination: Path) -> OperationSubmit:
    return OperationSubmit(
        request_id=uuid4(),
        profile_id=runtime.profile_id,
        session_id=session,
        definition_id=PROFILE_BUNDLE_EXPORT_OPERATION_DEFINITION_ID,
        subject_ref=f"profile:{runtime.profile_id}",
        payload_json=json.dumps(
            {"profile_id": str(runtime.profile_id), "destination": str(destination), "purpose": "portable_transfer"}
        ),
    )


def _installation_list(runtime: StoredSignInRuntime, frontend: OperationFrontendProjection) -> object:
    client = InstallationClient(runtime.connect())
    try:
        return client.perform(ProfileListRequest(request_id=uuid4(), frontend=frontend), ProfileListReply)
    finally:
        client.close()


def _doors(runtime: StoredSignInRuntime, frontend: OperationFrontendProjection, scratch: Path) -> dict[str, str]:
    """Knock on every admission door and every person's act from ``frontend``, and record each answer."""
    answers: dict[str, str] = {}
    answers["receipt_resume"] = _answer(_client(runtime, frontend).resume_receipt)
    answers["key_sign_in"] = _answer(
        lambda: _client(runtime, frontend).login_api_key(bytearray(b"synthetic-not-a-key-0000000000000000"))
    )
    answers["attendance_ask"] = _answer(_client(runtime, frontend).request_attendance)
    answers["password_sign_in"] = _answer(
        lambda: _client(runtime, frontend).login_password(bytearray(PROFILE_INPUT.encode()), timeout=120)
    )

    # Held from the start, since an act the person takes on the way may end the stored sign-in.
    resumed = _client(runtime, frontend)
    resumed.resume_receipt()
    locking = _client(runtime, frontend)
    locking.resume_receipt()
    # On the person's frontends the submission starts the operation, so it holds a connection of its own.
    submitting = _client(runtime, frontend)
    submitting.resume_receipt()
    answers["session_inventory"] = _answer(resumed.sessions)
    answers["deny_automation"] = _answer(lambda: resumed.deny_automation(AutomationDenialKind.ALL))
    answers["enrollment_prepare"] = _answer(
        lambda: _client(runtime, frontend).prepare_enrollment(installed_automation_secret_store())
    )
    replacement = bytearray(b"synthetic-replacement-password-77c1")
    answers["password_reset"] = _answer(
        lambda: _client(runtime, frontend).reset_password(
            recovery_code=bytearray(b"synthetic-recovery-code"),
            new_passphrase=replacement,
            new_passphrase_confirmation=bytearray(replacement),
        )
    )
    answers["attendance_decide"] = _answer(resumed.attendance_inventory)
    answers["secret_operation_describe"] = _answer(
        lambda: resumed.describe(PROFILE_BUNDLE_EXPORT_OPERATION_DEFINITION_ID, deadline=time.monotonic() + 30)
    )
    answers["secret_operation_submit"] = _answer(
        lambda: submitting.operation(
            _bundle_export(runtime, submitting.session_id, scratch / f"{frontend.value}.bundle"),
            deadline=time.monotonic() + 30,
        )
    )
    answers["installation_profile_list"] = _answer(lambda: _installation_list(runtime, frontend))
    answers["session_lock"] = _answer(locking.lock)
    answers["human_sign_out"] = _answer(resumed.human_sign_out)
    # Last, because a person's recovery of the profile ends the sessions held before it.
    answers["profile_recovery"] = _answer(
        lambda: _client(runtime, frontend).recover_profile(bytearray(PROFILE_INPUT.encode()), grants=frozenset())
    )
    return answers


def test_every_frontend_is_on_exactly_one_side() -> None:
    assert frozenset(OperationFrontendProjection) == _PERSONS | _AGENTS
    assert not _PERSONS & _AGENTS


@pytest.mark.parametrize("frontend", sorted(OperationFrontendProjection), ids=lambda frontend: frontend.value)
def test_each_door_answers_each_frontend_by_whose_frontend_it_is(
    frontend: OperationFrontendProjection, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with stored_sign_in_runtime(tmp_path, monkeypatch) as runtime:
        answers = _doors(runtime, frontend, tmp_path)
        stored_after = runtime.stored_sign_in()

    # Every frontend resumes the person's stored sign-in.
    assert answers["receipt_resume"] == _SERVED, answers
    # Only external client asks to be attended; a person signs in with their own proof, and the automation host only resumes.
    if frontend is _EXTERNAL_CLIENT:
        assert answers["attendance_ask"] != _INVALID_FRAME, answers
    else:
        assert answers["attendance_ask"] == _INVALID_FRAME, answers
    # A key admits every frontend but the automation host, which is admitted by the resumed sign-in alone.
    if frontend is _AGENT_HOST:
        assert answers["key_sign_in"] == _INVALID_FRAME, answers
    else:
        assert answers["key_sign_in"] not in {_INVALID_FRAME, _PERSON, _SERVED}, answers

    acts = {act: answers[act] for act in _PERSONS_ACTS}
    if frontend in _AGENTS:
        assert acts == dict.fromkeys(_PERSONS_ACTS, _PERSON), answers
        # Refusing the automation took nothing from the person: the stored sign-in stands.
        assert stored_after is not None
        return
    refused_as_persons = sorted(act for act, answer in acts.items() if answer == _PERSON)
    assert not refused_as_persons, answers
    # The acts whose inputs are genuine are served outright on the person's frontends.
    served = {
        "password_sign_in",
        "session_inventory",
        "deny_automation",
        "secret_operation_describe",
        "installation_profile_list",
        "session_lock",
        "human_sign_out",
    }
    assert {act: acts[act] for act in served} == dict.fromkeys(served, _SERVED), answers
