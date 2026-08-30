"""Live filed observations become amendable baselines only with complete evidence."""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.outbound.aeat.sede.observation_store import FiledDeclaracionObservationStore
from ....adapters.outbound.aeat.sede.schema import ObservedCasillaValue
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....application.modelo.tests import seed_ready_profile as _seed_ready_profile
from ....core import CasillaValueKind, validated_casilla_id
from ....domain.modelos.calculation_revision import CalculationRevisionAmendmentKind
from ....tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from ...modelo._action_errors import ExternalModeloImportError
from ...modelo._amendment_actions import amend_modelo_revision
from ...modelo._calculation_actions import get_calculation_revision
from ..filed_data_capture import _CaptureAccumulator
from ._filed_capture_history_support import (
    _CAPTURED_AT,
    _M303_RESULTADO_CASILLA,
    _MODELO_130_FIXTURE_CSV,
    _MODELO_303_FIXTURE_CSV,
    _stored_130_justificante_observation,
    _stored_303_justificante_observation,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_ID = "23333333-2333-4333-8333-233333333333"
_INCOME = validated_casilla_id("01")
_EXPENSE = validated_casilla_id("02")


@pytest.fixture
def runtime_profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE_ID) as profile:
        _seed_ready_profile(bucket_id=_PROFILE_ID)
        yield profile


def _complete_live_observation(tmp_path: Path):
    store = FiledDeclaracionObservationStore(tmp_path / "filed")
    observation = _stored_130_justificante_observation(store)
    return store, observation.model_copy(
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


def test_live_capture_creates_exact_immediately_amendable_baseline(
    runtime_profile: TestRuntimeProfile,
    tmp_path: Path,
) -> None:
    store, observation = _complete_live_observation(tmp_path)
    accumulator = _CaptureAccumulator()
    accumulator.absorb(observation, store=store, bucket_id=_PROFILE_ID, output_root=tmp_path)

    assert accumulator.justificante_csvs == [_MODELO_130_FIXTURE_CSV]
    assert len(accumulator.filing_record_ids) == 1
    work_units = WorkUnitCatalogueRepository().load()
    assert len(work_units) == 1
    filing = (
        ModeloRecordCatalogueRepository()
        .load()
        .current_for(
            bucket_id=_PROFILE_ID,
            modelo="130",
            filing_year=2026,
            period=observation.period,
        )
    )
    assert filing is not None
    revision = get_calculation_revision(filing.calculation_revision_id)
    assert filing.filed_at == _CAPTURED_AT
    assert revision.input_values_by_casilla_id == {_INCOME: " 001500.00 ", _EXPENSE: "300,0"}

    amended = amend_modelo_revision(
        from_filing_record_id=filing.filing_record_id,
        overrides={_INCOME: Decimal("1600")},
        amendment_kind=CalculationRevisionAmendmentKind.COMPLEMENTARIA,
        reason="live imported baseline correction",
        actor="operator",
    )
    assert amended.amends_filing_record_id == filing.filing_record_id


def test_justificante_only_capture_remains_metadata_scaffold_without_work_unit(
    runtime_profile: TestRuntimeProfile,
    tmp_path: Path,
) -> None:
    store = FiledDeclaracionObservationStore(tmp_path / "filed")
    observation = _stored_130_justificante_observation(store)
    accumulator = _CaptureAccumulator()
    accumulator.absorb(observation, store=store, bucket_id=_PROFILE_ID, output_root=tmp_path)

    assert accumulator.justificante_csvs == [_MODELO_130_FIXTURE_CSV]
    assert accumulator.filing_record_ids == []
    assert not WorkUnitCatalogueRepository().load()
    assert not CalculationRevisionCatalogueRepository().load()


def test_incomplete_live_manifest_refusal_creates_no_work_unit(
    runtime_profile: TestRuntimeProfile,
    tmp_path: Path,
) -> None:
    store, observation = _complete_live_observation(tmp_path)
    incomplete = observation.model_copy(update={"casillas": observation.casillas[:1]})
    accumulator = _CaptureAccumulator()

    with pytest.raises(ExternalModeloImportError):
        accumulator.absorb(incomplete, store=store, bucket_id=_PROFILE_ID, output_root=tmp_path)

    assert not WorkUnitCatalogueRepository().load()
    assert not CalculationRevisionCatalogueRepository().load()


def test_m303_live_capture_stays_on_observation_path_without_baseline(
    runtime_profile: TestRuntimeProfile,
    tmp_path: Path,
) -> None:
    store = FiledDeclaracionObservationStore(tmp_path / "filed")
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
    accumulator = _CaptureAccumulator()
    accumulator.absorb(observation, store=store, bucket_id=_PROFILE_ID, output_root=tmp_path)

    assert accumulator.justificante_csvs == [_MODELO_303_FIXTURE_CSV]
    assert accumulator.observations_for_calculation == [observation]
    assert accumulator.filing_record_ids == []
    assert not WorkUnitCatalogueRepository().load()
    assert not CalculationRevisionCatalogueRepository().load()
    assert not ModeloRecordCatalogueRepository().load()


def test_nonnumeric_live_capture_stays_on_observation_path_without_baseline(
    runtime_profile: TestRuntimeProfile,
    tmp_path: Path,
) -> None:
    store, complete = _complete_live_observation(tmp_path)
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
    accumulator = _CaptureAccumulator()
    accumulator.absorb(observation, store=store, bucket_id=_PROFILE_ID, output_root=tmp_path)

    assert accumulator.justificante_csvs == [_MODELO_130_FIXTURE_CSV]
    assert accumulator.observations_for_calculation == [observation]
    assert accumulator.filing_record_ids == []
    assert not WorkUnitCatalogueRepository().load()
    assert not CalculationRevisionCatalogueRepository().load()
    assert not ModeloRecordCatalogueRepository().load()
