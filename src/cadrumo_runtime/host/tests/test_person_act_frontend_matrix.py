"""Frontend policy, real person acts and separated automation admission doors.

The command line, terminal interface and verified desktop are the person's
frontends. External clients and installed services never reach a person's act: signing
in by password, listing, locking or denying sessions, signing the person out,
requesting a key, recovering a profile, resetting a password, deciding who
follows the person's sign-in, installation acts, and every operation whose
contract needs a secret. CLI/TUI exercise genuine person acts; external attendance
exercises their refusals. Desktop exercises the unverified-holder fence. The
controlled service fixture exercises admission and supported session-act refusals.

Human frontends resume the person's stored sign-in. An external client instead
asks for exact attendance, and an installed service uses its own connection
and human-admission protocol. An unverified desktop holder is refused.

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
import os
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
from cadrumo.application.user_profile.access_contracts import AccessAction, AccessDenialCode, AccessScope, SessionKind
from cadrumo.application.user_profile.automation_lifecycle import AutomationDenialKind
from cadrumo.application.user_profile.profile_operation_contracts import PROFILE_BUNDLE_EXPORT_OPERATION_DEFINITION_ID
from cadrumo.core.errors.hierarchy import CadrumoError
from cadrumo_client.contracts.access_management import AutomationDeny, SessionInventory
from cadrumo_client.contracts.attendance import AttendanceDecide, AttendancePending
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.contracts.installation_requests import ProfileListReply, ProfileListRequest
from cadrumo_client.contracts.operation_access import OperationSubmit
from cadrumo_client.contracts.profile_access import AccessRefusal, ProfileStatus, SessionRequest
from cadrumo_client.contracts.service_access import ServiceConnected
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError
from cadrumo_client.transport.installation_client import InstallationClient

from .stored_sign_in_runtime import StoredSignInRuntime, stored_sign_in_runtime
from .test_service_records import service_record_runtime

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows worker and protected pipes"),
    pytest.mark.usefixtures("authority_operation"),
]

_CLI = OperationFrontendProjection.CLI
_TUI = OperationFrontendProjection.TUI
_DESKTOP = OperationFrontendProjection.DESKTOP
_EXTERNAL_CLIENT = OperationFrontendProjection.EXTERNAL_CLIENT
_SERVICE = OperationFrontendProjection.INSTALLED_SERVICE

_PERSONS: Final = frozenset({_CLI, _TUI, _DESKTOP})
_AUTOMATED: Final = frozenset({_EXTERNAL_CLIENT, _SERVICE})
_ATTENDANCE_SCOPE = AccessScope(
    operations=frozenset({PROFILE_BUNDLE_EXPORT_OPERATION_DEFINITION_ID}),
    actions=frozenset({AccessAction.SUBMIT}),
    disclosures=frozenset(),
    periods=frozenset(),
    allow_period_independent=True,
    allow_delegation=False,
)

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


def _client(
    runtime: StoredSignInRuntime, frontend: OperationFrontendProjection, *, scope: AccessScope | None = None
) -> FrontendClient:
    return FrontendClient(runtime.connect(), profile_id=runtime.profile_id, frontend=frontend, scope=scope)


def _attended(runtime: StoredSignInRuntime, person: FrontendClient) -> FrontendClient:
    client = _client(runtime, _EXTERNAL_CLIENT, scope=_ATTENDANCE_SCOPE)
    pending = client.request_attendance()
    assert isinstance(pending, AttendancePending)
    (candidate,) = person.attendance_inventory().candidates
    assert candidate.attendance_id == pending.attendance_id
    assert candidate.process_id == os.getpid() and candidate.image_path is not None
    assert candidate.frontend is _EXTERNAL_CLIENT and candidate.scope == _ATTENDANCE_SCOPE
    assert person.decide_attendance(pending.attendance_id, approve=True).approved
    admitted = client.attendance_status(pending.attendance_id)
    assert isinstance(admitted, ProfileStatus) and admitted.status.denial is None
    assert admitted.status.profile_id == runtime.profile_id and admitted.status.session_id == client.session_id
    lease = runtime.lease(client.session_id)
    assert lease.kind is SessionKind.ATTENDED and lease.parent_session_id == person.session_id
    assert lease.scope.operations == _ATTENDANCE_SCOPE.operations and lease.scope.actions == _ATTENDANCE_SCOPE.actions
    assert lease.scope.periods == frozenset() and lease.scope.allow_period_independent
    assert not lease.scope.allow_delegation and lease.originating_login_id == runtime.native_login.login_id
    return client


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
    answers["password_sign_in"] = _answer(
        lambda: _client(runtime, frontend).login_password(bytearray(PROFILE_INPUT.encode()), timeout=120)
    )

    # Attendance is registered by a real human connection, never by fixture state.
    if frontend is _EXTERNAL_CLIENT:
        person = _client(runtime, _CLI)
        person.resume_receipt()
        assert person.attendance_inventory().candidates == ()
        resumed = _attended(runtime, person)
        answers["attendance_ask"] = _SERVED
        locking = _attended(runtime, person)
        submitting = _attended(runtime, person)
    else:
        answers["attendance_ask"] = _answer(_client(runtime, frontend, scope=_ATTENDANCE_SCOPE).request_attendance)
        # Held before the person's later acts end sessions. Submission owns its connection.
        resumed, locking, submitting = (_client(runtime, frontend) for _ in range(3))
        for client in (resumed, locking, submitting):
            client.resume_receipt()
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
    assert frozenset(OperationFrontendProjection) == _PERSONS | _AUTOMATED
    assert not _PERSONS & _AUTOMATED


@pytest.mark.parametrize("frontend", (_CLI, _TUI, _EXTERNAL_CLIENT), ids=lambda frontend: frontend.value)
def test_each_door_answers_each_frontend_by_whose_frontend_it_is(
    frontend: OperationFrontendProjection, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with stored_sign_in_runtime(tmp_path, monkeypatch) as runtime:
        answers = _doors(runtime, frontend, tmp_path)
        stored_after = runtime.stored_sign_in()

    assert answers["receipt_resume"] == (_PERSON if frontend is _EXTERNAL_CLIENT else _SERVED), answers
    # An external client follows only the person's exact decision, without human receipt proof.
    if frontend is _EXTERNAL_CLIENT:
        assert answers["attendance_ask"] == _SERVED, answers
    else:
        assert answers["attendance_ask"] == _INVALID_FRAME, answers
    assert answers["key_sign_in"] not in {_INVALID_FRAME, _PERSON, _SERVED}, answers

    acts = {act: answers[act] for act in _PERSONS_ACTS}
    if frontend in _AUTOMATED:
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


@pytest.mark.parametrize("frontend", (_DESKTOP, _SERVICE), ids=lambda frontend: frontend.value)
def test_generic_login_cannot_claim_a_desktop_holder_or_installed_service(
    frontend: OperationFrontendProjection, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with stored_sign_in_runtime(tmp_path, monkeypatch) as runtime:
        expected_human = RefusalCode.PEER_UNTRUSTED.value if frontend is _DESKTOP else _PERSON
        assert _answer(_client(runtime, frontend).resume_receipt) == expected_human
        assert (
            _answer(lambda: _client(runtime, frontend).login_password(bytearray(PROFILE_INPUT.encode())))
            == expected_human
        )
        expected_key = RefusalCode.PEER_UNTRUSTED.value if frontend is _DESKTOP else _INVALID_FRAME
        assert (
            _answer(
                lambda: _client(runtime, frontend).login_api_key(bytearray(b"synthetic-not-a-key-0000000000000000"))
            )
            == expected_key
        )
        assert _answer(_client(runtime, frontend, scope=_ATTENDANCE_SCOPE).request_attendance) == _INVALID_FRAME
        assert runtime.stored_sign_in() is not None


def test_controlled_service_admission_never_confers_person_acts(tmp_path: Path) -> None:
    # The existing fixture controls installed-image verification; native transport,
    # actual worker custody and human approval are real. This is no installed-image proof.
    with service_record_runtime(tmp_path) as runtime:
        service = runtime.connect_service()
        approved = runtime.admit(service)
        assert isinstance(approved, ServiceConnected)
        lease = service.claim()
        assert lease is not None and lease.parent_session_id == runtime.person_session_id
        assert lease.profile_id == runtime.profile_id
        assert service.connected is not None and lease.connection_id == service.connected.connection_id
        connection = service.connection
        assert (
            _answer(
                lambda: connection.session_inventory(
                    SessionInventory(request_id=uuid4(), profile_id=runtime.profile_id, session_id=lease.session_id),
                    deadline=time.monotonic() + 30,
                )
            )
            == _PERSON
        )
        assert (
            _answer(
                lambda: connection.deny_automation(
                    AutomationDeny(
                        request_id=uuid4(),
                        profile_id=runtime.profile_id,
                        session_id=lease.session_id,
                        kind=AutomationDenialKind.ALL,
                    ),
                    deadline=time.monotonic() + 30,
                )
            )
            == _PERSON
        )
        assert (
            _answer(
                lambda: connection.attendance(
                    AttendanceDecide(
                        action="attendance_inventory",
                        request_id=uuid4(),
                        profile_id=runtime.profile_id,
                        session_id=lease.session_id,
                    ),
                    deadline=time.monotonic() + 30,
                )
            )
            == _PERSON
        )
        for action in ("session_lock", "human_sign_out"):
            assert (
                _answer(
                    lambda action=action: connection.session(
                        SessionRequest(
                            action=action,
                            request_id=uuid4(),
                            profile_id=runtime.profile_id,
                            session_id=lease.session_id,
                        ),
                        deadline=time.monotonic() + 30,
                    )
                )
                == _PERSON
            )
        status = service.status()
        assert isinstance(status, ProfileStatus) and status.status.denial is None
        assert status.status.session_id == lease.session_id
