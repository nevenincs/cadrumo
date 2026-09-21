"""Contract tests for immutable activity-asset facts and 2025 schedules."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ..errors import ActividadAssetIncompleteError
from ..lifecycle import (
    AcquisitionLineageReference,
    AcquisitionShape,
    ActivityAssetBasis,
    ActivityAssetRevision,
    AssetBasisStage,
    AssetKind,
    OpeningAmortizationHistory,
    OpeningHistoryStatus,
    OwnershipMode,
)
from ..schedule import ScheduleAuthority, calendar_days_in_tax_year, schedule_charge

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _property_basis(**overrides: object) -> ActivityAssetBasis:
    payload: dict[str, object] = {
        "stage": AssetBasisStage.WHOLE_PROPERTY,
        "basis_amount": Decimal("100000"),
        "is_property": True,
        "construction_cost": Decimal("80000"),
        "land_cost": Decimal("20000"),
        "ownership_mode": OwnershipMode.FRACTIONAL_DIRECT,
        "ownership_share": Decimal("0.5"),
        "office_area": Decimal("20"),
        "total_area": Decimal("100"),
    }
    payload.update(overrides)
    return ActivityAssetBasis.model_validate(payload)


def _ordinary_basis(**overrides: object) -> ActivityAssetBasis:
    payload: dict[str, object] = {
        "stage": AssetBasisStage.TAXPAYER_OWNED,
        "basis_amount": Decimal("1000"),
        "business_use_share": Decimal("0.8"),
    }
    payload.update(overrides)
    return ActivityAssetBasis.model_validate(payload)


def _revision(**overrides: object) -> ActivityAssetRevision:
    payload: dict[str, object] = {
        "asset_id": "home-office",
        "revision_number": 1,
        "acquisition": AcquisitionLineageReference(
            observed_transaction_id="a" * 64,
            observed_lineage_event_id="b" * 64,
            invoice_evidence_id="invoice-1",
            evidence_fingerprint="c" * 64,
        ),
        "acquisition_shape": AcquisitionShape.PRIMARY_PURCHASE,
        "asset_kind": AssetKind.MATERIAL,
        "basis": _property_basis(),
        "in_service_date": date(2025, 1, 1),
        "opening_history": OpeningAmortizationHistory(
            status=OpeningHistoryStatus.KNOWN,
            accumulated_amount=Decimal("0"),
        ),
    }
    payload.update(overrides)
    return ActivityAssetRevision.model_validate(payload)


def _authority(**overrides: object) -> ScheduleAuthority:
    payload: dict[str, object] = {
        "asset_kind": AssetKind.MATERIAL,
        "annual_rate": Decimal("0.10"),
        "authority_generation": "2025.1",
        "source_reference": "tabla-material-2025",
    }
    payload.update(overrides)
    return ScheduleAuthority.model_validate(payload)


def test_revision_identity_is_immutable_and_lineage_resolves_without_new_identity() -> None:
    revision = _revision()

    assert revision.revision_id == _revision().revision_id
    assert revision.acquisition.resolve_current_transaction_id({"a" * 64: "d" * 64}) == "d" * 64
    assert revision.is_stale_for({"a" * 64: "d" * 64})
    with pytest.raises(ValidationError):
        revision.asset_id = "other"  # type: ignore[misc]


def test_correction_keeps_asset_identity_and_links_to_prior_revision() -> None:
    original = _revision()
    correction = _revision(
        revision_number=2,
        supersedes_revision_id=original.revision_id,
        basis=_ordinary_basis(),
    )

    assert correction.asset_id == original.asset_id
    assert correction.revision_id != original.revision_id
    assert correction.supersedes_revision_id == original.revision_id


def test_initial_unsupported_acquisition_shapes_refuse() -> None:
    with pytest.raises(ValidationError, match="primary purchase"):
        _revision(acquisition_shape=AcquisitionShape.SPLIT_PAYMENT)


def test_whole_property_allocation_excludes_land_and_applies_share_and_area_once() -> None:
    allocation = _property_basis()

    assert allocation.deductible_basis() == Decimal("8000")


def test_ordinary_material_and_intangible_assets_do_not_need_property_facts() -> None:
    ordinary = _ordinary_basis()
    already_allocated = ActivityAssetBasis(
        stage=AssetBasisStage.BUSINESS_ALLOCATED,
        basis_amount=Decimal("800"),
        prior_allocation_provenance="transaction allocation revision 4",
    )
    material = _revision(basis=ordinary)
    intangible = _revision(asset_kind=AssetKind.INTANGIBLE, basis=already_allocated)

    assert ordinary.deductible_basis() == Decimal("800")
    assert already_allocated.deductible_basis() == Decimal("800")
    assert material.basis.is_property is False
    assert intangible.basis.is_property is False
    with pytest.raises(ValidationError, match="only valid for property"):
        ActivityAssetBasis(
            stage=AssetBasisStage.TAXPAYER_OWNED,
            basis_amount=Decimal("1000"),
            business_use_share=Decimal("1"),
            construction_cost=Decimal("800"),
        )
    with pytest.raises(ValidationError, match="whole-property"):
        ActivityAssetBasis(
            stage=AssetBasisStage.TAXPAYER_OWNED,
            basis_amount=Decimal("1000"),
            is_property=True,
            construction_cost=Decimal("800"),
            land_cost=Decimal("200"),
            office_area=Decimal("10"),
            total_area=Decimal("100"),
        )
    with pytest.raises(ValidationError, match="prior_allocation_provenance"):
        ActivityAssetBasis(stage=AssetBasisStage.BUSINESS_ALLOCATED, basis_amount=Decimal("800"))


def test_spousal_property_and_missing_opening_history_fail_closed() -> None:
    with pytest.raises(ValidationError, match="spousal"):
        _property_basis(
            ownership_mode=OwnershipMode.SPOUSAL_COMMUNITY,
            ownership_share=None,
        ).deductible_basis()
    missing = _revision(
        opening_history=OpeningAmortizationHistory(status=OpeningHistoryStatus.MISSING),
    )
    with pytest.raises(ActividadAssetIncompleteError, match="opening"):
        schedule_charge(missing, _authority(), covered_from=date(2025, 1, 1), covered_until=date(2025, 4, 1))


def test_schedule_distinguishes_material_intangible_and_uses_actual_service_days() -> None:
    material = schedule_charge(
        _revision(in_service_date=date(2025, 7, 1)),
        _authority(),
        covered_from=date(2025, 1, 1),
        covered_until=date(2026, 1, 1),
    )
    intangible_revision = _revision(asset_kind=AssetKind.INTANGIBLE, basis=_ordinary_basis())
    intangible_authority = _authority(asset_kind=AssetKind.INTANGIBLE)
    intangible = schedule_charge(
        intangible_revision,
        intangible_authority,
        covered_from=date(2025, 1, 1),
        covered_until=date(2026, 1, 1),
    )

    assert material.service_days == 184
    assert material.amount == Decimal("403.29")
    assert intangible.amount == Decimal("80.00")


def test_leap_year_denominator_and_final_residual_cap_emit_cents() -> None:
    revision = _revision(in_service_date=date(2025, 1, 1), residual_value=Decimal("7999.995"))
    capped = schedule_charge(
        revision,
        _authority(),
        covered_from=date(2025, 1, 1),
        covered_until=date(2026, 1, 1),
    )

    assert calendar_days_in_tax_year(2024) == 366
    assert calendar_days_in_tax_year(2025) == 365
    assert capped.amount == Decimal("0.01")
