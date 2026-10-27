"""A lost profile worker suspends its leases until the exact connection that held each one proves it again.

The runtime, the native transport, the session authority, the profile workers
and the stored sign-in are real. The worker is lost by terminating its process;
the runtime learns of the loss through its own health check. Only the clock
that measures the recovery window and the repeat-loss interval is the test's.
"""

from __future__ import annotations

import os
import signal
import sys
import time
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from cadrumo.application.modelo.query_read_operation import MODELO_BINDINGS_LIST_OPERATION_DEFINITION_ID
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.access_contracts import OsLockState
from cadrumo.core.config import override_settings
from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.contracts.automation_codes import AutomationCustodyCode
from cadrumo_client.contracts.deadline_budget import exchange_deadline
from cadrumo_client.contracts.operation_access import OperationContract, OperationContractReply
from cadrumo_client.contracts.profile_access import AccessRefusal, ProfileStatus
from cadrumo_client.contracts.sign_in import HumanSignedOut
from cadrumo_client.contracts.sign_in_outcomes import ProfileReceiptRefusedError
from cadrumo_client.transport.framing import VerifiedConnection

from ...application.session_authority_core import CustodyRecoveryPolicy
from .stored_sign_in_runtime import SessionReply, StoredSignInRuntime, stored_sign_in_runtime

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires real native Windows profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]


class RecoveryClock:
    """The monotonic clock that measures only the recovery window and the repeat-loss interval."""

    def __init__(self) -> None:
        self.now = time.monotonic()

    def __call__(self) -> float:
        return self.now


@contextmanager
def _runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[tuple[StoredSignInRuntime, RecoveryClock]]:
    clock = RecoveryClock()
    with (
        stored_sign_in_runtime(tmp_path, monkeypatch) as runtime,
        override_settings(cadrumo_active_profile=str(runtime.profile_id)),
    ):
        # The profile's host is composed at its first login and reads the policy then.
        runtime.profiles._custody_recovery = CustodyRecoveryPolicy(monotonic=clock)
        yield runtime, clock


def _worker_serves(runtime: StoredSignInRuntime, connection: VerifiedConnection, session_id: UUID) -> object:
    """Ask for an operation contract: a call only a worker holding the session's custody answers."""
    return connection.operation(
        OperationContract(
            request_id=uuid4(),
            profile_id=runtime.profile_id,
            session_id=session_id,
            definition_id=MODELO_BINDINGS_LIST_OPERATION_DEFINITION_ID,
        ),
        deadline=exchange_deadline(),
    )


def _signed_in(runtime: StoredSignInRuntime, connection: VerifiedConnection) -> ProfileStatus:
    admitted = runtime.resume(connection, OperationFrontendProjection.TUI)
    assert isinstance(admitted, ProfileStatus), admitted
    assert admitted.status.session_id is not None
    assert isinstance(_worker_serves(runtime, connection, admitted.status.session_id), OperationContractReply)
    return admitted


def _worker_id(runtime: StoredSignInRuntime) -> UUID:
    worker = runtime.profiles._profiles[runtime.profile_id].owner._worker
    assert worker is not None
    return worker.identity.worker_id


def _lose_worker(runtime: StoredSignInRuntime, connection: VerifiedConnection, session_id: UUID) -> SessionReply:
    """Terminate the profile worker's process from outside the runtime; return the session's first status after it."""
    host = runtime.profiles._profiles[runtime.profile_id]
    worker = host.owner._worker
    assert worker is not None
    os.kill(worker._process.pid, signal.SIGTERM)
    deadline = time.monotonic() + 30
    while True:
        # Each status observes the worker's health; the terminated process is a positive loss.
        reply = _session_status(runtime, connection, session_id)
        live = isinstance(reply, ProfileStatus) and reply.status.denial is None
        # An unobservable worker is not yet the runtime's decision.
        if not live and not (isinstance(reply, AccessRefusal) and reply.code is AutomationCustodyCode.UNAVAILABLE):
            return reply
        assert time.monotonic() < deadline, f"the runtime never observed the terminated worker: {reply!r}"
        time.sleep(0.05)


def _session_status(runtime: StoredSignInRuntime, connection: VerifiedConnection, session_id: UUID) -> SessionReply:
    return runtime.session(connection, session_id, "session_status")


def _recovering(reply: object) -> int:
    """Return the seconds left of a session that waits for custody to recover."""
    if isinstance(reply, AccessRefusal):
        assert reply.code is AccessDenialCode.CUSTODY_RECOVERING, reply
        seconds = reply.recovery_remaining_seconds
    else:
        assert isinstance(reply, ProfileStatus), reply
        assert reply.status.denial is AccessDenialCode.CUSTODY_RECOVERING, reply
        seconds = reply.status.recovery_remaining_seconds
    assert seconds is not None and 0 < seconds <= 120
    return seconds


def test_the_same_connection_rebinds_its_session_with_the_saved_sign_in_under_a_fresh_worker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with _runtime(tmp_path, monkeypatch) as (runtime, _clock):
        person = runtime.connect()
        admitted = _signed_in(runtime, person)
        session_id = admitted.status.session_id
        assert session_id is not None
        original_expiry = admitted.status.session_expires_at
        stored = runtime.stored_sign_in()
        assert stored is not None
        lost_worker = _worker_id(runtime)

        _recovering(_lose_worker(runtime, person, session_id))
        assert _recovering(_session_status(runtime, person, session_id)) > 0
        assert runtime.stored_sign_in() == stored

        resumed = runtime.resume(person, OperationFrontendProjection.TUI)

        assert isinstance(resumed, ProfileStatus), resumed
        assert resumed.status.session_id == session_id and resumed.status.denial is None
        assert original_expiry is not None and resumed.status.session_expires_at is not None
        assert resumed.status.session_expires_at <= original_expiry
        assert resumed.human_login is not None and resumed.human_login.resumed
        assert _worker_id(runtime) != lost_worker
        assert isinstance(_worker_serves(runtime, person, session_id), OperationContractReply)


def test_the_saved_sign_in_on_another_connection_is_an_ordinary_sign_in(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with _runtime(tmp_path, monkeypatch) as (runtime, _clock):
        person = runtime.connect()
        session_id = _signed_in(runtime, person).status.session_id
        assert session_id is not None
        _lose_worker(runtime, person, session_id)

        other = runtime.connect()
        fresh = runtime.resume(other, OperationFrontendProjection.TUI)

        assert isinstance(fresh, ProfileStatus), fresh
        assert fresh.status.session_id is not None and fresh.status.session_id != session_id
        assert isinstance(_worker_serves(runtime, other, fresh.status.session_id), OperationContractReply)
        _recovering(_session_status(runtime, person, session_id))


def test_an_api_key_session_rebinds_only_when_its_key_is_presented_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with _runtime(tmp_path, monkeypatch) as (runtime, _clock):
        enrollment = runtime.enrollment
        request_id = uuid4()
        enrollment.service.request(request_id, enrollment.proposal)
        enrollment.approve(request_id)
        credential = enrollment.owner.delivery.endpoint.possession(enrollment.store.enrollment_state().requests[0])
        assert credential is not None
        automation = runtime.connect()
        admitted = runtime.login(
            automation, "api_key", bytearray(credential.get_secret_value()), frontend=OperationFrontendProjection.CLI
        )
        assert isinstance(admitted, ProfileStatus), admitted
        session_id = admitted.status.session_id
        assert session_id is not None
        original_expiry = admitted.status.session_expires_at
        _lose_worker(runtime, automation, session_id)

        # A person's proof is not this lease's proof.
        refused = runtime.resume(automation, OperationFrontendProjection.CLI)
        _recovering(refused)
        _recovering(_session_status(runtime, automation, session_id))

        rebound = runtime.login(
            automation, "api_key", bytearray(credential.get_secret_value()), frontend=OperationFrontendProjection.CLI
        )

        assert isinstance(rebound, ProfileStatus), rebound
        assert rebound.status.session_id == session_id and rebound.status.denial is None
        assert original_expiry is not None and rebound.status.session_expires_at is not None
        assert rebound.status.session_expires_at <= original_expiry


def test_sessions_not_rebound_when_the_window_ends_retire_as_custody_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with _runtime(tmp_path, monkeypatch) as (runtime, clock):
        person = runtime.connect()
        session_id = _signed_in(runtime, person).status.session_id
        assert session_id is not None
        _lose_worker(runtime, person, session_id)

        clock.now += 120
        runtime.profiles.os_session_changed()
        deadline = time.monotonic() + 15
        while session_id in runtime.profiles._profiles[runtime.profile_id].authority._suspended:
            assert time.monotonic() < deadline, "the lifecycle pass never ended the recovery window"
            time.sleep(0.05)

        assert session_id not in runtime.profiles._profiles[runtime.profile_id].authority._sessions
        fresh = runtime.resume(person, OperationFrontendProjection.TUI)
        assert isinstance(fresh, ProfileStatus), fresh
        assert fresh.status.session_id != session_id


def test_a_second_loss_within_ten_minutes_retires_every_session_at_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with _runtime(tmp_path, monkeypatch) as (runtime, clock):
        person = runtime.connect()
        session_id = _signed_in(runtime, person).status.session_id
        assert session_id is not None
        _lose_worker(runtime, person, session_id)
        rebound = runtime.resume(person, OperationFrontendProjection.TUI)
        assert isinstance(rebound, ProfileStatus) and rebound.status.session_id == session_id, rebound
        assert isinstance(_worker_serves(runtime, person, session_id), OperationContractReply)
        clock.now += 599

        refused = _lose_worker(runtime, person, session_id)

        assert isinstance(refused, AccessRefusal | ProfileStatus), refused
        denial = refused.code if isinstance(refused, AccessRefusal) else refused.status.denial
        assert denial is not None and denial is not AccessDenialCode.CUSTODY_RECOVERING, refused
        host = runtime.profiles._profiles[runtime.profile_id]
        assert session_id not in host.authority._suspended and session_id not in host.authority._sessions
        fresh = runtime.resume(person, OperationFrontendProjection.TUI)
        assert isinstance(fresh, ProfileStatus) and fresh.status.session_id != session_id, fresh


@pytest.mark.parametrize("ending", ["sign_out", "positive_lock"])
def test_sign_out_or_a_positive_os_lock_during_recovery_ends_the_session_with_no_rebind(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, ending: str
) -> None:
    with _runtime(tmp_path, monkeypatch) as (runtime, _clock):
        person = runtime.connect()
        session_id = _signed_in(runtime, person).status.session_id
        assert session_id is not None
        _lose_worker(runtime, person, session_id)
        host = runtime.profiles._profiles[runtime.profile_id]

        if ending == "sign_out":
            signed_out = runtime.session(person, session_id, "human_sign_out")
            assert isinstance(signed_out, HumanSignedOut), signed_out
            assert session_id in signed_out.session_ids
        else:
            with host.guard:
                runtime.native_login.lock_state = OsLockState.LOCKED
                retired = host.observe_human_lock_down()
                assert session_id in retired
                runtime.profiles._retired(retired)
                runtime.native_login.lock_state = OsLockState.UNLOCKED

        assert session_id not in host.authority._suspended and session_id not in host.authority._sessions
        assert runtime.stored_sign_in() is None
        status = _session_status(runtime, person, session_id)
        assert not isinstance(status, ProfileStatus) or status.status.denial is not AccessDenialCode.CUSTODY_RECOVERING
        # Nothing is left to present: the saved sign-in went with the session.
        with pytest.raises(ProfileReceiptRefusedError):
            runtime.resume(person, OperationFrontendProjection.TUI)


def test_work_of_the_lost_worker_is_never_carried_to_its_replacement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with _runtime(tmp_path, monkeypatch) as (runtime, _clock):
        person = runtime.connect()
        session_id = _signed_in(runtime, person).status.session_id
        assert session_id is not None
        host = runtime.profiles._profiles[runtime.profile_id]
        lost_owner, lost_approvals = host.owner, host.approvals

        _lose_worker(runtime, person, session_id)

        # The approvals that could have continued its operations are closed with it.
        assert host.owner is not lost_owner and host.approvals is not lost_approvals
        assert lost_approvals._closed
        assert lost_owner.lost
        # The replacement starts at once, holding no key; let its launch finish before the runtime stops.
        deadline = time.monotonic() + 90
        while host.owner._worker is None:
            assert time.monotonic() < deadline, "the replacement worker never started"
            time.sleep(0.1)
