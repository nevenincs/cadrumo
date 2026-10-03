"""Installed CLI automation listing reads only current native human inventory."""

from __future__ import annotations

import asyncio
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from importlib.metadata import version
from pathlib import Path
from threading import Event
from uuid import uuid4

import pytest

from cadrumo.adapters.local_runtime.automation_inventory import read_automation_inventory
from cadrumo.adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from cadrumo.adapters.local_runtime.installation import runtime_installation
from cadrumo.adapters.local_runtime.runtime_client import open_installed_runtime_client
from cadrumo.adapters.local_runtime.server import RuntimeTransportServer
from cadrumo.adapters.local_runtime.tests.profile_worker_support import owner_id
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.adapters.persistence.storage.custody.acceleration_receipt import delete_profile_session
from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import (
    PROFILE_INPUT,
    administration_subject,
    changed,
)
from cadrumo.adapters.persistence.storage.custody.tests.native_enrollment_recipient import NativeEnrollmentRecipient
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.application.operations.frontend_requests import OPERATION_OBSERVATION_PROJECTION_ID
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    Availability,
    DisclosureCategory,
    DisclosurePermission,
    LoginEligibility,
    OsLoginContext,
)
from cadrumo.application.user_profile.automation_enrollment import EnrollmentStage
from cadrumo.application.user_profile.automation_operations import AUTOMATION_INVENTORY_OPERATION_DEFINITION_ID
from cadrumo.core.config import override_settings
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
    login_id = "cli-automation-list-native-login"

    def observe(self, *, credential_facilities: Availability) -> OsLoginContext:
        return OsLoginContext(
            login_id=self.login_id,
            os_owner_id=owner_id(),
            active=True,
            locked=False,
            unattended=LoginEligibility.ELIGIBLE,
            credential_facilities=credential_facilities,
        )


def test_installed_automation_list_projects_nonempty_exact_profile_and_denies_api_key(tmp_path: Path) -> None:
    """One human command returns the settled grant, key and pending review."""
    root = tmp_path / "cadrumo-storage"
    root.mkdir()
    endpoint = WindowsRuntimeEndpoint(storage_root=root)
    installation = runtime_installation(
        storage_root=root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity
    )
    with administration_subject(
        tmp_path, os_owner_id=owner_id(), installation_id=installation.installation_id
    ) as subject:
        requester = changed(subject.owner.requesting, destination_id=subject.owner.requesting.client_id)
        subject.owner.requesting = requester
        subject.owner.delivery.endpoint = NativeEnrollmentRecipient(
            requester=requester, secrets_store=subject.client_native
        )
        scope = changed(
            subject.proposal.scope,
            operations=frozenset({AUTOMATION_INVENTORY_OPERATION_DEFINITION_ID}),
            actions=frozenset(AccessAction),
            disclosures=frozenset(
                {
                    DisclosurePermission(
                        destination_id=requester.client_id,
                        projection_id=OPERATION_OBSERVATION_PROJECTION_ID,
                        category=DisclosureCategory.OPERATION_METADATA,
                    ),
                    DisclosurePermission(
                        destination_id=requester.client_id,
                        projection_id=AUTOMATION_INVENTORY_OPERATION_DEFINITION_ID + ".result",
                        category=DisclosureCategory.PROFILE_VALUES,
                    ),
                }
            ),
        )
        facts = subject.owner.current
        assert facts.session is not None
        subject.owner.current = changed(
            facts, profile=changed(facts.profile, scope=scope), session=changed(facts.session, scope=scope)
        )
        subject.proposal = changed(subject.proposal, scope=scope)

        approved_request = uuid4()
        subject.service.request(approved_request, subject.proposal)
        approved = subject.approve(approved_request)
        approved_record = next(
            item for item in subject.store.enrollment_state().requests if item.request_id == approved_request
        )
        credential = subject.owner.delivery.endpoint.possession(approved_record)
        assert approved.key_id is not None and credential is not None
        pending_request = uuid4()
        pending = subject.service.request(pending_request, subject.proposal).receipt
        assert pending.stage is EnrollmentStage.REQUESTED
        profile_id = subject.store.binding.profile_id
        close_active_bucket_session()
        delete_profile_session(storage_root=root, profile_id=profile_id)

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
        server = RuntimeTransportServer(
            endpoint, product_version=version("cadrumo"), stop=stop, profiles=profiles, boot_id=boot
        )
        with ThreadPoolExecutor(max_workers=1) as pool:
            running = pool.submit(server.serve)
            try:
                assert server.ready.wait(3)
                with override_settings(cadrumo_local_storage_root=root, cadrumo_output_language="en"):
                    listed = invoke_cached_cli(
                        (
                            "--format",
                            "json",
                            "--profile",
                            str(profile_id),
                            "--profile-secrets-stdin",
                            "config",
                            "profile",
                            "automation",
                            "list",
                        ),
                        input=json.dumps({"profile_passphrase": PROFILE_INPUT}),
                    )
                    assert listed.exit_code == 0, listed.output
                    document = json.loads(listed.stdout)
                    assert document["status"] == "warning"
                    assert [notice["code"] for notice in document["notices"]] == ["config.login.session_not_persisted"]
                    assert document["command"] == "config.profile.automation.list"
                    result = document["result"]
                    assert result["profile_id"] == "<profile-id>"
                    assert len(result["operation_id"]) == 64
                    assert all(character in "0123456789abcdef" for character in result["operation_id"])
                    inventory = result["inventory"]
                    assert len(inventory["grants"]) == len(inventory["keys"]) == 1
                    assert inventory["grants"][0]["grant_id"] == str(approved.grant_id)
                    assert inventory["grants"][0]["state"] == "active"
                    assert inventory["keys"][0]["key_id"] == str(approved.key_id)
                    assert inventory["keys"][0]["state"] == "active"
                    reviews = {item["receipt"]["request_id"]: item for item in inventory["requests"]}
                    assert set(reviews) == {str(approved_request), str(pending_request)}
                    assert reviews[str(approved_request)]["receipt"]["stage"] == "complete"
                    assert reviews[str(pending_request)]["receipt"]["stage"] == "requested"
                    assert reviews[str(pending_request)]["receipt"]["review_digest"] == pending.review_digest
                    assert PROFILE_INPUT not in listed.output
                    assert credential.get_secret_value().decode("utf-8") not in listed.output
                    assert "verifier" not in listed.output and "dek" not in listed.output

                    api = asyncio.run(
                        open_installed_runtime_client(profile_id=profile_id, frontend=OperationFrontendProjection.CLI)
                    )
                    try:
                        proof = bytearray(credential.get_secret_value())
                        api.login_api_key(proof, timeout=25)
                        assert not any(proof)
                        with pytest.raises(RuntimeFrontendRefusedError) as denied:
                            read_automation_inventory(api)
                        assert denied.value.reason == AccessDenialCode.HUMAN_AUTHORITY_REQUIRED.value
                    finally:
                        api.close()
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
