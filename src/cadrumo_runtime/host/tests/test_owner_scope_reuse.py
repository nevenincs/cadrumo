"""Reuse immutable owner ceilings without reusing delegated authorization.

These are scope-construction tests; native admission and custody integrity are
covered by the native session tests, not by this synthetic connection.
"""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from cadrumo.adapters.persistence.storage.custody.automation_store import AutomationControlStore
from cadrumo.adapters.persistence.storage.custody.tests.automation_support import MemoryNativePort
from cadrumo.application.operations.registry import OperationFrontendProjection, OperationPublicContractSetV1
from cadrumo.application.user_profile.access_contracts import ProfileAccessBinding
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from cadrumo.entrypoints.operation_composition import build_production_operation_registry
from cadrumo_client.contracts.contracts import Peer
from cadrumo_client.contracts.transport import ConnectionContext

from ..profile_host import ProfileConnection, RuntimeProfileHost
from .test_login_scope_binding import _Login

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _host(tmp_path: Path) -> tuple[RuntimeProfileHost, ProfileConnection]:
    binding = ProfileAccessBinding(
        profile_id=uuid4(),
        installation_id=uuid4(),
        os_owner_id="synthetic-owner",
        custody_generation=1,
        dek_epoch=uuid4(),
    )
    boot = uuid4()
    connection = ProfileConnection(
        ConnectionContext(uuid4(), boot, Peer(os_owner_id=binding.os_owner_id, process_id=1234)),
        _Login(binding.os_owner_id),
        uuid4(),
        binding.profile_id,
        OperationFrontendProjection.TUI,
    )
    host = RuntimeProfileHost(
        store=AutomationControlStore(root=tmp_path, binding=binding, secrets_store=MemoryNativePort()),
        runtime_boot_id=boot,
        registry=build_production_operation_registry(),
        connected=lambda _identity: connection,
        logins=lambda: (connection.login,),
        admitting=lambda: True,
    )
    return host, connection


def test_owner_ceiling_reuse_is_bound_to_contract_inventory_and_destination(tmp_path: Path) -> None:
    host, connection = _host(tmp_path)
    initial = host.scope(connection)
    assert host.scope(connection) is initial

    previous_client = connection.client_id
    connection.client_id = uuid4()
    changed_destination = host.scope(connection)
    assert changed_destination is not initial
    assert all(item.destination_id == connection.client_id for item in changed_destination.disclosures)
    assert all(item.destination_id != previous_client for item in changed_destination.disclosures)

    host._contracts = OperationPublicContractSetV1.build(host._contracts.definitions[:1])
    changed_inventory = host.scope(connection)
    assert changed_inventory is not changed_destination
    assert changed_inventory.operations == frozenset({host._contracts.definitions[0].definition_id})
    assert host.scope(connection) is changed_inventory


def test_delegated_scope_never_reuses_an_owner_ceiling(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    host, connection = _host(tmp_path)
    host.scope(connection)
    connection.method = "api_key"
    calls = 0

    def unavailable() -> None:
        nonlocal calls
        calls += 1
        raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)

    monkeypatch.setattr(host.store, "snapshot", unavailable)
    for _ in range(2):
        with pytest.raises(AutomationCustodyError):
            host.scope(connection)
    assert calls == 2
