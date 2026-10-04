"""Installed credential references require current custody and fresh native admission."""

from __future__ import annotations

import asyncio
import sys
from concurrent.futures import ThreadPoolExecutor
from importlib.metadata import version
from pathlib import Path
from threading import Event
from typing import override
from uuid import UUID, uuid4

import pytest
from pydantic import SecretBytes

from cadrumo.adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from cadrumo.adapters.local_runtime.installation import runtime_installation
from cadrumo.adapters.local_runtime.runtime_credentials import open_installed_credential_client
from cadrumo.adapters.local_runtime.tests.profile_worker_support import owner_id
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.adapters.persistence.storage.custody.automation_client_credentials import NativeClientCredentialStore
from cadrumo.adapters.persistence.storage.custody.automation_crypto import CustodyAutomationKeyIssuer
from cadrumo.adapters.persistence.storage.custody.tests.automation_support import MemoryNativePort
from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import (
    PROFILE_INPUT,
    administration_subject,
)
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import profile_authority_contexts
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.access_contracts import Availability, LoginEligibility, OsLoginContext
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from cadrumo.application.user_profile.passphrase_rotation import rotate_profile_passphrase
from cadrumo.application.user_profile.registration import register_profile_with_credentials
from cadrumo.entrypoints.runtime.profile_connections import RuntimeProfileConnections

from ...adapters.local_runtime.tests.retained_server import RetainedRuntimeTransportServer

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows runtime workers and pipes"),
    pytest.mark.usefixtures("authority_operation"),
]

_REPLACEMENT = "synthetic-credential-successor"


class _LoginObservation:
    login_id = "installed-credential-native-login"

    def observe(self, *, credential_facilities: Availability) -> OsLoginContext:
        return OsLoginContext(
            login_id=self.login_id,
            os_owner_id=owner_id(),
            active=True,
            locked=False,
            unattended=LoginEligibility.ELIGIBLE,
            credential_facilities=credential_facilities,
        )


class _BlockedNativePort(MemoryNativePort):
    def __init__(self, original: MemoryNativePort) -> None:
        super().__init__()
        self.items = original.items
        self.entered = Event()
        self.release = Event()

    @override
    def read(self, namespace: str, account: str) -> SecretBytes | None:
        self.entered.set()
        if not self.release.wait(10):
            raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)
        return super().read(namespace, account)


def test_installed_reference_reauthenticates_only_current_exact_native_credential(tmp_path: Path) -> None:
    root = tmp_path / "cadrumo-storage"
    root.mkdir()
    endpoint = WindowsRuntimeEndpoint(storage_root=root)
    installation = runtime_installation(
        storage_root=root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity
    )
    with administration_subject(
        tmp_path, os_owner_id=owner_id(), installation_id=installation.installation_id
    ) as subject:
        request_id = uuid4()
        subject.service.request(request_id, subject.proposal)
        approved = subject.approve(request_id)
        assert approved.credential_reference is not None and approved.key_id is not None
        grant = subject.store.snapshot().grants[0]
        profile_id = grant.binding.profile_id
        close_active_bucket_session()
        create, decode = profile_authority_contexts()
        other = register_profile_with_credentials(
            label="Independent credential target",
            passphrase=PROFILE_INPUT,
            profile_create_context=create,
            profile_decode_context=decode,
        )
        other_id = UUID(other.profile_id)
        assert other_id != profile_id
        close_active_bucket_session()
        stop = Event()
        profiles = RuntimeProfileConnections(
            storage_root=root,
            storage_identity=endpoint.storage_identity,
            runtime_boot_id=uuid4(),
            stop=stop,
            capture_login=lambda _channel: _LoginObservation(),
            secret_store=lambda: subject.native,
        )
        profiles.prepare_registry()
        server = RetainedRuntimeTransportServer(
            endpoint,
            product_version=version("cadrumo"),
            stop=stop,
            profiles=profiles,
            boot_id=profiles.boot,
        )
        with ThreadPoolExecutor(max_workers=1) as pool:
            running = pool.submit(server.serve)
            try:
                assert server.ready.wait(3)

                async def exercise() -> None:
                    client = await open_installed_credential_client(
                        profile_id=profile_id,
                        credential_reference=approved.credential_reference,
                        frontend=OperationFrontendProjection.CLI,
                        secrets_store=subject.client_native,
                    )
                    try:
                        assert client.profile_id == profile_id and client.status().status.connected
                        with pytest.raises(AutomationCustodyError, match=AutomationCustodyCode.MISSING):
                            await open_installed_credential_client(
                                profile_id=profile_id,
                                credential_reference=uuid4(),
                                frontend=OperationFrontendProjection.CLI,
                                secrets_store=subject.client_native,
                            )
                        with pytest.raises(AutomationCustodyError, match=AutomationCustodyCode.CREDENTIAL_REJECTED):
                            await open_installed_credential_client(
                                profile_id=other_id,
                                credential_reference=approved.credential_reference,
                                frontend=OperationFrontendProjection.CLI,
                                secrets_store=subject.client_native,
                            )
                        subject.client_native.unavailable = True
                        try:
                            with pytest.raises(AutomationCustodyError, match=AutomationCustodyCode.UNAVAILABLE):
                                await open_installed_credential_client(
                                    profile_id=profile_id,
                                    credential_reference=approved.credential_reference,
                                    frontend=OperationFrontendProjection.CLI,
                                    secrets_store=subject.client_native,
                                )
                        finally:
                            subject.client_native.unavailable = False

                        candidate_id, candidate = CustodyAutomationKeyIssuer.generate()
                        candidate_reference = uuid4()
                        NativeClientCredentialStore(
                            secrets_store=subject.client_native,
                            binding=grant.binding,
                            client_id=grant.client_id,
                            destination_id=grant.client_id,
                        ).replace(
                            credential_reference=candidate_reference,
                            grant_id=grant.grant_id,
                            key_id=candidate_id,
                            review_digest="b" * 64,
                            credential=candidate,
                        )
                        with pytest.raises(RuntimeFrontendRefusedError):
                            await open_installed_credential_client(
                                profile_id=profile_id,
                                credential_reference=candidate_reference,
                                frontend=OperationFrontendProjection.CLI,
                                secrets_store=subject.client_native,
                            )
                        assert client.status().status.connected

                        blocked = _BlockedNativePort(subject.client_native)
                        attempt = asyncio.create_task(
                            open_installed_credential_client(
                                profile_id=profile_id,
                                credential_reference=approved.credential_reference,
                                frontend=OperationFrontendProjection.CLI,
                                secrets_store=blocked,
                            )
                        )
                        try:
                            assert await asyncio.to_thread(blocked.entered.wait, 10)
                            attempt.cancel()
                            await asyncio.sleep(0.05)
                            assert not attempt.done()  # Read owner remains until the blocked native call settles.
                        finally:
                            blocked.release.set()
                        with pytest.raises(asyncio.CancelledError):
                            await attempt
                        assert client.status().status.connected
                    finally:
                        await asyncio.to_thread(client.close)

                asyncio.run(exercise())
                rotated = rotate_profile_passphrase(
                    profile_id=profile_id,
                    current_passphrase=PROFILE_INPUT,
                    new_passphrase=_REPLACEMENT,
                    new_passphrase_confirmation=_REPLACEMENT,
                    root=root,
                    profile_decode_context=decode,
                )
                assert rotated.password_generation == grant.binding.custody_generation + 1
                with pytest.raises(AutomationCustodyError, match=AutomationCustodyCode.CREDENTIAL_REJECTED):
                    asyncio.run(
                        open_installed_credential_client(
                            profile_id=profile_id,
                            credential_reference=approved.credential_reference,
                            frontend=OperationFrontendProjection.CLI,
                            secrets_store=subject.client_native,
                        )
                    )
            finally:
                stop.set()
                running.result(timeout=20)
                endpoint.close()
