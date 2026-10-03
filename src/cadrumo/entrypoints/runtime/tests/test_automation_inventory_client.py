"""A human reads canonical automation inventory through a native profile worker."""

from __future__ import annotations

import asyncio
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from uuid import uuid4

import pytest

from cadrumo.adapters.local_runtime.automation_inventory import read_automation_inventory
from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.adapters.local_runtime.installation import runtime_installation
from cadrumo.adapters.local_runtime.server import RuntimeTransportServer
from cadrumo.adapters.local_runtime.startup import RuntimeLaunchDoor
from cadrumo.adapters.local_runtime.tests.profile_worker_support import PROFILE_INPUT, owner_id, worker_profiles
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.adapters.persistence.operations.journal import OperationJournalRepository
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


class _LoginObservation:
    login_id = "automation-inventory-native-login"

    def observe(self, *, credential_facilities: Availability) -> OsLoginContext:
        """Supply synthetic OS facts while custody, worker and journal stay real."""
        return OsLoginContext(
            login_id=self.login_id,
            os_owner_id=owner_id(),
            active=True,
            locked=False,
            unattended=LoginEligibility.ELIGIBLE,
            credential_facilities=credential_facilities,
        )


def test_human_inventory_uses_registered_native_projection_and_exact_profile(tmp_path: Path) -> None:
    with worker_profiles(tmp_path) as (root, targets):
        first_profile = targets[0][0].binding.profile_id
        second_profile = targets[1][0].binding.profile_id
        endpoint = WindowsRuntimeEndpoint(storage_root=root)
        runtime_installation(storage_root=root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity)
        stop, boot, native = Event(), uuid4(), MemoryNativePort()
        profiles = RuntimeProfileConnections(
            storage_root=root,
            storage_identity=endpoint.storage_identity,
            runtime_boot_id=boot,
            stop=stop,
            capture_login=lambda _channel: _LoginObservation(),
            secret_store=lambda: native,
        )
        profiles.prepare_registry()
        server = RuntimeTransportServer(endpoint, product_version="test", stop=stop, profiles=profiles, boot_id=boot)
        launch = RuntimeLaunchDoor(
            endpoint, expected=RuntimeClientHello(product_version="test", storage_identity=endpoint.storage_identity)
        )
        with ThreadPoolExecutor(max_workers=1) as pool:
            running = pool.submit(server.serve)
            try:
                assert server.ready.wait(3)
                for profile_id, frontend in (
                    (first_profile, OperationFrontendProjection.CLI),
                    (second_profile, OperationFrontendProjection.TUI),
                ):
                    client = asyncio.run(RuntimeFrontendClient.open(launch, profile_id=profile_id, frontend=frontend))
                    with client:
                        client.login_password(bytearray(PROFILE_INPUT.encode()))
                        completion = read_automation_inventory(client, timeout=60)
                        assert completion.operation_id
                        assert completion.projection.grants == ()
                        assert completion.projection.keys == ()
                        assert completion.projection.requests == ()
                        assert client.status().status.connected
                    snapshot = asyncio.run(OperationJournalRepository(storage_root=root).load(completion.operation_id))
                    assert snapshot.terminal_condition is OperationTerminalCondition.SUCCEEDED
                    assert snapshot.effect is OperationEffect.NONE
            finally:
                stop.set()
                running.result(timeout=20)
                endpoint.close()
