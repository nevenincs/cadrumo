"""Production composition proofs for the sole operation dependency graph."""

from __future__ import annotations

import ast
import asyncio
from dataclasses import fields
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from typing import cast

import pytest
from pydantic import BaseModel, Field

from ...adapters.persistence.operations.financial_operand_custody import (
    OperationFinancialOperandCustodyFilesystemRepository,
)
from ...adapters.persistence.operations.journal import OperationJournalRepository
from ...adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from ...adapters.persistence.operations.secure_references import operation_secure_reference_repository
from ...adapters.persistence.storage.master_key.active_session import current_active_bucket_session
from ...adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root, isolated_runtime_profile
from ...application.modelo.operation_definitions import ModeloWorkCalculateExecutor
from ...application.operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ...application.operations.composition import (
    OperationComposedServices,
    OperationSubmission,
    OperationSubmissionService,
    compose_operation_services,
)
from ...application.operations.financial_operand import OperationTransientFinancialOperandDeclaration
from ...application.operations.models import OperationRequest
from ...application.operations.observation import OperationObservationService
from ...application.operations.projection_services import (
    OperationCancellationService,
    OperationDetachService,
    OperationResultProjectionService,
    OperationReviewProjectionService,
    OperationWorkspaceRefreshTargetService,
)
from ...application.operations.registry import (
    OperationDefinition,
    OperationExecutorFactory,
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationRegistry,
    OperationSchemaBindingV1,
)
from ...application.operations.tests.authority_test_support import unread_authority_operation
from ...core.config import load_settings
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationInteractionKind,
)
from ...core.time.clock import now
from ...domain.attachments.protocols import AttachmentStoreProtocol
from ..operation_composition import build_production_operation_registry, compose_operation_dependencies

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


#: No production definition declares a transient financial operand today:
#: manual edit amounts travel as secure-reference requests instead. The
#: composition guarantee still holds for any definition that declares one, so
#: these proofs enrol one test-only declaring definition beside the production
#: inventory rather than assert a production declaration that no longer exists.
_OPERAND_DEFINITION_ID = "operation.composition.operand-declaring"


class _OperandRequest(BaseModel):
    """A request carrying no operand material of its own."""

    model_config = STRICT_FROZEN_CONFIG

    subject: str = Field(min_length=1)


class _NeverStartedOperandExecutor:
    """Composition proofs construct the seam; they never run this operation."""

    async def execute(self, request: OperationRequest[BaseModel], context: object) -> None:
        del request, context
        raise AssertionError("a composition proof started the operand-declaring operation")


def _declaring_registry() -> OperationRegistry:
    """The production inventory plus one definition that declares an operand."""
    production = build_production_operation_registry()
    declaring = OperationDefinition(
        definition_id=_OPERAND_DEFINITION_ID,
        request_type=_OperandRequest,
        result_type=None,
        executor_factory=OperationExecutorFactory(
            request_type=_OperandRequest,
            executor_type=_NeverStartedOperandExecutor,
            build=_NeverStartedOperandExecutor,
        ),
        phase_codes=("operation.phase.declared",),
        interaction_kinds=frozenset({OperationInteractionKind.INPUT}),
        capabilities=OperationCapabilities(
            durability=OperationDurability.RECORDED,
            cancellation=OperationCancellation.UNSUPPORTED,
            deadline=OperationDeadline.ABSENT,
            replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
            baseline=OperationBaselinePolicy.NONE,
            request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
            sensitive_input=OperationSensitiveInputPolicy.SECURE_REFERENCE,
            conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
            owned_resources=frozenset(),
            permitted_effects=frozenset({OperationEffect.NONE, OperationEffect.UNKNOWN}),
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.TUI}),
        transient_financial_operands=(
            OperationTransientFinancialOperandDeclaration(
                operand_kind="regularizacion.cuota",
                currency="EUR",
                scale=2,
                minimum=Decimal("0.00"),
                maximum=Decimal("5000.00"),
                lifetime=timedelta(minutes=5),
            ),
        ),
    )
    registration = OperationPublicDefinitionRegistrationV1.compose(
        definition=declaring,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id="operation.composition.operand-declaring.request",
            schema_version=1,
            model_type=_OperandRequest,
        ),
    )
    return OperationRegistry(
        definitions=tuple(sorted((*production.definitions, declaring), key=lambda item: item.definition_id)),
        public_registrations=tuple(
            sorted(
                (*production.public_registrations, registration),
                key=lambda item: item.contract.definition_id,
            )
        ),
    )


def _compose_declaring(
    tmp_path: Path, *, custody: OperationFinancialOperandCustodyFilesystemRepository | None
) -> OperationComposedServices:
    storage_root = tmp_path / "durable-state"
    journal = OperationJournalRepository(storage_root=storage_root)
    return compose_operation_services(
        registry=_declaring_registry(),
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
        financial_operand_custody=custody,
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

        assert dependencies.observation.registry.lookup("auth.profile.login").definition_id == "auth.profile.login"
        asyncio.run(dependencies.shutdown())


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
            tmp_path, custody=OperationFinancialOperandCustodyFilesystemRepository(settings=load_settings())
        )

        # Constructing while a declaring definition is enrolled is the whole
        # point: satisfying the supervisor guard by deleting the declaration
        # would turn this green while discarding the capability.
        assert services.observation.registry.lookup(_OPERAND_DEFINITION_ID).transient_financial_operands

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
    with isolated_runtime_profile(tmp_path=tmp_path), pytest.raises(ValueError, match="transient financial operand"):
        _compose_declaring(tmp_path, custody=None)
