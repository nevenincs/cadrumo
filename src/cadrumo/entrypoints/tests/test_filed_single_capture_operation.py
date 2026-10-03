"""Conformance proof for the recorded single-pair filed-capture operation."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from typing import cast
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.outbound.aeat.sede.schema import FiledDeclaracionArtefact, FiledDeclaracionObservation
from cadrumo.adapters.persistence.operations.journal import OperationJournalRepository
from cadrumo.adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from cadrumo.adapters.persistence.operations.secure_references import operation_secure_reference_repository
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.calculations.observations_repository import ObservationEnvelopePayload
from cadrumo.application.live.filed_data_ports import (
    DeferredFiledObservation,
    DeferredFiledObservations,
    FiledArtefactSink,
    FiledDataCapturePort,
    FiledDataRegisterPort,
    FiledDeclarationAvailabilityReportProtocol,
    FiledEffectGuard,
    FiledRegisterDeclarationProtocol,
)
from cadrumo.application.live.filed_history_operation import FiledHistoryComposition
from cadrumo.application.live.filed_observation_ports import (
    FiledObservationArtefactProtocol,
    FiledObservationPersistencePorts,
    FiledObservationProtocol,
)
from cadrumo.application.live.filed_single_capture_operation import (
    FILED_SINGLE_CAPTURE_DEFINITION_ID,
    FiledSingleCapturePublicResultV1,
    FiledSingleCaptureRequest,
    build_filed_single_capture_definition,
    build_filed_single_capture_registration,
)
from cadrumo.application.live.remote_state_models import FiledDataCaptureReport
from cadrumo.application.live.session import SessionWriteReporter
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
from cadrumo.application.user_profile.access_contracts import AccessAction, AccessDenialCode, Availability
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.core.operations import (
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
    profile_operation_subject,
)
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.calculations.registry.schema import ModeloRevision

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_NOW = datetime(2026, 8, 24, 20, tzinfo=UTC)
_PERIOD = Period.from_year_and_code(2025, "0A")
_EXPEDIENTE_ID = "202510013522222A"
_DECLARATION_BODY = b"synthetic filed declaration"


@dataclass(frozen=True, slots=True)
class _Declaration:
    """One synthetic register row accepted by the real capture service."""

    modelo: str = "100"
    ejercicio: int = 2025
    period: Period = field(default_factory=lambda: _PERIOD)
    expediente_id: str = _EXPEDIENTE_ID
    estado: str = "ALTA"
    presented_at: datetime = _NOW
    tipo_solicitud: str | None = None
    observaciones: str | None = None
    justificante_link_text: str | None = None
    archive_link_text: str | None = "synthetic-file"
    declaration_copy_link_text: str | None = None
    justificante_cell_index: int = 7
    archive_cell_index: int | None = 8
    declaration_copy_cell_index: int | None = None


class _SyntheticDeferredObservation:
    def __init__(self, observation: FiledDeclaracionObservation, is_guarded: Callable[[], bool]) -> None:
        self._observation = observation
        self._is_guarded = is_guarded

    def persist_artefacts(self, sink: FiledArtefactSink) -> FiledObservationProtocol:
        assert self._is_guarded(), "downloaded bytes reached local persistence outside the operation fence"
        artifact = self._observation.artefacts[0]
        stored = sink(
            (self._observation.modelo, self._observation.ejercicio, self._observation.period, _EXPEDIENTE_ID),
            artifact,
            _DECLARATION_BODY,
        )
        stored_artifact = artifact.model_copy(update={"storage_ref": stored.storage_ref})
        return self._observation.model_copy(update={"artefacts": (stored_artifact,)})


class _SyntheticRegister:
    walk_timeout_ms = 1000

    def __init__(
        self,
        declaration: _Declaration,
        observation: FiledDeclaracionObservation,
        is_guarded: Callable[[], bool],
    ) -> None:
        self._declaration = declaration
        self._observation = observation
        self._is_guarded = is_guarded
        self.remote_capture_count = 0

    async def walk(self, *, modelo: str, ejercicio: int) -> tuple[FiledRegisterDeclarationProtocol, ...]:
        assert (modelo, ejercicio) == ("100", 2025)
        return (self._declaration,)

    async def capture_observation_deferred(
        self,
        declaration: FiledRegisterDeclarationProtocol,
    ) -> DeferredFiledObservation:
        assert declaration is self._declaration
        assert not self._is_guarded(), "remote acquisition should finish before the local write fence"
        self.remote_capture_count += 1
        return _SyntheticDeferredObservation(self._observation, self._is_guarded)

    async def capture_observation(
        self,
        declaration: FiledRegisterDeclarationProtocol,
        *,
        artefact_sink: FiledArtefactSink | None = None,
    ) -> FiledObservationProtocol:
        del declaration, artefact_sink
        raise AssertionError("the recorded single operation must use deferred capture")


class _SyntheticFiledPort:
    def __init__(self, register: _SyntheticRegister) -> None:
        self._register = register
        self.opened_operations: list[str] = []

    @asynccontextmanager
    async def open_register(
        self,
        *,
        operation: str,
        authority_operation: PinnedAuthorityOperation | None = None,
        effect_guard: FiledEffectGuard | None = None,
        on_session_write: SessionWriteReporter | None = None,
    ) -> AsyncIterator[FiledDataRegisterPort]:
        assert effect_guard is not None and on_session_write is not None
        self.opened_operations.append(operation)
        yield self._register

    async def discover_availability(
        self, *, operation: str, **_kwargs: object
    ) -> FiledDeclarationAvailabilityReportProtocol:
        del operation
        raise AssertionError("single-pair capture must not discover register options")

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
        del revision, filing_year, period, artefact_sink, operation
        raise AssertionError("single-pair capture must not capture filing sources")

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
        del revision, filing_year, period, operation
        raise AssertionError("single-pair capture must not defer filing source capture")


@dataclass(frozen=True, slots=True)
class _Composition:
    ports: FiledObservationPersistencePorts
    filed_data_port: FiledDataCapturePort


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


def test_supervisor_binds_single_capture_to_exact_profile_and_projects_guarded_accounting(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A real supervisor records one synthetic capture under its exact profile fence."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile, bundled_indexed_authority().operation() as authority:
        profile_id = UUID(profile.bucket_id)
        snapshot = authority.snapshot("100", filing_year=2025, period="0A")
        observation = FiledDeclaracionObservation(
            modelo="100",
            ejercicio=2025,
            period=_PERIOD,
            expediente_id=_EXPEDIENTE_ID,
            status="ALTA",
            presented_at=_NOW,
            authenticated_identity="12345678Z",
            artefacts=(
                FiledDeclaracionArtefact(
                    kind="submitted_file",
                    source_url="https://test.invalid/declared-file",
                    content_type="application/octet-stream",
                    byte_count=len(_DECLARATION_BODY),
                    sha256=sha256(_DECLARATION_BODY).hexdigest(),
                    captured_at=_NOW,
                ),
            ),
            extraction_coverage={"submitted_file": 1.0},
            registry_snapshot_ref=snapshot.snapshot_ref,
        )
        declaration = _Declaration()
        guard_depth = 0
        guarded_writes: list[str] = []

        def is_guarded() -> bool:
            return guard_depth > 0

        bundle = in_memory_filed_observation_test_bundle()
        register = _SyntheticRegister(declaration, observation, is_guarded)
        filed_port = _SyntheticFiledPort(register)
        resource_scope = _ResourceScope()

        observation_persistence = bundle.ports.observation_persistence
        persist_artefact = observation_persistence.persist_artefact
        persist_observation = observation_persistence.persist_observation

        def guarded_persist_artefact(
            _self: object,
            observation_key: tuple[str, int, Period, str],
            artifact: FiledObservationArtefactProtocol,
            body: bytes,
        ) -> FiledObservationArtefactProtocol:
            assert is_guarded()
            guarded_writes.append("artefact")
            return persist_artefact(observation_key, artifact, body)

        def guarded_persist_observation(_self: object, observed: FiledObservationProtocol) -> Path:
            assert is_guarded()
            guarded_writes.append("manifest")
            return persist_observation(observed)

        monkeypatch.setattr(type(observation_persistence), "persist_artefact", guarded_persist_artefact)
        monkeypatch.setattr(type(observation_persistence), "persist_observation", guarded_persist_observation)

        calculation_repository = bundle.ports.calculation_repository
        save_calculation_observation = calculation_repository.save

        def guarded_save_calculation_observation(_self: object, payload: ObservationEnvelopePayload) -> None:
            assert is_guarded()
            guarded_writes.append("calculation")
            save_calculation_observation(payload)

        monkeypatch.setattr(type(calculation_repository), "save", guarded_save_calculation_observation)

        from cadrumo.application.live import filed_single_capture_operation as operation_module

        capture_filed_data = operation_module.capture_filed_data
        guard_entries = 0

        async def capture_with_tracked_guard(
            *,
            filed_data_port: FiledDataCapturePort,
            modelo: str,
            year: int,
            output_root: Path,
            ports: FiledObservationPersistencePorts,
            period: Period | None = None,
            expediente_id: str | None = None,
            limit: int | None = None,
            effect_guard: FiledEffectGuard | None = None,
            on_session_write: SessionWriteReporter | None = None,
            operation: PinnedAuthorityOperation | None = None,
        ) -> FiledDataCaptureReport:
            assert effect_guard is not None
            assert on_session_write is not None

            @asynccontextmanager
            async def tracked_guard() -> AsyncIterator[None]:
                nonlocal guard_depth, guard_entries
                async with effect_guard():
                    guard_depth += 1
                    guard_entries += 1
                    try:
                        yield
                    finally:
                        guard_depth -= 1

            return await capture_filed_data(
                filed_data_port=filed_data_port,
                modelo=modelo,
                year=year,
                output_root=output_root,
                ports=ports,
                period=period,
                expediente_id=expediente_id,
                limit=limit,
                effect_guard=tracked_guard,
                on_session_write=on_session_write,
                operation=operation,
            )

        monkeypatch.setattr(operation_module, "capture_filed_data", capture_with_tracked_guard)

        composition = _Composition(ports=bundle.ports, filed_data_port=filed_port)
        provider_preflights: list[tuple[UUID, PinnedAuthorityOperation]] = []

        def provider_preflight(profile: UUID, pinned_authority: PinnedAuthorityOperation) -> None:
            provider_preflights.append((profile, pinned_authority))

        def composition_factory(_output_root: Path) -> FiledHistoryComposition:
            return cast(FiledHistoryComposition, composition)

        definition = build_filed_single_capture_definition(
            composition_factory=composition_factory,
            browser_resources_factory=lambda: resource_scope,
            provider_preflight=provider_preflight,
        )
        registration = build_filed_single_capture_registration(definition)
        registry = OperationRegistry(definitions=(definition,), public_registrations=(registration,))
        request = OperationRequest(
            definition_id=FILED_SINGLE_CAPTURE_DEFINITION_ID,
            subject_ref=profile_operation_subject(profile.bucket_id),
            payload=FiledSingleCaptureRequest(
                profile_id=profile_id,
                output_root=tmp_path / "filed-output",
                modelo="100",
                year=2025,
                period="0A",
                expediente_id=_EXPEDIENTE_ID,
                limit=1,
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
        assert admitted.request.period_independent
        assert admitted.request.periods == frozenset()
        assert admitted.policy.requires_all_periods
        assert AccessAction.COMMIT in admitted.policy.actions

        foreign_profile_id = uuid4()
        assert foreign_profile_id != profile_id
        foreign_request = request.model_copy(
            update={
                "subject_ref": profile_operation_subject(str(foreign_profile_id)),
                "payload": request.payload.model_copy(update={"profile_id": foreign_profile_id}),
            }
        )
        with pytest.raises(ProfileAccessRefusedError) as refusal:
            resolve_operation_access(
                registry=registry,
                request=foreign_request,
                context=access_context,
            )
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
                FiledSingleCapturePublicResultV1,
            )
            return terminal, projected

        terminal, projected = asyncio.run(run())

    assert definition.definition_id == "live.filed-capture.single"
    assert terminal.lifecycle is OperationLifecycle.TERMINAL
    assert terminal.terminal_condition is OperationTerminalCondition.SUCCEEDED
    assert terminal.effect is OperationEffect.UPDATED
    assert isinstance(projected, OperationResultProjectionSuccessV1)
    assert isinstance(projected.projection, FiledSingleCapturePublicResultV1)
    result = projected.projection
    assert result.output_root == str(tmp_path / "filed-output")
    assert (result.modelo, result.year) == ("100", 2025)
    assert (result.captured_count, result.reached_count) == (1, 1)
    assert result.observation_paths == (str(Path("memory-observations") / "1" / "manifest.json"),)
    assert result.artefact_refs == ("memory-artefact:1",)
    assert result.casilla_count == 0
    assert result.calculation_observation_count == 1
    assert result.calculation_observation_keys == ("100:2025:0A",)
    assert result.justificante_metadata_count == 0
    assert result.filing_evidence_stamped_count == 0
    assert result.filing_evidence_conflict_count == 0
    assert provider_preflights == [(profile_id, authority)]
    assert filed_port.opened_operations == ["live-filed-read"]
    assert register.remote_capture_count == 1
    assert guard_entries == 2
    assert guarded_writes == ["artefact", "manifest", "calculation"]
    assert resource_scope.closed
