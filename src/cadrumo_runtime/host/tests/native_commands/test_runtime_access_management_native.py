"""Installed CLI lifecycle verbs use the canonical native profile runtime."""

from __future__ import annotations

import asyncio
import json
import sys
from importlib.metadata import version
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
from click.testing import Result

from cadrumo.adapters.persistence.storage.custody.acceleration_receipt import delete_profile_session
from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import (
    PROFILE_INPUT,
    AdministrationSubject,
    administration_subject,
)
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.core.config import override_settings
from cadrumo_client.contracts.access_vocabulary import AuthorityState
from cadrumo_client.transport.frontend_client import FrontendClient
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
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]


def _human(root: Path, profile_id: UUID, *command: str) -> Result:
    """Supply a fresh explicit password, independent of any acceleration receipt."""
    delete_profile_session(storage_root=root, profile_id=profile_id)
    return invoke_runtime_cli(
        ("--format", "json", "--profile", str(profile_id), "--profile-secrets-stdin", *command),
        input=json.dumps({"profile_passphrase": PROFILE_INPUT}),
    )


def _resume(profile_id: UUID, password: str, *, grant_id: UUID) -> Result:
    return invoke_runtime_cli(
        (
            "--format",
            "json",
            "--profile",
            str(profile_id),
            "config",
            "profile",
            "resume",
            "--grant",
            str(grant_id),
            "--secrets-stdin",
        ),
        input=json.dumps({"passphrase": password}),
    )


def _successful(result: Result, command: str) -> dict[str, Any]:
    assert result.exit_code == 0, result.output
    document = json.loads(result.stdout)
    assert document["command"] == command and document["status"] in {"success", "warning"}
    assert isinstance(document["result"], dict)
    return document["result"]


def _api(profile_id: UUID, secret: bytes) -> FrontendClient:
    client = asyncio.run(open_installed_client(profile_id=profile_id, frontend=OperationFrontendProjection.CLI))
    try:
        client.login_api_key(bytearray(secret), timeout=25)
    except BaseException:
        client.close()
        raise
    return client


def _fenced(client: FrontendClient) -> None:
    try:
        status = client.status()
    except FrontendRefusedError:
        return
    assert status.status.denial is not None


def _issue_two_keys(subject: AdministrationSubject) -> list[tuple[UUID, UUID, bytes]]:
    """Enrol two grants, each with its own delivered key."""
    issued: list[tuple[UUID, UUID, bytes]] = []
    for _ in range(2):
        request_id = uuid4()
        subject.service.request(request_id, subject.proposal)
        receipt = subject.approve(request_id)
        record = next(item for item in subject.store.enrollment_state().requests if item.request_id == request_id)
        key = subject.owner.delivery.endpoint.possession(record)
        assert receipt.key_id is not None and key is not None
        issued.append((receipt.grant_id, receipt.key_id, key.get_secret_value()))
    return issued


def _assert_selected_and_global_lock(
    subject: AdministrationSubject, root: Path, profile_id: UUID, api: FrontendClient
) -> UUID:
    """A selected-session lock fences one key session; the global lock suspends every grant."""
    api_session_id = api.session_id
    inventory = _successful(_human(root, profile_id, "config", "profile", "sessions"), "config.profile.sessions")
    assert any(item["session_id"] == str(api_session_id) for item in inventory["sessions"]), inventory

    selected = _successful(
        _human(root, profile_id, "config", "profile", "lock", "--session", str(api_session_id)),
        "config.profile.lock",
    )
    assert selected["scope"] == "selected"
    assert selected["target_session_id"] == str(api_session_id)
    assert str(api_session_id) in selected["session_ids"]
    _fenced(api)

    current = _successful(_human(root, profile_id, "config", "profile", "lock"), "config.profile.lock")
    assert current["scope"] == "current" and current["session_ids"]

    global_lock = _successful(
        _human(root, profile_id, "config", "profile", "lock", "--all"),
        "config.profile.lock",
    )
    assert global_lock["scope"] == "profile"
    assert global_lock["denial"]["access_denied"] is True
    assert subject.store.profile_lock_state().globally_locked
    assert {item.state for item in subject.store.snapshot().grants} == {AuthorityState.SUSPENDED}
    return api_session_id


def _assert_resume_reactivates_only_the_selected_grant(
    subject: AdministrationSubject,
    profile_id: UUID,
    api: FrontendClient,
    opened: list[FrontendClient],
    *,
    selected_grant: UUID,
    held_grant: UUID,
    selected_secret: bytes,
    held_secret: bytes,
    api_session_id: UUID,
) -> Result:
    wrong = _resume(profile_id, "wrong-synthetic-password", grant_id=selected_grant)
    assert wrong.exit_code == 2
    assert subject.store.profile_lock_state().globally_locked

    resumed = _successful(_resume(profile_id, PROFILE_INPUT, grant_id=selected_grant), "config.profile.resume")
    assert resumed["receipt"]["reactivated_grants"] == [str(selected_grant)]
    assert not subject.store.profile_lock_state().globally_locked
    grants = {item.grant_id: item for item in subject.store.snapshot().grants}
    assert grants[selected_grant].state is AuthorityState.ACTIVE
    assert grants[held_grant].state is AuthorityState.SUSPENDED
    _fenced(api)

    fresh = _api(profile_id, selected_secret)
    opened.append(fresh)
    assert fresh.session_id != api_session_id
    with pytest.raises(FrontendRefusedError):
        _api(profile_id, held_secret)
    return wrong


def _assert_key_denial_revokes_only_that_key(
    subject: AdministrationSubject,
    root: Path,
    profile_id: UUID,
    fresh: FrontendClient,
    *,
    selected_key: UUID,
    held_key: UUID,
) -> None:
    denied = _successful(
        _human(root, profile_id, "config", "profile", "automation", "deny", "key", str(selected_key)),
        "config.profile.automation.deny",
    )
    assert denied["kind"] == "key" and denied["target_id"] == "<profile-id>"
    assert denied["receipt"]["access_denied"] is True
    assert {item.key_id: item.state for item in subject.store.snapshot().keys}[selected_key] is AuthorityState.REVOKED
    assert {item.key_id: item.state for item in subject.store.snapshot().keys}[held_key] is AuthorityState.SUSPENDED
    _fenced(fresh)


def test_cli_session_lock_global_resume_and_key_denial_use_native_authority(tmp_path: Path) -> None:
    root = tmp_path / "cadrumo-storage"
    root.mkdir()
    endpoint = WindowsEndpoint(storage_root=root)
    installation_record = installation(
        storage_root=root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity
    )
    with administration_subject(
        tmp_path, os_owner_id=owner_id(), installation_id=installation_record.installation_id
    ) as subject:
        issued = _issue_two_keys(subject)
        (selected_grant, selected_key, selected_secret), (held_grant, held_key, held_secret) = issued
        profile_id = subject.store.binding.profile_id
        assert selected_grant != held_grant and selected_key != held_key
        close_active_bucket_session()

        with (
            serving_runtime(
                endpoint,
                root,
                capture_login=lambda _channel: SyntheticLogin("cli-access-management-native-login"),
                secret_store=lambda: subject.native,
                workers=1,
                product_version=version("cadrumo"),
            ),
            override_settings(
                cadrumo_storage_root=root,
                cadrumo_output_language="en",
            ),
        ):
            api = _api(profile_id, selected_secret)
            opened = [api]
            try:
                api_session_id = _assert_selected_and_global_lock(subject, root, profile_id, api)
                wrong = _assert_resume_reactivates_only_the_selected_grant(
                    subject,
                    profile_id,
                    api,
                    opened,
                    selected_grant=selected_grant,
                    held_grant=held_grant,
                    selected_secret=selected_secret,
                    held_secret=held_secret,
                    api_session_id=api_session_id,
                )
                _assert_key_denial_revokes_only_that_key(
                    subject, root, profile_id, opened[-1], selected_key=selected_key, held_key=held_key
                )
                assert PROFILE_INPUT not in wrong.output
                assert selected_secret.decode("ascii") not in wrong.output
            finally:
                for client in reversed(opened):
                    client.close()
