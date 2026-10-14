"""A client reconciles a filing by capturing first and then naming what the capture returned.

The sequence is two registered operations on the real supervisor over a real
encrypted profile: a capture, then ``modelo.reconcile.pull`` addressed by the
filing's coordinates and by the identifier the capture's own result carries. Only
the tax agency's site is replaced, by a register that serves one synthetic
declaration; persistence, the work catalogue, reconciliation and the journal are
the production ones.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from contextlib import AbstractContextManager, asynccontextmanager, nullcontext
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import cast
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, ValidationError

from ...adapters.outbound.aeat.sede.schema import (
    FiledDeclaracionArtefact,
    FiledDeclaracionObservation,
    ObservedCasillaValue,
)
from ...adapters.persistence.operations.journal import OperationJournalRepository
from ...adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from ...adapters.persistence.operations.secure_references import operation_secure_reference_repository
from ...adapters.persistence.profile.modelo_reconciliation import ModeloReconciliationPersistence
from ...adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ...adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ...adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from ...application.live.filed_data_ports import (
    DeferredFiledObservation,
    FiledArtefactSink,
    FiledDataRegisterPort,
    FiledEffectGuard,
    FiledRegisterDeclarationProtocol,
)
from ...application.live.filed_history_operation import FiledHistoryComposition
from ...application.live.filed_observation_ports import FiledObservationProtocol
from ...application.live.filed_single_capture_operation import (
    FILED_SINGLE_CAPTURE_DEFINITION_ID,
    FiledSingleCapturePublicResultV1,
    FiledSingleCaptureRequest,
    build_filed_single_capture_definition,
    build_filed_single_capture_registration,
)
from ...application.live.session import SessionWriteReporter
from ...application.modelo.reconciliation_import_operation import ModeloReconciliationImportProjection
from ...application.modelo.reconciliation_pull_operation import (
    MODELO_RECONCILIATION_PULL_OPERATION_DEFINITION_ID,
    ModeloReconciliationPullRequest,
    build_modelo_reconciliation_pull_definition,
    build_modelo_reconciliation_pull_registration,
    reconciliation_pull_source_ref,
)
from ...application.modelo.reconciliation_records import (
    ModeloReconciliationEvidenceKind,
    ModeloReconciliationVerdict,
)
from ...application.operations.frontend_requests import (
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
)
from ...application.operations.models import OperationRequest
from ...application.operations.persistence.journal import OperationPersistedSnapshot
from ...application.operations.projection_services import OperationResultProjectionService
from ...application.operations.public_period import PublicPeriod
from ...application.operations.registry import OperationFrontendProjection, OperationRegistry
from ...application.operations.supervisor import OperationSupervisor
from ...core.casilla_value_kind import CasillaValueKind
from ...core.config import override_settings
from ...core.hashing import sha256_hex
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.period import Period
from ...domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ...domain.calculations.registry.schema_references import RegistrySnapshotRef
from ...domain.modelos.work_unit import WorkUnit
from ...tests.aeat_literal_fixtures import SEDE_TEST_URL_FIXTURE
from ..justificante_composition import build_justificante_capture_service, load_reconciliation_filed_observation
from ..live_state_composition import compose_filed_observation_persistence_ports
from . import modelo_operation_test_support
from . import registered_executor_case_support as conformance
from .test_modelo_reconciliation_frontend_parity import _JUSTIFICANTE_FIXTURE, _session_host

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_NOW = datetime(2026, 9, 29, 12, tzinfo=UTC)
_EXPEDIENTE_ID = "202513000000001Z"
_DECLARATION_BODY = b"synthetic filed declaration"


@dataclass(frozen=True, slots=True)
class _Declaration:
    """One synthetic register row for the seeded filing."""

    modelo: str
    ejercicio: int
    period: Period
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


class _DeferredObservation:
    def __init__(self, observation: FiledDeclaracionObservation) -> None:
        self._observation = observation

    def persist_artefacts(self, sink: FiledArtefactSink) -> FiledObservationProtocol:
        artefact = self._observation.artefacts[0]
        key = (self._observation.modelo, self._observation.ejercicio, self._observation.period, _EXPEDIENTE_ID)
        stored = sink(key, artefact, _DECLARATION_BODY)
        return self._observation.model_copy(
            update={"artefacts": (artefact.model_copy(update={"storage_ref": stored.storage_ref}),)}
        )


class _Register:
    walk_timeout_ms = 1000

    def __init__(self, declaration: _Declaration, observation: FiledDeclaracionObservation) -> None:
        self._declaration = declaration
        self._observation = observation

    async def walk(self, *, modelo: str, ejercicio: int) -> tuple[FiledRegisterDeclarationProtocol, ...]:
        assert (modelo, ejercicio) == (self._declaration.modelo, self._declaration.ejercicio)
        return (self._declaration,)

    async def capture_observation_deferred(
        self, declaration: FiledRegisterDeclarationProtocol
    ) -> DeferredFiledObservation:
        assert declaration is self._declaration
        return _DeferredObservation(self._observation)

    async def capture_observation(
        self, declaration: FiledRegisterDeclarationProtocol, *, artefact_sink: FiledArtefactSink | None = None
    ) -> FiledObservationProtocol:
        raise AssertionError("the recorded single operation must use deferred capture")


class _FiledPort:
    """The tax agency's site as the capture sees it: one register serving one declaration."""

    def __init__(self, register: _Register) -> None:
        self._register = register

    @asynccontextmanager
    async def open_register(
        self,
        *,
        operation: str,
        authority_operation: PinnedAuthorityOperation | None = None,
        effect_guard: FiledEffectGuard | None = None,
        on_session_write: SessionWriteReporter | None = None,
    ) -> AsyncGenerator[FiledDataRegisterPort]:
        yield self._register


@dataclass(frozen=True, slots=True)
class _Composition:
    ports: object
    filed_data_port: object


class _Resources:
    """The browser process the capture would own; the synthetic site needs none."""

    def activate(self) -> AbstractContextManager[None]:
        return nullcontext()

    async def close(self) -> None:
        return None


def _observation(unit: WorkUnit, values: dict[str, Decimal]) -> FiledDeclaracionObservation:
    return FiledDeclaracionObservation(
        modelo=str(unit.modelo),
        ejercicio=unit.filing_year,
        period=unit.period,
        expediente_id=_EXPEDIENTE_ID,
        status="ALTA",
        presented_at=datetime(2025, 4, 20, tzinfo=UTC),
        authenticated_identity=modelo_operation_test_support.SEEDED_SOURCE_TAX_ID,
        artefacts=(
            FiledDeclaracionArtefact(
                kind="submitted_file",
                source_url=SEDE_TEST_URL_FIXTURE,
                content_type="text/plain",
                byte_count=len(_DECLARATION_BODY),
                sha256=sha256_hex(_DECLARATION_BODY),
                captured_at=_NOW,
            ),
        ),
        casillas=tuple(
            ObservedCasillaValue(
                casilla_id=key,
                value=str(value),
                value_kind=CasillaValueKind.NUMERIC,
                source_artefact_kind="submitted_file",
                source_locator="synthetic",
                confidence=1.0,
            )
            for key, value in values.items()
        ),
        extraction_coverage={"submitted_file": 1.0},
        registry_snapshot_ref=RegistrySnapshotRef(
            modelo=unit.modelo,
            modelo_year=unit.filing_year,
            period=unit.period.registry_token,
            revision_id=unit.revision_id,
        ),
    )


class _Run:
    """Submit registered operations to one real supervisor and read their settled results."""

    def __init__(self, supervisor: OperationSupervisor, registry: OperationRegistry, resolver) -> None:
        self._supervisor = supervisor
        self._registry = registry
        self._resolver = resolver

    async def execute(
        self, profile_id: UUID, definition_id: str, payload: BaseModel, result_type: type[BaseModel]
    ) -> tuple[OperationPersistedSnapshot, BaseModel]:
        request = OperationRequest(
            definition_id=definition_id, subject_ref=profile_operation_subject(str(profile_id)), payload=payload
        )
        operation_id = await self._supervisor.submit(request, operation_id=uuid4().hex + uuid4().hex)
        await self._supervisor.start(operation_id)
        terminal = await self._supervisor.settled(operation_id)
        contract = self._registry.lookup_public_contract(definition_id)
        assert contract.result_schema is not None
        projected = await self._resolver.resolve(
            OperationResultProjectionRequestV1(
                operation_id=operation_id,
                terminal_revision=terminal.revision,
                definition_contract_digest=contract.definition_contract_digest,
                result_schema=contract.result_schema,
            ),
            result_type,
        )
        assert isinstance(projected, OperationResultProjectionSuccessV1)
        assert isinstance(projected.projection, result_type)
        return terminal, projected.projection


def test_a_client_captures_then_reconciles_with_the_identifier_the_capture_returned(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile, bundled_indexed_authority().operation() as authority:
        profile_id = UUID(profile.bucket_id)
        revision_id = modelo_operation_test_support.seeded_modelo_calculation_revision(profile_id, operation=authority)
        revision = CalculationRevisionCatalogueRepository().load(operation=authority).get(revision_id)
        assert revision is not None
        unit = WorkUnitCatalogueRepository().load().get(revision.work_unit_id)
        assert unit is not None
        values = dict(revision.casilla_values)
        values["19"] = Decimal("123.45")
        observation = _observation(unit, values)
        declaration = _Declaration(modelo=str(unit.modelo), ejercicio=unit.filing_year, period=unit.period)
        filed_port = _FiledPort(_Register(declaration, observation))
        output_root = tmp_path / "filed-output"

        def composition_factory(output_root: Path, *, operation: PinnedAuthorityOperation) -> FiledHistoryComposition:
            return cast(
                FiledHistoryComposition,
                _Composition(
                    ports=compose_filed_observation_persistence_ports(
                        bucket_id=profile.bucket_id,
                        output_root=output_root,
                        objects=profile.repository,
                        operation=operation,
                    ),
                    filed_data_port=filed_port,
                ),
            )

        capture_definition = build_filed_single_capture_definition(
            composition_factory=composition_factory,
            browser_resources_factory=lambda: _Resources(),
            provider_preflight=lambda _profile, _authority: None,
        )
        pull_definition = build_modelo_reconciliation_pull_definition(
            build_justificante_capture_service, load_reconciliation_filed_observation
        )
        registry = OperationRegistry(
            definitions=(capture_definition, pull_definition),
            public_registrations=(
                build_filed_single_capture_registration(capture_definition),
                build_modelo_reconciliation_pull_registration(pull_definition),
            ),
        )
        durable_root = tmp_path / "operations"
        journal = OperationJournalRepository(storage_root=durable_root)
        operands = operation_secure_reference_repository(objects=profile.repository)
        supervisor = OperationSupervisor(
            authority_operation=authority,
            registry=registry,
            journal=journal,
            event_stream=journal,
            leases=OperationLeaseFilesystemRepository(storage_root=durable_root),
            operands=operands,
            owner_id="1" * 64,
            lease_token_factory=lambda: "2" * 64,
            clock=lambda: _NOW,
            lease_duration=timedelta(minutes=5),
        )
        run = _Run(
            supervisor, registry, OperationResultProjectionService(reader=journal, registry=registry, operands=operands)
        )

        async def sequence():
            captured_terminal, captured = await run.execute(
                profile_id,
                FILED_SINGLE_CAPTURE_DEFINITION_ID,
                FiledSingleCaptureRequest(
                    profile_id=profile_id,
                    output_root=output_root,
                    modelo=str(unit.modelo),
                    year=unit.filing_year,
                    period=unit.period.registry_token,
                    expediente_id=_EXPEDIENTE_ID,
                    limit=1,
                ),
                FiledSingleCapturePublicResultV1,
            )
            assert isinstance(captured, FiledSingleCapturePublicResultV1)
            (observation_id,) = captured.observation_ids
            before = tuple(ModeloReconciliationPersistence().iter_records())
            reconciled_terminal, reconciled = await run.execute(
                profile_id,
                MODELO_RECONCILIATION_PULL_OPERATION_DEFINITION_ID,
                ModeloReconciliationPullRequest(
                    profile_id=profile_id,
                    modelo=str(unit.modelo),
                    year=unit.filing_year,
                    period=PublicPeriod.from_period(unit.period),
                    source_kind=ModeloReconciliationEvidenceKind.DECLARATION,
                    observation_id=observation_id,
                    calculation_revision_id=revision_id,
                ),
                ModeloReconciliationImportProjection,
            )
            return captured_terminal, captured, observation_id, before, reconciled_terminal, reconciled

        captured_terminal, captured, observation_id, before, reconciled_terminal, reconciled = asyncio.run(sequence())
        after = tuple(ModeloReconciliationPersistence().iter_records())

    assert captured_terminal.terminal_condition is OperationTerminalCondition.SUCCEEDED
    assert captured.captured_count == 1
    assert len(observation_id) == 64
    assert captured.observation_paths[0].endswith(observation_id)
    assert reconciled_terminal.terminal_condition is OperationTerminalCondition.SUCCEEDED
    assert reconciled_terminal.effect is OperationEffect.UPDATED
    assert isinstance(reconciled, ModeloReconciliationImportProjection)
    assert reconciled.work_unit_id == unit.work_unit_id
    assert reconciled.source_path.endswith(observation_id)
    assert reconciled.verdict is ModeloReconciliationVerdict.MISMATCHES
    assert next(diff for diff in reconciled.diffs if diff.field_name == "19").evidence_value == "123.45"
    assert len(after) == len(before) + 1


@pytest.mark.parametrize("frontend", sorted(OperationFrontendProjection))
def test_a_receipt_capture_is_reconciled_by_the_filings_coordinates_on_every_frontend(
    tmp_path: Path, operation: PinnedAuthorityOperation, frontend: OperationFrontendProjection
) -> None:
    """The snapshot a receipt capture stored, and the filing's coordinates, are all a client sends."""
    with conformance._runtime(
        tmp_path / "runtime", cleanup=conformance._CloseWitness(), execution_caller_reader=_session_host(frontend)
    ) as (driver, registry, profile_id):
        subject_ref = profile_operation_subject(str(profile_id))
        with override_settings(cadrumo_active_profile=str(profile_id)):
            unit = modelo_operation_test_support.seeded_modelo_work_unit(profile_id, operation=operation)
            pdf = _JUSTIFICANTE_FIXTURE.read_bytes()
            snapshot = build_justificante_capture_service(str(profile_id)).capture(
                modelo=str(unit.modelo),
                filing_year=unit.filing_year,
                period=unit.period,
                expediente_id="202413000000001Z",
                csv="ABCD1234EFGH",
                pdf_bytes=pdf,
                pdf_sha256=sha256_hex(pdf),
                captured_at=datetime(2026, 9, 29, tzinfo=UTC),
            )
            before = tuple(ModeloReconciliationPersistence().iter_records())
            submitted, observed = asyncio.run(
                driver.run(
                    definition_id=MODELO_RECONCILIATION_PULL_OPERATION_DEFINITION_ID,
                    subject_ref=subject_ref,
                    payload=ModeloReconciliationPullRequest(
                        profile_id=profile_id,
                        snapshot_id=snapshot.snapshot_id,
                        modelo=str(unit.modelo),
                        year=unit.filing_year,
                        period=PublicPeriod.from_period(unit.period),
                    ),
                )
            )
            after = tuple(ModeloReconciliationPersistence().iter_records())
            absent = asyncio.run(
                driver.run(
                    definition_id=MODELO_RECONCILIATION_PULL_OPERATION_DEFINITION_ID,
                    subject_ref=subject_ref,
                    payload=ModeloReconciliationPullRequest(
                        profile_id=profile_id,
                        snapshot_id=snapshot.snapshot_id,
                        modelo=str(unit.modelo),
                        year=unit.filing_year,
                        period=PublicPeriod(filing_year=unit.filing_year, code="4T"),
                    ),
                )
            )[1]
            unchanged = tuple(ModeloReconciliationPersistence().iter_records())
        assert observed.projection.terminal_condition is OperationTerminalCondition.SUCCEEDED
        assert observed.projection.effect is OperationEffect.UPDATED
        projection = conformance._resolve_result_projection(
            driver,
            registry,
            definition_id=MODELO_RECONCILIATION_PULL_OPERATION_DEFINITION_ID,
            operation_id=submitted.receipt.operation_id,
            terminal_revision=observed.projection.revision,
            projection_type=ModeloReconciliationImportProjection,
        )

    assert projection.work_unit_id == unit.work_unit_id
    assert projection.source_path == reconciliation_pull_source_ref(
        ModeloReconciliationEvidenceKind.JUSTIFICANTE, snapshot.snapshot_id, None
    )
    assert len(after) == len(before) + 1
    assert absent.projection.terminal_condition is not OperationTerminalCondition.SUCCEEDED
    assert absent.projection.effect is OperationEffect.NONE
    assert unchanged == after


@pytest.mark.parametrize(
    ("modelo", "year"), [(None, None), ("130", None), ("130", 2025)], ids=["nothing", "modelo-only", "no-period"]
)
def test_a_pull_that_names_neither_a_work_unit_nor_a_complete_filing_is_not_a_request(
    modelo: str | None, year: int | None
) -> None:
    with pytest.raises(ValidationError, match="work unit id, or modelo, year and period"):
        ModeloReconciliationPullRequest(profile_id=uuid4(), snapshot_id="a" * 64, modelo=modelo, year=year)
