"""Native password rotation retires old authority and requires fresh proof."""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from threading import Event
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient, RuntimeFrontendRefusedError
from cadrumo.adapters.local_runtime.installation import runtime_installation
from cadrumo.adapters.local_runtime.profile_mutations import ProfileMutationRunError
from cadrumo.adapters.local_runtime.profile_password_rotation import run_profile_password_rotation
from cadrumo.adapters.local_runtime.server import RuntimeTransportServer
from cadrumo.adapters.local_runtime.startup import RuntimeLaunchDoor
from cadrumo.adapters.local_runtime.tests.profile_worker_support import PROFILE_INPUT, owner_id, worker_profiles
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.adapters.persistence.operations.journal import OperationJournalRepository
from cadrumo.adapters.persistence.storage.custody.automation_profile import current_automation_profile_binding
from cadrumo.adapters.persistence.storage.custody.tests.automation_support import MemoryNativePort
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.contracts import RuntimeClientHello
from cadrumo.application.user_profile.access_contracts import Availability, LoginEligibility, OsLoginContext
from cadrumo.core.operations import OperationEffect, OperationTerminalCondition

from ..profile_connections import RuntimeProfileConnections

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires real native Windows profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]

_SUCCESSOR = b"synthetic-worker-password-successor"


class _LoginObservation:
    login_id = "profile-rotation-native-login"

    def observe(self, *, credential_facilities: Availability) -> OsLoginContext:
        """Supply synthetic OS facts while the installed custody path stays real."""
        return OsLoginContext(
            login_id=self.login_id,
            os_owner_id=owner_id(),
            active=True,
            locked=False,
            unattended=LoginEligibility.ELIGIBLE,
            credential_facilities=credential_facilities,
        )


@contextmanager
def _native_runtime(tmp_path: Path) -> Iterator[tuple[UUID, UUID, RuntimeLaunchDoor, UUID, Path]]:
    """Launch a real installed server over synthetic OS and native-store ports."""
    with worker_profiles(tmp_path) as (root, targets):
        profile_id = targets[0][0].binding.profile_id
        other_profile_id = targets[1][0].binding.profile_id
        endpoint = WindowsRuntimeEndpoint(storage_root=root)
        installation = runtime_installation(
            storage_root=root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity
        )
        stop, native = Event(), MemoryNativePort()
        boot = uuid4()
        profiles = RuntimeProfileConnections(
            storage_root=root,
            storage_identity=endpoint.storage_identity,
            runtime_boot_id=boot,
            stop=stop,
            capture_login=lambda _channel: _LoginObservation(),
            secret_store=lambda: native,
        )
        server = RuntimeTransportServer(endpoint, product_version="test", stop=stop, profiles=profiles, boot_id=boot)
        launch = RuntimeLaunchDoor(
            endpoint, expected=RuntimeClientHello(product_version="test", storage_identity=endpoint.storage_identity)
        )

        with ThreadPoolExecutor(max_workers=1) as pool:
            running = pool.submit(server.serve)
            primary: BaseException | None = None
            try:
                assert server.ready.wait(3)
                yield profile_id, other_profile_id, launch, installation.installation_id, root
            except BaseException as error:
                primary = error
                raise
            finally:
                stop.set()
                try:
                    running.result(timeout=20)
                except Exception as cleanup:
                    if primary is None:
                        raise
                    primary.add_note(f"runtime cleanup also failed: {type(cleanup).__name__}")
                finally:
                    endpoint.close()


def _fresh_client(launch: RuntimeLaunchDoor, profile_id: UUID) -> RuntimeFrontendClient:
    return asyncio.run(
        RuntimeFrontendClient.open(launch, profile_id=profile_id, frontend=OperationFrontendProjection.CLI)
    )


def test_rotation_requires_fresh_successor_login_and_wipes_all_proofs(tmp_path: Path) -> None:
    with _native_runtime(tmp_path) as (profile_id, other_profile_id, launch, installation_id, root):
        before = current_automation_profile_binding(
            profile_id=profile_id, installation_id=installation_id, os_owner_id=owner_id(), root=root
        )

        def fresh_client() -> RuntimeFrontendClient:
            return _fresh_client(launch, profile_id)

        with (
            fresh_client() as client,
            fresh_client() as sibling,
            _fresh_client(launch, other_profile_id) as other_profile,
        ):
            client.login_password(bytearray(PROFILE_INPUT.encode()))
            sibling.login_password(bytearray(PROFILE_INPUT.encode()))
            other_profile.login_password(bytearray(PROFILE_INPUT.encode()))
            assert sibling.session_id != client.session_id
            assert other_profile.status().status.connected
            current = bytearray(PROFILE_INPUT.encode())
            successor = bytearray(_SUCCESSOR)
            confirmation = bytearray(_SUCCESSOR)
            completion = run_profile_password_rotation(
                client,
                current_passphrase=current,
                new_passphrase=successor,
                new_passphrase_confirmation=confirmation,
                fresh_client=fresh_client,
                timeout=90,
            )
            assert current == bytes(len(PROFILE_INPUT.encode()))
            assert successor == bytes(len(_SUCCESSOR))
            assert confirmation == bytes(len(_SUCCESSOR))
            assert completion.operation_id
            assert completion.outcome.profile_id == str(profile_id)
            assert completion.outcome.password_generation == before.custody_generation + 1
            assert completion.outcome.dek_epoch_preserved
            with pytest.raises(RuntimeFrontendRefusedError):
                client.status()
            with pytest.raises(RuntimeFrontendRefusedError):
                sibling.status()
            assert other_profile.status().status.connected

        after = current_automation_profile_binding(
            profile_id=profile_id, installation_id=installation_id, os_owner_id=owner_id(), root=root
        )
        assert after.custody_generation == before.custody_generation + 1
        assert after.dek_epoch == before.dek_epoch
        with fresh_client() as successor_proof:
            successor_proof.login_password(bytearray(_SUCCESSOR))
            assert successor_proof.status().status.connected
        with fresh_client() as old_proof, pytest.raises(RuntimeFrontendRefusedError):
            old_proof.login_password(bytearray(PROFILE_INPUT.encode()))


def test_wrong_current_password_refuses_without_retiring_original_session(tmp_path: Path) -> None:
    with _native_runtime(tmp_path) as (profile_id, _other_profile_id, launch, installation_id, root):
        before = current_automation_profile_binding(
            profile_id=profile_id, installation_id=installation_id, os_owner_id=owner_id(), root=root
        )

        def fresh_client() -> RuntimeFrontendClient:
            return _fresh_client(launch, profile_id)

        with fresh_client() as client:
            client.login_password(bytearray(PROFILE_INPUT.encode()))
            wrong = bytearray(b"wrong-current-profile-password")
            successor = bytearray(_SUCCESSOR)
            confirmation = bytearray(_SUCCESSOR)
            with pytest.raises(ProfileMutationRunError) as failed:
                run_profile_password_rotation(
                    client,
                    current_passphrase=wrong,
                    new_passphrase=successor,
                    new_passphrase_confirmation=confirmation,
                    fresh_client=fresh_client,
                    timeout=90,
                )
            assert wrong == bytes(len(b"wrong-current-profile-password"))
            assert successor == bytes(len(_SUCCESSOR))
            assert confirmation == bytes(len(_SUCCESSOR))
            assert failed.value.terminal_condition is OperationTerminalCondition.REFUSED
            assert failed.value.effect is OperationEffect.NONE
            assert "wrong-current-profile-password" not in str(failed.value)
            assert _SUCCESSOR.decode() not in str(failed.value)
            snapshot = asyncio.run(OperationJournalRepository(storage_root=root).load(failed.value.operation_id))
            assert snapshot.terminal_condition is OperationTerminalCondition.REFUSED
            assert snapshot.effect is OperationEffect.NONE
            assert client.status().status.connected

        after = current_automation_profile_binding(
            profile_id=profile_id, installation_id=installation_id, os_owner_id=owner_id(), root=root
        )
        assert after == before
