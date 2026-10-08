"""Parent operation contracts are prepared before runtime readiness."""

from __future__ import annotations

from pathlib import Path
from threading import Event
from typing import cast
from uuid import uuid4

import pytest

from cadrumo.application.operations.registry import OperationRegistry
from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.application.user_profile.automation_custody_port import AutomationSecretStore

from .. import profile_connections
from ..profile_connections import RuntimeProfileConnections

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _connections(root: Path, stop: Event) -> RuntimeProfileConnections:
    def private_access() -> AutomationSecretStore:
        raise AssertionError("registry preparation must not access profile or credentials")

    return RuntimeProfileConnections(
        storage_root=root,
        storage_identity="test-storage",
        runtime_boot_id=uuid4(),
        stop=stop,
        secret_store=private_access,
    )


def test_prepare_registry_is_idempotent_without_profile_or_secret_access(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = 0
    graph = cast(OperationRegistry, object())

    def build() -> OperationRegistry:
        nonlocal calls
        calls += 1
        return graph

    monkeypatch.setattr(profile_connections, "build_production_operation_registry", build)
    connections = _connections(tmp_path, Event())
    assert connections.prepare_registry() is graph
    assert connections.prepare_registry() is graph
    assert calls == 1
    assert connections._registry is graph
    assert not connections._profiles and not connections._connections
    assert connections._installation is None


def test_failed_or_stopped_preparation_publishes_no_graph(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    stop = Event()
    connections = _connections(tmp_path, stop)
    calls = 0

    def fail() -> OperationRegistry:
        nonlocal calls
        calls += 1
        raise ValueError("invalid public graph")

    monkeypatch.setattr(profile_connections, "build_production_operation_registry", fail)
    with pytest.raises(ValueError, match="invalid public graph"):
        connections.prepare_registry()
    assert calls == 1 and connections._registry is None
    assert not connections._profiles and not connections._connections

    def stop_during_build() -> OperationRegistry:
        nonlocal calls
        calls += 1
        stop.set()
        return cast(OperationRegistry, object())

    monkeypatch.setattr(profile_connections, "build_production_operation_registry", stop_during_build)
    with pytest.raises(RuntimeRefusalError) as refused:
        connections.prepare_registry()
    assert refused.value.reason is RuntimeRefusalCode.DRAINING
    assert calls == 2 and connections._registry is None
