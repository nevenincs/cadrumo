"""Conformance proof for the recorded bulk filed-capture operation."""

from __future__ import annotations

import asyncio
from contextlib import AbstractAsyncContextManager, contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.live.filed_bulk_capture_operation import (
    FILED_BULK_CAPTURE_DEFINITION_ID,
    FiledBulkCapturePublicResultV1,
    FiledBulkCaptureRequest,
    build_filed_bulk_capture_definition,
    build_filed_bulk_capture_registration,
)
from cadrumo.application.live.filed_data_ports import (
    DeferredFiledObservations,
    FiledArtefactSink,
    FiledDataCapturePort,
    FiledDataRegisterPort,
    FiledDeclarationAvailabilityReportProtocol,
    FiledEffectGuard,
)
from cadrumo.application.live.filed_history_operation import FiledHistoryComposition
from cadrumo.application.live.filed_observation_ports import FiledObservationPersistencePorts, FiledObservationProtocol
from cadrumo.application.live.remote_state_models import BulkFiledDataCaptureReport, FiledCapturePairOutcome
from cadrumo.application.live.session import SessionWriteReporter
from cadrumo.application.live.tests.filed_observation_test_support import in_memory_filed_observation_test_bundle
from cadrumo.application.operations.access_resolution import OperationAccessContext, resolve_operation_access
from cadrumo.application.operations.frontend_requests import (
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
)
from cadrumo.application.operations.models import OperationRequest
from cadrumo.application.operations.persistence.journal import OperationPersistedSnapshot
from cadrumo.application.operations.registry import OperationFrontendProjection, OperationRegistry
from cadrumo.application.operations.supervisor import OperationSupervisor
from cadrumo.application.storage.sync_runs.records import SyncRunRecordRepositoryProtocol
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.core.operations import (
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
    profile_operation_subject,
)
from cadrumo.core.period import Period
from cadrumo.core.storage_taxonomy import StorageCategory
from cadrumo.core.storage_taxonomy_locations import storage_path
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.contracts.access_vocabulary import AccessAction, Availability

from .supervised_operation_rig import build_supervised_operation

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_NOW = datetime(2026, 8, 24, 20, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class _Composition:
    """Supply inert persistence ports and a filed-data port that must stay unused."""

    ports: FiledObservationPersistencePorts
    filed_data_port: FiledDataCapturePort


class _NeverOpenFiledDataPort:
    def open_register(
        self,
        *,
        operation: str,
        authority_operation: PinnedAuthorityOperation | None = None,
        effect_guard: FiledEffectGuard | None = None,
        on_session_write: SessionWriteReporter | None = None,
    ) -> AbstractAsyncContextManager[FiledDataRegisterPort]:
        raise AssertionError(f"unsupported-only preview unexpectedly opened register: {operation}")

    async def discover_availability(
        self,
        *,
        operation: str,
        effect_guard: FiledEffectGuard | None = None,
        on_session_write: SessionWriteReporter | None = None,
    ) -> FiledDeclarationAvailabilityReportProtocol:
        raise AssertionError("unsupported-only preview unexpectedly read register availability")

    async def capture_source_observations(
        self,
        revision: ModeloRevision,
        *,
        filing_year: int,
        period: Period,
        artefact_sink: FiledArtefactSink | None = None,
        operation: str,
        effect_guard: FiledEffectGuard | None = None,
        on_session_write: SessionWriteReporter | None = None,
    ) -> tuple[FiledObservationProtocol, ...]:
        raise AssertionError("unsupported-only preview unexpectedly captured filed observations")

    async def capture_source_observations_deferred(
        self,
        revision: ModeloRevision,
        *,
        filing_year: int,
        period: Period,
        operation: str,
        effect_guard: FiledEffectGuard | None = None,
        on_session_write: SessionWriteReporter | None = None,
    ) -> DeferredFiledObservations:
        raise AssertionError("unsupported-only preview unexpectedly captured deferred filed observations")


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


@pytest.mark.parametrize("names_root", [True, False], ids=["named_root", "configured_default_root"])
def test_supervisor_records_bulk_preview_for_exact_profile_without_register_access(
    tmp_path: Path, names_root: bool
) -> None:
    """A no-supported-pair preview is supervised, safely projected, and effect-free.

    A request that names no output root is captured under the configured filed-declarations directory.
    """
    with isolated_runtime_profile(tmp_path=tmp_path) as profile, bundled_indexed_authority().operation() as authority:
        profile_id = UUID(profile.bucket_id)
        output_root = tmp_path / "filed-bulk-output" if names_root else storage_path(StorageCategory.FILED_DECLARATIONS)
        composed_roots: list[Path] = []
        bundle = in_memory_filed_observation_test_bundle()
        filed_data_port = _NeverOpenFiledDataPort()
        composition = _Composition(ports=bundle.ports, filed_data_port=filed_data_port)
        resources = _ResourceScope()
        preflight_calls: list[tuple[UUID, PinnedAuthorityOperation]] = []

        def provider_preflight(profile_id_arg: UUID, pinned_authority: PinnedAuthorityOperation) -> None:
            preflight_calls.append((profile_id_arg, pinned_authority))

        def composition_factory(output_root: Path, *, operation: PinnedAuthorityOperation) -> FiledHistoryComposition:
            composed_roots.append(output_root)
            return cast(FiledHistoryComposition, composition)

        def unused_sync_run_repository_factory() -> SyncRunRecordRepositoryProtocol:
            raise AssertionError("dry-run preview must not construct a sync-run repository")

        definition = build_filed_bulk_capture_definition(
            composition_factory=composition_factory,
            browser_resources_factory=lambda: resources,
            provider_preflight=provider_preflight,
            sync_run_repository_factory=unused_sync_run_repository_factory,
        )
        registration = build_filed_bulk_capture_registration(definition)
        registry = OperationRegistry(definitions=(definition,), public_registrations=(registration,))
        request = OperationRequest(
            definition_id=FILED_BULK_CAPTURE_DEFINITION_ID,
            subject_ref=profile_operation_subject(profile.bucket_id),
            payload=FiledBulkCaptureRequest(
                profile_id=profile_id,
                output_root=output_root if names_root else None,
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

        _, _, operands, supervisor, result_service = build_supervised_operation(
            tmp_path=tmp_path, objects=profile.repository, authority=authority, registry=registry, now=_NOW
        )

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
            receipt = terminal.terminal_receipt
            assert receipt is not None and receipt.result_ref is not None
            report = await operands.resolve(receipt.result_ref, BulkFiledDataCaptureReport)
            assert registration.result_projector is not None
            accounting_projections: list[FiledBulkCapturePublicResultV1] = []
            # These synthetic scalar reports exercise secure serialization and
            # the registered projector, independently of provider acquisition.
            for dry_run, attempted, completed, rows, reached, captured in (
                (True, True, True, 2, 2, 0),
                (True, False, False, 0, 0, 0),
                (False, True, True, 2, 2, 2),
            ):
                pair = FiledCapturePairOutcome(
                    modelo="303",
                    year=2025,
                    walk_attempted=attempted,
                    walk_completed=completed,
                    row_count=rows,
                    reached_count=reached,
                    captured_count=captured,
                )
                accounting_report = report.model_copy(
                    update={
                        "modelos": ("303",),
                        "dry_run": dry_run,
                        "pair_outcomes": (pair,),
                        "reached_count": reached,
                        "captured_count": captured,
                        "observation_paths": ("first", "second") if captured else (),
                        "calculation_observation_count": 1 if captured else 0,
                        "calculation_observation_keys": ("303:2025:1T",) if captured else (),
                        "failed_count": 0,
                        "failures": (),
                    }
                )
                accounting_report.require_consistent()
                reference = await operands.put(accounting_report, written_at=_NOW)
                restored = await operands.resolve(reference, BulkFiledDataCaptureReport)
                public = registration.result_projector(restored, receipt)
                wire = FiledBulkCapturePublicResultV1.model_validate_json(public.model_dump_json())
                assert wire.pair_outcomes == (pair,)
                accounting_projections.append(wire)
            return terminal, projected, accounting_projections

        terminal, projected, accounting_projections = asyncio.run(run())

    assert definition.definition_id == "live.filed-capture.bulk"
    assert terminal.lifecycle is OperationLifecycle.TERMINAL
    assert terminal.terminal_condition is OperationTerminalCondition.SUCCEEDED
    assert terminal.effect is OperationEffect.NONE
    assert isinstance(projected, OperationResultProjectionSuccessV1)
    assert isinstance(projected.projection, FiledBulkCapturePublicResultV1)
    result = projected.projection
    assert result.output_root == str(output_root)
    assert composed_roots == [output_root]
    assert (result.modelos, result.year_from, result.year_to, result.dry_run) == (("999",), 2025, 2025, True)
    assert (result.captured_count, result.reached_count, result.failed_count) == (0, 0, 1)
    assert result.sync_run_ref is None
    assert result.observation_paths == ()
    assert result.artefact_refs == ()
    assert len(result.pair_outcomes) == 1
    pair = result.pair_outcomes[0]
    assert (pair.modelo, pair.year) == ("999", 2025)
    assert (pair.walk_attempted, pair.walk_completed) == (False, False)
    assert (pair.row_count, pair.reached_count, pair.captured_count) == (0, 0, 0)
    assert len(result.failures) == 1
    failure = result.failures[0]
    assert (failure.modelo, failure.year, failure.period, failure.expediente_id) == ("999", 2025, None, None)
    assert failure.error_type == "LiveApplicationInputError"
    assert "registry has no modelo definition" in failure.message
    assert preflight_calls == [(profile_id, authority)]
    assert resources.closed
    preview, unwalked, persisted = accounting_projections
    assert (preview.pair_outcomes[0].row_count, preview.reached_count, preview.captured_count) == (2, 2, 0)
    assert unwalked.pair_outcomes[0].walk_attempted is False
    assert unwalked.pair_outcomes[0].walk_completed is False
    assert (persisted.pair_outcomes[0].row_count, persisted.captured_count) == (2, 2)
    assert persisted.calculation_observation_count == 1
    assert persisted.calculation_observation_keys == ("303:2025:1T",)
