"""Installed CLI lifecycle verbs use the canonical native profile runtime."""

from __future__ import annotations

import asyncio
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from importlib.metadata import version
from pathlib import Path
from threading import Event
from typing import Any
from uuid import UUID, uuid4

import pytest
from click.testing import Result

from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from cadrumo.adapters.local_runtime.installation import runtime_installation
from cadrumo.adapters.local_runtime.runtime_client import open_installed_runtime_client
from cadrumo.adapters.local_runtime.tests.profile_worker_support import owner_id
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.adapters.persistence.storage.custody.acceleration_receipt import delete_profile_session
from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import (
    PROFILE_INPUT,
    administration_subject,
)
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.access_contracts import (
    AuthorityState,
    Availability,
    LoginEligibility,
    OsLockState,
    OsLoginContext,
)
from cadrumo.core.config import override_settings
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
    login_id = "cli-access-management-native-login"

    def observe(self, *, credential_facilities: Availability) -> OsLoginContext:
        return OsLoginContext(
            login_id=self.login_id,
            os_owner_id=owner_id(),
            active=True,
            lock_state=OsLockState.UNLOCKED,
            unattended=LoginEligibility.ELIGIBLE,
            credential_facilities=credential_facilities,
        )


def _human(root: Path, profile_id: UUID, *command: str) -> Result:
    """Supply a fresh explicit password, independent of any acceleration receipt."""
    delete_profile_session(storage_root=root, profile_id=profile_id)
    return invoke_cached_cli(
        ("--format", "json", "--profile", str(profile_id), "--profile-secrets-stdin", *command),
        input=json.dumps({"profile_passphrase": PROFILE_INPUT}),
    )


def _resume(profile_id: UUID, password: str, *, grant_id: UUID) -> Result:
    return invoke_cached_cli(
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


def _api(profile_id: UUID, secret: bytes) -> RuntimeFrontendClient:
    client = asyncio.run(open_installed_runtime_client(profile_id=profile_id, frontend=OperationFrontendProjection.CLI))
    try:
        client.login_api_key(bytearray(secret), timeout=25)
    except BaseException:
        client.close()
        raise
    return client


def _fenced(client: RuntimeFrontendClient) -> None:
    try:
        status = client.status()
    except RuntimeFrontendRefusedError:
        return
    assert status.status.denial is not None


def test_cli_session_lock_global_resume_and_key_denial_use_native_authority(tmp_path: Path) -> None:
    root = tmp_path / "cadrumo-storage"
    root.mkdir()
    endpoint = WindowsRuntimeEndpoint(storage_root=root)
    installation = runtime_installation(
        storage_root=root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity
    )
    with administration_subject(
        tmp_path, os_owner_id=owner_id(), installation_id=installation.installation_id
    ) as subject:
        issued: list[tuple[UUID, UUID, bytes]] = []
        for _ in range(2):
            request_id = uuid4()
            subject.service.request(request_id, subject.proposal)
            receipt = subject.approve(request_id)
            record = next(item for item in subject.store.enrollment_state().requests if item.request_id == request_id)
            key = subject.owner.delivery.endpoint.possession(record)
            assert receipt.key_id is not None and key is not None
            issued.append((receipt.grant_id, receipt.key_id, key.get_secret_value()))
        (selected_grant, selected_key, selected_secret), (held_grant, held_key, held_secret) = issued
        profile_id = subject.store.binding.profile_id
        assert selected_grant != held_grant and selected_key != held_key
        close_active_bucket_session()

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
        with ThreadPoolExecutor(max_workers=1) as pool:
            running = pool.submit(server.serve)
            try:
                assert server.ready.wait(3)
                with override_settings(cadrumo_local_storage_root=root, cadrumo_output_language="en"):
                    api = _api(profile_id, selected_secret)
                    opened = [api]
                    try:
                        api_session_id = api.session_id
                        inventory = _successful(
                            _human(root, profile_id, "config", "profile", "sessions"), "config.profile.sessions"
                        )
                        assert any(item["session_id"] == str(api_session_id) for item in inventory["sessions"])

                        selected = _successful(
                            _human(root, profile_id, "config", "profile", "lock", "--session", str(api_session_id)),
                            "config.profile.lock",
                        )
                        assert selected["scope"] == "selected"
                        assert selected["target_session_id"] == str(api_session_id)
                        assert str(api_session_id) in selected["session_ids"]
                        _fenced(api)

                        current = _successful(
                            _human(root, profile_id, "config", "profile", "lock"), "config.profile.lock"
                        )
                        assert current["scope"] == "current" and current["session_ids"]

                        global_lock = _successful(
                            _human(root, profile_id, "config", "profile", "lock", "--all"),
                            "config.profile.lock",
                        )
                        assert global_lock["scope"] == "profile"
                        assert global_lock["denial"]["access_denied"] is True
                        assert subject.store.profile_lock_state().globally_locked
                        assert {item.state for item in subject.store.snapshot().grants} == {AuthorityState.SUSPENDED}

                        wrong = _resume(profile_id, "wrong-synthetic-password", grant_id=selected_grant)
                        assert wrong.exit_code == 2
                        assert subject.store.profile_lock_state().globally_locked

                        resumed = _successful(
                            _resume(profile_id, PROFILE_INPUT, grant_id=selected_grant), "config.profile.resume"
                        )
                        assert resumed["receipt"]["reactivated_grants"] == [str(selected_grant)]
                        assert not subject.store.profile_lock_state().globally_locked
                        grants = {item.grant_id: item for item in subject.store.snapshot().grants}
                        assert grants[selected_grant].state is AuthorityState.ACTIVE
                        assert grants[held_grant].state is AuthorityState.SUSPENDED
                        _fenced(api)

                        fresh = _api(profile_id, selected_secret)
                        opened.append(fresh)
                        assert fresh.session_id != api_session_id
                        with pytest.raises(RuntimeFrontendRefusedError):
                            _api(profile_id, held_secret)

                        denied = _successful(
                            _human(
                                root,
                                profile_id,
                                "config",
                                "profile",
                                "automation",
                                "deny",
                                "key",
                                str(selected_key),
                            ),
                            "config.profile.automation.deny",
                        )
                        assert denied["kind"] == "key" and denied["target_id"] == str(selected_key)
                        assert denied["receipt"]["access_denied"] is True
                        assert {item.key_id: item.state for item in subject.store.snapshot().keys}[
                            selected_key
                        ] is AuthorityState.REVOKED
                        assert {item.key_id: item.state for item in subject.store.snapshot().keys}[
                            held_key
                        ] is AuthorityState.SUSPENDED
                        _fenced(fresh)

                        assert PROFILE_INPUT not in wrong.output
                        assert selected_secret.decode("ascii") not in wrong.output
                    finally:
                        for client in reversed(opened):
                            client.close()
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
