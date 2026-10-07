"""Production composition proofs for the sole operation dependency graph."""

from __future__ import annotations

import ast
import asyncio
from dataclasses import fields
from datetime import timedelta
from pathlib import Path
from typing import cast

import pytest

from ...adapters.persistence.operations.journal import OperationJournalRepository
from ...adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from ...adapters.persistence.operations.secure_references import operation_secure_reference_repository
from ...adapters.persistence.operations.typed_financial_operand_custody import (
    OperationTypedFinancialOperandCustodyFilesystemRepository,
)
from ...adapters.persistence.storage.master_key.active_session import current_active_bucket_session
from ...adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root, isolated_runtime_profile
from ...application.export.calculation_review_xlsx_operation import (
    CalculationReviewXlsxExecutionResult,
    CalculationReviewXlsxRequest,
)
from ...application.modelo.operation_definitions import ModeloWorkCalculateExecutor
from ...application.modelo.reconciliation_export_operation import ReconciliationExportXlsxRequest
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
from ...application.operations.registry import OperationFrontendProjection
from ...application.operations.tests.authority_test_support import unread_authority_operation
from ...core.config import load_settings
from ...core.time.clock import now
from ...domain.attachments.protocols import AttachmentStoreProtocol
from ..operation_composition import build_production_operation_registry, compose_operation_dependencies

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


_OPERAND_DEFINITION_ID = "modelo.edit.apply"


def _compose_declaring(
    tmp_path: Path, *, custody: OperationTypedFinancialOperandCustodyFilesystemRepository | None
) -> OperationComposedServices:
    storage_root = tmp_path / "durable-state"
    journal = OperationJournalRepository(storage_root=storage_root)
    return compose_operation_services(
        registry=build_production_operation_registry(),
        authority_operation=unread_authority_operation(),
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
        typed_financial_operand_custody=custody,
    )


def test_production_composition_reaches_the_owner_registry_fixed_point(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path):
        dependencies = compose_operation_dependencies(authority_operation=unread_authority_operation())
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


def test_production_registry_injects_the_secure_attachment_store_into_m303_calculation() -> None:
    """M303 evidence resolves through composition-owned encrypted attachment custody."""

    def attachment_store_factory(_bucket_id: str) -> AttachmentStoreProtocol:
        return cast(AttachmentStoreProtocol, object())

    registry = build_production_operation_registry(attachment_store_factory=attachment_store_factory)
    definition = registry.lookup("modelo.work.calculate")
    executor = cast(ModeloWorkCalculateExecutor, definition.executor_factory.build())

    assert executor._attachment_store_factory is attachment_store_factory


def test_production_composition_is_available_before_profile_login(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        assert current_active_bucket_session() is None
        dependencies = compose_operation_dependencies(authority_operation=unread_authority_operation())

        assert dependencies.observation.registry.lookup("auth.profile.passphrase-rotate").definition_id == (
            "auth.profile.passphrase-rotate"
        )
        asyncio.run(dependencies.shutdown())


def test_saved_calculation_review_export_is_registered_for_both_operator_surfaces(tmp_path: Path) -> None:
    """Local saved review export is a real runtime operation, available without Google configuration."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        assert current_active_bucket_session() is None
        registry = build_production_operation_registry()
        definition = registry.lookup("export.calculation-review-xlsx")
        contract = registry.lookup_public_contract(definition.definition_id)
        assert definition.request_type is CalculationReviewXlsxRequest
        assert definition.result_type is CalculationReviewXlsxExecutionResult
        assert contract.permitted_frontends == frozenset(
            {OperationFrontendProjection.CLI, OperationFrontendProjection.TUI}
        )
        assert (
            registry.lookup_public_registration(definition.definition_id).contract.definition_id
            == definition.definition_id
        )
        reconciliation = registry.lookup("modelo.reconcile.export-xlsx")
        assert reconciliation.request_type is ReconciliationExportXlsxRequest
        assert registry.lookup_public_contract(reconciliation.definition_id).permitted_frontends == frozenset(
            {OperationFrontendProjection.CLI, OperationFrontendProjection.TUI}
        )


def test_submission_issues_actor_bound_opaque_response_capability(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path):
        dependencies = compose_operation_dependencies(authority_operation=unread_authority_operation())
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
        assert result.response_capability is not None
        assert callable(result.response_capability.close)


def test_idempotent_replay_keeps_the_receipt_without_reissuing_response_authority(tmp_path: Path) -> None:
    """Same-owner, other-actor and replacement-host retries preserve one invocation."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        services = compose_operation_dependencies(authority_operation=unread_authority_operation())
        definition = services.observation.registry.lookup("auth.session.logout")
        request = OperationRequest(
            definition_id=definition.definition_id,
            subject_ref="profile:active",
            payload=definition.request_type(),
            idempotency_key="same-scoped-request",
        )

        async def exercise() -> None:
            try:
                first = await services.submission.submit(request, actor_ref="operator:first")
                assert first.response_capability is not None
                for actor in ("operator:first", "operator:second"):
                    replay = await services.submission.submit(request, actor_ref=actor)
                    assert replay.receipt == first.receipt
                    assert replay.response_capability is None
            finally:
                await services.shutdown()
            replacement = compose_operation_dependencies(authority_operation=unread_authority_operation())
            try:
                replay = await replacement.submission.submit(request, actor_ref="operator:replacement")
                assert replay.receipt == first.receipt
                assert replay.response_capability is None
            finally:
                await replacement.shutdown()

        asyncio.run(exercise())


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
        "application.operations.authorization",
        "application.operations.composition",
        "application.operations.operation_definition",
        "application.operations.registry",
        "application.operations.registry_schema_validation",
    }


def test_inbound_entrypoints_do_not_import_the_operation_owner_module() -> None:
    """Inbound production code reaches operations through frontend requests, never the owner.

    Test packages are not inbound surfaces: a test that drives an operation end
    to end supplies a fake executor, which implements the owner's own emitter
    protocol.
    """
    entrypoints_root = Path(__file__).parents[1]
    owner_imports: list[tuple[Path, str]] = []

    for source in entrypoints_root.rglob("*.py"):
        if "tests" in source.relative_to(entrypoints_root).parts:
            continue
        tree = ast.parse(source.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.ImportFrom)
                and node.module is not None
                and node.module.endswith("operations.owner")
            ):
                owner_imports.append((source, node.module))

    assert owner_imports == []


def test_the_production_custody_wire_composes_a_registry_that_declares_an_operand(tmp_path: Path) -> None:
    """The seam constructs WITH operand custody, so a declaring definition keeps its capability."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        services = _compose_declaring(
            tmp_path, custody=OperationTypedFinancialOperandCustodyFilesystemRepository(settings=load_settings())
        )

        # Constructing while a declaring definition is enrolled is the whole
        # point: satisfying the supervisor guard by deleting the declaration
        # would turn this green while discarding the capability.
        assert services.observation.registry.lookup(_OPERAND_DEFINITION_ID).transient_financial_operand

        asyncio.run(services.shutdown())


def test_production_composition_submits_through_the_constructed_seam(tmp_path: Path) -> None:
    """The seam is functional end to end, not merely constructible."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        dependencies = compose_operation_dependencies(authority_operation=unread_authority_operation())
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
    with (
        isolated_runtime_profile(tmp_path=tmp_path),
        pytest.raises(ValueError, match="typed financial operations require hardened durable custody"),
    ):
        _compose_declaring(tmp_path, custody=None)
