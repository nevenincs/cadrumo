"""An MCP connection receives a reviewed child of the person's held sign-in.

Locking, signing out and signing in by password are the person's acts on the
command line and terminal interface. Only those frontends resume stored proof;
MCP needs exact attendance approval and is refused the person's acts.

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

from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import PROFILE_INPUT
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.access_contracts import AccessDenialCode, EffectiveScopeSummary, SessionKind
from cadrumo.application.user_profile.automation_lifecycle import AutomationDenialKind
from cadrumo_client.contracts.contracts import RefusalCode
from cadrumo_client.contracts.profile_access import AccessRefusal, ProfileStatus, SessionsLocked
from cadrumo_client.contracts.sign_in import HumanSignedOut, SignInPresence
from cadrumo_client.transport.framing import VerifiedConnection
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError
from cadrumo_harness.mcp.access_scope import surface_scope
from cadrumo_harness.mcp.surfaces import DEFAULT_MCP_SURFACE, MCP_SURFACES
from cadrumo_runtime.host.tests.stored_sign_in_runtime import SessionReply, StoredSignInRuntime, stored_sign_in_runtime

from .attended_mcp_support import attended_client, holding_person

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows worker and protected pipes"),
    pytest.mark.usefixtures("authority_operation"),
]

_CLI = OperationFrontendProjection.CLI
_TUI = OperationFrontendProjection.TUI
_MCP = OperationFrontendProjection.EXTERNAL_CLIENT


def _admitted(reply: ProfileStatus | AccessRefusal) -> UUID:
    """Return the session a login was admitted with; a refusal fails the test with its code."""
    assert isinstance(reply, ProfileStatus), reply
    assert reply.status.denial is None and reply.status.session_id is not None
    return reply.status.session_id


def _refused(reply: SessionReply, code: AccessDenialCode | RefusalCode) -> None:
    assert isinstance(reply, AccessRefusal), reply
    assert reply.code is code


def _live(runtime: StoredSignInRuntime, connection: VerifiedConnection, session_id: UUID) -> bool:
    """Ask the runtime whether a session is still admitted on the connection that holds it."""
    reply = runtime.session(connection, session_id, "session_status")
    return isinstance(reply, ProfileStatus) and reply.status.denial is None


def test_an_attended_mcp_connection_follows_the_persons_held_sign_in_and_extends_nothing(
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

        scopes: dict[OperationFrontendProjection, EffectiveScopeSummary] = {}
        for frontend in (_CLI, _TUI):
            reply = runtime.resume(runtime.connect(), frontend)
            session_id = _admitted(reply)
            assert isinstance(reply, ProfileStatus)
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
            assert lease.scope.allow_changes_records
            scopes[frontend] = status.effective_scope
        assert scopes[_CLI].operations == scopes[_TUI].operations
        person = holding_person(runtime)
        agent = attended_client(runtime, person)
        attended = agent.status()
        assert attended.human_login is None
        child = runtime.lease(agent.session_id)
        assert child.kind is SessionKind.ATTENDED and child.binding == runtime.binding
        assert child.parent_session_id == person.session_id
        assert child.expires_at <= min(idle, absolute)
        scopes[_MCP] = attended.status.effective_scope
        ceiling = surface_scope(MCP_SURFACES[DEFAULT_MCP_SURFACE])
        assert scopes[_MCP].operations == scopes[_CLI].operations & ceiling.operations
        assert scopes[_MCP].actions == scopes[_CLI].actions & ceiling.actions

        # Receipt resumes moved neither deadline and rewrote nothing.
        assert runtime.stored_sign_in() == stored
        assert runtime.sign_in(observer) == before
        assert [(item.method, item.frontend) for item in runtime.profiles.logins[:3]] == [
            ("receipt", _CLI),
            ("receipt", _TUI),
            ("receipt", _CLI),
        ]

        # The password signs the person in on the person's frontends, to the same kind of lease.
        for frontend in (_CLI, _TUI):
            password = runtime.login(
                runtime.connect(), "password", bytearray(PROFILE_INPUT.encode()), frontend=frontend
            )
            lease = runtime.lease(_admitted(password))
            assert lease.kind is SessionKind.HUMAN and lease.scope.allow_changes_records
        # Signing in by password is the person's act, so the MCP frontend is refused it.
        agent = runtime.login(runtime.connect(), "password", bytearray(PROFILE_INPUT.encode()), frontend=_MCP)
        _refused(agent, AccessDenialCode.PERSON_ACT_REQUIRED)


@pytest.mark.parametrize("state", ["never-signed-in", "timed-out"])
def test_absent_or_expired_human_proof_leaves_no_session_for_mcp_attendance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, state: str
) -> None:
    timed_out = state == "timed-out"
    with stored_sign_in_runtime(tmp_path, monkeypatch, signed_in=timed_out) as runtime:
        if timed_out:
            # The sign-in is stored and its proof is good, but the runtime is past both of its deadlines.
            runtime.clock.ahead = timedelta(days=2)
        if timed_out:
            reply = runtime.resume(runtime.connect(), _CLI)
        else:
            reply = runtime.login(runtime.connect(), "receipt", bytearray(32), frontend=_CLI)
        assert isinstance(reply, AccessRefusal), reply
        expected = AccessDenialCode.SESSION_EXPIRED if timed_out else AccessDenialCode.AUTHENTICATION_REQUIRED
        assert reply.code is expected
        # No live human holder exists. The external connection presents no receipt proof.
        agent = FrontendClient(
            runtime.connect(),
            profile_id=runtime.profile_id,
            frontend=_MCP,
            scope=surface_scope(MCP_SURFACES[DEFAULT_MCP_SURFACE]),
        )
        with pytest.raises(FrontendRefusedError) as denied:
            agent.request_attendance()
        assert denied.value.reason == AccessDenialCode.AUTHENTICATION_REQUIRED.value
        assert denied.value.sign_in is None
        assert all(item.frontend is _CLI for item in runtime.profiles.logins)
        assert runtime.leases() == ()


@pytest.mark.parametrize("acting", [_CLI, _TUI], ids=["cli", "tui"])
def test_the_persons_session_locks_any_session_and_signs_out_everywhere_from_the_persons_frontends(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, acting: OperationFrontendProjection
) -> None:
    with stored_sign_in_runtime(tmp_path, monkeypatch) as runtime:
        stored = runtime.stored_sign_in()
        actor, other, third = runtime.connect(), runtime.connect(), runtime.connect()
        holder = FrontendClient(actor, profile_id=runtime.profile_id, frontend=acting)
        actor_id = _admitted(holder.resume_receipt())
        other_id = _admitted(runtime.resume(other, _TUI))
        third_id = attended_client(runtime, holder, connection=third).session_id

        revoked = runtime.session(actor, actor_id, "session_lock", target_session_id=third_id)
        assert isinstance(revoked, SessionsLocked) and revoked.session_ids == (third_id,)
        assert not _live(runtime, third, third_id)
        assert _live(runtime, actor, actor_id) and _live(runtime, other, other_id)

        # A session ends itself whether it names itself as the target or names none.
        named, unnamed = runtime.connect(), runtime.connect()
        named_id = _admitted(runtime.resume(named, acting))
        unnamed_id = _admitted(runtime.resume(unnamed, acting))
        by_name = runtime.session(named, named_id, "session_lock", target_session_id=named_id)
        assert isinstance(by_name, SessionsLocked) and by_name.session_ids == (named_id,)
        own = runtime.session(unnamed, unnamed_id, "session_lock")
        assert isinstance(own, SessionsLocked) and own.session_ids == (unnamed_id,)
        assert not _live(runtime, named, named_id) and not _live(runtime, unnamed, unnamed_id)
        # No lock touched the stored sign-in, so a connection resumes it again until the person signs out.
        assert runtime.stored_sign_in() == stored
        resumed = runtime.connect()
        resumed_id = attended_client(runtime, holder, connection=resumed).session_id

        signed_out = runtime.session(actor, actor_id, "human_sign_out")
        assert isinstance(signed_out, HumanSignedOut), signed_out
        assert {actor_id, other_id, resumed_id} <= set(signed_out.session_ids)
        assert signed_out.receipt_removed and signed_out.keychain_removed
        assert runtime.stored_sign_in() is None
        assert not _live(runtime, other, other_id) and not _live(runtime, resumed, resumed_id)

        after = runtime.login(runtime.connect(), "receipt", bytearray(32), frontend=acting)
        _refused(after, AccessDenialCode.AUTHENTICATION_REQUIRED)


@pytest.mark.parametrize("acting", [_CLI, _TUI], ids=["cli", "tui"])
def test_the_person_locks_the_profile_and_resumes_it_with_the_password_from_the_persons_frontends(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, acting: OperationFrontendProjection
) -> None:
    with stored_sign_in_runtime(tmp_path, monkeypatch) as runtime:
        actor = FrontendClient(runtime.connect(), profile_id=runtime.profile_id, frontend=acting)
        actor.resume_receipt()
        assert [item.session_id for item in actor.sessions()] == [actor.session_id]

        locked = actor.deny_automation(AutomationDenialKind.PROFILE_LOCK)

        assert locked.access_denied and locked.profile_lock_generation is not None
        assert runtime.enrollment.store.profile_lock_state().globally_locked
        assert runtime.leases() == ()
        # The lock retired the stored sign-in with it, so no frontend resumes it.
        refused = runtime.login(runtime.connect(), "receipt", bytearray(32), frontend=acting)
        assert isinstance(refused, AccessRefusal), refused

        fresh = FrontendClient(runtime.connect(), profile_id=runtime.profile_id, frontend=acting)
        resumed = fresh.recover_profile(bytearray(PROFILE_INPUT.encode()))

        assert resumed.profile_id == runtime.profile_id
        assert resumed.lock_generation == locked.profile_lock_generation
        assert not runtime.enrollment.store.profile_lock_state().globally_locked
        password = runtime.login(runtime.connect(), "password", bytearray(PROFILE_INPUT.encode()), frontend=acting)
        assert runtime.lease(_admitted(password)).kind is SessionKind.HUMAN
