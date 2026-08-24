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
    OperationEventEmitter,
    OperationExecutor,
    OperationExecutorContext,
    OperationInteractionAccess,
    OperationLogSeverity,
    OperationObservationService,
    OperationPublicProjectionV1,
    OperationRegistry,
    OperationRequest,
    OperationResumableExecutor,
    OperationResumeCheckpoint,
    OperationReviewProjectionService,
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
    assert OperationExecutorContext.__module__.endswith("._executor")
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
        "OperationJournal",
        "OperationLeaseObservation",
        "OperationPendingInteraction",
        "OperationPersistedSnapshot",
        "OperationReplayPage",
        "OperationResponseIntent",
        "OperationResponseToken",
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
        "_executor",
        "_models",
        "_observation",
        "_public",
        "_projection_services",
        "_replay",
        "_registry",
        "_secret_submission",
    }


def test_application_owners_do_not_import_private_operation_modules() -> None:
    application_root = Path(__file__).parents[2]
    owner_roots = (application_root / "auth", application_root / "live", application_root / "user_profile")
    private_imports: list[tuple[Path, str]] = []

    for owner_root in owner_roots:
        for source in owner_root.rglob("*.py"):
            if "tests" in source.parts:
                continue
            tree = ast.parse(source.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module is not None and "operations._" in node.module:
                    private_imports.append((source, node.module))

    assert private_imports == []


def test_owner_contracts_resolve_from_the_canonical_facade() -> None:
    assert OperationEventEmitter.__module__.endswith("._executor")
    assert OperationExecutor.__module__.endswith("._executor")
    assert OperationExecutorContext.__module__.endswith("._executor")
    assert OperationInteractionAccess.__module__.endswith("._executor")
    assert OperationResumableExecutor.__module__.endswith("._executor")
    assert OperationResumeCheckpoint.__module__.endswith("._executor")
