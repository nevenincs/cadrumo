"""Public-facade contract for the generic operation platform."""

from __future__ import annotations

import ast
import importlib
from pathlib import Path
from types import ModuleType

import pytest

from .. import (
    OperationCapabilities,
    OperationComposedServices,
    OperationEventCursor,
    OperationLogSeverity,
    OperationObservationService,
    OperationPublicProjectionV1,
    OperationRegistry,
    OperationRequest,
    OperationResponseIntent,
    OperationReviewProjectionService,
    _executor,
    owner,
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
    assert OperationComposedServices.__module__.endswith("._composition")
    assert str(OperationEventCursor).startswith("typing.Annotated")
    assert OperationLogSeverity.__module__.endswith("._events")
    assert OperationRequest.__module__.endswith("._models")
    assert OperationPublicProjectionV1.__module__.endswith("._public")
    assert OperationResponseIntent.__module__.endswith("._interactions")
    assert OperationRegistry.__module__.endswith("._registry")
    assert OperationObservationService.__module__.endswith("._observation")
    assert OperationReviewProjectionService.__module__.endswith("._projection_services")
    assert callable(OperationRegistry.resolve_request_json)
    assert callable(OperationRegistry.resolve_snapshot_json)


def test_facade_does_not_export_runtime_or_persistence_authorities() -> None:
    operations = importlib.import_module("..", package=__package__)
    forbidden = {
        "BoundOperationSecureResponseAuthority",
        "OperationConsumedInteraction",
        "OperationControlSupervisor",
        "OperationDeadlineAccess",
        "OperationEphemeralSecretAccess",
        "OperationEvent",
        "OperationEventEmitter",
        "OperationExecutor",
        "OperationExecutorContext",
        "OperationInteractionAccess",
        "OperationJournal",
        "OperationLeaseObservation",
        "OperationPendingInteraction",
        "OperationPersistedSnapshot",
        "OperationReplayPage",
        "OperationResponseCapability",
        "OperationResponseToken",
        "OperationResumableExecutor",
        "OperationResumeCheckpoint",
        "OperationSecureOperandLookup",
        "OperationSecureResponseAuthority",
        "OperationSnapshot",
        "OperationSupervisor",
        "EphemeralSecretSubmission",
    }

    assert forbidden.isdisjoint(public_names)
    assert all(not hasattr(operations, name) for name in forbidden)


def test_facade_does_not_import_frontend_or_adapter_modules() -> None:
    facade = Path(__file__).parents[1] / "__init__.py"
    tree = ast.parse(facade.read_text(encoding="utf-8"))
    targets = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module is not None}

    assert targets == {
        "core",
        "_capabilities",
        "_composition",
        "_events",
        "_interactions",
        "_models",
        "_observation",
        "_public",
        "_projection_services",
        "_replay",
        "_registry",
        "_secret_submission",
    }


def test_live_operation_boundary_census_has_no_private_consumer_or_redeclaration() -> None:
    """Join live facade exports to every production consumer import."""
    application_root = Path(__file__).parents[2]
    source_root = application_root.parent
    operations_root = application_root / "operations"
    persistence_adapter_root = source_root / "adapters" / "persistence" / "operations"
    top_level_exports = frozenset(public_names)
    owner_exports = frozenset(owner.__all__)
    private_imports: list[tuple[Path, str]] = []
    invalid_imports: list[tuple[Path, str, str]] = []
    owner_consumers: set[Path] = set()

    assert top_level_exports.isdisjoint(owner_exports)
    assert owner.OperationEventEmitter is _executor.OperationEventEmitter
    assert owner.OperationExecutor is _executor.OperationExecutor
    assert owner.OperationExecutorContext is _executor.OperationExecutorContext
    assert owner.OperationInteractionAccess is _executor.OperationInteractionAccess
    assert owner.OperationResumableExecutor is _executor.OperationResumableExecutor
    assert owner.OperationResumeCheckpoint is _executor.OperationResumeCheckpoint

    for source in source_root.rglob("*.py"):
        if (
            "tests" in source.parts
            or source.is_relative_to(operations_root)
            or source.is_relative_to(persistence_adapter_root)
        ):
            continue
        tree = ast.parse(source.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or node.module is None:
                continue
            module = node.module
            if "operations._" in module:
                private_imports.append((source, module))
                continue
            if module.endswith("operations.owner"):
                owner_consumers.add(source)
                for imported in node.names:
                    if imported.name not in owner_exports:
                        invalid_imports.append((source, module, imported.name))
                continue
            if module == "operations" or module.endswith(".application.operations"):
                for imported in node.names:
                    if imported.name not in top_level_exports:
                        invalid_imports.append((source, module, imported.name))

    assert private_imports == []
    assert invalid_imports == []
    assert owner_consumers
