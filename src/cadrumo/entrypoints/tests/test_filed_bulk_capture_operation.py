"""Conformance proof for the recorded bulk filed-capture operation."""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.persistence.operations.journal import OperationJournalRepository
from cadrumo.adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from cadrumo.adapters.persistence.operations.secure_references import operation_secure_reference_repository
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.live.filed_bulk_capture_operation import (
    FILED_BULK_CAPTURE_DEFINITION_ID,
    FiledBulkCapturePublicResultV1,
    FiledBulkCaptureRequest,
    build_filed_bulk_capture_definition,
    build_filed_bulk_capture_registration,
)
from cadrumo.application.live.filed_data_ports import FiledDataCapturePort
from cadrumo.application.live.filed_history_operation import FiledHistoryComposition
from cadrumo.application.live.filed_observation_ports import FiledObservationPersistencePorts
from cadrumo.application.live.tests.filed_observation_test_support import in_memory_filed_observation_test_bundle
from cadrumo.application.operations.access_resolution import OperationAccessContext, resolve_operation_access
from cadrumo.application.operations.frontend_requests import (
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
)
from cadrumo.application.operations.models import OperationRequest
from cadrumo.application.operations.persistence.journal import OperationPersistedSnapshot
from cadrumo.application.operations.projection_services import OperationResultProjectionService
from cadrumo.application.operations.registry import OperationFrontendProjection, OperationRegistry
from cadrumo.application.operations.supervisor import OperationSupervisor
from cadrumo.application.storage.sync_runs.records import SyncRunRecordRepositoryProtocol
from cadrumo.application.user_profile.access_contracts import AccessAction, AccessDenialCode, Availability
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.core.operations import (
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
    profile_operation_subject,
)
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_NOW = datetime(2026, 8, 24, 20, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class _Composition:
    """Supply inert persistence ports and a filed-data port that must stay unused."""

    ports: FiledObservationPersistencePorts
    filed_data_port: FiledDataCapturePort


class _NeverOpenFiledDataPort:
    async def open_register(self, *, operation: str):
        raise AssertionError(f"unsupported-only preview unexpectedly opened register: {operation}")


class _ResourceScope:
    def __init__(self) -> None:
        self.closed = False

    @contextmanager
    def activate(self):
        yield

    async def close(self) -> None:
        self.closed = True


async def _run_to_terminal(supervisor: OperationSupervisor, operation_id: str) -> OperationPersistedSnapshot:
    await supervisor.start(operation_id)
    return await supervisor.settled(operation_id)


def test_supervisor_records_bulk_preview_for_exact_profile_without_register_access(tmp_path: Path) -> None:
    """A no-supported-pair preview is supervised, safely projected, and effect-free."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile, bundled_indexed_authority().operation() as authority:
        profile_id = UUID(profile.bucket_id)
        bundle = in_memory_filed_observation_test_bundle()
        filed_data_port = cast(FiledDataCapturePort, _NeverOpenFiledDataPort())
        composition = _Composition(ports=bundle.ports, filed_data_port=filed_data_port)
        resources = _ResourceScope()
        preflight_calls: list[tuple[UUID, PinnedAuthorityOperation]] = []

        def provider_preflight(profile_id_arg: UUID, pinned_authority: PinnedAuthorityOperation) -> None:
            preflight_calls.append((profile_id_arg, pinned_authority))

        def composition_factory(_output_root: Path) -> FiledHistoryComposition:
            return cast(FiledHistoryComposition, composition)

        def unused_sync_run_repository_factory() -> SyncRunRecordRepositoryProtocol:
            raise AssertionError("dry-run preview must not construct a sync-run repository")

        definition = build_filed_bulk_capture_definition(
            composition_factory=composition_factory,
            browser_resources_factory=lambda: resources,
            provider_preflight=provider_preflight,
            sync_run_repository_factory=cast(type[SyncRunRecordRepositoryProtocol], unused_sync_run_repository_factory),
        )
        registration = build_filed_bulk_capture_registration(definition)
        registry = OperationRegistry(definitions=(definition,), public_registrations=(registration,))
        request = OperationRequest(
            definition_id=FILED_BULK_CAPTURE_DEFINITION_ID,
            subject_ref=profile_operation_subject(profile.bucket_id),
            payload=FiledBulkCaptureRequest(
                profile_id=profile_id,
                output_root=tmp_path / "filed-bulk-output",
                year_from=2025,
                year_to=2025,
                modelos=("999",),
                dry_run=True,
            ),
        )
        access_context = OperationAccessContext(
            profile_id=profile_id,
            destination_id=uuid4(),
            action=AccessAction.SUBMIT,
            frontend=OperationFrontendProjection.CLI,
            contract=registration.contract,
            published_authority=Availability.AVAILABLE,
        )
        admitted = resolve_operation_access(registry=registry, request=request, context=access_context)
        assert admitted.request.profile_id == profile_id
        assert admitted.policy.requires_all_periods
        assert AccessAction.COMMIT in admitted.policy.actions

        foreign_profile_id = uuid4()
        foreign_request = request.model_copy(
            update={
                "subject_ref": profile_operation_subject(str(foreign_profile_id)),
                "payload": request.payload.model_copy(update={"profile_id": foreign_profile_id}),
            }
        )
        with pytest.raises(ProfileAccessRefusedError) as refusal:
            resolve_operation_access(registry=registry, request=foreign_request, context=access_context)
        assert refusal.value.reason is AccessDenialCode.PROFILE_MISMATCH

        durable_root = tmp_path / "operations"
        journal = OperationJournalRepository(storage_root=durable_root)
        leases = OperationLeaseFilesystemRepository(storage_root=durable_root)
        operands = operation_secure_reference_repository(objects=profile.repository)
        supervisor = OperationSupervisor(
            authority_operation=authority,
            registry=registry,
            journal=journal,
            event_stream=journal,
            leases=leases,
            operands=operands,
            owner_id="1" * 64,
            lease_token_factory=lambda: "2" * 64,
            clock=lambda: _NOW,
            lease_duration=timedelta(minutes=5),
        )
        result_service = OperationResultProjectionService(reader=journal, registry=registry, operands=operands)

        async def run():
            operation_id = await supervisor.submit(request, operation_id="3" * 64)
            terminal = await _run_to_terminal(supervisor, operation_id)
            contract = registry.lookup_public_contract(definition.definition_id)
            assert contract.result_schema is not None
            projected = await result_service.resolve(
                OperationResultProjectionRequestV1(
                    operation_id=operation_id,
                    terminal_revision=terminal.revision,
                    definition_contract_digest=contract.definition_contract_digest,
                    result_schema=contract.result_schema,
                ),
                FiledBulkCapturePublicResultV1,
            )
            return terminal, projected

        terminal, projected = asyncio.run(run())

    assert definition.definition_id == "live.filed-capture.bulk"
    assert terminal.lifecycle is OperationLifecycle.TERMINAL
    assert terminal.terminal_condition is OperationTerminalCondition.SUCCEEDED
    assert terminal.effect is OperationEffect.NONE
    assert isinstance(projected, OperationResultProjectionSuccessV1)
    assert isinstance(projected.projection, FiledBulkCapturePublicResultV1)
    result = projected.projection
    assert result.output_root == str(tmp_path / "filed-bulk-output")
    assert (result.modelos, result.year_from, result.year_to, result.dry_run) == (("999",), 2025, 2025, True)
    assert (result.captured_count, result.reached_count, result.failed_count) == (0, 0, 1)
    assert result.sync_run_ref is None
    assert result.observation_paths == ()
    assert result.artefact_refs == ()
    assert len(result.failures) == 1
    failure = result.failures[0]
    assert (failure.modelo, failure.year, failure.period, failure.expediente_id) == ("999", 2025, None, None)
    assert failure.error_type == "LiveApplicationInputError"
    assert "registry has no modelo definition" in failure.message
    assert preflight_calls == [(profile_id, authority)]
    assert resources.closed
