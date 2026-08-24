"""Public-facade contract for the generic operation platform."""

from __future__ import annotations

import ast
import importlib
from pathlib import Path
from types import ModuleType

import pytest

from .. import (
    OperationCapabilities,
    OperationExecutorContext,
    OperationInteractionRequest,
    OperationLeaseObservation,
    OperationLeaseObservationDisposition,
    OperationPersistedSnapshot,
    OperationPublicProjectionV1,
    OperationRegistry,
    OperationReplayPage,
    OperationRequest,
    OperationSupervisor,
)
from .. import __all__ as public_names

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_facade_exports_only_declared_public_generic_symbols() -> None:
    operations = importlib.import_module("..", package=__package__)

    assert sorted(public_names) == public_names
    assert len(public_names) == len(set(public_names))
    assert all(not name.startswith("_") for name in public_names)
    assert all(hasattr(operations, name) for name in public_names)
    assert all(not isinstance(getattr(operations, name), ModuleType) for name in public_names)


def test_representative_contracts_resolve_from_public_facade() -> None:
    assert OperationCapabilities.__module__.endswith("._capabilities")
    assert OperationRequest.__module__.endswith("._models")
    assert OperationPersistedSnapshot.__module__.endswith("._journal")
    assert OperationPublicProjectionV1.__module__.endswith("._public")
    assert OperationLeaseObservation.__module__.endswith("._leases")
    assert OperationLeaseObservationDisposition.__module__.endswith("._leases")
    assert OperationReplayPage.__module__.endswith("._replay")
    assert "OperationEvent" in public_names
    assert OperationExecutorContext.__module__.endswith("._executor")
    assert OperationInteractionRequest.__module__.endswith("._interactions")
    assert OperationRegistry.__module__.endswith("._registry")
    assert callable(OperationRegistry.resolve_request_json)
    assert callable(OperationRegistry.resolve_snapshot_json)
    assert OperationSupervisor.__module__.endswith("._supervisor")


def test_facade_does_not_import_frontend_or_adapter_modules() -> None:
    facade = Path(__file__).parents[1] / "__init__.py"
    tree = ast.parse(facade.read_text(encoding="utf-8"))
    targets = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module is not None}

    assert targets == {
        "core",
        "_capabilities",
        "_events",
        "_execution_context",
        "_executor",
        "_interactions",
        "_journal",
        "_leases",
        "_models",
        "_public",
        "_replay",
        "_registry",
        "_secret_submission",
        "_supervisor",
    }
