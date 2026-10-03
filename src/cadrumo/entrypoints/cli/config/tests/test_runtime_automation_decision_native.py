"""Installed CLI review decisions use native authority and protected delivery."""

from __future__ import annotations

import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from datetime import timedelta
from importlib.metadata import version
from pathlib import Path
from threading import Event
from uuid import UUID, uuid4

import pytest
from click.testing import Result

from cadrumo.adapters.local_runtime.enrollment_client import NativeEnrollmentClient
from cadrumo.adapters.local_runtime.framing import VerifiedRuntimeConnection
from cadrumo.adapters.local_runtime.installation import runtime_installation
from cadrumo.adapters.local_runtime.server import RuntimeTransportServer
from cadrumo.adapters.local_runtime.tests.profile_worker_support import PROFILE_INPUT, owner_id, worker_profiles
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.adapters.persistence.storage.custody.acceleration_receipt import delete_profile_session
from cadrumo.adapters.persistence.storage.custody.automation_native_identity import CLIENT_NAMESPACE
from cadrumo.adapters.persistence.storage.custody.automation_profile import current_automation_profile_binding
from cadrumo.adapters.persistence.storage.custody.automation_store import AutomationControlStore
from cadrumo.adapters.persistence.storage.custody.tests.automation_support import MemoryNativePort
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.contracts import RuntimeClientHello
from cadrumo.application.runtime.enrollment_access import RuntimeEnrollmentPrepare, RuntimeEnrollmentPrepared
from cadrumo.application.user_profile.access_contracts import (
    AccessAction,
    AccessScope,
    Availability,
    LoginEligibility,
    OsLoginContext,
)
from cadrumo.application.user_profile.automation_enrollment import EnrollmentKind, EnrollmentProposal, EnrollmentStage
from cadrumo.core.config import override_settings
from cadrumo.core.time.clock import now
from cadrumo.entrypoints.cli.tests.cli_runner import invoke_cached_cli
from cadrumo.entrypoints.runtime.profile_connections import RuntimeProfileConnections

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires real native Windows profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]


class _LoginObservation:
    login_id = "cli-automation-decision-native-login"

    def observe(self, *, credential_facilities: Availability) -> OsLoginContext:
        return OsLoginContext(
            login_id=self.login_id,
            os_owner_id=owner_id(),
            active=True,
            locked=False,
            unattended=LoginEligibility.ELIGIBLE,
            credential_facilities=credential_facilities,
        )


def _requester(
    endpoint: WindowsRuntimeEndpoint, profile_id: UUID, native_store: MemoryNativePort
) -> tuple[VerifiedRuntimeConnection, NativeEnrollmentClient]:
    connection = VerifiedRuntimeConnection(
        endpoint.connect(timeout=3),
        expected=RuntimeClientHello(product_version=version("cadrumo"), storage_identity=endpoint.storage_identity),
        deadline=time.monotonic() + 3,
    )
    prepared = connection.enrollment_prepare(
        RuntimeEnrollmentPrepare(request_id=uuid4(), profile_id=profile_id, frontend=OperationFrontendProjection.MCP),
        deadline=time.monotonic() + 5,
    )
    assert isinstance(prepared, RuntimeEnrollmentPrepared)
    return connection, NativeEnrollmentClient(connection=connection, prepared=prepared, secrets_store=native_store)


def _proposal() -> EnrollmentProposal:
    return EnrollmentProposal(
        kind=EnrollmentKind.ENROLL,
        scope=AccessScope(
            operations=frozenset({"user-profile.field-mutation"}),
            actions=frozenset({AccessAction.SUBMIT, AccessAction.START, AccessAction.COMMIT}),
            disclosures=frozenset(),
            periods=None,
            allow_period_independent=True,
            allow_delegation=False,
        ),
        expires_at=now() + timedelta(days=30),
        key_expires_at=now() + timedelta(days=15),
        unattended=True,
        allow_os_lock=False,
    )


def _cli(profile_id: UUID, *leaf: str, password: str = PROFILE_INPUT) -> Result:
    return invoke_cached_cli(
        (
            "--format",
            "json",
            "--profile",
            str(profile_id),
            "--profile-secrets-stdin",
            "config",
            "profile",
            "automation",
            *leaf,
        ),
        input=json.dumps({"profile_passphrase": password}),
    )


def _leaf_pipe(password: str) -> tuple[int, bytes]:
    payload = json.dumps({"passphrase": password}).encode("utf-8")
    reader, writer = os.pipe()
    try:
        os.write(writer, payload)
    finally:
        os.close(writer)
    return reader, payload


def test_installed_cli_inspect_approve_and_decline_preserve_two_proof_channels(tmp_path: Path) -> None:
    """A reviewed human decision updates custody while requester keeps its key."""
    with worker_profiles(tmp_path) as (root, targets):
        profile_id = targets[-1][0].binding.profile_id
        delete_profile_session(storage_root=root, profile_id=profile_id)
        endpoint = WindowsRuntimeEndpoint(storage_root=root)
        installation = runtime_installation(
            storage_root=root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity
        )
        binding = current_automation_profile_binding(
            profile_id=profile_id,
            installation_id=installation.installation_id,
            os_owner_id=installation.os_owner_id,
            root=root,
        )
        server_native, client_native = MemoryNativePort(), MemoryNativePort()
        store = AutomationControlStore(root=root, binding=binding, secrets_store=server_native)
        stop, boot = Event(), uuid4()
        profiles = RuntimeProfileConnections(
            storage_root=root,
            storage_identity=endpoint.storage_identity,
            runtime_boot_id=boot,
            stop=stop,
            capture_login=lambda _channel: _LoginObservation(),
            secret_store=lambda: server_native,
        )
        profiles.prepare_registry()
        server = RuntimeTransportServer(
            endpoint, product_version=version("cadrumo"), stop=stop, profiles=profiles, boot_id=boot
        )
        with ThreadPoolExecutor(max_workers=3) as pool:
            running = pool.submit(server.serve)
            try:
                assert server.ready.wait(3)
                requester, enrollment = _requester(endpoint, profile_id, client_native)
                try:
                    pending = enrollment.submit(_proposal())
                    assert pending.stage is EnrollmentStage.REQUESTED
                    with override_settings(cadrumo_local_storage_root=root, cadrumo_output_language="en"):
                        inspected = _cli(profile_id, "inspect", str(pending.request_id))
                        assert inspected.exit_code == 0, inspected.output
                        review = json.loads(inspected.stdout)["result"]["review"]
                        assert review["receipt"]["request_id"] == str(pending.request_id)
                        assert review["receipt"]["review_digest"] == pending.review_digest
                        assert review["receipt"]["stage"] == "requested"
                        assert json.loads(inspected.stdout)["command"] == "config.profile.automation.inspect"

                        stale_fd, stale_payload = _leaf_pipe("fresh-proof-must-remain-unread")
                        try:
                            stale = _cli(
                                profile_id,
                                "approve",
                                str(pending.request_id),
                                "--review-digest",
                                "0" * 64,
                                "--secrets-fd",
                                str(stale_fd),
                            )
                            assert stale.exit_code != 0
                            assert os.read(stale_fd, len(stale_payload) + 1) == stale_payload
                        finally:
                            with suppress(OSError):
                                os.close(stale_fd)
                        current = enrollment.inspect()
                        assert current is not None and current.stage is EnrollmentStage.REQUESTED
                        assert store.snapshot().grants == ()

                        wrong_fd, _ = _leaf_pipe("wrong-fresh-approval-proof")
                        wrong = _cli(
                            profile_id,
                            "approve",
                            str(pending.request_id),
                            "--review-digest",
                            pending.review_digest,
                            "--secrets-fd",
                            str(wrong_fd),
                        )
                        assert wrong.exit_code != 0
                        current = enrollment.inspect()
                        assert current is not None and current.stage is EnrollmentStage.REQUESTED
                        assert store.snapshot().grants == ()

                        done = Event()

                        def poll_requester() -> None:
                            deadline = time.monotonic() + 75
                            while not done.is_set() and time.monotonic() < deadline:
                                enrollment.poll(timeout=10)

                        polling = pool.submit(poll_requester)
                        try:
                            approval_fd, _ = _leaf_pipe(PROFILE_INPUT)
                            approved = _cli(
                                profile_id,
                                "approve",
                                str(pending.request_id),
                                "--review-digest",
                                pending.review_digest,
                                "--secrets-fd",
                                str(approval_fd),
                            )
                        finally:
                            done.set()
                            polling.result(timeout=15)
                        assert approved.exit_code == 0, approved.output
                        approved_result = json.loads(approved.stdout)
                        assert approved_result["command"] == "config.profile.automation.approve"
                        assert approved_result["result"]["decision"] == "approve"
                        assert approved_result["result"]["effect"] == "updated"
                        assert len(approved_result["result"]["operation_id"]) == 64
                        receipt = approved_result["result"]["receipt"]
                        assert receipt["request_id"] == str(pending.request_id)
                        assert receipt["review_digest"] == pending.review_digest
                        assert receipt["stage"] == "complete"
                        current = enrollment.inspect()
                        assert current is not None and current.stage is EnrollmentStage.COMPLETE
                        assert receipt["credential_reference"] is not None
                        assert (CLIENT_NAMESPACE, receipt["credential_reference"]) in client_native.items
                        assert (CLIENT_NAMESPACE, receipt["credential_reference"]) not in server_native.items
                        assert PROFILE_INPUT not in approved.output
                        assert "wrong-fresh-approval-proof" not in wrong.output
                        assert "fresh-proof-must-remain-unread" not in stale.output

                        second_requester, second_enrollment = _requester(endpoint, profile_id, MemoryNativePort())
                        try:
                            second = second_enrollment.submit(_proposal())
                            declined = _cli(
                                profile_id,
                                "decline",
                                str(second.request_id),
                                "--review-digest",
                                second.review_digest,
                            )
                            assert declined.exit_code == 0, declined.output
                            declined_result = json.loads(declined.stdout)
                            assert declined_result["command"] == "config.profile.automation.decline"
                            assert declined_result["result"]["decision"] == "decline"
                            assert declined_result["result"]["effect"] == "updated"
                            assert declined_result["result"]["receipt"]["stage"] == "declined"
                            current = second_enrollment.inspect()
                            assert current is not None and current.stage is EnrollmentStage.DECLINED
                            assert len(store.snapshot().grants) == 1
                            assert PROFILE_INPUT not in declined.output
                        finally:
                            second_requester.close()
                finally:
                    requester.close()
            finally:
                primary = sys.exception()
                stop.set()
                try:
                    try:
                        running.result(timeout=20)
                    except Exception:
                        if primary is None:
                            raise
                finally:
                    endpoint.close()
