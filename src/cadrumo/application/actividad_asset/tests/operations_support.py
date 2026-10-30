"""Shared builders for activity-asset operation tests: one acquisition, one revision, one wired operations object."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from cadrumo.application.actividad_asset.operations import ActivityAssetOperations
from cadrumo.domain.contribuyente.tax_residence import ResidenceTerritory
from cadrumo.domain.renta.actividad_asset.election import (
    AcquiredCondition,
    ActivityAssetAmortizationElection,
    AmortizationMethod,
    DirectEstimationRegime,
)
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

ACQUISITION = acquisition_transaction()


def build_revision(
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
            observed_transaction_id=ACQUISITION.transaction_id,
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


def build_forecast(
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


def build_operations(*, territory: ResidenceTerritory = ResidenceTerritory.COMMON) -> ActivityAssetOperations:
    operations = ActivityAssetOperations(
        repository=MemoryRepository(),
        ledger=MemoryLedger(ACQUISITION),
        forecast_operation=build_forecast,
        taxpayer_modality=lambda: DirectEstimationRegime.SIMPLIFIED,
        register_authority=memory_register_authority(territory=territory),
    )
    operations.create(build_revision(), ActivityAssetDescriptorFacts(name="Office laptop"))
    return operations
