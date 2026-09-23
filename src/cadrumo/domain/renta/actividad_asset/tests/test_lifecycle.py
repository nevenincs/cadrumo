"""Contract tests for immutable activity-asset facts and 2025 schedules."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ..election import AcquiredCondition, ActivityAssetAmortizationElection, AmortizationMethod, DirectEstimationRegime
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
from ..schedule import AssetScheduleHistory, ScheduleAuthority, calendar_days_in_tax_year, schedule_charge

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_NO_HISTORY = AssetScheduleHistory()


def _linear_election(
    class_key: str = "edificio-comercial-administrativo-servicios-vivienda",
) -> ActivityAssetAmortizationElection:
    return ActivityAssetAmortizationElection(
        regime=DirectEstimationRegime.NORMAL,
        method=AmortizationMethod.LINEAR,
        authority_class_key=class_key,
    )


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
        "acquired_condition": AcquiredCondition.NEW,
        "amortization": _linear_election(),
    }
    payload.update(overrides)
    return ActivityAssetRevision.model_validate(payload)


def _authority(revision: ActivityAssetRevision, **overrides: object) -> ScheduleAuthority:
    payload: dict[str, object] = {
        "tax_year": 2025,
        "asset_kind": revision.asset_kind,
        "method": AmortizationMethod.LINEAR,
        "election_fingerprint": revision.amortization.fingerprint,
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
        schedule_charge(
            missing,
            _authority(missing),
            covered_from=date(2025, 1, 1),
            covered_until=date(2025, 4, 1),
            history=_NO_HISTORY,
        )


def test_schedule_distinguishes_material_intangible_and_uses_actual_service_days() -> None:
    material_revision = _revision(in_service_date=date(2025, 7, 1))
    material = schedule_charge(
        material_revision,
        _authority(material_revision),
        covered_from=date(2025, 1, 1),
        covered_until=date(2026, 1, 1),
        history=_NO_HISTORY,
    )
    intangible_revision = _revision(
        asset_kind=AssetKind.INTANGIBLE,
        basis=_ordinary_basis(),
        amortization=_linear_election("intangible-software"),
    )
    intangible = schedule_charge(
        intangible_revision,
        _authority(intangible_revision),
        covered_from=date(2025, 1, 1),
        covered_until=date(2026, 1, 1),
        history=_NO_HISTORY,
    )

    # 8,000 x 10% x 184/365 and 800 x 10% x 365/365, rounded half-up at emission.
    assert material.service_days == 184
    assert material.amount == Decimal("403.29")
    assert intangible.amount == Decimal("80.00")


def test_rate_applies_to_the_basis_less_residual_value_and_is_capped_at_the_remaining_base() -> None:
    residual = _revision(residual_value=Decimal("800"))
    nearly_amortized = _revision(
        residual_value=Decimal("800"),
        opening_history=OpeningAmortizationHistory(
            status=OpeningHistoryStatus.KNOWN,
            accumulated_amount=Decimal("7100"),
        ),
    )

    charge = schedule_charge(
        residual,
        _authority(residual),
        covered_from=date(2025, 1, 1),
        covered_until=date(2026, 1, 1),
        history=_NO_HISTORY,
    )
    capped = schedule_charge(
        nearly_amortized,
        _authority(nearly_amortized),
        covered_from=date(2025, 1, 1),
        covered_until=date(2026, 1, 1),
        history=_NO_HISTORY,
    )

    # RIS art. 3.2: (8,000 - 800) x 10% = 720; 7,200 - 7,100 leaves 100 to amortize.
    assert charge.amount == Decimal("720.00")
    assert capped.amount == Decimal("100.00")
    assert calendar_days_in_tax_year(2024) == 366
    assert calendar_days_in_tax_year(2025) == 365


def test_an_authority_resolved_for_another_election_is_refused() -> None:
    revision = _revision()
    other = _revision(amortization=_linear_election("otro-elemento"))

    with pytest.raises(ValueError, match="different amortization election"):
        schedule_charge(
            revision,
            _authority(other),
            covered_from=date(2025, 1, 1),
            covered_until=date(2026, 1, 1),
            history=_NO_HISTORY,
        )
