"""Real-adapter tests for safe projection and public operation controls."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel

from cadrumo.adapters.persistence.operations.journal import OperationJournalRepository
from cadrumo.adapters.persistence.operations.secure_references import operation_secure_reference_repository
from cadrumo.adapters.persistence.storage.secure_object_namespaces import OPERATION_SECURE_REFERENCE_NAMESPACE
from cadrumo.adapters.persistence.storage.tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from cadrumo.application.operations.frontend_projection import OperationReviewProjectionReferenceV1
from cadrumo.application.operations.frontend_requests import (
    OperationResultProjectionRefusalCode,
    OperationResultProjectionRefusalV1,
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
    OperationReviewProjectionRefusalCode,
    OperationReviewProjectionRefusalV1,
    OperationReviewProjectionRequestV1,
    OperationReviewProjectionSuccessV1,
    OperationReviewProjectionVersionHeader,
    OperationWorkspaceRefreshTargetRefusalCode,
    OperationWorkspaceRefreshTargetRefusalV1,
    OperationWorkspaceRefreshTargetRequestV1,
    OperationWorkspaceRefreshTargetSuccessV1,
    OperationWorkspaceRefreshTargetVersionHeader,
)
from cadrumo.application.operations.models import (
    OperationTerminalReceipt,
)
from cadrumo.application.operations.persistence.journal import OperationPersistedSnapshot
from cadrumo.application.operations.projection_services import (
    OperationResultProjectionService,
    OperationReviewProjectionService,
    OperationWorkspaceRefreshTargetService,
)
from cadrumo.application.operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionContractV1,
)
from cadrumo.core.operations import (
    OperationEffect,
    OperationTerminalCondition,
)

from .projection_services_support import (
    _DEFINITION_ID,
    _INTERACTION_ID,
    _NOW,
    _OPERATION_ID,
    _REFUSAL_CODE,
    _REFUSAL_SENTINEL,
    _TOKEN,
    PrivateRefusalDetail,
    ProjectionResult,
    PublicProjectionResult,
    PublicRefusalDetail,
    ReviewedOperand,
    SafeReviewProjection,
    WorkspaceRefreshTarget,
    _lease,
    _observe_refused_operation,
    _pending,
    _project_refusal_detail,
    _project_result,
    _refused_snapshot,
    _registry,
    _running_snapshot,
    _terminal_snapshot,
    _unsafe_refresh_target,
    _unsafe_result_projection,
    _unsafe_review_projection,
    _waiting_snapshot,
    _write,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_review_resolution_uses_encrypted_operand_and_is_read_only(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        root = tmp_path / "durable"
        registry = _registry()
        operands = operation_secure_reference_repository(objects=profile.repository)
        proposal = asyncio.run(operands.put(ReviewedOperand(summary_code="safe.review"), written_at=_NOW))
        pending = _pending(registry, proposal=proposal)
        repository = OperationJournalRepository(storage_root=root)
        _write(root, repository, _waiting_snapshot(registry, pending))
        journal_path = root / "operation-journals" / f"{_OPERATION_ID}.json"
        before = journal_path.read_bytes()
        contract = registry.lookup_public_contract(_DEFINITION_ID)
        assert contract.review_projection_schema is not None
        request = OperationReviewProjectionRequestV1(
            reference=OperationReviewProjectionReferenceV1(
                operation_id=_OPERATION_ID,
                interaction_id=_INTERACTION_ID,
                revision=0,
                review_projection_schema=contract.review_projection_schema,
                definition_contract_digest=contract.definition_contract_digest,
                expires_at=pending.request.expires_at,
            )
        )
        service = OperationReviewProjectionService(
            reader=repository,
            registry=registry,
            operands=operands,
            clock=lambda: _NOW,
        )

        result = asyncio.run(service.resolve(request, SafeReviewProjection))
        stale = asyncio.run(
            service.resolve(
                request.model_copy(
                    update={"reference": request.reference.model_copy(update={"interaction_id": "9" * 64})}
                ),
                SafeReviewProjection,
            )
        )
        expired = asyncio.run(
            OperationReviewProjectionService(
                reader=repository,
                registry=registry,
                operands=operands,
                clock=lambda: _NOW + timedelta(hours=1),
            ).resolve(request, SafeReviewProjection)
        )
        digest_mismatch = asyncio.run(
            service.resolve(
                request.model_copy(
                    update={"reference": request.reference.model_copy(update={"definition_contract_digest": "a" * 64})}
                ),
                SafeReviewProjection,
            )
        )
        assert contract.result_schema is not None
        schema_mismatch = asyncio.run(
            service.resolve(
                request.model_copy(
                    update={
                        "reference": request.reference.model_copy(
                            update={"review_projection_schema": contract.result_schema}
                        )
                    }
                ),
                SafeReviewProjection,
            )
        )
        unsafe_output = asyncio.run(
            OperationReviewProjectionService(
                reader=repository,
                registry=_registry(review_projector=_unsafe_review_projection),
                operands=operands,
                clock=lambda: _NOW,
            ).resolve(request, SafeReviewProjection)
        )

        assert isinstance(result, OperationReviewProjectionSuccessV1)
        assert result.projection == SafeReviewProjection(summary_code="safe.review")
        assert isinstance(stale, OperationReviewProjectionRefusalV1)
        assert isinstance(expired, OperationReviewProjectionRefusalV1)
        assert isinstance(digest_mismatch, OperationReviewProjectionRefusalV1)
        assert isinstance(schema_mismatch, OperationReviewProjectionRefusalV1)
        assert isinstance(unsafe_output, OperationReviewProjectionRefusalV1)
        assert stale.code is OperationReviewProjectionRefusalCode.STALE_REVIEW_REFERENCE
        assert expired.code is OperationReviewProjectionRefusalCode.REVIEW_EXPIRED
        assert digest_mismatch.code is OperationReviewProjectionRefusalCode.DEFINITION_CONTRACT_MISMATCH
        assert schema_mismatch.code is OperationReviewProjectionRefusalCode.REVIEW_SCHEMA_MISMATCH
        assert unsafe_output.code is OperationReviewProjectionRefusalCode.REVIEW_PROJECTION_UNAVAILABLE
        assert journal_path.read_bytes() == before
        assert _TOKEN.encode() not in before and proposal.encode() in before
        assert "result_ref" not in type(request).model_fields


def test_result_resolution_uses_encrypted_operand_and_public_contract(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        root = tmp_path / "result-durable"
        registry = _registry(result_projector=_project_result, result_schema_type=PublicProjectionResult)
        repository = OperationJournalRepository(storage_root=root)
        operands = operation_secure_reference_repository(objects=profile.repository)
        result_ref = asyncio.run(operands.put(ProjectionResult(result_code="safe.result"), written_at=_NOW))
        assert asyncio.run(operands.resolve(result_ref, ProjectionResult)) == ProjectionResult(
            result_code="safe.result"
        )
        terminal = _terminal_snapshot(registry, result_ref=result_ref)
        _write(root, repository, _running_snapshot(registry))
        asyncio.run(repository.commit_settlement(terminal, expected_revision=0, lease=_lease()))
        contract = registry.lookup_public_contract(_DEFINITION_ID)
        assert contract.result_schema is not None
        request = OperationResultProjectionRequestV1(
            operation_id=_OPERATION_ID,
            terminal_revision=terminal.revision,
            definition_contract_digest=contract.definition_contract_digest,
            result_schema=contract.result_schema,
        )
        service = OperationResultProjectionService(reader=repository, registry=registry, operands=operands)

        result = asyncio.run(service.resolve(request, PublicProjectionResult))
        stale = asyncio.run(
            service.resolve(
                request.model_copy(update={"terminal_revision": terminal.revision + 1}), PublicProjectionResult
            )
        )
        digest_mismatch = asyncio.run(
            service.resolve(request.model_copy(update={"definition_contract_digest": "a" * 64}), PublicProjectionResult)
        )
        schema_mismatch = asyncio.run(
            service.resolve(
                request.model_copy(update={"result_schema": contract.request_schema}), PublicProjectionResult
            )
        )
        unsafe_output = asyncio.run(
            OperationResultProjectionService(
                reader=repository,
                registry=_registry(
                    result_projector=_unsafe_result_projection,
                    result_schema_type=PublicProjectionResult,
                ),
                operands=operands,
            ).resolve(request, PublicProjectionResult)
        )

        assert isinstance(result, OperationResultProjectionSuccessV1)
        assert result.projection == PublicProjectionResult(result_code="safe.result")
        assert isinstance(stale, OperationResultProjectionRefusalV1)
        assert isinstance(digest_mismatch, OperationResultProjectionRefusalV1)
        assert isinstance(schema_mismatch, OperationResultProjectionRefusalV1)
        assert isinstance(unsafe_output, OperationResultProjectionRefusalV1)
        assert stale.code is OperationResultProjectionRefusalCode.STALE_OPERATION_REVISION
        assert digest_mismatch.code is OperationResultProjectionRefusalCode.DEFINITION_CONTRACT_MISMATCH
        assert schema_mismatch.code is OperationResultProjectionRefusalCode.RESULT_SCHEMA_MISMATCH
        assert unsafe_output.code is OperationResultProjectionRefusalCode.RESULT_PROJECTION_UNAVAILABLE
        assert "result_ref" not in type(request).model_fields


@dataclass
class _PagedResultRig:
    """A persisted terminal result read through the projection service with a counted projector."""

    service: OperationResultProjectionService
    request: OperationResultProjectionRequestV1
    contract: OperationPublicDefinitionContractV1
    terminal: OperationPersistedSnapshot
    projections: list[str]
    scope: tuple[UUID, OperationFrontendProjection]

    def read(
        self,
        selected: OperationResultProjectionRequestV1 | None = None,
        *,
        continuation: bool = True,
        reader_scope: tuple[UUID, OperationFrontendProjection] | None = None,
    ) -> OperationResultProjectionSuccessV1[PublicProjectionResult] | OperationResultProjectionRefusalV1:
        return asyncio.run(
            self.service.resolve(
                self.request if selected is None else selected,
                PublicProjectionResult,
                snapshot_scope=self.scope if reader_scope is None else reader_scope,
                continue_snapshot=continuation,
            )
        )


def _paged_result_rig(tmp_path: Path, profile: TestRuntimeProfile) -> _PagedResultRig:
    projections: list[str] = []

    def project(result: BaseModel, receipt: OperationTerminalReceipt) -> BaseModel:
        projections.append("projected")
        return _project_result(result, receipt)

    root = tmp_path / "paged-result-durable"
    registry = _registry(result_projector=project, result_schema_type=PublicProjectionResult)
    repository = OperationJournalRepository(storage_root=root)
    operands = operation_secure_reference_repository(objects=profile.repository)
    result_ref = asyncio.run(operands.put(ProjectionResult(result_code="safe.result"), written_at=_NOW))
    terminal = _terminal_snapshot(registry, result_ref=result_ref)
    _write(root, repository, _running_snapshot(registry))
    asyncio.run(repository.commit_settlement(terminal, expected_revision=0, lease=_lease()))
    contract = registry.lookup_public_contract(_DEFINITION_ID)
    assert contract.result_schema is not None
    request = OperationResultProjectionRequestV1(
        operation_id=_OPERATION_ID,
        terminal_revision=terminal.revision,
        definition_contract_digest=contract.definition_contract_digest,
        result_schema=contract.result_schema,
    )
    service = OperationResultProjectionService(reader=repository, registry=registry, operands=operands)
    return _PagedResultRig(
        service=service,
        request=request,
        contract=contract,
        terminal=terminal,
        projections=projections,
        scope=(uuid4(), OperationFrontendProjection.TUI),
    )


def _assert_paged_read_refusals(rig: _PagedResultRig) -> None:
    request = rig.request
    stale = rig.read(request.model_copy(update={"terminal_revision": rig.terminal.revision + 1}))
    assert isinstance(stale, OperationResultProjectionRefusalV1)
    assert stale.code is OperationResultProjectionRefusalCode.STALE_OPERATION_REVISION
    changed_contract = rig.read(request.model_copy(update={"definition_contract_digest": "a" * 64}))
    assert isinstance(changed_contract, OperationResultProjectionRefusalV1)
    assert changed_contract.code is OperationResultProjectionRefusalCode.DEFINITION_CONTRACT_MISMATCH
    changed_schema = rig.read(request.model_copy(update={"result_schema": rig.contract.request_schema}))
    assert isinstance(changed_schema, OperationResultProjectionRefusalV1)
    assert changed_schema.code is OperationResultProjectionRefusalCode.RESULT_SCHEMA_MISMATCH
    assert len(rig.projections) == 1
    wrong_model = asyncio.run(
        rig.service.resolve(request, ProjectionResult, snapshot_scope=rig.scope, continue_snapshot=True)
    )
    assert isinstance(wrong_model, OperationResultProjectionRefusalV1)
    assert wrong_model.code is OperationResultProjectionRefusalCode.RESULT_PROJECTION_UNAVAILABLE
    assert len(rig.projections) == 2


def _assert_paged_reads_reuse_only_their_own_snapshot(
    rig: _PagedResultRig,
    first: OperationResultProjectionSuccessV1[PublicProjectionResult] | OperationResultProjectionRefusalV1,
) -> None:
    projections = rig.projections
    # A page-zero read and another session each resolve the real encrypted
    # operand again; neither is an earlier reader's continuation.
    assert rig.read(continuation=False) == first
    assert len(projections) == 3
    assert rig.read(reader_scope=(uuid4(), OperationFrontendProjection.TUI)) == first
    assert len(projections) == 4
    assert rig.read() == first
    assert len(projections) == 5
    assert rig.read(reader_scope=(rig.scope[0], OperationFrontendProjection.CLI)) == first
    assert len(projections) == 6
    assert rig.read() == first
    assert len(projections) == 7
    rig.service.forget_snapshot(_OPERATION_ID)
    assert rig.read() == first
    assert len(projections) == 8
    rig.service.forget_snapshot()
    assert rig.read() == first
    assert len(projections) == 9

    # The ordinary service remains a fresh read even while another paged
    # transfer has a snapshot; the optimization is explicitly requested.
    assert asyncio.run(rig.service.resolve(rig.request, PublicProjectionResult)) == first
    assert len(projections) == 10


def test_paged_snapshot_rechecks_terminal_contract_and_keeps_readers_separate(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        rig = _paged_result_rig(tmp_path, profile)
        first = rig.read(continuation=False)
        assert isinstance(first, OperationResultProjectionSuccessV1)
        assert rig.read() == first
        assert len(rig.projections) == 1
        _assert_paged_read_refusals(rig)
        _assert_paged_reads_reuse_only_their_own_snapshot(rig, first)


def test_refused_detail_uses_encrypted_operand_and_preserves_the_refused_receipt(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        root = tmp_path / "refused-detail-durable"
        registry = _registry(
            result_projector=_project_refusal_detail,
            result_schema_type=PublicRefusalDetail,
            result_type=PrivateRefusalDetail,
            refusal_detail_codes=frozenset({_REFUSAL_CODE}),
        )
        repository = OperationJournalRepository(storage_root=root)
        operands = operation_secure_reference_repository(objects=profile.repository)
        private_detail = PrivateRefusalDetail(
            detail_code="modelo.not_applicable",
            private_sentinel=_REFUSAL_SENTINEL,
        )
        detail_ref = asyncio.run(operands.put(private_detail, written_at=_NOW))
        assert asyncio.run(operands.resolve(detail_ref, PrivateRefusalDetail)) == private_detail

        terminal = _refused_snapshot(registry, detail_ref=detail_ref)
        _write(root, repository, _running_snapshot(registry))
        asyncio.run(repository.commit_settlement(terminal, expected_revision=0, lease=_lease()))
        contract = registry.lookup_public_contract(_DEFINITION_ID)
        assert contract.result_schema is not None
        request = OperationResultProjectionRequestV1(
            operation_id=_OPERATION_ID,
            terminal_revision=terminal.revision,
            definition_contract_digest=contract.definition_contract_digest,
            result_schema=contract.result_schema,
        )
        service = OperationResultProjectionService(reader=repository, registry=registry, operands=operands)
        before = _observe_refused_operation(repository, registry, expected_effect=OperationEffect.UNKNOWN)

        projected = asyncio.run(service.resolve(request, PublicRefusalDetail))
        after = _observe_refused_operation(repository, registry, expected_effect=OperationEffect.UNKNOWN)
        persisted = b"".join(path.read_bytes() for path in tmp_path.rglob("*") if path.is_file())
        snapshot = asyncio.run(repository.load(_OPERATION_ID))

    assert isinstance(projected, OperationResultProjectionSuccessV1)
    assert projected.projection == PublicRefusalDetail(detail_code="modelo.not_applicable")
    assert _REFUSAL_SENTINEL not in projected.model_dump_json()
    assert _REFUSAL_SENTINEL.encode() not in persisted
    assert detail_ref not in before.model_dump_json()
    assert before.projection.model_dump() == after.projection.model_dump()
    assert snapshot.terminal_receipt is not None
    assert snapshot.terminal_receipt.condition is OperationTerminalCondition.REFUSED
    assert snapshot.terminal_receipt.refusal_ref == _REFUSAL_CODE
    assert snapshot.terminal_receipt.refusal_detail_ref == detail_ref
    assert snapshot.terminal_receipt.result_ref is None
    assert snapshot.terminal_receipt.effect is OperationEffect.UNKNOWN


@pytest.mark.parametrize("stored_detail", ("missing", "wrong-model"))
def test_unavailable_refused_detail_keeps_refusal_code_and_unknown_effect_observable(
    tmp_path: Path,
    stored_detail: str,
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        root = tmp_path / f"refused-detail-{stored_detail}"
        registry = _registry(
            result_projector=_project_refusal_detail,
            result_schema_type=PublicRefusalDetail,
            result_type=PrivateRefusalDetail,
            refusal_detail_codes=frozenset({_REFUSAL_CODE}),
        )
        repository = OperationJournalRepository(storage_root=root)
        operands = operation_secure_reference_repository(objects=profile.repository)
        if stored_detail == "missing":
            detail_ref = "f" * 64
            missing = profile.repository.load(
                OPERATION_SECURE_REFERENCE_NAMESPACE.namespace,
                detail_ref,
                expected_class=OPERATION_SECURE_REFERENCE_NAMESPACE.sensitivity,
                max_supported_version=OPERATION_SECURE_REFERENCE_NAMESPACE.schema_version,
            )
            assert missing is None
        else:
            detail_ref = asyncio.run(operands.put(ProjectionResult(result_code=_REFUSAL_SENTINEL), written_at=_NOW))
        terminal = _refused_snapshot(registry, detail_ref=detail_ref, effect=OperationEffect.UNKNOWN)
        _write(root, repository, _running_snapshot(registry))
        asyncio.run(repository.commit_settlement(terminal, expected_revision=0, lease=_lease()))
        contract = registry.lookup_public_contract(_DEFINITION_ID)
        assert contract.result_schema is not None
        request = OperationResultProjectionRequestV1(
            operation_id=_OPERATION_ID,
            terminal_revision=terminal.revision,
            definition_contract_digest=contract.definition_contract_digest,
            result_schema=contract.result_schema,
        )
        service = OperationResultProjectionService(reader=repository, registry=registry, operands=operands)
        before = _observe_refused_operation(repository, registry, expected_effect=OperationEffect.UNKNOWN)

        unavailable = asyncio.run(service.resolve(request, PublicRefusalDetail))
        after = _observe_refused_operation(repository, registry, expected_effect=OperationEffect.UNKNOWN)
        snapshot = asyncio.run(repository.load(_OPERATION_ID))

    assert isinstance(unavailable, OperationResultProjectionRefusalV1)
    assert unavailable.code is OperationResultProjectionRefusalCode.RESULT_PROJECTION_UNAVAILABLE
    assert _REFUSAL_SENTINEL not in unavailable.model_dump_json()
    assert before.projection.model_dump() == after.projection.model_dump()
    assert snapshot.terminal_receipt is not None
    assert snapshot.terminal_receipt.condition is OperationTerminalCondition.REFUSED
    assert snapshot.terminal_receipt.refusal_ref == _REFUSAL_CODE
    assert snapshot.terminal_receipt.refusal_detail_ref == detail_ref
    assert snapshot.terminal_receipt.result_ref is None
    assert snapshot.terminal_receipt.effect is OperationEffect.UNKNOWN


@pytest.mark.parametrize(
    "condition",
    (
        OperationTerminalCondition.FAILED,
        OperationTerminalCondition.CANCELLED,
        OperationTerminalCondition.TIMED_OUT,
        OperationTerminalCondition.INTERRUPTED,
    ),
)
def test_result_projection_service_never_releases_result_ref_from_non_success_terminal(
    tmp_path: Path,
    condition: OperationTerminalCondition,
) -> None:
    """An incidental reference on any non-success receipt cannot become a result projection."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        root = tmp_path / f"non-success-result-{condition.value}"
        registry = _registry(result_projector=_project_result, result_schema_type=PublicProjectionResult)
        repository = OperationJournalRepository(storage_root=root)
        operands = operation_secure_reference_repository(objects=profile.repository)
        result_ref = asyncio.run(operands.put(ProjectionResult(result_code="must.not.escape"), written_at=_NOW))
        terminal = _terminal_snapshot(
            registry,
            result_ref=result_ref,
            condition=condition,
            effect=OperationEffect.NONE,
        )
        _write(root, repository, _running_snapshot(registry))
        asyncio.run(repository.commit_settlement(terminal, expected_revision=0, lease=_lease()))
        contract = registry.lookup_public_contract(_DEFINITION_ID)
        assert contract.result_schema is not None
        request = OperationResultProjectionRequestV1(
            operation_id=_OPERATION_ID,
            terminal_revision=terminal.revision,
            definition_contract_digest=contract.definition_contract_digest,
            result_schema=contract.result_schema,
        )

        result = asyncio.run(
            OperationResultProjectionService(reader=repository, registry=registry, operands=operands).resolve(
                request,
                PublicProjectionResult,
            )
        )

    assert isinstance(result, OperationResultProjectionRefusalV1)
    assert result.code is OperationResultProjectionRefusalCode.OPERATION_NOT_SUCCESSFUL


@pytest.mark.parametrize(
    ("stored", "expected_success"),
    [
        (ProjectionResult(result_code="identity.result"), True),
        (SafeReviewProjection(summary_code="wrong.stored.model"), False),
    ],
)
def test_identity_result_projection_validates_the_encrypted_stored_model(
    tmp_path: Path, stored: BaseModel, expected_success: bool
) -> None:
    """An identical public model needs no projector but still needs typed custody."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        root = tmp_path / "identity-result-durable"
        registry = _registry()
        repository = OperationJournalRepository(storage_root=root)
        operands = operation_secure_reference_repository(objects=profile.repository)
        result_ref = asyncio.run(operands.put(stored, written_at=_NOW))
        terminal = _terminal_snapshot(registry, result_ref=result_ref)
        _write(root, repository, _running_snapshot(registry))
        asyncio.run(repository.commit_settlement(terminal, expected_revision=0, lease=_lease()))
        contract = registry.lookup_public_contract(_DEFINITION_ID)
        assert contract.result_schema is not None
        request = OperationResultProjectionRequestV1(
            operation_id=_OPERATION_ID,
            terminal_revision=terminal.revision,
            definition_contract_digest=contract.definition_contract_digest,
            result_schema=contract.result_schema,
        )
        result = asyncio.run(
            OperationResultProjectionService(reader=repository, registry=registry, operands=operands).resolve(
                request, ProjectionResult
            )
        )

    if expected_success:
        assert isinstance(result, OperationResultProjectionSuccessV1)
        assert result.projection == stored
    else:
        assert isinstance(result, OperationResultProjectionRefusalV1)
        assert result.code is OperationResultProjectionRefusalCode.RESULT_PROJECTION_UNAVAILABLE


def test_refresh_target_resolves_only_authoritative_successful_terminal_receipt(tmp_path: Path) -> None:
    root = tmp_path / "durable"
    registry = _registry()
    repository = OperationJournalRepository(storage_root=root)
    terminal = _terminal_snapshot(registry)
    _write(root, repository, _running_snapshot(registry))
    asyncio.run(repository.commit_settlement(terminal, expected_revision=0, lease=_lease()))
    contract = registry.lookup_public_contract(_DEFINITION_ID)
    assert contract.workspace_refresh_target_schema is not None
    request = OperationWorkspaceRefreshTargetRequestV1(
        operation_id=_OPERATION_ID,
        terminal_revision=terminal.revision,
        definition_contract_digest=contract.definition_contract_digest,
        target_schema=contract.workspace_refresh_target_schema,
    )
    service = OperationWorkspaceRefreshTargetService(
        reader=OperationJournalRepository(storage_root=root),
        registry=registry,
    )

    result = asyncio.run(service.resolve(request, WorkspaceRefreshTarget))
    stale = asyncio.run(
        service.resolve(request.model_copy(update={"terminal_revision": terminal.revision + 1}), WorkspaceRefreshTarget)
    )
    digest_mismatch = asyncio.run(
        service.resolve(request.model_copy(update={"definition_contract_digest": "a" * 64}), WorkspaceRefreshTarget)
    )
    schema_mismatch = asyncio.run(
        service.resolve(request.model_copy(update={"target_schema": contract.request_schema}), WorkspaceRefreshTarget)
    )
    unsafe_output = asyncio.run(
        OperationWorkspaceRefreshTargetService(
            reader=repository,
            registry=_registry(refresh_adapter=_unsafe_refresh_target),
        ).resolve(request, WorkspaceRefreshTarget)
    )

    assert isinstance(result, OperationWorkspaceRefreshTargetSuccessV1)
    assert result.target == WorkspaceRefreshTarget(workspace_coordinate="profile:active")
    assert isinstance(stale, OperationWorkspaceRefreshTargetRefusalV1)
    assert isinstance(digest_mismatch, OperationWorkspaceRefreshTargetRefusalV1)
    assert isinstance(schema_mismatch, OperationWorkspaceRefreshTargetRefusalV1)
    assert isinstance(unsafe_output, OperationWorkspaceRefreshTargetRefusalV1)
    assert stale.code is OperationWorkspaceRefreshTargetRefusalCode.UNSAFE_REFRESH_TARGET
    assert digest_mismatch.code is OperationWorkspaceRefreshTargetRefusalCode.DEFINITION_CONTRACT_MISMATCH
    assert schema_mismatch.code is OperationWorkspaceRefreshTargetRefusalCode.REFRESH_SCHEMA_MISMATCH
    assert unsafe_output.code is OperationWorkspaceRefreshTargetRefusalCode.UNSAFE_REFRESH_TARGET
    assert "result_ref" not in type(request).model_fields


def test_projection_services_close_version_unknown_pending_terminal_and_adapter_refusals(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        registry = _registry()
        running_root = tmp_path / "running"
        running_repository = OperationJournalRepository(storage_root=running_root)
        _write(running_root, running_repository, _running_snapshot(registry))
        operands = operation_secure_reference_repository(objects=profile.repository)
        review_service = OperationReviewProjectionService(
            reader=running_repository,
            registry=registry,
            operands=operands,
            clock=lambda: _NOW,
        )
        contract = registry.lookup_public_contract(_DEFINITION_ID)
        assert contract.review_projection_schema is not None
        not_pending = asyncio.run(
            review_service.resolve(
                OperationReviewProjectionRequestV1(
                    reference=OperationReviewProjectionReferenceV1(
                        operation_id=_OPERATION_ID,
                        interaction_id=_INTERACTION_ID,
                        revision=0,
                        review_projection_schema=contract.review_projection_schema,
                        definition_contract_digest=contract.definition_contract_digest,
                        expires_at=None,
                    )
                ),
                SafeReviewProjection,
            )
        )
        unknown = asyncio.run(
            review_service.resolve(
                OperationReviewProjectionRequestV1(
                    reference=OperationReviewProjectionReferenceV1(
                        operation_id="9" * 64,
                        interaction_id=_INTERACTION_ID,
                        revision=0,
                        review_projection_schema=contract.review_projection_schema,
                        definition_contract_digest=contract.definition_contract_digest,
                        expires_at=None,
                    )
                ),
                SafeReviewProjection,
            )
        )
        unsupported = asyncio.run(
            review_service.resolve(
                OperationReviewProjectionVersionHeader(review_projection_version=2), SafeReviewProjection
            )
        )

        assert isinstance(not_pending, OperationReviewProjectionRefusalV1)
        assert isinstance(unknown, OperationReviewProjectionRefusalV1)
        assert isinstance(unsupported, OperationReviewProjectionRefusalV1)
        assert not_pending.code is OperationReviewProjectionRefusalCode.REVIEW_NOT_PENDING
        assert unknown.code is OperationReviewProjectionRefusalCode.UNKNOWN_OPERATION
        assert unsupported.code is OperationReviewProjectionRefusalCode.UNSUPPORTED_VERSION

        assert contract.workspace_refresh_target_schema is not None
        refresh_request = OperationWorkspaceRefreshTargetRequestV1(
            operation_id=_OPERATION_ID,
            terminal_revision=0,
            definition_contract_digest=contract.definition_contract_digest,
            target_schema=contract.workspace_refresh_target_schema,
        )
        refresh_service = OperationWorkspaceRefreshTargetService(reader=running_repository, registry=registry)
        not_terminal = asyncio.run(refresh_service.resolve(refresh_request, WorkspaceRefreshTarget))
        refresh_unsupported = asyncio.run(
            refresh_service.resolve(
                OperationWorkspaceRefreshTargetVersionHeader(refresh_target_version=2), WorkspaceRefreshTarget
            )
        )

        no_adapter_registry = _registry(include_refresh=False)
        no_adapter_root = tmp_path / "no-adapter"
        no_adapter_repository = OperationJournalRepository(storage_root=no_adapter_root)
        no_adapter_terminal = _terminal_snapshot(no_adapter_registry)
        _write(no_adapter_root, no_adapter_repository, _running_snapshot(no_adapter_registry))
        asyncio.run(no_adapter_repository.commit_settlement(no_adapter_terminal, expected_revision=0, lease=_lease()))
        no_adapter_contract = no_adapter_registry.lookup_public_contract(_DEFINITION_ID)
        assert no_adapter_contract.result_schema is not None
        unavailable = asyncio.run(
            OperationWorkspaceRefreshTargetService(
                reader=OperationJournalRepository(storage_root=no_adapter_root),
                registry=no_adapter_registry,
            ).resolve(
                OperationWorkspaceRefreshTargetRequestV1(
                    operation_id=_OPERATION_ID,
                    terminal_revision=1,
                    definition_contract_digest=no_adapter_contract.definition_contract_digest,
                    target_schema=no_adapter_contract.result_schema,
                ),
                WorkspaceRefreshTarget,
            )
        )

        assert isinstance(not_terminal, OperationWorkspaceRefreshTargetRefusalV1)
        assert isinstance(refresh_unsupported, OperationWorkspaceRefreshTargetRefusalV1)
        assert isinstance(unavailable, OperationWorkspaceRefreshTargetRefusalV1)
        assert not_terminal.code is OperationWorkspaceRefreshTargetRefusalCode.OPERATION_NOT_TERMINAL
        assert refresh_unsupported.code is OperationWorkspaceRefreshTargetRefusalCode.UNSUPPORTED_VERSION
        assert unavailable.code is OperationWorkspaceRefreshTargetRefusalCode.REFRESH_ADAPTER_UNAVAILABLE
