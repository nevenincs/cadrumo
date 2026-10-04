"""Installed CLI first enrollment retains the real protected requester connection."""

from __future__ import annotations

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from datetime import timedelta
from importlib.metadata import version
from pathlib import Path
from threading import Event
from typing import cast
from uuid import uuid4

import pytest
from click.testing import Result

from cadrumo.adapters.local_runtime.automation_decision import run_automation_decision
from cadrumo.adapters.local_runtime.automation_inventory import read_automation_inventory
from cadrumo.adapters.local_runtime.framing import VerifiedRuntimeConnection
from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.adapters.local_runtime.installation import runtime_installation
from cadrumo.adapters.local_runtime.tests.profile_worker_support import PROFILE_INPUT, owner_id, worker_profiles
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.adapters.persistence.storage.custody.acceleration_receipt import delete_profile_session
from cadrumo.adapters.persistence.storage.custody.automation_native_identity import CLIENT_NAMESPACE
from cadrumo.adapters.persistence.storage.custody.automation_profile import current_automation_profile_binding
from cadrumo.adapters.persistence.storage.custody.automation_store import AutomationControlStore
from cadrumo.adapters.persistence.storage.custody.tests.automation_support import MemoryNativePort
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.contracts import RuntimeClientHello
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
from cadrumo.entrypoints.cli.config import runtime_automation_request
from cadrumo.entrypoints.cli.tests.cli_runner import invoke_cached_cli
from cadrumo.entrypoints.runtime.profile_connections import RuntimeProfileConnections

from .....adapters.local_runtime.tests.retained_server import RetainedRuntimeTransportServer

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]


class _LoginObservation:
    login_id = "cli-automation-create-native-login"

    def observe(self, *, credential_facilities: Availability) -> OsLoginContext:
        return OsLoginContext(
            login_id=self.login_id,
            os_owner_id=owner_id(),
            active=True,
            locked=False,
            unattended=LoginEligibility.ELIGIBLE,
            credential_facilities=credential_facilities,
        )


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


def test_installed_create_waits_for_separate_human_decision_and_protects_candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The CLI holds its verified native offer while another human approves."""
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
        monkeypatch.setattr(runtime_automation_request, "installed_automation_secret_store", lambda: client_native)
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
        server = RetainedRuntimeTransportServer(
            endpoint, product_version=version("cadrumo"), stop=stop, profiles=profiles, boot_id=boot
        )
        with ThreadPoolExecutor(max_workers=2) as pool:
            running = pool.submit(server.serve)
            try:
                assert server.ready.wait(3)
                proposal = _proposal()

                def invoke_create() -> Result:
                    with override_settings(cadrumo_local_storage_root=root, cadrumo_output_language="en"):
                        return invoke_cached_cli(
                            (
                                "--format",
                                "json",
                                "--profile",
                                str(profile_id),
                                "config",
                                "profile",
                                "automation",
                                "create",
                                "--secrets-stdin",
                            ),
                            input=json.dumps({"proposal": proposal.model_dump(mode="json")}),
                        )

                invocation = copy_context()
                creating = pool.submit(invocation.run, invoke_create)
                deadline = time.monotonic() + 20
                while not store.enrollment_state().requests and time.monotonic() < deadline:
                    if creating.done():
                        early = creating.result()
                        pytest.fail(f"requester exited before a review existed: {early!r}")
                    time.sleep(0.05)
                assert store.enrollment_state().requests
                assert not creating.done()
                raw = VerifiedRuntimeConnection(
                    endpoint.connect(timeout=3),
                    expected=RuntimeClientHello(
                        product_version=version("cadrumo"), storage_identity=endpoint.storage_identity
                    ),
                    deadline=time.monotonic() + 3,
                )
                human = RuntimeFrontendClient(raw, profile_id=profile_id, frontend=OperationFrontendProjection.CLI)
                try:
                    human.login_password(bytearray(PROFILE_INPUT.encode()), timeout=25)
                    review = read_automation_inventory(human).projection.requests[0]
                    assert review.receipt.stage is EnrollmentStage.REQUESTED
                    proof = bytearray(PROFILE_INPUT.encode())
                    approved = run_automation_decision(human, review, decision="approve", password=proof)
                    assert approved.receipt.stage is EnrollmentStage.COMPLETE
                    assert not any(proof)
                finally:
                    human.close()
                created = cast(Result, creating.result(timeout=45))
                assert created.exit_code == 0, created.output
                envelope = json.loads(created.stdout)
                assert envelope["command"] == "config.profile.automation.create"
                result = envelope["result"]
                assert result["profile_id"] == "<profile-id>"
                assert result["submitted"]["stage"] == "requested"
                assert result["terminal"]["stage"] == "complete"
                assert result["terminal"]["request_id"] == str(review.receipt.request_id)
                assert result["terminal"]["review_digest"] == review.receipt.review_digest
                assert result["credential_reference"] == result["terminal"]["credential_reference"]
                assert (CLIENT_NAMESPACE, result["credential_reference"]) in client_native.items
                assert (CLIENT_NAMESPACE, result["credential_reference"]) not in server_native.items
                assert PROFILE_INPUT not in created.output
                assert '"proposal"' not in created.stdout
            finally:
                primary = sys.exception()
                stop.set()
                try:
                    running.result(timeout=20)
                except Exception:
                    if primary is None:
                        raise
                finally:
                    endpoint.close()
