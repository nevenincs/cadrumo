"""Installed CLI automation listing reads only current native human inventory."""

from __future__ import annotations

import asyncio
import json
import sys
from importlib.metadata import version
from pathlib import Path
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
from cadrumo.adapters.persistence.storage.custody.tests.native_enrollment_recipient import NativeEnrollmentRecipient
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.application.operations.frontend_requests import OPERATION_OBSERVATION_PROJECTION_ID
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.automation_enrollment import EnrollmentStage
from cadrumo.application.user_profile.automation_operations import AUTOMATION_INVENTORY_OPERATION_DEFINITION_ID
from cadrumo.core.config import override_settings
from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.contracts.access_vocabulary import (
    AccessAction,
    DisclosureCategory,
    DisclosurePermission,
)
from cadrumo_client.transport.automation_inventory import read_automation_inventory
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError
from cadrumo_client.transport.installation import installation
from cadrumo_client.transport.installed_client import open_installed_client
from cadrumo_client.transport.windows import WindowsEndpoint
from cadrumo_runtime.adapters.tests.profile_worker_support import owner_id
from cadrumo_runtime.commands.tests.config.runtime_cli import invoke_runtime_cli

from ..served_runtime import SyntheticLogin, serving_runtime

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires real native Windows profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]


def _scope_for_inventory(subject: AdministrationSubject, destination_id: UUID) -> None:
    """Narrow the enrolled scope to the inventory operation and its two disclosures."""
    scope = changed(
        subject.proposal.scope,
        operations=frozenset({AUTOMATION_INVENTORY_OPERATION_DEFINITION_ID}),
        actions=frozenset(AccessAction),
        disclosures=frozenset(
            {
                DisclosurePermission(
                    destination_id=destination_id,
                    projection_id=OPERATION_OBSERVATION_PROJECTION_ID,
                    category=DisclosureCategory.OPERATION_METADATA,
                ),
                DisclosurePermission(
                    destination_id=destination_id,
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


def _assert_inventory_projection(
    listed: Result,
    *,
    approved_request: UUID,
    pending_request: UUID,
    approved_grant_id: UUID,
    approved_key_id: UUID,
    review_digest: str,
    credential: bytes,
) -> None:
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
    assert inventory["grants"][0]["grant_id"] == str(approved_grant_id)
    assert inventory["grants"][0]["state"] == "active"
    assert inventory["keys"][0]["key_id"] == str(approved_key_id)
    assert inventory["keys"][0]["state"] == "active"
    reviews = {item["receipt"]["request_id"]: item for item in inventory["requests"]}
    assert set(reviews) == {str(approved_request), str(pending_request)}
    assert reviews[str(approved_request)]["receipt"]["stage"] == "complete"
    assert reviews[str(pending_request)]["receipt"]["stage"] == "requested"
    assert reviews[str(pending_request)]["receipt"]["review_digest"] == review_digest
    assert PROFILE_INPUT not in listed.output
    assert credential.decode("utf-8") not in listed.output
    assert "verifier" not in listed.output and "dek" not in listed.output


def _assert_api_key_denied_inventory(profile_id: UUID, credential: bytes) -> None:
    api = asyncio.run(open_installed_client(profile_id=profile_id, frontend=OperationFrontendProjection.CLI))
    try:
        proof = bytearray(credential)
        api.login_api_key(proof, timeout=25)
        assert not any(proof)
        with pytest.raises(FrontendRefusedError) as denied:
            read_automation_inventory(api)
        assert denied.value.reason == AccessDenialCode.HUMAN_AUTHORITY_REQUIRED.value
    finally:
        api.close()


def test_installed_automation_list_projects_nonempty_exact_profile_and_denies_api_key(tmp_path: Path) -> None:
    """One human command returns the settled grant, key and pending review."""
    root = tmp_path / "cadrumo-storage"
    root.mkdir()
    endpoint = WindowsEndpoint(storage_root=root)
    installation_record = installation(
        storage_root=root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity
    )
    with administration_subject(
        tmp_path, os_owner_id=owner_id(), installation_id=installation_record.installation_id
    ) as subject:
        requester = changed(subject.owner.requesting, destination_id=subject.owner.requesting.client_id)
        subject.owner.requesting = requester
        subject.owner.delivery.endpoint = NativeEnrollmentRecipient(
            requester=requester, secrets_store=subject.client_native
        )
        _scope_for_inventory(subject, requester.client_id)

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

        with (
            serving_runtime(
                endpoint,
                root,
                capture_login=lambda _channel: SyntheticLogin("cli-automation-list-native-login"),
                secret_store=lambda: subject.native,
                workers=1,
                product_version=version("cadrumo"),
            ),
            override_settings(cadrumo_storage_root=root, cadrumo_output_language="en"),
        ):
            listed = invoke_runtime_cli(
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
            _assert_inventory_projection(
                listed,
                approved_request=approved_request,
                pending_request=pending_request,
                approved_grant_id=approved.grant_id,
                approved_key_id=approved.key_id,
                review_digest=pending.review_digest,
                credential=credential.get_secret_value(),
            )
            _assert_api_key_denied_inventory(profile_id, credential.get_secret_value())
