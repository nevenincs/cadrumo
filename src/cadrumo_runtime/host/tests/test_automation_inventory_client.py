"""A human reads canonical automation inventory through a native profile worker."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.operations.journal import OperationJournalRepository
from cadrumo.adapters.persistence.storage.custody.tests.automation_support import MemoryNativePort
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.core.operations import OperationEffect, OperationTerminalCondition
from cadrumo_client.transport.automation_inventory import read_automation_inventory
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.installation import installation
from cadrumo_client.transport.windows import WindowsEndpoint

from ...adapters.tests.profile_worker_support import PROFILE_INPUT, owner_id, worker_profiles
from .served_runtime import SyntheticLogin, serving_runtime

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires real native Windows profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]


def test_human_inventory_uses_registered_native_projection_and_exact_profile(tmp_path: Path) -> None:
    with worker_profiles(tmp_path) as (root, targets):
        first_profile = targets[0][0].binding.profile_id
        second_profile = targets[1][0].binding.profile_id
        endpoint = WindowsEndpoint(storage_root=root)
        installation(storage_root=root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity)
        native = MemoryNativePort()
        with serving_runtime(
            endpoint,
            root,
            capture_login=lambda _channel: SyntheticLogin("automation-inventory-native-login"),
            secret_store=lambda: native,
        ) as served:
            for profile_id, frontend in (
                (first_profile, OperationFrontendProjection.CLI),
                (second_profile, OperationFrontendProjection.TUI),
            ):
                client = asyncio.run(FrontendClient.open(served.launch, profile_id=profile_id, frontend=frontend))
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
