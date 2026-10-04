"""Installed CLI own-grant changes reconcile under fresh native key authority."""

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

from cadrumo.adapters.local_runtime import runtime_credentials
from cadrumo.adapters.local_runtime.automation_decision import run_automation_decision
from cadrumo.adapters.local_runtime.automation_inventory import read_automation_inventory
from cadrumo.adapters.local_runtime.framing import VerifiedRuntimeConnection
from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.adapters.local_runtime.installation import runtime_installation
from cadrumo.adapters.local_runtime.tests.profile_worker_support import owner_id
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.adapters.persistence.storage.custody.acceleration_receipt import delete_profile_session
from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import (
    PROFILE_INPUT,
    administration_subject,
    changed,
)
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.contracts import RuntimeClientHello
from cadrumo.application.user_profile.access_contracts import (
    AccessAction,
    Availability,
    LoginEligibility,
    OsLockState,
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
    pytest.mark.skipif(sys.platform != "win32", reason="requires real native Windows profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]


class _LoginObservation:
    login_id = "cli-automation-change-native-login"

    def observe(self, *, credential_facilities: Availability) -> OsLoginContext:
        return OsLoginContext(
            login_id=self.login_id,
            os_owner_id=owner_id(),
            active=True,
            lock_state=OsLockState.UNLOCKED,
            unattended=LoginEligibility.ELIGIBLE,
            credential_facilities=credential_facilities,
        )


@pytest.mark.parametrize("kind", [EnrollmentKind.ROTATE, EnrollmentKind.RENEW, EnrollmentKind.CHANGE_SCOPE])
def test_installed_change_reconciles_without_forwarding_human_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: EnrollmentKind
) -> None:
    """The old requester lease retires; the CLI proves a key on a new connection."""
    root = tmp_path / "cadrumo-storage"
    root.mkdir()
    endpoint = WindowsRuntimeEndpoint(storage_root=root)
    installation = runtime_installation(
        storage_root=root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity
    )
    with administration_subject(
        tmp_path, os_owner_id=owner_id(), installation_id=installation.installation_id
    ) as subject:
        initial_request_id = uuid4()
        subject.service.request(initial_request_id, subject.proposal)
        approved_initial = subject.approve(initial_request_id)
        assert approved_initial.key_id is not None
        initial_record = next(
            item for item in subject.store.enrollment_state().requests if item.request_id == initial_request_id
        )
        metadata = subject.owner.delivery.endpoint.possession(initial_record)
        assert metadata is not None
        initial_grant = subject.store.snapshot().grants[0]
        initial_reference = initial_record.credential_reference
        assert initial_reference is not None
        profile_id = initial_grant.binding.profile_id
        close_active_bucket_session()
        delete_profile_session(storage_root=root, profile_id=profile_id)
        monkeypatch.setattr(runtime_credentials, "installed_automation_secret_store", lambda: subject.client_native)
        monkeypatch.setattr(
            runtime_automation_request, "installed_automation_secret_store", lambda: subject.client_native
        )
        stop, boot = Event(), uuid4()
        profiles = RuntimeProfileConnections(
            storage_root=root,
            storage_identity=endpoint.storage_identity,
            runtime_boot_id=boot,
            stop=stop,
            capture_login=lambda _channel: _LoginObservation(),
            secret_store=lambda: subject.native,
        )
        profiles.prepare_registry()
        server = RetainedRuntimeTransportServer(
            endpoint, product_version=version("cadrumo"), stop=stop, profiles=profiles, boot_id=boot
        )
        proposal = EnrollmentProposal(
            kind=kind,
            scope=changed(initial_grant.scope, actions=frozenset({AccessAction.SUBMIT}))
            if kind is EnrollmentKind.CHANGE_SCOPE
            else initial_grant.scope,
            expires_at=initial_grant.expires_at + timedelta(days=30)
            if kind is EnrollmentKind.RENEW
            else initial_grant.expires_at,
            key_expires_at=now() + timedelta(days=15) if kind is EnrollmentKind.ROTATE else None,
            unattended=initial_grant.unattended,
            allow_os_lock=initial_grant.allow_os_lock,
            target_grant_id=initial_grant.grant_id,
            target_key_id=approved_initial.key_id if kind is EnrollmentKind.ROTATE else None,
        )
        with ThreadPoolExecutor(max_workers=2) as pool:
            running = pool.submit(server.serve)
            try:
                assert server.ready.wait(3)

                def invoke_change() -> Result:
                    with override_settings(cadrumo_local_storage_root=root, cadrumo_output_language="en"):
                        return invoke_cached_cli(
                            (
                                "--format",
                                "json",
                                "--profile",
                                str(profile_id),
                                "--profile-auth-method",
                                "api-key",
                                "--profile-credential-ref",
                                str(initial_reference),
                                "config",
                                "profile",
                                "automation",
                                "change",
                                kind.value,
                                "--secrets-stdin",
                            ),
                            input=json.dumps({"proposal": proposal.model_dump(mode="json")}),
                        )

                changing = pool.submit(copy_context().run, invoke_change)
                deadline = time.monotonic() + 30
                while len(subject.store.enrollment_state().requests) < 2 and time.monotonic() < deadline:
                    if changing.done():
                        early = changing.result()
                        pytest.fail(f"grant-change command exited before review: {early!r}")
                    time.sleep(0.05)
                assert len(subject.store.enrollment_state().requests) == 2
                assert not changing.done()
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
                    reviews = read_automation_inventory(human).projection.requests
                    review = next(item for item in reviews if item.receipt.stage is EnrollmentStage.REQUESTED)
                    proof = bytearray(PROFILE_INPUT.encode())
                    approved = run_automation_decision(human, review, decision="approve", password=proof)
                    assert approved.receipt.stage is EnrollmentStage.COMPLETE
                    assert not any(proof)
                finally:
                    human.close()
                outcome = cast(Result, changing.result(timeout=75))
                assert outcome.exit_code == 0, outcome.output
                envelope = json.loads(outcome.stdout)
                assert envelope["command"] == "config.profile.automation.change"
                result = envelope["result"]
                assert result["kind"] == kind.value
                assert result["submitted"]["stage"] == "requested"
                assert result["terminal"]["stage"] == "complete"
                assert result["terminal"]["request_id"] == str(review.receipt.request_id)
                assert result["terminal"]["review_digest"] == approved.receipt.review_digest
                assert result["profile_id"] == "<profile-id>"
                if kind is EnrollmentKind.ROTATE:
                    assert result["credential_reference"] == result["terminal"]["credential_reference"]
                    assert result["credential_reference"] != str(initial_reference)
                else:
                    assert result["credential_reference"] is None
                    assert result["terminal"]["key_id"] is None
                assert PROFILE_INPUT not in outcome.output
                assert '"proposal"' not in outcome.stdout
                current = subject.store.snapshot().grants[0]
                assert current.scope == proposal.scope
                assert current.expires_at == proposal.expires_at
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
