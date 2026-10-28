"""Owned first-login proofs leave the verified reader available for cancellation."""

from __future__ import annotations

import os
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from threading import Event
from uuid import uuid4

import pytest

from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.contracts.profile_access import (
    AccessRefusal,
    ProfileLogin,
    ProfileLoginPending,
    ProfileLoginStatusQuery,
    ProfileStatus,
    SecretReady,
    SessionRequest,
)
from cadrumo_client.contracts.profile_selection import ActiveProfileReply, ActiveProfileRequest
from cadrumo_client.contracts.session_events import ProfileLoginChanged
from cadrumo_client.transport.frontend_client import FrontendClient

from ...adapters import profile_worker_transport
from ...adapters.tests.profile_worker_support import PROFILE_INPUT
from .test_profile_connections import connect
from .test_service_records import service_record_runtime

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]


@pytest.mark.parametrize("ending", ["cancel", "cancel_bound", "disconnect", "lock", "profile_change", "commit"])
def test_pending_login_keeps_reader_free_and_fences_late_proof(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, ending: str
) -> None:
    with service_record_runtime(tmp_path) as runtime:
        contender = connect(runtime.endpoint)
        runtime.clients.append(contender)
        host = runtime.profiles._profiles[runtime.profile_id]
        entered, release, settled = Event(), Event(), Event()
        original = host.owner.authenticate_human
        proofs = []
        bound_sessions = []

        @contextmanager
        def paused(connection_id):
            with original(connection_id) as outcome:
                proofs.append(connection_id)
                if ending != "cancel_bound":
                    entered.set()
                    assert release.wait(20), "test did not release the owned proof"
                yield outcome

        monkeypatch.setattr(host.owner, "authenticate_human", paused)
        if ending == "cancel_bound":
            original_publish = host.authority._publish_human_candidate

            def paused_publication(connection_id, candidate, retirement):
                bound_sessions.append(candidate.session.session_id)
                entered.set()
                assert release.wait(20), "test did not release the bound candidate"
                return original_publish(connection_id, candidate, retirement)

            monkeypatch.setattr(host.authority, "_publish_human_candidate", paused_publication)
        request = ProfileLogin(
            request_id=uuid4(),
            profile_id=runtime.profile_id,
            method="password",
            frontend=OperationFrontendProjection.CLI,
            persist_receipt=False,
        )
        unsubscribe = contender.subscribe_session_events(
            lambda event: (
                settled.set()
                if isinstance(event, ProfileLoginChanged) and event.login_request_id == request.request_id
                else None
            ),
        )
        try:
            with contender.held_exchange(request, request.request_id, deadline=time.monotonic() + 20) as exchange:
                assert isinstance(exchange.reply().root, SecretReady)
                proof = bytearray(PROFILE_INPUT.encode())
                contender.send_secret(proof, deadline=time.monotonic() + 10)
                pending = exchange.reply().root
                assert isinstance(pending, ProfileLoginPending)
                assert proof == bytearray(len(proof))
            assert entered.wait(10), "login did not reach its retained proof"
            attempt = runtime.profiles._pending_logins[pending.connection_id]
            status = runtime.human.session(
                SessionRequest(
                    action="session_status",
                    request_id=uuid4(),
                    profile_id=runtime.profile_id,
                    session_id=runtime.person_session_id,
                ),
                deadline=time.monotonic() + 5,
            )
            assert isinstance(status, ProfileStatus) and status.status.denial is None
            wrong = contender.login_status(
                ProfileLoginStatusQuery(
                    action="profile_login_cancel",
                    request_id=uuid4(),
                    profile_id=runtime.profile_id,
                    login_request_id=uuid4(),
                ),
                deadline=time.monotonic() + 5,
            )
            assert isinstance(wrong, AccessRefusal) and wrong.code is AccessDenialCode.CONNECTION_MISMATCH
            assert not attempt.control.cancelled
            if ending in {"cancel", "cancel_bound"}:
                cancelled = contender.login_status(
                    ProfileLoginStatusQuery(
                        action="profile_login_cancel",
                        request_id=uuid4(),
                        profile_id=runtime.profile_id,
                        login_request_id=request.request_id,
                    ),
                    deadline=time.monotonic() + 5,
                )
                assert isinstance(cancelled, ProfileLoginPending)
                assert attempt.control.cancelled and not attempt.control.committed
            elif ending == "disconnect":
                contender.close()
                assert attempt.control.cancelled_event.wait(5), "runtime did not observe the peer's EOF"
                assert runtime.profiles._pending_logins.get(pending.connection_id) is attempt
            elif ending == "lock":
                host.authority.retire_human_sessions(reason=AccessDenialCode.PROFILE_LOCKED)
            elif ending == "profile_change":
                other = connect(runtime.endpoint)
                runtime.clients.append(other)
                other_profile = FrontendClient(
                    other,
                    profile_id=runtime.other_profile_id,
                    frontend=OperationFrontendProjection.CLI,
                )
                assert (
                    other_profile.login_password(bytearray(PROFILE_INPUT.encode()), persist_receipt=True).status.denial
                    is None
                )
            release.set()
            assert attempt.finished.wait(10), "proof owner did not settle after its outcome"
            assert attempt.secret == bytearray(len(attempt.secret))
            assert len(proofs) == 1
            if ending == "disconnect":
                assert not attempt.control.committed
                assert attempt.connection.session_id is None
                return
            assert settled.wait(5), "terminal login outcome was not cued"
            result = contender.login_status(
                ProfileLoginStatusQuery(
                    action="profile_login_status",
                    request_id=uuid4(),
                    profile_id=runtime.profile_id,
                    login_request_id=request.request_id,
                ),
                deadline=time.monotonic() + 5,
            )
            if ending == "commit":
                assert isinstance(result, ProfileStatus) and result.status.denial is None
                assert attempt.control.committed
                repeated = contender.login_status(
                    ProfileLoginStatusQuery(
                        action="profile_login_cancel",
                        request_id=uuid4(),
                        profile_id=runtime.profile_id,
                        login_request_id=request.request_id,
                    ),
                    deadline=time.monotonic() + 5,
                )
                assert isinstance(repeated, ProfileStatus)
                assert repeated.status.session_id == result.status.session_id
                assert not attempt.control.cancelled and len(proofs) == 1
            else:
                assert isinstance(result, AccessRefusal)
                assert result.code is AccessDenialCode.AUTHENTICATION_REQUIRED
                assert not attempt.control.committed
                assert attempt.connection.session_id is None
                if bound_sessions:
                    assert host.owner._worker is not None
                    assert bound_sessions[0] not in host.owner._worker.status().sessions
        finally:
            release.set()
            unsubscribe()


def test_named_first_login_selects_product_target_before_terminal_claim(tmp_path: Path) -> None:
    with service_record_runtime(tmp_path) as runtime:
        contender = connect(runtime.endpoint)
        runtime.clients.append(contender)
        client = FrontendClient(
            contender,
            profile_id=runtime.other_profile_id,
            frontend=OperationFrontendProjection.CLI,
        )
        admitted = client.login_password(bytearray(PROFILE_INPUT.encode()), persist_receipt=True)
        assert admitted.status.denial is None and admitted.status.profile_id == runtime.other_profile_id
        active = contender.active_profile(ActiveProfileRequest(request_id=uuid4()), deadline=time.monotonic() + 5)
        assert isinstance(active, ActiveProfileReply)
        assert active.selected_profile_id == runtime.other_profile_id
        assert active.signed_in_profile_id == runtime.other_profile_id


@contextmanager
def _legacy_kdf_permit(root: Path):
    """Hold the exact native byte lock used by an already running installation."""
    if sys.platform != "win32":
        pytest.fail("Windows legacy permit selected on another OS")
    import msvcrt

    descriptor = os.open(root / "profile-kdf.v1.lock", os.O_RDWR | os.O_CREAT | os.O_BINARY, 0o600)
    if os.fstat(descriptor).st_size == 0:
        os.write(descriptor, b"\0")
    os.lseek(descriptor, 0, os.SEEK_SET)
    msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
    try:
        yield
    finally:
        os.lseek(descriptor, 0, os.SEEK_SET)
        msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
        os.close(descriptor)


@pytest.mark.parametrize("ending", ["cancel", "disconnect"])
def test_cancelled_native_proof_settles_while_the_legacy_kdf_permit_is_still_held(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, ending: str
) -> None:
    with service_record_runtime(tmp_path) as runtime:
        contender = connect(runtime.endpoint)
        runtime.clients.append(contender)
        host = runtime.profiles._profiles[runtime.profile_id]
        worker = host.owner._worker
        assert worker is not None
        sent = Event()
        write_secret = profile_worker_transport.write_secret

        def sent_proof(channel, secret, *, deadline):
            write_secret(channel, secret, deadline=deadline)
            if channel is worker._channel:
                sent.set()

        monkeypatch.setattr(profile_worker_transport, "write_secret", sent_proof)
        request = ProfileLogin(
            request_id=uuid4(),
            profile_id=runtime.profile_id,
            method="password",
            frontend=OperationFrontendProjection.CLI,
            persist_receipt=False,
        )
        with _legacy_kdf_permit(runtime.root):
            with contender.held_exchange(request, request.request_id, deadline=time.monotonic() + 20) as exchange:
                assert isinstance(exchange.reply().root, SecretReady)
                original_secret = bytearray(PROFILE_INPUT.encode())
                contender.send_secret(original_secret, deadline=time.monotonic() + 10)
                pending = exchange.reply().root
                assert isinstance(pending, ProfileLoginPending)
            assert sent.wait(10), "the owned worker never received the original protected proof"
            attempt = runtime.profiles._pending_logins[pending.connection_id]
            if ending == "cancel":
                contender.login_status(
                    ProfileLoginStatusQuery(
                        action="profile_login_cancel",
                        request_id=uuid4(),
                        profile_id=runtime.profile_id,
                        login_request_id=request.request_id,
                    ),
                    deadline=time.monotonic() + 5,
                )
            else:
                contender.close()
            assert attempt.finished.wait(10), "cancelled proof waited for the legacy permit to be released"
            assert not attempt.control.committed
            assert attempt.connection.session_id is None
            assert original_secret == bytearray(len(original_secret))
            assert attempt.secret == bytearray(len(attempt.secret))
            assert host.owner._worker is worker and not worker.stopping
            assert runtime.person_session_id in worker.status().sessions
            replacement = connect(runtime.endpoint) if ending == "disconnect" else contender
            if replacement is not contender:
                runtime.clients.append(replacement)
            next_request = request.model_copy(update={"request_id": uuid4()})
            sent.clear()
            with replacement.held_exchange(
                next_request, next_request.request_id, deadline=time.monotonic() + 20
            ) as exchange:
                assert isinstance(exchange.reply().root, SecretReady)
                replacement.send_secret(bytearray(PROFILE_INPUT.encode()), deadline=time.monotonic() + 10)
                next_pending = exchange.reply().root
                assert isinstance(next_pending, ProfileLoginPending)
            assert sent.wait(10), "the completed cancellation retained the proof slot"
            next_attempt = runtime.profiles._pending_logins[next_pending.connection_id]
            # An old exact cancellation is acknowledged while the next proof
            # waits for the same legacy permit; it cannot cancel that proof.
            worker._proof_command("cancel", attempt.control.attempt_id, deadline=time.monotonic() + 5)
            assert not next_attempt.finished.is_set()
        assert next_attempt.finished.wait(20), "the next proof did not acquire the released legacy permit"
        admitted = replacement.login_status(
            ProfileLoginStatusQuery(
                action="profile_login_status",
                request_id=uuid4(),
                profile_id=runtime.profile_id,
                login_request_id=next_request.request_id,
            ),
            deadline=time.monotonic() + 5,
        )
        assert isinstance(admitted, ProfileStatus) and admitted.status.denial is None
        assert host.owner._worker is worker and not worker.stopping


def test_cancelling_a_queued_proof_preserves_the_current_owner_and_releases_its_secret(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with service_record_runtime(tmp_path) as runtime:
        owner = runtime.profiles._profiles[runtime.profile_id].owner
        worker = owner._worker
        assert worker is not None
        first, queued_client, following = (connect(runtime.endpoint) for _ in range(3))
        runtime.clients.extend((first, queued_client, following))
        entered, release, queued = Event(), Event(), Event()
        proof_calls = []
        authenticate, admission_slot = worker.authenticate_human, owner._human_queue.admit

        @contextmanager
        def paused(secret, **options):
            proof_calls.append(options["attempt_id"])
            with authenticate(secret, **options) as outcome:
                if len(proof_calls) == 1:
                    entered.set()
                    assert release.wait(20), "test did not release the healthy candidate owner"
                yield outcome

        @contextmanager
        def waiting(proof):
            if entered.is_set() and not release.is_set():
                queued.set()
            with admission_slot(proof):
                yield

        monkeypatch.setattr(worker, "authenticate_human", paused)
        monkeypatch.setattr(owner._human_queue, "admit", waiting)

        def begin(client):
            request = ProfileLogin(
                request_id=uuid4(),
                profile_id=runtime.profile_id,
                method="password",
                frontend=OperationFrontendProjection.CLI,
                persist_receipt=False,
            )
            with client.held_exchange(request, request.request_id, deadline=time.monotonic() + 20) as exchange:
                assert isinstance(exchange.reply().root, SecretReady)
                client.send_secret(bytearray(PROFILE_INPUT.encode()), deadline=time.monotonic() + 10)
                pending = exchange.reply().root
                assert isinstance(pending, ProfileLoginPending)
            return request, pending

        try:
            first_request, first_pending = begin(first)
            assert entered.wait(10), "the first proof did not retain its candidate"
            first_attempt = runtime.profiles._pending_logins[first_pending.connection_id]
            queued_request, queued_pending = begin(queued_client)
            assert queued.wait(5), "the second proof did not reach the occupied parent queue"
            queued_attempt = runtime.profiles._pending_logins[queued_pending.connection_id]
            queued_client.login_status(
                ProfileLoginStatusQuery(
                    action="profile_login_cancel",
                    request_id=uuid4(),
                    profile_id=runtime.profile_id,
                    login_request_id=queued_request.request_id,
                ),
                deadline=time.monotonic() + 5,
            )
            assert queued_attempt.finished.wait(5), "queued cancellation waited for the healthy proof owner"
            assert queued_attempt.secret == bytearray(len(queued_attempt.secret))
            assert not queued_attempt.control.committed
            assert proof_calls == [first_attempt.control.attempt_id]
            assert not first_attempt.finished.is_set() and not first_attempt.control.cancelled
            assert owner._prepared_human_worker is worker
            assert owner._human_connection == first_pending.connection_id
            assert not worker.stopping
            release.set()
            assert first_attempt.finished.wait(10)
            first_result = first.login_status(
                ProfileLoginStatusQuery(
                    action="profile_login_status",
                    request_id=uuid4(),
                    profile_id=runtime.profile_id,
                    login_request_id=first_request.request_id,
                ),
                deadline=time.monotonic() + 5,
            )
            assert isinstance(first_result, ProfileStatus) and first_result.status.denial is None
            third = FrontendClient(
                following, profile_id=runtime.profile_id, frontend=OperationFrontendProjection.CLI
            ).login_password(bytearray(PROFILE_INPUT.encode()), persist_receipt=False)
            assert third.status.denial is None
            assert len(proof_calls) == 2 and queued_attempt.control.attempt_id not in proof_calls
            assert owner._worker is worker and not worker.stopping
        finally:
            release.set()
