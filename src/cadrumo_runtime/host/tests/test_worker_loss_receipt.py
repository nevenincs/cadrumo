"""A lost profile worker suspends its leases until the exact connection that held each one proves it again.

The runtime, the native transport, the session authority, the profile workers
and the stored sign-in are real. The worker is lost by terminating its process;
the runtime learns of the loss through its own health check. Only the clock
that measures the recovery window and the repeat-loss interval is the test's,
and one test holds the runtime's answer to a commit so that work is in flight
when the worker is lost.
"""

from __future__ import annotations

import asyncio
import os
import signal
import sys
import time
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from threading import Event, Thread
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.persistence.operations.journal import OperationJournalRepository
from cadrumo.application.modelo.query_read_operation import MODELO_BINDINGS_LIST_OPERATION_DEFINITION_ID
from cadrumo.application.operations.frontend_projection import OperationPublicProjectionV1
from cadrumo.application.operations.frontend_requests import (
    OperationObservationRequestV1,
    OperationObservationSuccessV1,
)
from cadrumo.application.operations.models import OperationId
from cadrumo.application.operations.persistence.journal import OperationPersistedSnapshot
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.access_contracts import OsLockState
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.application.user_profile.profile_operation_contracts import (
    PROFILE_FIELD_MUTATION_OPERATION_DEFINITION_ID,
    ProfileFieldMutationOperationRequest,
)
from cadrumo.application.user_profile.view_operation import ProfileViewFactItem, ProfileViewPageKind
from cadrumo.core.config import override_settings
from cadrumo.core.operations import OperationEffect, OperationLifecycle, profile_operation_subject
from cadrumo.domain.user_profile.setup_answers import PROFILE_OUTPUT_LANGUAGE_PATH
from cadrumo.tests.hang_guard import HANG_GUARD_SECONDS
from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.contracts.access_vocabulary import AccessAction
from cadrumo_client.contracts.automation_codes import AutomationCustodyCode
from cadrumo_client.contracts.deadline_budget import exchange_deadline
from cadrumo_client.contracts.operation_access import (
    OperationAcknowledged,
    OperationContract,
    OperationContractReply,
    OperationControl,
    OperationObserve,
    OperationObserved,
    OperationRequest,
    OperationSubmit,
    OperationSubmitted,
)
from cadrumo_client.contracts.profile_access import AccessRefusal, ProfileStatus
from cadrumo_client.contracts.sign_in import HumanSignedOut
from cadrumo_client.contracts.sign_in_outcomes import ProfileReceiptRefusedError
from cadrumo_client.transport.framing import VerifiedConnection
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.windows_process import WindowsOwnedProcess
from cadrumo_runtime.contracts.worker_authorization import WorkerAuthorityRequest, WorkerAuthorizationRequest

from ...adapters.profile_worker import ProfileWorkerProcess
from ...application.session_authority_core import CustodyRecoveryPolicy
from ..profile_host import RuntimeProfileHost
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


def _kill_worker(runtime: StoredSignInRuntime) -> None:
    """Terminate the profile worker's process from outside the runtime, and return once it has exited."""
    worker = runtime.profiles._profiles[runtime.profile_id].owner._worker
    assert worker is not None
    process = worker._process
    assert isinstance(process, WindowsOwnedProcess)
    waiter = process.retain_waiter()
    try:
        os.kill(process.pid, signal.SIGTERM)
        waiter.wait(timeout=HANG_GUARD_SECONDS)
    finally:
        waiter.close()


def _lose_worker(runtime: StoredSignInRuntime, connection: VerifiedConnection, session_id: UUID) -> SessionReply:
    """Terminate the profile worker's process from outside the runtime; return the session's first status after it."""
    _kill_worker(runtime)
    deadline = time.monotonic() + HANG_GUARD_SECONDS
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


def _idle(runtime: StoredSignInRuntime) -> None:
    """Run as the installed runtime does once nothing happens: the OS reports session changes, so no pass is on a timer.

    Returns once no lifecycle pass has been due for a second, longer than a
    finished request takes to owe one, so only the runtime's own observation
    of the worker can bring the next one.
    """
    runtime.profiles.session_changes_pushed(True)
    # This runtime has no logon inventory to report the test's logon as one with a lock surface.
    runtime.profiles._unreported_logins = False
    deadline = time.monotonic() + HANG_GUARD_SECONDS
    quiet_since = time.monotonic()
    while time.monotonic() - quiet_since < 1.0:
        assert time.monotonic() < deadline, "a lifecycle pass stayed due"
        if (due := runtime.profiles.lifecycle_due_in()) is not None and due < 10:
            quiet_since = time.monotonic()
        time.sleep(0.05)


def _suspended_without_a_request(runtime: StoredSignInRuntime, session_id: UUID) -> None:
    """Wait for the runtime's own observation of the loss to suspend the session; how soon is the machine's."""
    authority = runtime.profiles._profiles[runtime.profile_id].authority
    deadline = time.monotonic() + HANG_GUARD_SECONDS
    while session_id not in authority._suspended:
        assert time.monotonic() < deadline, "no session was suspended after the worker's loss"
        time.sleep(0.05)


def _without_exit_watch(monkeypatch: pytest.MonkeyPatch) -> None:
    """Leave the loss to the runtime's other observations, as where no exit can be waited on."""
    monkeypatch.setattr(ProfileWorkerProcess, "_watch_exit", lambda _worker, _exited: None)


def test_a_killed_worker_suspends_its_sessions_with_no_request_or_heartbeat(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with _runtime(tmp_path, monkeypatch) as (runtime, _clock):
        person = runtime.connect()
        session_id = _signed_in(runtime, person).status.session_id
        assert session_id is not None
        _idle(runtime)

        _kill_worker(runtime)

        _suspended_without_a_request(runtime, session_id)
        _recovering(_session_status(runtime, person, session_id))


def test_a_heartbeat_that_finds_the_worker_gone_suspends_its_sessions_at_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _without_exit_watch(monkeypatch)
    with _runtime(tmp_path, monkeypatch) as (runtime, _clock):
        person = runtime.connect()
        session_id = _signed_in(runtime, person).status.session_id
        assert session_id is not None
        _idle(runtime)
        _kill_worker(runtime)

        # The supervisor's heartbeat asks for this count; a dead worker cannot answer it. The
        # probe's bound only ends a hang: a bound the machine can pass would end the probe as
        # unanswered rather than as a loss, and nothing would then suspend the session.
        assert runtime.profiles.in_flight_operation_count(timeout=HANG_GUARD_SECONDS) is None

        _suspended_without_a_request(runtime, session_id)
        _recovering(_session_status(runtime, person, session_id))


def test_the_first_submission_after_an_unobserved_loss_hears_the_session_is_recovering(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _without_exit_watch(monkeypatch)
    with _runtime(tmp_path, monkeypatch) as (runtime, _clock):
        person = runtime.connect()
        session_id = _signed_in(runtime, person).status.session_id
        assert session_id is not None
        _idle(runtime)
        _kill_worker(runtime)

        refused = person.operation(
            _field_mutation(runtime, session_id, revision=1, digest="0" * 64, language="es"),
            deadline=exchange_deadline(),
        )

        assert _recovering(refused) > 0


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
        deadline = time.monotonic() + HANG_GUARD_SECONDS
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


@dataclass
class _AuthorityHold:
    """What the held authority request saw: the operations that asked, and the runtime's answer to each."""

    entered: list[OperationId] = field(default_factory=list)
    entered_event: Event = field(default_factory=Event)
    release: Event = field(default_factory=Event)
    answered: list[BaseException | None] = field(default_factory=list)


@contextmanager
def _authority_held(
    monkeypatch: pytest.MonkeyPatch, action: AccessAction, definition_id: str
) -> Generator[_AuthorityHold]:
    """Hold the runtime's answer to the first worker request for ``action`` on ``definition_id`` until released.

    The hold waits before the runtime's own authority runs, so no profile guard
    is held meanwhile; the worker has already entered the request and waits for
    the answer. The runtime's decision, once released, is the real one. Every
    later request for the same door is recorded and passes at once.
    """
    hold = _AuthorityHold()
    original = RuntimeProfileHost.authorize

    @contextmanager
    def held(host: RuntimeProfileHost, request: WorkerAuthorityRequest) -> Generator[object]:
        if not (
            isinstance(request, WorkerAuthorizationRequest)
            and request.request.action is action
            and request.request.definition_id == definition_id
        ):
            with original(host, request) as allowed:
                yield allowed
            return
        first = not hold.entered
        hold.entered.append(request.operation_id)
        if first:
            hold.entered_event.set()
            if not hold.release.wait(timeout=60):
                raise TimeoutError("the held authority request was never released")
        try:
            with original(host, request) as allowed:
                hold.answered.append(None)
                yield allowed
        except BaseException as error:
            hold.answered.append(error)
            raise

    monkeypatch.setattr(RuntimeProfileHost, "authorize", held)
    try:
        yield hold
    finally:
        hold.release.set()


def _profile_view(reader: FrontendClient) -> tuple[int, str, dict[str, str]]:
    page = reader.read_profile_view((ProfileViewPageKind.FACTS,), timeout=90)
    facts = {
        item.path: item.value for item in page.items(ProfileViewPageKind.FACTS) if isinstance(item, ProfileViewFactItem)
    }
    return page.record_revision, page.content_digest, facts


def _observe(
    runtime: StoredSignInRuntime, connection: VerifiedConnection, session_id: UUID, operation_id: OperationId
) -> OperationPublicProjectionV1:
    observed = connection.operation(
        OperationObserve(
            request_id=uuid4(),
            profile_id=runtime.profile_id,
            session_id=session_id,
            observation=OperationObservationRequestV1(operation_id=operation_id, after_cursor=0, page_limit=32),
        ),
        deadline=exchange_deadline(),
    )
    assert isinstance(observed, OperationObserved), observed
    assert isinstance(observed.observation, OperationObservationSuccessV1), observed.observation
    return observed.observation.projection


def _field_mutation(
    runtime: StoredSignInRuntime, session_id: UUID, *, revision: int, digest: str, language: str
) -> OperationSubmit:
    return OperationSubmit(
        request_id=uuid4(),
        profile_id=runtime.profile_id,
        session_id=session_id,
        definition_id=PROFILE_FIELD_MUTATION_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(runtime.profile_id)),
        payload_json=ProfileFieldMutationOperationRequest(
            profile_id=runtime.profile_id,
            expected_revision=revision,
            expected_content_digest=digest,
            path=PROFILE_OUTPUT_LANGUAGE_PATH,
            value=language,
        ).model_dump_json(),
    )


def _start(
    runtime: StoredSignInRuntime, connection: VerifiedConnection, session_id: UUID, operation_id: OperationId
) -> object:
    return connection.operation(
        OperationControl(
            action="operation_start",
            request_id=uuid4(),
            profile_id=runtime.profile_id,
            session_id=session_id,
            operation_id=operation_id,
        ),
        deadline=exchange_deadline(),
    )


def _journal(runtime: StoredSignInRuntime, operation_id: OperationId) -> OperationPersistedSnapshot:
    return asyncio.run(OperationJournalRepository(storage_root=runtime.root).load(operation_id))


def _reader(runtime: StoredSignInRuntime) -> FrontendClient:
    """A person's own reader session on a connection of its own."""
    reader = FrontendClient(runtime.connect(), profile_id=runtime.profile_id, frontend=OperationFrontendProjection.TUI)
    reader.resume_receipt()
    return reader


def test_work_in_flight_at_the_loss_stays_unknown_after_the_same_connection_rebinds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with (
        _runtime(tmp_path, monkeypatch) as (runtime, _clock),
        _authority_held(monkeypatch, AccessAction.COMMIT, PROFILE_FIELD_MUTATION_OPERATION_DEFINITION_ID) as hold,
    ):
        person = runtime.connect()
        session_id = _signed_in(runtime, person).status.session_id
        assert session_id is not None
        revision, digest, facts = _profile_view(_reader(runtime))
        language = "hu" if facts.get(PROFILE_OUTPUT_LANGUAGE_PATH) == "es" else "es"
        submitted = person.operation(
            _field_mutation(runtime, session_id, revision=revision, digest=digest, language=language),
            deadline=exchange_deadline(),
        )
        assert isinstance(submitted, OperationSubmitted), submitted
        operation_id = submitted.receipt.operation_id
        assert isinstance(_start(runtime, person, session_id, operation_id), OperationAcknowledged)
        assert hold.entered_event.wait(timeout=60), "the operation never reached its commit"
        in_flight = _journal(runtime, operation_id)
        assert in_flight.executor_entered_at is not None and in_flight.terminal_condition is None

        _recovering(_lose_worker(runtime, person, session_id))
        # The lost worker's own commit request is answered only now, while its session is suspended.
        hold.release.set()
        deadline = time.monotonic() + HANG_GUARD_SECONDS
        while not hold.answered:
            assert time.monotonic() < deadline, "the held commit was never answered"
            time.sleep(0.05)
        assert isinstance(hold.answered[0], ProfileAccessRefusedError), hold.answered

        rebound = runtime.resume(person, OperationFrontendProjection.TUI)
        assert isinstance(rebound, ProfileStatus) and rebound.status.session_id == session_id, rebound

        # The rebound session sees the same operation, unresolved: neither completed nor failed.
        projection = _observe(runtime, person, session_id, operation_id)
        assert (projection.operation_id, projection.definition_id, projection.subject_ref) == (
            in_flight.identity.operation_id,
            in_flight.identity.definition_id,
            in_flight.identity.subject_ref,
        )
        assert projection.terminal_condition is None and projection.lifecycle is not OperationLifecycle.TERMINAL
        assert projection.effect is OperationEffect.UNKNOWN
        assert projection.result_ref is None and projection.failure_error_code is None
        # Starting it again resumes nothing, and a new change to the subject names it as the holder.
        assert isinstance(restart := _start(runtime, person, session_id, operation_id), AccessRefusal), restart
        busy = person.operation(
            _field_mutation(runtime, session_id, revision=revision, digest=digest, language="ca"),
            deadline=exchange_deadline(),
        )
        assert isinstance(busy, AccessRefusal), busy
        assert busy.code is AccessDenialCode.SUBJECT_BUSY and busy.holder_operation_id == operation_id, busy

        # The replacement worker never executed it: no commit was asked again, the
        # journal did not move and the profile record is the one before the loss.
        assert hold.entered == [operation_id] and len(hold.answered) == 1
        after = _journal(runtime, operation_id)
        assert after.identity == in_flight.identity and after.revision == in_flight.revision
        assert after.executor_entered_at == in_flight.executor_entered_at and after.terminal_condition is None
        assert after.effect is OperationEffect.UNKNOWN
        assert _profile_view(_reader(runtime))[:2] == (revision, digest)


def _in_flight_when_lost(
    runtime: StoredSignInRuntime, connection: VerifiedConnection, request: OperationRequest, hold: _AuthorityHold
) -> object:
    """Send ``request``, kill the worker while it waits on the held authority, and return the runtime's answer."""
    answers: list[object] = []
    sender = Thread(target=lambda: answers.append(connection.operation(request, deadline=exchange_deadline())))
    sender.start()
    try:
        assert hold.entered_event.wait(timeout=60), "the worker never asked for the request's authority"
        assert not answers, f"the request was answered before the worker asked: {answers!r}"
        _kill_worker(runtime)
    finally:
        hold.release.set()
        sender.join(timeout=60)
    assert not sender.is_alive(), "the request in flight at the loss was never answered"
    assert len(answers) == 1
    return answers[0]


def test_a_read_in_flight_when_the_worker_is_lost_hears_the_session_is_recovering(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with (
        _runtime(tmp_path, monkeypatch) as (runtime, _clock),
        _authority_held(monkeypatch, AccessAction.OBSERVE, PROFILE_FIELD_MUTATION_OPERATION_DEFINITION_ID) as hold,
    ):
        person = runtime.connect()
        session_id = _signed_in(runtime, person).status.session_id
        assert session_id is not None
        revision, digest, _facts = _profile_view(_reader(runtime))
        submitted = person.operation(
            _field_mutation(runtime, session_id, revision=revision, digest=digest, language="ca"),
            deadline=exchange_deadline(),
        )
        assert isinstance(submitted, OperationSubmitted), submitted
        operation_id = submitted.receipt.operation_id

        refused = _in_flight_when_lost(
            runtime,
            person,
            OperationObserve(
                request_id=uuid4(),
                profile_id=runtime.profile_id,
                session_id=session_id,
                observation=OperationObservationRequestV1(operation_id=operation_id, after_cursor=0, page_limit=32),
            ),
            hold,
        )

        # A read changed nothing: it is the ordinary, retryable refusal of a suspended session.
        assert _recovering(refused) > 0
        assert isinstance(refused, AccessRefusal)
        assert refused.effect is None and refused.operation_id is None
        assert hold.entered == [operation_id]


def test_a_mutation_in_flight_when_the_worker_is_lost_is_unknown_and_never_run_again_after_rebinding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with (
        _runtime(tmp_path, monkeypatch) as (runtime, _clock),
        _authority_held(monkeypatch, AccessAction.START, PROFILE_FIELD_MUTATION_OPERATION_DEFINITION_ID) as hold,
    ):
        person = runtime.connect()
        session_id = _signed_in(runtime, person).status.session_id
        assert session_id is not None
        revision, digest, facts = _profile_view(_reader(runtime))
        language = "hu" if facts.get(PROFILE_OUTPUT_LANGUAGE_PATH) == "es" else "es"
        submitted = person.operation(
            _field_mutation(runtime, session_id, revision=revision, digest=digest, language=language),
            deadline=exchange_deadline(),
        )
        assert isinstance(submitted, OperationSubmitted), submitted
        operation_id = submitted.receipt.operation_id
        before = _journal(runtime, operation_id)

        refused = _in_flight_when_lost(
            runtime,
            person,
            OperationControl(
                action="operation_start",
                request_id=uuid4(),
                profile_id=runtime.profile_id,
                session_id=session_id,
                operation_id=operation_id,
            ),
            hold,
        )

        # The start may have taken effect: the session is recovering, and the start's outcome is unknown.
        assert _recovering(refused) > 0
        assert isinstance(refused, AccessRefusal)
        assert refused.effect is OperationEffect.UNKNOWN and refused.operation_id == operation_id, refused

        rebound = runtime.resume(person, OperationFrontendProjection.TUI)
        assert isinstance(rebound, ProfileStatus) and rebound.status.session_id == session_id, rebound
        projection = _observe(runtime, person, session_id, operation_id)
        assert projection.terminal_condition is None and projection.lifecycle is not OperationLifecycle.TERMINAL
        # Observing it is the reconciliation: the lost worker never began it, so nothing took effect.
        assert projection.effect is OperationEffect.NONE, projection.effect
        assert projection.result_ref is None and projection.failure_error_code is None
        # Rebinding ran nothing: the replacement never asked to start it, and its record and the profile are as before.
        assert hold.entered == [operation_id]
        after = _journal(runtime, operation_id)
        assert after.identity == before.identity and after.terminal_condition is None
        assert after.executor_entered_at is None
        assert _profile_view(_reader(runtime))[:2] == (revision, digest)
