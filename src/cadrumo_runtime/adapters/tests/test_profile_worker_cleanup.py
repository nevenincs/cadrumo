"""Worker transfer and shutdown over explicit native acquisition/release fault ports.

Actual construction, framing, peer binding and retry ownership execute. Native
process acquisition is an isolated fault seam, not platform acceptance evidence.
"""

from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from cadrumo.application.user_profile.proof_cancellation import ProfileProofCancellation
from cadrumo.core.async_cleanup import AsyncResourceCleanupError
from cadrumo_client.contracts.automation_codes import AutomationCustodyCode, AutomationCustodyError
from cadrumo_client.contracts.contracts import Peer, RefusalCode, RefusalError
from cadrumo_client.contracts.deadline_budget import OrchestrationTimeoutError, TimeoutDeadline
from cadrumo_client.transport.frame_io import document_frame, read_document
from cadrumo_runtime.contracts.profile_worker import (
    ProfileWorkerControlRequest,
    ProfileWorkerProofTransfer,
    ProfileWorkerReady,
    ProfileWorkerRefusal,
    ProfileWorkerRequest,
    ProfileWorkerStatus,
)

from .. import profile_worker, profile_worker_human_admission, profile_worker_lifetime, profile_worker_transport
from .profile_worker_cleanup_support import Channel, Fixture, control_reply, retained_cleanup_error

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


@pytest.mark.parametrize("script_mode", [False, True])
def test_successful_construction_transfers_worker_after_both_listeners_retire(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, script_mode: bool
) -> None:

    fixture = Fixture(monkeypatch, tmp_path)

    script = tmp_path / "worker.py"

    script.write_text("# synthetic trusted host entrypoint\n", encoding="ascii")

    selected = script if script_mode else None

    worker = fixture.open(worker_script=selected)

    try:
        prefix = (
            ("-I", "-B", str(script.resolve(strict=True)))
            if script_mode
            else ("-I", "-B", "-m", "cadrumo_runtime.host.worker")
        )

        assert fixture.scope.launch_arguments == (
            *prefix,
            "--storage-root",
            str(tmp_path),
            "--worker-id",
            str(fixture.identity.worker_id),
            "--parent-pid",
            str(os.getpid()),
            "--expected-version",
            "worker-test",
        )

        assert fixture.scope.launch_directory == tmp_path

        environment = fixture.scope.launch_environment

        assert environment is not None

        assert environment["CADRUMO_STORAGE_ROOT"] == str(tmp_path)

        assert environment["PYDANTIC_DISABLE_PLUGINS"] == "__all__"

        assert environment["TEMP"] == environment["TMP"] == environment["TMPDIR"]

        assert Path(environment["TEMP"]).is_absolute()

        assert worker.identity == fixture.identity

        assert fixture.native_process.opened == fixture.native_process.closed == 3

        assert [channel.peer_checks for channel in fixture.channels] == [1, 1, 1]

        assert fixture.scope.membership_checks == 3

        assert all(endpoint.release.released for endpoint in fixture.endpoints)

        assert fixture.scope.launched and not fixture.scope.release.released

        assert all(not channel.release.released for channel in fixture.channels)

    finally:
        worker.close()

    assert fixture.scope.release.released

    assert all(channel.release.released for channel in fixture.channels)


@pytest.mark.parametrize("channel_index", [0, 1, 2], ids=["control", "operation", "proof"])
@pytest.mark.parametrize("failure", ["owner", "process", "incarnation", "membership"])
def test_native_peer_refusal_contains_unreturned_worker_and_releases_query_handles(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, channel_index: int, failure: str
) -> None:

    fixture = Fixture(monkeypatch, tmp_path)

    channel = fixture.channels[channel_index]

    if failure == "owner":
        channel.native_peer = Peer(os_owner_id="foreign-owner", process_id=1234)

    elif failure == "process":
        channel.native_peer = Peer(os_owner_id="synthetic-owner", process_id=9876)

    elif failure == "incarnation":
        channel.incarnation_matches = False

    else:
        fixture.endpoints[channel_index].before_accept = lambda: setattr(fixture.scope, "native_member", False)

    with pytest.raises(RefusalError) as caught:
        fixture.open()

    assert caught.value.reason is RefusalCode.PEER_UNTRUSTED

    assert fixture.native_process.opened == fixture.native_process.closed

    assert fixture.native_process.opened == channel_index + int(failure in {"incarnation", "membership"})

    assert fixture.scope.release.released

    assert all(endpoint.release.released for endpoint in fixture.endpoints)

    assert all(accepted.release.released for accepted in fixture.channels[: channel_index + 1])


@pytest.mark.parametrize("failed_listener", [0, 1, 2])
@pytest.mark.parametrize("persistent_listener", [False, True])
@pytest.mark.parametrize("failed_channel", [False, True])
def test_failed_listener_transfer_contains_unreturned_worker_and_retains_release_owners(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    failed_listener: int,
    persistent_listener: bool,
    failed_channel: bool,
) -> None:

    fixture = Fixture(monkeypatch, tmp_path)

    listener = fixture.endpoints[failed_listener].release

    listener.failures = 2 if persistent_listener else 1

    fixture.channels[0].release.failures = int(failed_channel)

    with pytest.raises(RefusalError) as caught:
        fixture.open()

    assert caught.value.reason is RefusalCode.UNAVAILABLE

    assert isinstance(caught.value.__cause__, AsyncResourceCleanupError)

    assert fixture.scope.release.released and fixture.authorization.release.released

    assert all(endpoint.release.calls == 1 for endpoint in fixture.endpoints)

    assert all(channel.release.calls == 1 for channel in fixture.channels)

    cleanup = retained_cleanup_error(caught.value)

    if persistent_listener:
        with pytest.raises(AsyncResourceCleanupError) as retry_failed:
            asyncio.run(cleanup.retry_cleanup())

        cleanup = retry_failed.value

        assert not listener.released

        assert all(channel.release.released for channel in fixture.channels)

    asyncio.run(cleanup.retry_cleanup())

    asyncio.run(cleanup.retry_cleanup())

    assert all(endpoint.release.released for endpoint in fixture.endpoints)

    assert all(channel.release.released for channel in fixture.channels)

    assert listener.calls == listener.failures + 1

    assert all(
        endpoint.release.calls == 1 for index, endpoint in enumerate(fixture.endpoints) if index != failed_listener
    )

    assert fixture.channels[0].release.calls == int(failed_channel) + 1

    assert fixture.channels[1].release.calls == 1


@pytest.mark.parametrize("cancellation", [False, True])
def test_failed_launch_preserves_exact_primary_and_retries_all_failed_listeners(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, cancellation: bool
) -> None:

    fixture = Fixture(monkeypatch, tmp_path)

    primary = (
        asyncio.CancelledError("synthetic interrupted launch") if cancellation else OSError("synthetic listen refusal")
    )

    fixture.endpoints[1].listen_failure = primary

    for endpoint in fixture.endpoints:
        endpoint.release.failures = 1

    fixture.scope.release.failures = 1

    with pytest.raises(type(primary)) as caught:
        fixture.open()

    assert caught.value is primary

    assert not fixture.scope.launched

    assert fixture.scope.release.calls == 1

    assert all(endpoint.release.calls == 1 for endpoint in fixture.endpoints)

    asyncio.run(retained_cleanup_error(primary).retry_cleanup())

    assert fixture.scope.release.released

    assert all(endpoint.release.released for endpoint in fixture.endpoints)


def test_shutdown_attempts_containment_and_both_channels_after_other_releases_fail(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:

    fixture = Fixture(monkeypatch, tmp_path)

    worker = fixture.open()

    fixture.authorization.release.failures = 1

    fixture.scope.release.failures = 1

    fixture.channels[0].release.failures = 1

    with pytest.raises(ExceptionGroup) as caught:
        worker.close()

    assert caught.value.exceptions == (
        fixture.authorization.release.failure,
        fixture.scope.release.failure,
        fixture.channels[0].release.failure,
    )

    assert fixture.scope.release.calls == 1

    assert fixture.channels[1].release.released

    assert worker._channel is fixture.channels[0] and worker._operation_channel is None

    worker.close()

    assert worker._channel is worker._operation_channel is None

    assert fixture.scope.release.released and fixture.authorization.release.released

    assert fixture.channels[0].release.calls == 2 and fixture.channels[1].release.calls == 1


def test_protocol_failure_preserves_primary_and_retains_failed_worker_containment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:

    fixture = Fixture(monkeypatch, tmp_path)

    worker = fixture.open()

    primary = OSError("synthetic interrupted reply")

    fixture.channels[0].read_failure = primary

    fixture.scope.release.failures = 1

    with pytest.raises(OSError) as caught:
        worker.status()

    assert caught.value is primary

    assert fixture.scope.release.calls == 1

    assert all(channel.release.released for channel in fixture.channels)

    asyncio.run(retained_cleanup_error(primary).retry_cleanup())

    assert fixture.scope.release.released

    assert fixture.channels[1].release.calls == 1


def test_protocol_cleanup_retry_gets_fresh_bound_after_original_request_deadline(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:

    fixture = Fixture(monkeypatch, tmp_path)

    worker = fixture.open()

    primary = OSError("synthetic interrupted reply")

    fixture.channels[0].read_failure = primary

    fixture.scope.refuse_zero_timeout = True

    clock = SimpleNamespace(instant=time.monotonic())

    def finish_request_budget() -> None:

        clock.instant += 6

    fixture.channels[0].before_read = finish_request_budget

    for owner in (profile_worker_lifetime, profile_worker_transport, profile_worker_human_admission):
        monkeypatch.setattr(owner, "time", SimpleNamespace(monotonic=lambda: clock.instant))

    with pytest.raises(OSError) as caught:
        worker._exchange(
            ProfileWorkerRequest(ProfileWorkerControlRequest(action="status", request_id=uuid4())),
            ProfileWorkerStatus,
            deadline=clock.instant + 5,
        )

    assert caught.value is primary

    assert fixture.scope.timeouts == [0]

    assert not fixture.scope.release.released

    asyncio.run(retained_cleanup_error(primary).retry_cleanup())

    assert fixture.scope.timeouts == [0, 2]

    assert fixture.scope.release.released


def test_post_accept_child_death_keeps_failed_temporary_channel_on_unreturned_candidate(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:

    fixture = Fixture(monkeypatch, tmp_path)

    channel = fixture.channels[0]

    channel.release.failures = 1

    def exit_on_accept() -> None:

        fixture.scope.child.exited = True

    fixture.endpoints[0].before_accept = exit_on_accept

    with pytest.raises(RefusalError) as caught:
        fixture.open()

    assert caught.value.reason is RefusalCode.CONNECTION_CLOSED

    candidate = profile_worker.unreturned_profile_worker(caught.value)

    assert candidate is not None and candidate._channel is None

    assert channel.release.calls == 1 and not channel.release.released

    assert fixture.scope.release.released

    # The parent keeps this candidate after projecting only the refusal code;

    # settlement must work without needing the original exception attachment.

    candidate.close()

    assert channel.release.calls == 2 and channel.release.released

    candidate.close()

    assert channel.release.calls == 2


def test_worker_ready_from_another_incarnation_never_completes_construction(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:

    fixture = Fixture(monkeypatch, tmp_path)

    channel = fixture.channels[0]

    valid = document_frame(ProfileWorkerReady(identity=fixture.identity))

    foreign = ProfileWorkerReady(identity=fixture.identity.model_copy(update={"worker_id": uuid4()}))

    assert channel.inbound.endswith(valid)

    channel.inbound[-len(valid) :] = document_frame(foreign)

    with pytest.raises(RefusalError) as refused:
        fixture.open()

    assert refused.value.reason is RefusalCode.PEER_UNTRUSTED

    assert fixture.scope.release.released

    assert all(endpoint.release.released for endpoint in fixture.endpoints)


def test_worker_timeout_contains_original_owner_without_readiness(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:

    fixture = Fixture(monkeypatch, tmp_path)

    monkeypatch.setattr(
        profile_worker,
        "DEFAULT_TIMEOUT_POLICY",
        SimpleNamespace(
            deadline=lambda: TimeoutDeadline(time.monotonic() - 1),
        ),
    )

    with pytest.raises(OrchestrationTimeoutError):
        fixture.open()

    assert fixture.scope.launched and fixture.scope.release.released

    assert all(endpoint.release.released for endpoint in fixture.endpoints)


@pytest.mark.parametrize("stage", ["before_header", "after_header"])
def test_cancelled_owned_proof_never_sends_its_secret_and_keeps_the_stream_aligned(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, stage: str
) -> None:

    fixture = Fixture(monkeypatch, tmp_path)

    worker = fixture.open()

    channel = fixture.channels[0]

    channel.writes.clear()

    token, secret = ProfileProofCancellation(), bytearray(b"original-protected-proof")

    native_write = channel.write_all

    actions: list[str] = []

    def write(payload, *, deadline):

        native_write(payload, deadline=deadline)

        if stage == "after_header":
            try:
                request = ProfileWorkerRequest.model_validate_json(payload[5:]).root

            except ValidationError:
                return

            if isinstance(request, ProfileWorkerControlRequest) and request.action == "password":
                token.cancel()

    def respond() -> None:

        if channel.inbound:
            return

        reader = Channel(fixture.identity)

        reader.inbound = bytearray(b"".join(channel.writes))

        channel.writes.clear()

        request = read_document(reader, ProfileWorkerRequest, deadline=time.monotonic() + 5).root

        assert isinstance(request, ProfileWorkerControlRequest)

        actions.append(request.action)

        if request.action == "password":
            transfer = read_document(reader, ProfileWorkerProofTransfer, deadline=time.monotonic() + 5)

            assert transfer.proof_attempt_id == request.proof_attempt_id and transfer.cancelled

            assert not reader.inbound, "an abandoned proof sent a protected secret frame"

            control_reply(
                channel,
                ProfileWorkerRefusal(
                    identity=fixture.identity,
                    request_id=request.request_id,
                    reason=AutomationCustodyCode.REQUESTER_DISCONNECTED,
                ),
            )

        else:
            assert request.action == "cancel_human" and not reader.inbound

            control_reply(
                channel, ProfileWorkerStatus(identity=fixture.identity, request_id=request.request_id, sessions=())
            )

    monkeypatch.setattr(channel, "write_all", write)

    channel.before_read = respond

    if stage == "before_header":
        token.cancel()

    try:
        with pytest.raises(AutomationCustodyError) as refused, worker.authenticate_human(secret, cancellation=token):
            pytest.fail("a cancelled proof produced a human outcome")

        assert refused.value.reason is AutomationCustodyCode.REQUESTER_DISCONNECTED

        assert actions == (["cancel_human"] if stage == "before_header" else ["password", "cancel_human"])

        assert secret == bytearray(len(secret))

        assert not worker.stopping

        assert all(not owned.release.released for owned in fixture.channels)

    finally:
        worker.close()

        worker._settle_proof_dispatcher(deadline=time.monotonic() + 5)


def test_foreign_proof_acknowledgement_contains_the_exact_worker(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:

    fixture = Fixture(monkeypatch, tmp_path)

    worker = fixture.open()

    fixture.channels[2].identity = fixture.identity.model_copy(update={"worker_id": uuid4()})

    try:
        with pytest.raises(RefusalError) as refused:
            worker._proof_command("register", uuid4(), deadline=time.monotonic() + 5)

        assert refused.value.reason is RefusalCode.PEER_UNTRUSTED

        assert fixture.scope.release.released

        assert all(channel.release.released for channel in fixture.channels)

    finally:
        worker.close()

        worker._settle_proof_dispatcher(deadline=time.monotonic() + 5)
