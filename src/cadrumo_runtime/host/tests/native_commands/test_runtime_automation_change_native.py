"""Installed CLI own-grant changes reconcile under fresh native key authority."""

from __future__ import annotations

import json
import sys
import time
from concurrent.futures import Future, ThreadPoolExecutor
from contextvars import copy_context
from datetime import timedelta
from importlib.metadata import version
from pathlib import Path
from threading import Event
from uuid import UUID, uuid4

import pytest
from click.testing import Result

from cadrumo.adapters.persistence.storage.custody.acceleration_receipt import delete_profile_session
from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import (
    PROFILE_INPUT,
    AdministrationSubject,
    administration_subject,
    changed,
)
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.application.user_profile.access_contracts import AutomationGrant
from cadrumo.application.user_profile.automation_enrollment import EnrollmentStage
from cadrumo.core.config import override_settings
from cadrumo.core.operations import OperationFrontendProjection
from cadrumo.core.time.clock import now
from cadrumo_client.contracts.access_vocabulary import AccessAction
from cadrumo_client.contracts.contracts import ClientHello
from cadrumo_client.contracts.enrollment_proposal import EnrollmentKind, EnrollmentProposal
from cadrumo_client.transport import credentials
from cadrumo_client.transport.automation_decision import run_automation_decision
from cadrumo_client.transport.automation_inventory import read_automation_inventory
from cadrumo_client.transport.framing import VerifiedConnection
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.installation import installation
from cadrumo_client.transport.windows import WindowsEndpoint
from cadrumo_runtime.adapters.tests.profile_worker_support import owner_id
from cadrumo_runtime.adapters.tests.retained_server import RetainedRuntimeTransportServer
from cadrumo_runtime.commands import runtime_automation_request
from cadrumo_runtime.commands.tests.config.runtime_cli import invoke_runtime_cli
from cadrumo_runtime.host.profile_connections import RuntimeProfileConnections

from ..served_runtime import SyntheticLogin

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires real native Windows profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]


def _change_proposal(kind: EnrollmentKind, grant: AutomationGrant, initial_key_id: UUID) -> EnrollmentProposal:
    return EnrollmentProposal(
        kind=kind,
        scope=changed(grant.scope, actions=frozenset({AccessAction.SUBMIT}))
        if kind is EnrollmentKind.CHANGE_SCOPE
        else grant.scope,
        expires_at=grant.expires_at + timedelta(days=30) if kind is EnrollmentKind.RENEW else grant.expires_at,
        key_expires_at=now() + timedelta(days=15) if kind is EnrollmentKind.ROTATE else None,
        unattended=grant.unattended,
        allow_os_lock=grant.allow_os_lock,
        target_grant_id=grant.grant_id,
        target_key_id=initial_key_id if kind is EnrollmentKind.ROTATE else None,
    )


def _invoke_change(
    root: Path, profile_id: UUID, kind: EnrollmentKind, reference: UUID, proposal: EnrollmentProposal
) -> Result:
    with override_settings(cadrumo_storage_root=root, cadrumo_output_language="en"):
        return invoke_runtime_cli(
            (
                "--format",
                "json",
                "--profile",
                str(profile_id),
                "--profile-auth-method",
                "api-key",
                "--profile-credential-ref",
                str(reference),
                "config",
                "profile",
                "automation",
                "change",
                kind.value,
                "--secrets-stdin",
            ),
            input=json.dumps({"proposal": proposal.model_dump(mode="json")}),
        )


def _wait_for_pending_review(subject: AdministrationSubject, changing: Future[Result]) -> None:
    """The change command submits its request and then waits for a separate human."""
    deadline = time.monotonic() + 30
    while len(subject.store.enrollment_state().requests) < 2 and time.monotonic() < deadline:
        if changing.done():
            early = changing.result()
            pytest.fail(
                f"grant-change command exited before review: {early!r}; "
                f"output={early.output!r}; exception={early.exception!r}"
            )
        time.sleep(0.05)
    assert len(subject.store.enrollment_state().requests) == 2
    assert not changing.done()


def _approve_pending_review(endpoint: WindowsEndpoint, profile_id: UUID) -> tuple[UUID, str]:
    """A person signs in with the password and approves the requested change on a fresh connection."""
    raw = VerifiedConnection(
        endpoint.connect(timeout=3),
        expected=ClientHello(product_version=version("cadrumo"), storage_identity=endpoint.storage_identity),
        deadline=time.monotonic() + 3,
    )
    human = FrontendClient(raw, profile_id=profile_id, frontend=OperationFrontendProjection.CLI)
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
    return review.receipt.request_id, approved.receipt.review_digest


def _assert_change_outcome(
    outcome: Result,
    kind: EnrollmentKind,
    request_id: UUID,
    review_digest: str,
    initial_reference: UUID,
) -> None:
    assert outcome.exit_code == 0, outcome.output
    envelope = json.loads(outcome.stdout)
    assert envelope["command"] == "config.profile.automation.change"
    result = envelope["result"]
    assert result["kind"] == kind.value
    assert result["submitted"]["stage"] == "requested"
    assert result["terminal"]["stage"] == "complete"
    assert result["terminal"]["request_id"] == str(request_id), result["terminal"]
    assert result["terminal"]["review_digest"] == review_digest
    assert result["profile_id"] == "<profile-id>"
    if kind is EnrollmentKind.ROTATE:
        assert result["credential_reference"] == result["terminal"]["credential_reference"]
        assert result["credential_reference"] != str(initial_reference)
    else:
        assert result["credential_reference"] is None
        assert result["terminal"]["key_id"] is None
    assert PROFILE_INPUT not in outcome.output
    assert '"proposal"' not in outcome.stdout


@pytest.mark.parametrize("kind", [EnrollmentKind.ROTATE, EnrollmentKind.RENEW, EnrollmentKind.CHANGE_SCOPE])
def test_installed_change_reconciles_without_forwarding_human_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: EnrollmentKind
) -> None:
    """The old requester lease retires; the CLI proves a key on a new connection."""
    root = tmp_path / "cadrumo-storage"
    root.mkdir()
    endpoint = WindowsEndpoint(storage_root=root)
    installation_record = installation(
        storage_root=root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity
    )
    with administration_subject(
        tmp_path, os_owner_id=owner_id(), installation_id=installation_record.installation_id
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
        monkeypatch.setattr(credentials, "installed_automation_secret_store", lambda: subject.client_native)
        monkeypatch.setattr(
            runtime_automation_request, "installed_automation_secret_store", lambda: subject.client_native
        )
        stop, boot = Event(), uuid4()
        profiles = RuntimeProfileConnections(
            storage_root=root,
            storage_identity=endpoint.storage_identity,
            runtime_boot_id=boot,
            stop=stop,
            capture_login=lambda _channel: SyntheticLogin("cli-automation-change-native-login"),
            secret_store=lambda: subject.native,
        )
        profiles.prepare_registry()
        server = RetainedRuntimeTransportServer(
            endpoint, product_version=version("cadrumo"), stop=stop, profiles=profiles, boot_id=boot
        )
        proposal = _change_proposal(kind, initial_grant, approved_initial.key_id)
        with ThreadPoolExecutor(max_workers=2) as pool:
            running = pool.submit(server.serve)
            try:
                assert server.ready.wait(3)
                invocation_context = copy_context()
                changing = pool.submit(
                    lambda: invocation_context.run(_invoke_change, root, profile_id, kind, initial_reference, proposal)
                )
                _wait_for_pending_review(subject, changing)
                request_id, review_digest = _approve_pending_review(endpoint, profile_id)
                outcome = changing.result(timeout=75)
                _assert_change_outcome(outcome, kind, request_id, review_digest, initial_reference)
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
