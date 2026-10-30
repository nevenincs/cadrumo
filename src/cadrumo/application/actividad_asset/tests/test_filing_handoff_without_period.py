"""A filing handoff states the Modelo 100 boxes alone when no Modelo 130 period is asked for."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from cadrumo.application.actividad_asset.activity_asset_contracts import ActivityAssetFilingHandoffRequest
from cadrumo.application.actividad_asset.activity_asset_projections import ActivityAssetFilingHandoffProjection
from cadrumo.application.actividad_asset.activity_asset_results import ActivityAssetFilingHandoffResult
from cadrumo.application.actividad_asset.operation_dtos import ActivityAssetFilingHandoffSnapshot
from cadrumo.application.actividad_asset.operations import ActivityAssetFilingHandoff, ActivityAssetOperations
from cadrumo.core.casilla_id import CasillaId
from cadrumo.core.period import Period
from cadrumo.domain.contribuyente.tax_residence import ResidenceTerritory
from cadrumo.domain.renta.actividad_asset.election import (
    AcquiredCondition,
    ActivityAssetAmortizationElection,
    AmortizationMethod,
    DirectEstimationRegime,
)
from cadrumo.domain.renta.actividad_asset.errors import ActividadAssetValidationError
from cadrumo.domain.renta.actividad_asset.lifecycle import (
    AcquisitionLineageReference,
    AcquisitionShape,
    ActivityAssetBasis,
    ActivityAssetRevision,
    AssetBasisStage,
    AssetKind,
    OpeningAmortizationHistory,
    OpeningHistoryStatus,
)
from cadrumo.domain.renta.actividad_asset.register_records import ActivityAssetDescriptorFacts
from cadrumo.domain.renta.actividad_asset.schedule import (
    AssetScheduleHistory,
    ScheduleAuthority,
    ScheduledAmortizationCharge,
    schedule_charge,
)

from .ledger_support import MemoryLedger, acquisition_transaction
from .register_support import MemoryRepository, memory_register_authority

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_ACQUISITION = acquisition_transaction()
_AUTHORITY = {"logical_generation": "a" * 64, "reader_incarnation": "b" * 64}


def _revision(
    *,
    number: int = 1,
    supersedes: str | None = None,
    basis: str = "2000",
    class_key: str = "equipo-informacion-software",
) -> ActivityAssetRevision:
    return ActivityAssetRevision(
        asset_id="laptop-1",
        revision_number=number,
        supersedes_revision_id=supersedes,
        acquisition=AcquisitionLineageReference(
            observed_transaction_id=_ACQUISITION.transaction_id,
            invoice_evidence_id="invoice-1",
            evidence_fingerprint="b" * 64,
        ),
        acquisition_shape=AcquisitionShape.PRIMARY_PURCHASE,
        asset_kind=AssetKind.MATERIAL,
        basis=ActivityAssetBasis(
            stage=AssetBasisStage.BUSINESS_ALLOCATED,
            basis_amount=Decimal(basis),
            non_deductible_iva=Decimal("0"),
            prior_allocation_provenance="ledger allocation allocation-1",
        ),
        in_service_date=date(2025, 1, 1),
        opening_history=OpeningAmortizationHistory(status=OpeningHistoryStatus.KNOWN, accumulated_amount=Decimal("0")),
        acquired_condition=AcquiredCondition.NEW,
        amortization=ActivityAssetAmortizationElection(
            regime=DirectEstimationRegime.SIMPLIFIED,
            method=AmortizationMethod.LINEAR,
            authority_class_key=class_key,
        ),
    )


def _forecast(
    revision: ActivityAssetRevision,
    *,
    covered_from: date,
    covered_until: date,
    history: AssetScheduleHistory,
    requested_free_amount: Decimal | None = None,
) -> ScheduledAmortizationCharge:
    return schedule_charge(
        revision,
        ScheduleAuthority(
            tax_year=covered_from.year,
            asset_kind=revision.asset_kind,
            method=revision.amortization.method,
            election_fingerprint=revision.amortization.fingerprint,
            annual_rate=Decimal("0.26"),
            authority_generation="handoff-test-v1",
            source_reference="handoff test table",
            maximum_period_ends_on=date(2035, 1, 1),
        ),
        covered_from=covered_from,
        covered_until=covered_until,
        history=history,
        requested_free_amount=requested_free_amount,
    )


def _operations(*, territory: ResidenceTerritory = ResidenceTerritory.COMMON) -> ActivityAssetOperations:
    operations = ActivityAssetOperations(
        repository=MemoryRepository(),
        ledger=MemoryLedger(_ACQUISITION),
        forecast_operation=_forecast,
        taxpayer_modality=lambda: DirectEstimationRegime.SIMPLIFIED,
        register_authority=memory_register_authority(territory=territory),
    )
    operations.create(_revision(), ActivityAssetDescriptorFacts(name="Office laptop"))
    return operations


def _operations_that_cannot_work_out_modelo_130() -> ActivityAssetOperations:
    """Wire a register whose Modelo 130 box and schedule reads fail, so any reach for them shows."""

    def no_modelo_130_box(_period: Period) -> CasillaId:
        raise AssertionError("the Modelo 100 boxes alone must not read the Modelo 130 box")

    def no_forecast(
        revision: ActivityAssetRevision,
        *,
        covered_from: date,
        covered_until: date,
        history: AssetScheduleHistory,
        requested_free_amount: Decimal | None = None,
    ) -> ScheduledAmortizationCharge:
        raise AssertionError(f"the Modelo 100 boxes alone must not work out {covered_from} to {covered_until}")

    repository = MemoryRepository()
    ActivityAssetOperations(
        repository=repository,
        ledger=MemoryLedger(_ACQUISITION),
        forecast_operation=_forecast,
        taxpayer_modality=lambda: DirectEstimationRegime.SIMPLIFIED,
        register_authority=memory_register_authority(),
    ).create(_revision(), ActivityAssetDescriptorFacts(name="Office laptop"))
    return ActivityAssetOperations(
        repository=repository,
        ledger=MemoryLedger(_ACQUISITION),
        forecast_operation=no_forecast,
        taxpayer_modality=lambda: DirectEstimationRegime.SIMPLIFIED,
        register_authority=replace(memory_register_authority(), m130_amortization_casilla=no_modelo_130_box),
    )


def test_a_year_alone_projects_the_modelo_100_boxes_and_no_modelo_130_figure() -> None:
    operations = _operations()
    claim = operations.record_claim(
        operations.forecast(asset_id="laptop-1", covered_from=date(2025, 1, 1), covered_until=date(2026, 1, 1)),
        creating_operation="test.year",
    ).claim

    bare = operations.filing_handoff(tax_year=2025)
    framed = operations.filing_handoff(tax_year=2025, m130_period=Period.from_year_and_code(2025, "4T"))

    assert bare.material_m130 is None
    assert bare.intangible_m130 is None
    assert bare.material_m100.claim_ids == (claim.claim_id,)
    assert bare.material_m100 == framed.material_m100
    assert bare.intangible_m100 == framed.intangible_m100
    assert framed.material_m130 is not None


def test_a_year_alone_reads_no_modelo_130_authority_and_works_out_no_schedule() -> None:
    handoff = _operations_that_cannot_work_out_modelo_130().filing_handoff(tax_year=2025)

    assert handoff.material_m130 is None
    assert handoff.intangible_m130 is None


def test_a_year_alone_still_refuses_a_foral_residence() -> None:
    with pytest.raises(ActividadAssetValidationError, match="foral_territory"):
        _operations(territory=ResidenceTerritory.FORAL).filing_handoff(tax_year=2025)


@pytest.mark.parametrize("period", ["9T", "", "2025"])
def test_the_request_still_refuses_a_stated_period_that_is_not_one(period: str) -> None:
    with pytest.raises(ValidationError):
        ActivityAssetFilingHandoffRequest.model_validate_json(
            f'{{"profile_id":"{uuid4()}","tax_year":2025,"m130_period":"{period}"}}'
        )


def test_the_request_decodes_with_or_without_a_period() -> None:
    profile_id = uuid4()

    bare = ActivityAssetFilingHandoffRequest.model_validate_json(f'{{"profile_id":"{profile_id}","tax_year":2025}}')
    explicit_null = ActivityAssetFilingHandoffRequest.model_validate_json(
        f'{{"profile_id":"{profile_id}","tax_year":2025,"m130_period":null}}'
    )
    framed = ActivityAssetFilingHandoffRequest.model_validate_json(
        f'{{"profile_id":"{profile_id}","tax_year":2025,"m130_period":"2T"}}'
    )

    assert bare.m130_period is None
    assert explicit_null == bare
    assert framed.m130_period == "2T"


def test_the_handoff_round_trips_through_its_public_snapshot_with_the_modelo_130_absent() -> None:
    bare = _operations().filing_handoff(tax_year=2025)

    snapshot = ActivityAssetFilingHandoffSnapshot.from_domain(bare)
    restored = ActivityAssetFilingHandoffSnapshot.model_validate_json(snapshot.model_dump_json()).to_domain()

    assert snapshot.material_m130 is None
    assert snapshot.intangible_m130 is None
    assert restored == bare


def test_a_handoff_states_the_modelo_130_of_both_kinds_or_of_neither() -> None:
    framed = _operations().filing_handoff(tax_year=2025, m130_period=Period.from_year_and_code(2025, "4T"))

    with pytest.raises(ValidationError):
        ActivityAssetFilingHandoff(
            material_m100=framed.material_m100,
            intangible_m100=framed.intangible_m100,
            material_m130=framed.material_m130,
        )
    one_sided = ActivityAssetFilingHandoffSnapshot.from_domain(framed).model_dump() | {"intangible_m130": None}
    with pytest.raises(ValidationError):
        ActivityAssetFilingHandoffSnapshot.model_validate(one_sided)


def test_the_result_states_the_modelo_130_exactly_for_a_requested_period() -> None:
    operations = _operations()
    bare = operations.filing_handoff(tax_year=2025)
    framed = operations.filing_handoff(tax_year=2025, m130_period=Period.from_year_and_code(2025, "4T"))

    def result(handoff: ActivityAssetFilingHandoff, period: str | None) -> ActivityAssetFilingHandoffResult:
        return ActivityAssetFilingHandoffResult.model_validate(
            {
                "profile_id": uuid4(),
                "authority": _AUTHORITY,
                "outcome": "succeeded",
                "tax_year": 2025,
                "m130_period": period,
                "filing_handoff": handoff,
            }
        )

    assert result(bare, None).m130_period is None
    assert result(framed, "4T").m130_period == "4T"
    with pytest.raises(ValidationError):
        result(bare, "4T")
    with pytest.raises(ValidationError):
        result(framed, None)


def test_the_public_projection_decodes_a_handoff_without_a_period() -> None:
    bare = _operations().filing_handoff(tax_year=2025)
    document = {
        "profile_id": str(uuid4()),
        "authority": _AUTHORITY,
        "outcome": "succeeded",
        "tax_year": 2025,
        "filing_handoff": ActivityAssetFilingHandoffSnapshot.from_domain(bare).model_dump(mode="json"),
    }

    projection = ActivityAssetFilingHandoffProjection.model_validate_json(json.dumps(document))

    assert projection.m130_period is None
    assert projection.filing_handoff is not None
    assert projection.filing_handoff.material_m130 is None
    with pytest.raises(ValidationError):
        ActivityAssetFilingHandoffProjection.model_validate_json(json.dumps({**document, "m130_period": "4T"}))
