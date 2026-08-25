"""Production composition proofs for the sole operation dependency graph."""

from __future__ import annotations

import ast
import asyncio
from dataclasses import fields
from pathlib import Path

import pytest

from ...adapters.persistence.storage import current_active_bucket_session
from ...application.operations import (
    OperationCancellationService,
    OperationComposedServices,
    OperationDetachService,
    OperationObservationService,
    OperationRequest,
    OperationReviewProjectionService,
    OperationSubmission,
    OperationSubmissionService,
    OperationWorkspaceRefreshTargetService,
)
from ...tests.secure_sql import isolated_profile_storage_root, isolated_runtime_profile
from .. import build_production_operation_registry
from .._operation_composition import compose_operation_dependencies

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_production_composition_reaches_the_owner_registry_fixed_point(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path):
        dependencies = compose_operation_dependencies()
        expected_registry = build_production_operation_registry()
        registry = dependencies.observation.registry

        assert tuple(item.definition_id for item in registry.definitions) == tuple(
            item.definition_id for item in expected_registry.definitions
        )
        assert registry.public_contract_set == expected_registry.public_contract_set
        assert len(registry.public_contract_set.contract_set_digest) == 64
        assert isinstance(dependencies.observation, OperationObservationService)
        assert isinstance(dependencies.submission, OperationSubmissionService)
        assert isinstance(dependencies.review, OperationReviewProjectionService)
        assert isinstance(dependencies.refresh, OperationWorkspaceRefreshTargetService)
        assert isinstance(dependencies.cancellation, OperationCancellationService)
        assert isinstance(dependencies.detach, OperationDetachService)
        assert dependencies.observation.reader is dependencies.review.reader
        assert dependencies.observation.reader is dependencies.refresh.reader
        assert dependencies.observation.registry is dependencies.review.registry
        assert dependencies.observation.registry is dependencies.refresh.registry
        assert dependencies.observation.registry is dependencies.cancellation.registry
        assert dependencies.observation.registry is dependencies.detach.registry
        asyncio.run(dependencies.shutdown())


def test_production_composition_is_available_before_profile_login(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        assert current_active_bucket_session() is None
        dependencies = compose_operation_dependencies()

        assert dependencies.observation.registry.lookup("auth.profile.login").definition_id == "auth.profile.login"
        asyncio.run(dependencies.shutdown())


def test_submission_issues_actor_bound_opaque_response_capability(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path):
        dependencies = compose_operation_dependencies()
        definition = dependencies.observation.registry.lookup("auth.session.logout")
        payload = definition.request_type()
        request = OperationRequest(
            definition_id=definition.definition_id,
            subject_ref="profile:active",
            payload=payload,
        )

        async def submit() -> OperationSubmission:
            result = await dependencies.submission.submit(
                request,
                actor_ref="operator:composition-test",
                operation_id="a" * 64,
            )
            await dependencies.shutdown()
            return result

        result = asyncio.run(submit())

        assert result.receipt.operation_id == "a" * 64
        assert callable(result.response_capability.close)


def test_production_composition_exposes_only_public_services() -> None:
    public_fields = {item.name for item in fields(OperationComposedServices) if not item.name.startswith("_")}

    assert public_fields == {"submission", "observation", "review", "refresh", "cancellation", "detach"}
    assert {"registry", "supervisor", "response"}.isdisjoint(public_fields)
    assert callable(OperationComposedServices.response)


def test_production_composition_imports_user_profile_operations_from_its_canonical_module() -> None:
    source_path = Path(__file__).parents[1] / "_operation_composition.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imported_modules = tuple(node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom))

    assert not any(module.endswith("_operation_definitions") for module in imported_modules)
    assert "application.user_profile.operations" in imported_modules
    assert not any(module.endswith("_censal_operation") for module in imported_modules)
    assert not any(module.endswith("_filed_history_operation") for module in imported_modules)


def test_production_composition_imports_only_the_inbound_safe_operation_facade() -> None:
    source_path = Path(__file__).parents[1] / "_operation_composition.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    operation_imports = tuple(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("application.operations")
    )

    assert len(operation_imports) == 1
    assert operation_imports[0].module == "application.operations"
    assert operation_imports[0].level == 2
    assert {item.name for item in operation_imports[0].names} == {
        "OperationComposedServices",
        "OperationDefinition",
        "OperationRegistry",
        "compose_operation_services",
    }


def test_inbound_entrypoints_do_not_import_the_operation_owner_module() -> None:
    entrypoints_root = Path(__file__).parents[1]
    owner_imports: list[tuple[Path, str]] = []

    for source in entrypoints_root.rglob("*.py"):
        tree = ast.parse(source.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.ImportFrom)
                and node.module is not None
                and node.module.endswith("operations.owner")
            ):
                owner_imports.append((source, node.module))

    assert owner_imports == []
