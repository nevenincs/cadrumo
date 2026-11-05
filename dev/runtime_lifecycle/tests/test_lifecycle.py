"""Real admitted manager/runtime lifecycle, without Tauri or GUI automation."""

from __future__ import annotations

import secrets
import statistics
import time
from collections.abc import Mapping, Sequence
from uuid import uuid4

import pytest

from cadrumo.application.operations.frontend_requests import (
    OperationPublicPhaseEventV1,
)
from cadrumo.application.user_profile.profile_pointer import observe_active_profile_pointer
from cadrumo.core.operations import OperationLifecycle, OperationTerminalCondition
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.contracts.profile_access import AccessRefusal, ProfileLogin
from cadrumo_client.contracts.sign_in import SignInPresence
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError
from cadrumo_client.transport.receipt_proof import borrow_receipt_proof

from ..client_probes import (
    execute_read,
    observe_read,
    private_request,
    read,
    refused,
    submit_read,
)
from ..harness import LifecycleHarness

pytestmark = [
    pytest.mark.integration,
    pytest.mark.native_package,
    pytest.mark.hex_entrypoint,
    pytest.mark.serial,
    pytest.mark.windows_only,
    pytest.mark.os_keychain,
    pytest.mark.external_tool,
]


def _ready_replacement_pid(events: Sequence[Mapping[str, object]], retired_pid: int) -> int | None:
    """Wait for the latest launched replacement's facts before authenticating its pipe."""
    launched = [event["pid"] for event in events if event["kind"] == "launched" and event["pid"] != retired_pid]
    if not launched:
        return None
    replacement = launched[-1]
    assert isinstance(replacement, int) and not isinstance(replacement, bool) and replacement > 0
    observed = {(event["kind"], event["pid"]) for event in events}
    required = {("exited", retired_pid), ("ready", replacement), ("boot_confirmed", replacement)}
    return replacement if required <= observed else None


def test_login_logout_profile_switch_and_stale_receipt(harness: LifecycleHarness) -> None:
    first = harness.create_profile("Lifecycle A")
    second = harness.create_profile("Lifecycle B")
    assert first.profile_id != second.profile_id
    a = harness.connect(first.profile_id)
    assert a.client.sign_in_status().status.presence is SignInPresence.ABSENT
    started = time.monotonic()
    admitted = a.client.login_password(bytearray(first.password, "utf-8"), persist_receipt=True)
    harness.metrics["password_login_seconds"] = time.monotonic() - started
    assert admitted.status.credential_authenticated and admitted.status.profile_bound
    session_id = a.client.session_id
    read(a)
    assert admitted.human_login is not None and admitted.human_login.session_persisted
    observer = harness.connect(first.profile_id)
    assert observer.client.sign_in_status().status.presence is SignInPresence.PRESENT
    refused(private_request(observer, session_id))
    refused(private_request(a, session_id, profile_id=second.profile_id))
    with borrow_receipt_proof(profile_id=first.profile_id) as proof:
        stale_proof = bytearray(proof)
    try:
        resumed = harness.connect(first.profile_id)
        resumed.client.resume_receipt()
        resumed_id = resumed.client.session_id
        read(resumed)
        # Profile switching uses the shipped CLI's real password login protocol.
        harness.cli("login", "Lifecycle B", "--secrets-stdin", secret={"passphrase": second.password})
        assert observe_active_profile_pointer(harness.root).bucket_id == str(second.profile_id)
        b = harness.connect(second.profile_id)
        b.client.resume_receipt()
        read(b)
        # One profile is signed in at a time: the person's sign-in to B signed A out everywhere,
        # its own session, the session resumed from its stored sign-in, and that stored sign-in.
        assert a.client.profile_id == first.profile_id
        refused(private_request(a, session_id))
        refused(private_request(resumed, resumed_id))
        assert observer.client.sign_in_status().status.presence is SignInPresence.ABSENT
        forged = harness.connect(first.profile_id)
        refusal = forged.wire.login(
            ProfileLogin(
                request_id=uuid4(),
                profile_id=first.profile_id,
                method="receipt",
                frontend=forged.client.frontend,
            ),
            stale_proof,
            deadline=time.monotonic() + 75,
        )
        assert isinstance(refusal, AccessRefusal)
        assert refusal.code.value in {"authentication_required", "credential_rejected", "custody_changed"}
        read(b)
        b_session = b.client.session_id
        started = time.monotonic()
        logout = b.client.human_sign_out()
        harness.metrics["logout_seconds"] = time.monotonic() - started
        assert logout.receipt_removed and logout.keychain_removed
        refused(private_request(b, b_session))
        harness.cli("login", "Lifecycle A", "--secrets-stdin", secret={"passphrase": first.password})
        assert observe_active_profile_pointer(harness.root).bucket_id == str(first.profile_id)
        renewed = harness.connect(first.profile_id)
        renewed.client.resume_receipt()
        read(renewed)
        renewed.client.human_sign_out()
    finally:
        stale_proof[:] = bytes(len(stale_proof))


def test_exact_runtime_crash_manager_recovery_and_operation_state(harness: LifecycleHarness) -> None:
    profile = harness.create_profile("Lifecycle recovery")
    connection = harness.connect(profile.profile_id)
    admitted = connection.client.login_password(bytearray(profile.password, "utf-8"), persist_receipt=True)
    read(connection)
    assert admitted.human_login is not None and admitted.human_login.session_persisted
    operation_id = execute_read(connection)
    pending_id = submit_read(connection, diagnostics=True)
    assert observe_read(connection, pending_id, "diagnostics.read").projection.lifecycle is OperationLifecycle.CREATED
    request_samples = []
    for _ in range(12):
        started = time.monotonic()
        assert connection.client.status().status.credential_authenticated
        request_samples.append(time.monotonic() - started)
    harness.metrics["request_median_seconds"] = statistics.median(request_samples)
    harness.metrics["request_max_seconds"] = max(request_samples)
    for cycle in range(2):
        old_session = connection.client.session_id
        old_boot = connection.wire.hello.boot_id
        event_cursor = len(harness.events())
        started = time.monotonic()
        terminated = harness.terminate_runtime(connection)
        while not any(
            event["kind"] == "exited" and event["pid"] == terminated.pid for event in harness.events()[event_cursor:]
        ):
            assert time.monotonic() - started < 15, "Manager did not detect the exact terminated runtime"
            time.sleep(0.02)
        harness.metrics[f"failure_detection_{cycle}_seconds"] = time.monotonic() - started
        with pytest.raises(RefusalError) as stale:
            private_request(connection, old_session)
        assert stale.value.reason in {
            RefusalCode.CONNECTION_CLOSED,
            RefusalCode.UNAVAILABLE,
            RefusalCode.TIMEOUT,
            RefusalCode.PEER_UNTRUSTED,
        }
        recovered = harness.connect(profile.profile_id, after_boot=old_boot)
        harness.metrics[f"reconnect_{cycle}_seconds"] = time.monotonic() - started
        assert recovered.wire.hello.boot_id != old_boot
        refused(private_request(recovered, old_session))
        # Valid persisted proof remains usable after a boot; the old session never does.
        recovered.client.resume_receipt()
        assert recovered.client.session_id != old_session
        read(recovered)
        retained = observe_read(recovered, operation_id).projection
        assert retained.lifecycle is OperationLifecycle.TERMINAL
        assert retained.terminal_condition is OperationTerminalCondition.SUCCEEDED
        pending = observe_read(recovered, pending_id, "diagnostics.read").projection
        if cycle == 0:
            assert pending.lifecycle is OperationLifecycle.CREATED
            continuation_started = time.monotonic()
            assert execute_read(recovered, pending_id) == pending_id
            harness.metrics["pending_operation_recovery_seconds"] = time.monotonic() - continuation_started
        else:
            assert pending.lifecycle is OperationLifecycle.TERMINAL
            assert pending.terminal_condition is OperationTerminalCondition.SUCCEEDED
        history = observe_read(recovered, pending_id, "diagnostics.read").event_page
        assert history.next_cursor == history.anchor_cursor
        assert (
            sum(
                isinstance(event, OperationPublicPhaseEventV1) and event.phase_code == "diagnostics.read.execute"
                for event in history.events
            )
            == 1
        )
        execute_read(recovered)
        events = harness.events()[event_cursor:]
        exited = [event for event in events if event["kind"] == "exited" and event["pid"] == terminated.pid]
        launched = [
            event
            for event in events
            if event["kind"] == "launched" and event["pid"] == recovered.native.peer.process_id
        ]
        assert exited and launched
        assert launched[-1]["seconds"] >= exited[-1]["seconds"]
        connection = recovered
    connection.client.human_sign_out()


def test_wrong_password_never_admits_private_work(harness: LifecycleHarness) -> None:
    profile = harness.create_profile("Lifecycle wrong password")
    rejected = harness.connect(profile.profile_id)
    with pytest.raises(FrontendRefusedError) as refusal:
        rejected.client.login_password(bytearray(secrets.token_urlsafe(32), "utf-8"))
    assert refusal.value.reason == "credential_rejected"
    assert rejected.client.sign_in_status().status.presence is SignInPresence.ABSENT
    refused(private_request(rejected, uuid4()))


def test_manager_death_preserves_custody_and_successor_restores_verified_supervision(harness: LifecycleHarness) -> None:
    profile = harness.create_profile("Lifecycle manager recovery")
    live = harness.connect(profile.profile_id)
    live.client.login_password(bytearray(profile.password, "utf-8"), persist_receipt=True)
    boot, pid = live.wire.hello.boot_id, live.native.peer.process_id
    assert pid is not None
    stale_session = live.client.session_id
    read(live)
    harness.terminate_manager()
    read(live)
    assert harness.cli("profile", "view", profile_secret=profile.password)["result"]["display_name"] == (
        "Lifecycle manager recovery"
    )
    harness.start_manager()
    deadline = time.monotonic() + 90
    while not any(event["kind"] == "adopted" and event["pid"] == pid for event in harness.events()):
        assert time.monotonic() < deadline, "Successor did not adopt the verified survivor"
        time.sleep(0.05)
    # Adoption retains exact native custody, then drains the survivor because
    # its old manager's heartbeat channel cannot be recovered.
    # Authenticating the survivor's pipe while it exits can correctly refuse an
    # unverifiable peer. Await the replacement's native facts before connecting.
    while (replacement_pid := _ready_replacement_pid(harness.events(), pid)) is None:
        assert time.monotonic() < deadline, "Replacement lacked verified readiness and restored control"
        time.sleep(0.05)
    recovered = harness.connect(profile.profile_id, after_boot=boot)
    assert recovered.native.peer.process_id == replacement_pid
    assert recovered.native.peer.process_id != pid
    with pytest.raises(RefusalError) as stale:
        private_request(live, stale_session)
    assert stale.value.reason in {
        RefusalCode.CONNECTION_CLOSED,
        RefusalCode.UNAVAILABLE,
        RefusalCode.TIMEOUT,
        RefusalCode.PEER_UNTRUSTED,
    }
    refused(private_request(recovered, uuid4()))
    recovered.client.resume_receipt()
    read(recovered)
    assert any(
        event["kind"] == "launched" and event["pid"] == recovered.native.peer.process_id for event in harness.events()
    )
    recovered.client.human_sign_out()
