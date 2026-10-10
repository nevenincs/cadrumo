"""An MCP connection resumes the person's stored sign-in, and may end no session but its own.

The runtime, its connection service, the session authority, the profile worker
and the stored sign-in are real. Only the native login the runtime observes,
the keychain holding the proof and the runtime's wall clock are ports held by
the test.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest

from cadrumo.adapters.local_runtime.framing import VerifiedRuntimeConnection
from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import PROFILE_INPUT
from cadrumo.application.operations.mcp_surfaces import McpSurfaceName
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.contracts import RuntimeRefusalCode
from cadrumo.application.runtime.profile_access import RuntimeAccessRefusal, RuntimeProfileStatus, RuntimeSessionsLocked
from cadrumo.application.runtime.sign_in import RuntimeHumanSignedOut, SignInPresence
from cadrumo.application.user_profile.access_contracts import AccessDenialCode, AccessScope, SessionKind

from .stored_sign_in_runtime import SessionReply, StoredSignInRuntime, stored_sign_in_runtime

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows worker and protected pipes"),
    pytest.mark.usefixtures("authority_operation"),
]

_CLI = OperationFrontendProjection.CLI
_TUI = OperationFrontendProjection.TUI
_MCP = OperationFrontendProjection.MCP


def _admitted(reply: RuntimeProfileStatus | RuntimeAccessRefusal) -> UUID:
    """Return the session a login was admitted with; a refusal fails the test with its code."""
    assert isinstance(reply, RuntimeProfileStatus), reply
    assert reply.status.denial is None and reply.status.session_id is not None
    return reply.status.session_id


def _refused(reply: SessionReply, code: AccessDenialCode | RuntimeRefusalCode) -> None:
    assert isinstance(reply, RuntimeAccessRefusal), reply
    assert reply.code is code


def _live(runtime: StoredSignInRuntime, connection: VerifiedRuntimeConnection, session_id: UUID) -> bool:
    """Ask the runtime whether a session is still admitted on the connection that holds it."""
    reply = runtime.session(connection, session_id, "session_status")
    return isinstance(reply, RuntimeProfileStatus) and reply.status.denial is None


def test_an_mcp_connection_resumes_the_stored_sign_in_as_the_person_and_extends_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with stored_sign_in_runtime(tmp_path, monkeypatch) as runtime:
        stored = runtime.stored_sign_in()
        assert stored is not None
        metadata = json.loads(stored)
        idle = datetime.fromisoformat(metadata["idle_deadline"])
        absolute = datetime.fromisoformat(metadata["absolute_deadline"])
        observer = runtime.connect()
        before = runtime.sign_in(observer)
        assert before.presence is SignInPresence.PRESENT
        assert (before.idle_deadline, before.absolute_deadline) == (idle, absolute)

        scopes: dict[OperationFrontendProjection, AccessScope] = {}
        for frontend in (_CLI, _TUI, _MCP):
            reply = runtime.resume(runtime.connect(), frontend)
            session_id = _admitted(reply)
            assert isinstance(reply, RuntimeProfileStatus)
            status = reply.status
            # The same sign-in admits each frontend to the same lease: the person's, bounded by the sign-in.
            assert status.profile_id == runtime.profile_id and status.profile_bound
            assert status.session_expires_at == min(idle, absolute)
            assert status.grant_state is None and not status.grant_valid
            assert reply.human_login is not None and reply.human_login.resumed
            assert (reply.human_login.idle_deadline, reply.human_login.absolute_deadline) == (idle, absolute)
            lease = runtime.lease(session_id)
            assert lease.kind is SessionKind.HUMAN and lease.binding == runtime.binding
            assert lease.expires_at == min(idle, absolute)
            assert lease.surface is None
            scopes[frontend] = status.effective_scope
        assert scopes[_MCP].operations == scopes[_CLI].operations == scopes[_TUI].operations
        assert scopes[_MCP].actions == scopes[_CLI].actions

        narrowed = runtime.resume(runtime.connect(), _MCP, surface=McpSurfaceName.READ_ONLY_LOCAL)
        narrowed_lease = runtime.lease(_admitted(narrowed))
        assert narrowed_lease.kind is SessionKind.HUMAN
        assert narrowed_lease.surface is McpSurfaceName.READ_ONLY_LOCAL

        # An MCP connection sends no password and never asks for a sign-in to be stored.
        for method, persist_receipt in (("password", False), ("password", True), ("receipt", True)):
            secret = bytearray(PROFILE_INPUT.encode())
            refused = runtime.login(runtime.connect(), method, secret, frontend=_MCP, persist_receipt=persist_receipt)
            _refused(refused, RuntimeRefusalCode.INVALID_FRAME)

        # Four resumes, one of them from MCP on a surface, moved neither deadline and rewrote nothing.
        assert runtime.stored_sign_in() == stored
        assert runtime.sign_in(observer) == before
        assert [(item.method, item.frontend) for item in runtime.profiles.logins[:4]] == [
            ("receipt", _CLI),
            ("receipt", _TUI),
            ("receipt", _MCP),
            ("receipt", _MCP),
        ]

        # The command line still signs in with the password, as before.
        password = runtime.login(runtime.connect(), "password", bytearray(PROFILE_INPUT.encode()), frontend=_CLI)
        assert runtime.lease(_admitted(password)).kind is SessionKind.HUMAN


@pytest.mark.parametrize("state", ["never-signed-in", "timed-out"])
def test_an_mcp_resume_is_refused_exactly_as_the_command_line_is(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, state: str
) -> None:
    timed_out = state == "timed-out"
    with stored_sign_in_runtime(tmp_path, monkeypatch, signed_in=timed_out) as runtime:
        if timed_out:
            # The sign-in is stored and its proof is good, but the runtime is past both of its deadlines.
            runtime.clock.ahead = timedelta(days=2)
        refusals: dict[OperationFrontendProjection, tuple[object, object]] = {}
        for frontend in (_CLI, _MCP):
            if timed_out:
                reply = runtime.resume(runtime.connect(), frontend)
            else:
                reply = runtime.login(runtime.connect(), "receipt", bytearray(32), frontend=frontend)
            assert isinstance(reply, RuntimeAccessRefusal), (frontend, reply)
            refusals[frontend] = (reply.code, reply.sign_in)

        assert refusals[_MCP] == refusals[_CLI]
        expected = AccessDenialCode.SESSION_EXPIRED if timed_out else AccessDenialCode.AUTHENTICATION_REQUIRED
        assert refusals[_MCP][0] is expected
        assert runtime.leases() == ()


def test_a_session_on_the_mcp_frontend_may_end_only_itself(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with stored_sign_in_runtime(tmp_path, monkeypatch) as runtime:
        stored = runtime.stored_sign_in()
        person, agent = runtime.connect(), runtime.connect()
        person_id = _admitted(runtime.resume(person, _CLI))
        agent_id = _admitted(runtime.resume(agent, _MCP))

        _refused(runtime.session(agent, agent_id, "human_sign_out"), AccessDenialCode.FRONTEND_DENIED)
        _refused(
            runtime.session(agent, agent_id, "session_lock", target_session_id=person_id),
            AccessDenialCode.FRONTEND_DENIED,
        )
        # Neither refusal ended a session or touched the person's sign-in.
        assert _live(runtime, person, person_id) and _live(runtime, agent, agent_id)
        assert runtime.stored_sign_in() == stored

        own = runtime.session(agent, agent_id, "session_lock")
        assert isinstance(own, RuntimeSessionsLocked) and own.session_ids == (agent_id,)
        assert not _live(runtime, agent, agent_id)
        assert _live(runtime, person, person_id)

        # Naming its own session as the target is the same act.
        second = runtime.connect()
        second_id = _admitted(runtime.resume(second, _MCP))
        named = runtime.session(second, second_id, "session_lock", target_session_id=second_id)
        assert isinstance(named, RuntimeSessionsLocked) and named.session_ids == (second_id,)
        assert _live(runtime, person, person_id)
        assert runtime.stored_sign_in() == stored


def test_a_person_on_the_command_line_still_locks_any_session_and_signs_out_everywhere(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with stored_sign_in_runtime(tmp_path, monkeypatch) as runtime:
        person, other, agent = runtime.connect(), runtime.connect(), runtime.connect()
        person_id = _admitted(runtime.resume(person, _CLI))
        other_id = _admitted(runtime.resume(other, _TUI))
        agent_id = _admitted(runtime.resume(agent, _MCP))

        revoked = runtime.session(person, person_id, "session_lock", target_session_id=agent_id)
        assert isinstance(revoked, RuntimeSessionsLocked) and revoked.session_ids == (agent_id,)
        assert not _live(runtime, agent, agent_id)

        own = runtime.session(person, person_id, "session_lock")
        assert isinstance(own, RuntimeSessionsLocked) and own.session_ids == (person_id,)

        # The sign-in is still stored, so an MCP connection resumes it again until the person signs out.
        resumed = runtime.connect()
        resumed_id = _admitted(runtime.resume(resumed, _MCP))
        signed_out = runtime.session(other, other_id, "human_sign_out")
        assert isinstance(signed_out, RuntimeHumanSignedOut), signed_out
        assert {other_id, resumed_id} <= set(signed_out.session_ids)
        assert signed_out.receipt_removed and signed_out.keychain_removed
        assert runtime.stored_sign_in() is None
        assert not _live(runtime, resumed, resumed_id)

        after = runtime.login(runtime.connect(), "receipt", bytearray(32), frontend=_MCP)
        _refused(after, AccessDenialCode.AUTHENTICATION_REQUIRED)
