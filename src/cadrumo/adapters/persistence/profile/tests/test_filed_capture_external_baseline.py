"""Live filed observations become amendable baselines only with complete evidence."""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.adapters.outbound.aeat.sede.filed_observation_persistence import (
    BaselineImportAdapter,
    BucketEventRepositoryAdapter,
    CalculationObservationRepositoryAdapter,
    FiledDeclarationTransformationAdapter,
    FiledObservationParserAdapter,
    FiledObservationStoreAdapter,
    FilingRepositoryAdapter,
    IvaHistoryRepositoryAdapter,
    IvaObservationPersistenceAdapter,
    JustificanteRepositoryAdapter,
)
from cadrumo.adapters.outbound.aeat.sede.observation_store import FiledDeclaracionObservationStore
from cadrumo.adapters.outbound.aeat.sede.schema import ObservedCasillaValue
from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from cadrumo.adapters.persistence.profile.iva_compensation_history import IvaCompensationHistoryRepository
from cadrumo.adapters.persistence.profile.justificante import JustificanteRepository
from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.profile.tests._file_flow_support import calculation_ports_for_test
from cadrumo.adapters.persistence.profile.tests._filed_capture_history_support import (
    _CAPTURED_AT,
    _M303_RESULTADO_CASILLA,
    _MODELO_130_FIXTURE_CSV,
    _MODELO_303_FIXTURE_CSV,
    _stored_130_justificante_observation,
    _stored_303_justificante_observation,
)
from cadrumo.adapters.persistence.profile.tests.import_flow_support import seed_ready_profile
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.adapters.persistence.storage.tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from cadrumo.application.live.filed_data_capture import FiledCaptureAccumulator
from cadrumo.application.live.filed_observation_ports import FiledObservationPersistencePorts
from cadrumo.application.modelo.action_errors import ExternalModeloImportError
from cadrumo.application.modelo.amendment_actions import amend_modelo_revision
from cadrumo.application.modelo.calculation_actions import get_calculation_revision
from cadrumo.application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from cadrumo.core.casilla_id import validated_casilla_id
from cadrumo.core.casilla_value_kind import CasillaValueKind
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.modelos.calculation_revision_amendment import CalculationRevisionAmendmentKind
from cadrumo.entrypoints.adapter_composition import build_amendment_action_ports

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_ID = "23333333-2333-4333-8333-233333333333"
_INCOME = validated_casilla_id("01")
_EXPENSE = validated_casilla_id("02")


@pytest.fixture
def runtime_profile(tmp_path: Path, operation: PinnedAuthorityOperation) -> Iterator[TestRuntimeProfile]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE_ID) as profile:
        seed_ready_profile(bucket_id=_PROFILE_ID)
        yield profile


def _complete_live_observation(tmp_path: Path, objects: SecureObjectRepository):
    store = FiledDeclaracionObservationStore(tmp_path / "filed", objects=objects)
    observation = _stored_130_justificante_observation(store)
    return observation.model_copy(
        update={
            "casillas": (
                ObservedCasillaValue(
                    casilla_id=_INCOME,
                    value=" 001500.00 ",
                    value_kind=CasillaValueKind.NUMERIC,
                    source_artefact_kind="submitted_file",
                    source_locator="submitted-file:01",
                    confidence=1.0,
                ),
                ObservedCasillaValue(
                    casilla_id=_EXPENSE,
                    value="300,0",
                    value_kind=CasillaValueKind.NUMERIC,
                    source_artefact_kind="submitted_file",
                    source_locator="submitted-file:02",
                    confidence=1.0,
                ),
            ),
            "extraction_coverage": {"submitted_file": 1.0},
        },
    )


def _filed_capture_ports(
    *,
    runtime_profile: TestRuntimeProfile,
    operation: PinnedAuthorityOperation,
    tmp_path: Path,
) -> FiledObservationPersistencePorts:
    objects = runtime_profile.repository
    work_units = WorkUnitCatalogueRepository(bucket_id=_PROFILE_ID, objects=objects)
    filing = ModeloRecordCatalogueRepository(bucket_id=_PROFILE_ID, objects=objects)
    events = BucketEventHistoryRepository(objects=objects)
    justificantes = JustificanteRepository(objects=objects)
    observations = CalculationObservationRepository(bucket_id=_PROFILE_ID, objects=objects)
    history = IvaCompensationHistoryRepository(bucket_id=_PROFILE_ID, objects=objects)
    return FiledObservationPersistencePorts(
        parser=FiledObservationParserAdapter(),
        transformation=FiledDeclarationTransformationAdapter(operation=operation),
        observation_persistence=FiledObservationStoreAdapter(root=tmp_path / "filed", objects=objects),
        calculation_repository=CalculationObservationRepositoryAdapter(repository=observations),
        iva_history_repository=IvaHistoryRepositoryAdapter(repository=history),
        iva_observation_persistence=IvaObservationPersistenceAdapter(),
        justificante_repository=JustificanteRepositoryAdapter(repository=justificantes),
        filing_repository=FilingRepositoryAdapter(repository=filing),
        bucket_event_repository=BucketEventRepositoryAdapter(repository=events),
        baseline_import=BaselineImportAdapter(
            work_lifecycle_ports=WorkLifecyclePorts(
                work_unit_repository=work_units,
                bucket_event_repository=events,
            ),
            calculation_repository=CalculationRevisionCatalogueRepository(bucket_id=_PROFILE_ID, objects=objects),
            filing_repository=filing,
            justificante_repository=justificantes,
            observation_repository=observations,
        ),
    )


def test_live_capture_creates_exact_immediately_amendable_baseline(
    runtime_profile: TestRuntimeProfile,
    operation: PinnedAuthorityOperation,
    tmp_path: Path,
) -> None:
    observation = _complete_live_observation(tmp_path, runtime_profile.repository)
    ports = _filed_capture_ports(runtime_profile=runtime_profile, operation=operation, tmp_path=tmp_path)
    accumulator = FiledCaptureAccumulator(operation=operation)
    accumulator.absorb(observation, ports=ports, bucket_id=_PROFILE_ID, output_root=tmp_path)

    assert accumulator.justificante_csvs == [_MODELO_130_FIXTURE_CSV]
    assert len(accumulator.filing_record_ids) == 1
    work_units = WorkUnitCatalogueRepository(bucket_id=_PROFILE_ID, objects=runtime_profile.repository).load()
    assert len(work_units) == 1
    filing = (
        ModeloRecordCatalogueRepository(bucket_id=_PROFILE_ID, objects=runtime_profile.repository)
        .load()
        .current_for(
            bucket_id=_PROFILE_ID,
            modelo="130",
            filing_year=2026,
            period=observation.period,
        )
    )
    assert filing is not None
    with calculation_ports_for_test(bucket_id=_PROFILE_ID) as _calculation_ports_100:
        revision = get_calculation_revision(filing.calculation_revision_id, ports=_calculation_ports_100)
    assert filing.filed_at == _CAPTURED_AT
    assert revision.input_values_by_casilla_id == {_INCOME: " 001500.00 ", _EXPENSE: "300,0"}
    with calculation_ports_for_test(bucket_id=_PROFILE_ID) as _calculation_ports_110:
        amended = amend_modelo_revision(
            from_filing_record_id=filing.filing_record_id,
            overrides={_INCOME: Decimal("1600")},
            amendment_kind=CalculationRevisionAmendmentKind.COMPLEMENTARIA,
            reason="live imported baseline correction",
            actor="operator",
            ports=build_amendment_action_ports(
                bucket_id=_PROFILE_ID,
                operation=_calculation_ports_110.operation,
            ),
        )
    assert amended.amends_filing_record_id == filing.filing_record_id


def test_justificante_only_capture_remains_metadata_scaffold_without_work_unit(
    runtime_profile: TestRuntimeProfile,
    operation: PinnedAuthorityOperation,
    tmp_path: Path,
) -> None:
    store = FiledDeclaracionObservationStore(tmp_path / "filed", objects=runtime_profile.repository)
    observation = _stored_130_justificante_observation(store)
    ports = _filed_capture_ports(runtime_profile=runtime_profile, operation=operation, tmp_path=tmp_path)
    accumulator = FiledCaptureAccumulator(operation=operation)
    accumulator.absorb(observation, ports=ports, bucket_id=_PROFILE_ID, output_root=tmp_path)

    assert accumulator.justificante_csvs == [_MODELO_130_FIXTURE_CSV]
    assert accumulator.filing_record_ids == []
    assert not WorkUnitCatalogueRepository(bucket_id=_PROFILE_ID, objects=runtime_profile.repository).load()
    assert not CalculationRevisionCatalogueRepository(bucket_id=_PROFILE_ID, objects=runtime_profile.repository).load()


def test_incomplete_live_manifest_refusal_creates_no_work_unit(
    runtime_profile: TestRuntimeProfile,
    operation: PinnedAuthorityOperation,
    tmp_path: Path,
) -> None:
    observation = _complete_live_observation(tmp_path, runtime_profile.repository)
    incomplete = observation.model_copy(update={"casillas": observation.casillas[:1]})
    ports = _filed_capture_ports(runtime_profile=runtime_profile, operation=operation, tmp_path=tmp_path)
    accumulator = FiledCaptureAccumulator(operation=operation)

    with pytest.raises(ExternalModeloImportError):
        accumulator.absorb(incomplete, ports=ports, bucket_id=_PROFILE_ID, output_root=tmp_path)

    assert not WorkUnitCatalogueRepository(bucket_id=_PROFILE_ID, objects=runtime_profile.repository).load()
    assert not CalculationRevisionCatalogueRepository(bucket_id=_PROFILE_ID, objects=runtime_profile.repository).load()


def test_m303_live_capture_stays_on_observation_path_without_baseline(
    runtime_profile: TestRuntimeProfile,
    operation: PinnedAuthorityOperation,
    tmp_path: Path,
) -> None:
    store = FiledDeclaracionObservationStore(tmp_path / "filed", objects=runtime_profile.repository)
    observation = _stored_303_justificante_observation(store).model_copy(
        update={
            "casillas": (
                ObservedCasillaValue(
                    casilla_id=_M303_RESULTADO_CASILLA,
                    value="125.00",
                    value_kind=CasillaValueKind.NUMERIC,
                    source_artefact_kind="submitted_file",
                    source_locator="submitted-file:69",
                    confidence=1.0,
                ),
            ),
        },
    )
    ports = _filed_capture_ports(runtime_profile=runtime_profile, operation=operation, tmp_path=tmp_path)
    accumulator = FiledCaptureAccumulator(operation=operation)
    accumulator.absorb(observation, ports=ports, bucket_id=_PROFILE_ID, output_root=tmp_path)

    assert accumulator.justificante_csvs == [_MODELO_303_FIXTURE_CSV]
    assert accumulator.observations_for_calculation == [observation]
    assert accumulator.filing_record_ids == []
    assert not WorkUnitCatalogueRepository(bucket_id=_PROFILE_ID, objects=runtime_profile.repository).load()
    assert not CalculationRevisionCatalogueRepository(bucket_id=_PROFILE_ID, objects=runtime_profile.repository).load()
    assert not ModeloRecordCatalogueRepository(bucket_id=_PROFILE_ID, objects=runtime_profile.repository).load()


def test_nonnumeric_live_capture_stays_on_observation_path_without_baseline(
    runtime_profile: TestRuntimeProfile,
    operation: PinnedAuthorityOperation,
    tmp_path: Path,
) -> None:
    complete = _complete_live_observation(tmp_path, runtime_profile.repository)
    observation = complete.model_copy(
        update={
            "casillas": (
                *complete.casillas,
                ObservedCasillaValue(
                    casilla_id=validated_casilla_id("03"),
                    value="ACTIVIDAD PROFESIONAL",
                    value_kind=CasillaValueKind.TEXT,
                    source_artefact_kind="declaration_pdf",
                    source_locator="declaration-pdf:03",
                    confidence=1.0,
                ),
            ),
        },
    )
    ports = _filed_capture_ports(runtime_profile=runtime_profile, operation=operation, tmp_path=tmp_path)
    accumulator = FiledCaptureAccumulator(operation=operation)
    accumulator.absorb(observation, ports=ports, bucket_id=_PROFILE_ID, output_root=tmp_path)

    assert accumulator.justificante_csvs == [_MODELO_130_FIXTURE_CSV]
    assert accumulator.observations_for_calculation == [observation]
    assert accumulator.filing_record_ids == []
    assert not WorkUnitCatalogueRepository(bucket_id=_PROFILE_ID, objects=runtime_profile.repository).load()
    assert not CalculationRevisionCatalogueRepository(bucket_id=_PROFILE_ID, objects=runtime_profile.repository).load()
    assert not ModeloRecordCatalogueRepository(bucket_id=_PROFILE_ID, objects=runtime_profile.repository).load()
