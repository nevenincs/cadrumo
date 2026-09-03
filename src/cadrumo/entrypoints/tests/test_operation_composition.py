"""Production composition proofs for the sole operation dependency graph."""

from __future__ import annotations

import ast
import asyncio
from dataclasses import fields
from datetime import timedelta
from pathlib import Path

import pytest

from ...adapters.persistence.operations.journal import OperationJournalRepository
from ...adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from ...adapters.persistence.operations.secure_references import operation_secure_reference_repository
from ...adapters.persistence.storage.master_key.active_session import current_active_bucket_session
from ...application.operations.composition import (
    OperationComposedServices,
    OperationSubmission,
    OperationSubmissionService,
    compose_operation_services,
)
from ...application.operations.models import OperationRequest
from ...application.operations.observation import OperationObservationService
from ...application.operations.projection_services import (
    OperationCancellationService,
    OperationDetachService,
    OperationResultProjectionService,
    OperationReviewProjectionService,
    OperationWorkspaceRefreshTargetService,
)
from ...core.time.clock import now
from ...tests.secure_sql import isolated_profile_storage_root, isolated_runtime_profile
from ..operation_composition import build_production_operation_registry, compose_operation_dependencies

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
        assert dependencies.public_contracts is registry.public_contract_set
        assert len(registry.public_contract_set.contract_set_digest) == 64
        assert isinstance(dependencies.observation, OperationObservationService)
        assert isinstance(dependencies.submission, OperationSubmissionService)
        assert isinstance(dependencies.review, OperationReviewProjectionService)
        assert isinstance(dependencies.result, OperationResultProjectionService)
        assert isinstance(dependencies.refresh, OperationWorkspaceRefreshTargetService)
        assert isinstance(dependencies.cancellation, OperationCancellationService)
        assert isinstance(dependencies.detach, OperationDetachService)
        assert dependencies.observation.reader is dependencies.review.reader
        assert dependencies.observation.reader is dependencies.result.reader
        assert dependencies.observation.reader is dependencies.refresh.reader
        assert dependencies.observation.registry is dependencies.review.registry
        assert dependencies.observation.registry is dependencies.result.registry
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

    assert public_fields == {
        "public_contracts",
        "submission",
        "observation",
        "review",
        "result",
        "refresh",
        "cancellation",
        "detach",
    }
    assert {"registry", "supervisor", "response"}.isdisjoint(public_fields)
    assert callable(OperationComposedServices.response)


def test_production_composition_imports_user_profile_operations_from_its_canonical_module() -> None:
    source_path = Path(__file__).parents[1] / "operation_composition.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imported_modules = tuple(node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom))

    assert not any(module.endswith("_operation_definitions") for module in imported_modules)
    assert "application.user_profile.operations" in imported_modules
    assert not any(module.endswith("_censal_operation") for module in imported_modules)
    assert not any(module.endswith("_filed_history_operation") for module in imported_modules)


def test_production_composition_imports_only_public_operation_defining_modules() -> None:
    source_path = Path(__file__).parents[1] / "operation_composition.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    operation_imports = tuple(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and (node.module or "").startswith(("application.operations", "cadrumo.application.operations"))
    )

    assert operation_imports
    assert all(node.level == 2 for node in operation_imports)
    assert {node.module for node in operation_imports} == {
        "application.operations.composition",
        "application.operations.registry",
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


def test_production_composition_retains_the_operand_declaring_definition(tmp_path: Path) -> None:
    """The seam constructs WITH the operand capability, not by dropping it."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        dependencies = compose_operation_dependencies()
        registry = dependencies.observation.registry
        declaring = tuple(
            definition.definition_id for definition in registry.definitions if definition.transient_financial_operands
        )

        # Constructing while a declaring definition is enrolled is the whole
        # point: satisfying the supervisor guard by deleting the declaration
        # would turn this green while discarding the capability.
        assert declaring
        for definition_id in declaring:
            assert registry.lookup(definition_id).transient_financial_operands

        asyncio.run(dependencies.shutdown())


def test_production_composition_submits_through_the_constructed_seam(tmp_path: Path) -> None:
    """The seam is functional end to end, not merely constructible."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        dependencies = compose_operation_dependencies()
        definition = dependencies.observation.registry.lookup("auth.session.logout")
        request = OperationRequest(
            definition_id=definition.definition_id,
            subject_ref="profile:active",
            payload=definition.request_type(),
        )

        async def submit() -> OperationSubmission:
            submitted = await dependencies.submission.submit(
                request,
                actor_ref="operator:custody-wire",
                operation_id="c" * 64,
            )
            await dependencies.shutdown()
            return submitted

        submission = asyncio.run(submit())

        assert submission.receipt.operation_id == "c" * 64


def test_composing_a_declaring_registry_without_custody_is_still_refused(tmp_path: Path) -> None:
    """The guard keeps biting; the wire satisfies it rather than disabling it."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        storage_root = tmp_path / "durable-state"
        journal = OperationJournalRepository(storage_root=storage_root)
        registry = build_production_operation_registry()

        assert any(definition.transient_financial_operands for definition in registry.definitions)

        with pytest.raises(ValueError, match="transient financial operand"):
            compose_operation_services(
                registry=registry,
                journal=journal,
                reader=journal,
                event_stream=journal,
                leases=OperationLeaseFilesystemRepository(storage_root=storage_root),
                operands=operation_secure_reference_repository(),
                owner_id="1" * 64,
                lease_token_factory=lambda: "2" * 64,
                clock=now,
                lease_duration=timedelta(minutes=10),
                execution_timeout=timedelta(hours=1),
                cleanup_timeout=timedelta(minutes=2),
                financial_operand_custody=None,
            )
