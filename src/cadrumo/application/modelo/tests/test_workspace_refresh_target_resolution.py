"""Real resolution of the typed Modelo workspace refresh target.

Drives the shipped registration through the real journal repository and the
real resolving service rather than calling the adapter directly: an adapter
that returns the right model proves nothing if no enrolment reaches it. The
assertions below distinguish a genuine Modelo target from the generic
operations-layer envelope, and prove the subject validation fails closed.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from ....adapters.persistence.operations.journal import OperationJournalRepository
from ....adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from ....core import (
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
    Period,
)
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.modelos import derive_work_unit_id
from ...operations.frontend_contracts import (
    OperationWorkspaceRefreshTargetRefusalCode,
    OperationWorkspaceRefreshTargetRefusalV1,
    OperationWorkspaceRefreshTargetRequestV1,
    OperationWorkspaceRefreshTargetSuccessV1,
)
from ...operations.models import OperationIdentity, OperationRequest, OperationTerminalReceipt
from ...operations.persistence.events import OperationPhaseEvent, OperationTerminalEvent
from ...operations.persistence.journal import OperationPersistedSnapshot
from ...operations.persistence.leases import OperationOwnerLease, operation_conflict_scope_reference
from ...operations.projection_services import OperationWorkspaceRefreshTargetService
from ...operations.registry import OperationRegistry, OperationRequestStoragePolicy
from ..operation_definitions import (
    MODELO_WORK_RENAME_OPERATION_DEFINITION_ID,
    MODELO_WORKSPACE_REFRESH_TARGET_SCHEMA_ID,
    ModeloWorkRenameRequest,
    build_modelo_lifecycle_operation_definitions,
    build_modelo_lifecycle_operation_registrations,
    resolve_modelo_work_unit_refresh_target,
)
from ..workspace_models import ModeloWorkspaceRefreshTargetV1

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_NOW = datetime(2026, 3, 4, 9, 0, 0, tzinfo=UTC)
_OPERATION_ID = "1" * 64
_DEFINITION_ID = MODELO_WORK_RENAME_OPERATION_DEFINITION_ID
_BUCKET_ID = "0f629c46-1dc8-4cb1-8d02-aa0ee4f45a45"


def _work_unit_id() -> str:
    """Derive a real work-unit identifier from the live registry authority."""
    period = Period.from_year_and_code(2025, "1T")
    revision_id = bundled_authority().snapshot("131", filing_year=2025, period=period.registry_token).revision.id
    return derive_work_unit_id(
        bucket_id=_BUCKET_ID, modelo="131", filing_year=2025, period=period, revision_id=revision_id
    )


def _registry() -> OperationRegistry:
    """The shipped Modelo enrolments, composed exactly as production composes them."""
    definitions = build_modelo_lifecycle_operation_definitions()
    return OperationRegistry(
        definitions=definitions,
        public_registrations=build_modelo_lifecycle_operation_registrations(definitions),
    )


def _canonical_request(subject_ref: str) -> str:
    """The real rename request this settled operation carried, journalled inline."""
    return OperationRequest[ModeloWorkRenameRequest](
        definition_id=_DEFINITION_ID,
        subject_ref=subject_ref,
        payload=ModeloWorkRenameRequest(work_unit_id=subject_ref, new_name="renamed unit", actor="operator"),
    ).model_dump_json()


def _lease(subject_ref: str) -> OperationOwnerLease:
    return OperationOwnerLease(
        operation_id=_OPERATION_ID,
        scope_ref=operation_conflict_scope_reference(definition_id=_DEFINITION_ID, subject_ref=subject_ref),
        owner_id="5" * 64,
        token="6" * 64,
        acquired_at=_NOW,
        expires_at=_NOW + timedelta(hours=1),
    )


def _snapshots(
    registry: OperationRegistry, subject_ref: str
) -> tuple[OperationPersistedSnapshot, OperationPersistedSnapshot]:
    identity = OperationIdentity(operation_id=_OPERATION_ID, definition_id=_DEFINITION_ID, subject_ref=subject_ref)
    running = OperationPersistedSnapshot(
        identity=identity,
        definition_contract_digest=registry.lookup_public_contract(_DEFINITION_ID).definition_contract_digest,
        request_storage=OperationRequestStoragePolicy.CREDENTIAL_FREE_JOURNAL,
        request_reference="8" * 64,
        credential_free_request_json=_canonical_request(subject_ref),
        revision=0,
        lifecycle=OperationLifecycle.RUNNING,
        phase_code="modelo.work.rename",
        started_at=_NOW,
        updated_at=_NOW,
        execution_deadline=_NOW + timedelta(hours=1),
        cleanup_deadline=None,
        cancellation_requested_at=None,
        cancellation_acknowledged_at=None,
        cancellation_deferred=False,
        event_cursor=1,
        events=(
            OperationPhaseEvent(
                identity=identity,
                revision=0,
                sequence=1,
                timestamp=_NOW,
                code="modelo.work.rename",
                phase_code="modelo.work.rename",
            ),
        ),
    )
    receipt = OperationTerminalReceipt(
        identity=identity,
        revision=1,
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=OperationEffect.UPDATED,
        settled_at=_NOW + timedelta(minutes=1),
        result_ref="result:modelo-rename-complete",
    )
    terminal = OperationPersistedSnapshot.model_validate(
        running.model_copy(
            update={
                "revision": 1,
                "lifecycle": OperationLifecycle.TERMINAL,
                "terminal_condition": OperationTerminalCondition.SUCCEEDED,
                "effect": OperationEffect.UPDATED,
                "updated_at": receipt.settled_at,
                "event_cursor": 2,
                "events": (
                    OperationTerminalEvent(
                        identity=identity,
                        revision=1,
                        sequence=2,
                        timestamp=receipt.settled_at,
                        code="operation.terminal",
                        receipt=receipt,
                    ),
                ),
                "terminal_receipt": receipt,
            }
        ).model_dump()
    )
    return running, terminal


def _resolve(tmp_path: Path, subject_ref: str):
    """Persist a real settled operation and resolve its refresh target."""
    root = tmp_path / "durable"
    registry = _registry()
    repository = OperationJournalRepository(storage_root=root)
    running, terminal = _snapshots(registry, subject_ref)

    lease = _lease(subject_ref)
    observed = asyncio.run(OperationLeaseFilesystemRepository(storage_root=root).acquire(lease, observed_at=_NOW))
    assert observed.current == lease
    asyncio.run(repository.create(running, lease=lease))
    asyncio.run(repository.commit(terminal, expected_revision=0, lease=lease))

    contract = registry.lookup_public_contract(_DEFINITION_ID)
    assert contract.workspace_refresh_target_schema is not None
    request = OperationWorkspaceRefreshTargetRequestV1(
        operation_id=_OPERATION_ID,
        terminal_revision=terminal.revision,
        definition_contract_digest=contract.definition_contract_digest,
        target_schema=contract.workspace_refresh_target_schema,
    )
    service = OperationWorkspaceRefreshTargetService(
        reader=OperationJournalRepository(storage_root=root), registry=registry
    )
    return asyncio.run(service.resolve(request))


def test_a_real_enrolled_operation_resolves_a_genuine_modelo_target(tmp_path: Path) -> None:
    """The resolved target is the Modelo workspace target, not the generic envelope."""
    work_unit_id = _work_unit_id()
    result = _resolve(tmp_path, work_unit_id)

    assert isinstance(result, OperationWorkspaceRefreshTargetSuccessV1)
    target = result.target
    assert isinstance(target, ModeloWorkspaceRefreshTargetV1)
    assert target.work_unit_id == work_unit_id
    assert target.contract_version == 1


def test_a_subject_that_is_not_a_work_unit_refuses_rather_than_resolving(tmp_path: Path) -> None:
    """The subject validation fails closed; a foreign subject never yields a target."""
    result = _resolve(tmp_path, "profile:active")

    assert isinstance(result, OperationWorkspaceRefreshTargetRefusalV1)
    assert result.code is OperationWorkspaceRefreshTargetRefusalCode.UNSAFE_REFRESH_TARGET


def test_every_shipped_modelo_enrolment_declares_the_one_shared_refresh_schema() -> None:
    """One canonical refresh target across the family, never a per-definition copy."""
    registry = _registry()
    declared = {
        registration.contract.definition_id: registration.contract.workspace_refresh_target_schema
        for registration in registry.public_registrations
    }
    assert declared, "no Modelo enrolment was composed"
    for definition_id, schema in declared.items():
        assert schema is not None, f"{definition_id} declares no workspace refresh target"
        assert schema.schema_id == MODELO_WORKSPACE_REFRESH_TARGET_SCHEMA_ID, definition_id

    fingerprints = {schema.schema_fingerprint for schema in declared.values() if schema is not None}
    assert len(fingerprints) == 1, fingerprints


def test_the_adapter_itself_refuses_a_subject_that_is_not_a_work_unit() -> None:
    """The adapter validates its own subject rather than relying on the resolver.

    The resolving service revalidates whatever an adapter returns, so a
    non-work-unit subject would be refused even by a trusting adapter. This
    asserts the adapter's own guard independently, so the fail-closed
    behaviour does not silently become the service's job alone.
    """
    identity = OperationIdentity(operation_id=_OPERATION_ID, definition_id=_DEFINITION_ID, subject_ref="profile:active")
    receipt = OperationTerminalReceipt(
        identity=identity,
        revision=1,
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=OperationEffect.UPDATED,
        settled_at=_NOW,
        result_ref="result:modelo-rename-complete",
    )

    with pytest.raises(ValidationError):
        resolve_modelo_work_unit_refresh_target(receipt)

    work_unit_id = _work_unit_id()
    accepted = resolve_modelo_work_unit_refresh_target(
        receipt.model_copy(update={"identity": identity.model_copy(update={"subject_ref": work_unit_id})})
    )
    assert accepted.work_unit_id == work_unit_id
