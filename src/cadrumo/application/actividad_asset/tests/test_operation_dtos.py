"""Strict registered-operation snapshots preserve canonical asset facts."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.application.actividad_asset.history import ActivityAssetHistory
from cadrumo.application.actividad_asset.operation_dtos import (
    ActivityAssetFilingHandoffSnapshot,
    ActivityAssetHistorySnapshot,
    ActivityAssetRevisionSnapshot,
    ScheduledAmortizationChargeSnapshot,
)
from cadrumo.application.actividad_asset.operations import ActivityAssetFilingHandoff
from cadrumo.domain.renta.actividad_asset.claims import (
    AmortizationClaim,
    ClaimProjection,
    asset_schedule_history,
)
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
from cadrumo.domain.renta.actividad_asset.schedule import ScheduleAuthority, schedule_charge

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _revision() -> ActivityAssetRevision:
    return ActivityAssetRevision(
        asset_id="operation-dto-asset",
        revision_number=1,
        acquisition=AcquisitionLineageReference(
            observed_transaction_id="a" * 64,
            invoice_evidence_id="invoice-operation-dto",
            evidence_fingerprint="b" * 64,
        ),
        acquisition_shape=AcquisitionShape.PRIMARY_PURCHASE,
        asset_kind=AssetKind.MATERIAL,
        basis=ActivityAssetBasis(
            stage=AssetBasisStage.BUSINESS_ALLOCATED,
            basis_amount=Decimal("300.00"),
            prior_allocation_provenance="reviewed test allocation",
        ),
        in_service_date=date(2025, 1, 1),
        opening_history=OpeningAmortizationHistory(
            status=OpeningHistoryStatus.KNOWN,
            accumulated_amount=Decimal("0"),
        ),
        acquired_condition=AcquiredCondition.NEW,
        amortization=ActivityAssetAmortizationElection(
            regime=DirectEstimationRegime.NORMAL,
            method=AmortizationMethod.LINEAR,
            authority_class_key="equipo-proceso-informacion",
        ),
    )


def test_public_asset_snapshots_roundtrip_every_decimal_bearing_history_fact() -> None:
    revision = _revision()
    schedule = schedule_charge(
        revision,
        ScheduleAuthority(
            tax_year=2025,
            asset_kind=AssetKind.MATERIAL,
            method=AmortizationMethod.LINEAR,
            election_fingerprint=revision.amortization.fingerprint,
            annual_rate=Decimal("0.26"),
            authority_generation="test-pinned-generation",
            source_reference="test-pinned-m100-2025",
        ),
        covered_from=date(2025, 1, 1),
        covered_until=date(2026, 1, 1),
        history=asset_schedule_history((), (revision,), asset_id=revision.asset_id, tax_year=2025),
    )
    claim = AmortizationClaim.from_schedule(
        schedule,
        asset_kind=revision.asset_kind,
        creating_operation="operation-dto-test",
    )
    history = ActivityAssetHistory(revisions=(revision,), claims=(claim,))

    revision_snapshot = ActivityAssetRevisionSnapshot.from_domain(revision)
    schedule_snapshot = ScheduledAmortizationChargeSnapshot.from_domain(schedule)
    history_snapshot = ActivityAssetHistorySnapshot.from_domain(history)

    assert (
        ActivityAssetRevisionSnapshot.model_validate_json(revision_snapshot.model_dump_json()).to_domain() == revision
    )
    assert (
        ScheduledAmortizationChargeSnapshot.model_validate_json(schedule_snapshot.model_dump_json()).to_domain()
        == schedule
    )
    assert ActivityAssetHistorySnapshot.model_validate_json(history_snapshot.model_dump_json()).to_domain() == history
    assert '"basis_amount":{"decimal":"300.00"}' in revision_snapshot.model_dump_json()
    assert '"amount":{"decimal":"78.00"}' in schedule_snapshot.model_dump_json()


def test_filing_handoff_snapshots_preserve_decimal_claim_projections() -> None:
    projection = ClaimProjection(
        target_casilla_id="06",
        tax_year=2025,
        claim_ids=("c" * 64,),
        amount=Decimal("78.00"),
    )
    handoff = ActivityAssetFilingHandoff(
        material_m100=projection,
        intangible_m100=projection.model_copy(update={"target_casilla_id": "07", "amount": Decimal("0.00")}),
        material_m130=projection,
        intangible_m130=projection.model_copy(update={"target_casilla_id": "07", "amount": Decimal("0.00")}),
    )

    snapshot = ActivityAssetFilingHandoffSnapshot.from_domain(handoff)
    reopened = ActivityAssetFilingHandoffSnapshot.model_validate_json(snapshot.model_dump_json()).to_domain()

    assert reopened == handoff
    assert '"amount":{"decimal":"78.00"}' in snapshot.model_dump_json()
