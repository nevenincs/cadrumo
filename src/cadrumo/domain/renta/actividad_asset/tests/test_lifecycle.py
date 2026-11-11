"""Contract tests for immutable activity-asset facts and their yearly schedules."""

from __future__ import annotations

from calendar import isleap
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from itertools import pairwise

import pytest
from pydantic import ValidationError

from ....calculations.registry.tests.authored_editions import filing_year_envelope
from ..election import AcquiredCondition, ActivityAssetAmortizationElection, AmortizationMethod, DirectEstimationRegime
from ..errors import ActividadAssetIncompleteError, ActividadAssetUnsupportedError, ActividadAssetValidationError
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
from .lineage_projection import resolve_current_transaction_id

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_NO_HISTORY = AssetScheduleHistory()
_TAX_YEAR = filing_year_envelope().horizon
_YEAR_START = date(_TAX_YEAR, 1, 1)
_YEAR_END = date(_TAX_YEAR + 1, 1, 1)
_MID_YEAR = date(_TAX_YEAR, 7, 1)
_YEAR_DAYS = (_YEAR_END - _YEAR_START).days
_SERVICE_DAYS_FROM_MID_YEAR = (_YEAR_END - _MID_YEAR).days


def _accrued(amount: Decimal, rate: Decimal, days: int) -> Decimal:
    """Return ``amount`` x ``rate`` x ``days`` / the days of the schedule year, rounded half-up to cents."""
    return (amount * rate * days / _YEAR_DAYS).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


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
        "non_deductible_iva": Decimal("0"),
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
        "non_deductible_iva": Decimal("0"),
        "business_use_share": Decimal("0.8"),
    }
    payload.update(overrides)
    return ActivityAssetBasis.model_validate(payload)


def lifecycle_revision(**overrides: object) -> ActivityAssetRevision:
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
        "in_service_date": _YEAR_START,
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
        "tax_year": _TAX_YEAR,
        "asset_kind": revision.asset_kind,
        "method": AmortizationMethod.LINEAR,
        "election_fingerprint": revision.amortization.fingerprint,
        "annual_rate": Decimal("0.10"),
        "authority_generation": f"{_TAX_YEAR}.1",
        "source_reference": f"tabla-material-{_TAX_YEAR}",
    }
    payload.update(overrides)
    if overrides.get("method", AmortizationMethod.LINEAR) is AmortizationMethod.LINEAR:
        payload.setdefault("maximum_period_ends_on", date(_TAX_YEAR + 20, 1, 1))
    return ScheduleAuthority.model_validate(payload)


def test_revision_identity_is_immutable_and_lineage_resolves_without_new_identity() -> None:
    revision = lifecycle_revision()

    assert revision.revision_id == lifecycle_revision().revision_id
    assert resolve_current_transaction_id(revision.acquisition, {"a" * 64: "d" * 64}) == "d" * 64
    with pytest.raises(ValidationError):
        revision.asset_id = "other"  # type: ignore[misc]


def test_correction_keeps_asset_identity_and_links_to_prior_revision() -> None:
    original = lifecycle_revision()
    correction = lifecycle_revision(
        revision_number=2,
        supersedes_revision_id=original.revision_id,
        basis=_ordinary_basis(),
    )

    assert correction.asset_id == original.asset_id
    assert correction.revision_id != original.revision_id
    assert correction.supersedes_revision_id == original.revision_id


def test_initial_unsupported_acquisition_shapes_refuse() -> None:
    with pytest.raises(ValidationError, match="acquisition_shape_not_registerable"):
        lifecycle_revision(acquisition_shape=AcquisitionShape.SPLIT_PAYMENT)


def test_whole_property_allocation_excludes_land_and_applies_share_and_area_once() -> None:
    allocation = _property_basis()

    assert allocation.deductible_basis() == Decimal("8000")


def test_ordinary_material_and_intangible_assets_do_not_need_property_facts() -> None:
    ordinary = _ordinary_basis()
    already_allocated = ActivityAssetBasis(
        stage=AssetBasisStage.BUSINESS_ALLOCATED,
        basis_amount=Decimal("800"),
        non_deductible_iva=Decimal("0"),
        prior_allocation_provenance="transaction allocation revision 4",
    )
    material = lifecycle_revision(basis=ordinary)
    intangible = lifecycle_revision(asset_kind=AssetKind.INTANGIBLE, basis=already_allocated)

    assert ordinary.deductible_basis() == Decimal("800")
    assert already_allocated.deductible_basis() == Decimal("800")
    assert material.basis.is_property is False
    assert intangible.basis.is_property is False
    with pytest.raises(ValidationError, match="basis_stage_refuses_fact"):
        ActivityAssetBasis(
            stage=AssetBasisStage.TAXPAYER_OWNED,
            basis_amount=Decimal("1000"),
            non_deductible_iva=Decimal("0"),
            business_use_share=Decimal("1"),
            construction_cost=Decimal("800"),
        )
    with pytest.raises(ValidationError, match="basis_mixed_use_needs_whole_property"):
        ActivityAssetBasis(
            stage=AssetBasisStage.TAXPAYER_OWNED,
            basis_amount=Decimal("1000"),
            non_deductible_iva=Decimal("0"),
            is_property=True,
            construction_cost=Decimal("800"),
            land_cost=Decimal("200"),
            office_area=Decimal("10"),
            total_area=Decimal("100"),
        )
    with pytest.raises(ValidationError, match="basis_stage_requires_fact"):
        ActivityAssetBasis(
            stage=AssetBasisStage.BUSINESS_ALLOCATED,
            basis_amount=Decimal("800"),
            non_deductible_iva=Decimal("0"),
        )


def test_spousal_property_and_missing_opening_history_fail_closed() -> None:
    with pytest.raises(ValidationError, match="spousal"):
        _property_basis(
            ownership_mode=OwnershipMode.SPOUSAL_COMMUNITY,
            ownership_share=None,
        ).deductible_basis()
    missing = lifecycle_revision(
        opening_history=OpeningAmortizationHistory(status=OpeningHistoryStatus.MISSING),
    )
    with pytest.raises(ActividadAssetIncompleteError, match="opening"):
        schedule_charge(
            missing,
            _authority(missing),
            covered_from=_YEAR_START,
            covered_until=date(_TAX_YEAR, 4, 1),
            history=_NO_HISTORY,
        )


def test_a_non_zero_opening_amount_requires_the_last_tax_year_it_covers() -> None:
    with pytest.raises(ValidationError, match="opening_amount_requires_covered_year"):
        OpeningAmortizationHistory(status=OpeningHistoryStatus.KNOWN, accumulated_amount=Decimal("3000"))
    with pytest.raises(ValidationError, match="opening_covered_year_requires_amount"):
        OpeningAmortizationHistory(
            status=OpeningHistoryStatus.KNOWN,
            accumulated_amount=Decimal("0"),
            covered_through_tax_year=_TAX_YEAR,
        )
    with pytest.raises(ValidationError, match="opening_covered_year_requires_amount"):
        OpeningAmortizationHistory(status=OpeningHistoryStatus.MISSING, covered_through_tax_year=_TAX_YEAR)


def test_an_opening_year_before_the_in_service_year_is_refused_and_the_in_service_year_is_accepted() -> None:
    def opening_through(year: int) -> OpeningAmortizationHistory:
        return OpeningAmortizationHistory(
            status=OpeningHistoryStatus.KNOWN,
            accumulated_amount=Decimal("3000"),
            covered_through_tax_year=year,
        )

    with pytest.raises(ValidationError, match="opening_year_before_in_service"):
        lifecycle_revision(in_service_date=_MID_YEAR, opening_history=opening_through(_TAX_YEAR - 1))

    accepted = lifecycle_revision(in_service_date=_MID_YEAR, opening_history=opening_through(_TAX_YEAR))
    assert accepted.opening_history.covered_through_tax_year == _TAX_YEAR


def test_opening_year_changes_the_revision_identity() -> None:
    def revision_through(year: int) -> ActivityAssetRevision:
        return lifecycle_revision(
            in_service_date=_YEAR_START,
            opening_history=OpeningAmortizationHistory(
                status=OpeningHistoryStatus.KNOWN,
                accumulated_amount=Decimal("3000"),
                covered_through_tax_year=year,
            ),
        )

    assert revision_through(_TAX_YEAR).revision_id != revision_through(_TAX_YEAR + 1).revision_id


def test_schedule_distinguishes_material_intangible_and_uses_actual_service_days() -> None:
    material_revision = lifecycle_revision(in_service_date=_MID_YEAR)
    material = schedule_charge(
        material_revision,
        _authority(material_revision),
        covered_from=_YEAR_START,
        covered_until=_YEAR_END,
        history=_NO_HISTORY,
    )
    intangible_revision = lifecycle_revision(
        asset_kind=AssetKind.INTANGIBLE,
        basis=_ordinary_basis(),
        amortization=_linear_election("intangible-software"),
    )
    intangible = schedule_charge(
        intangible_revision,
        _authority(intangible_revision),
        covered_from=_YEAR_START,
        covered_until=_YEAR_END,
        history=_NO_HISTORY,
    )

    # 8,000 x 10% x the days in service / the days of the year, and 800 x 10% over the whole year,
    # rounded half-up at emission.
    assert material.service_days == _SERVICE_DAYS_FROM_MID_YEAR
    assert material.amount == _accrued(Decimal("8000"), Decimal("0.10"), _SERVICE_DAYS_FROM_MID_YEAR)
    assert intangible.amount == _accrued(Decimal("800"), Decimal("0.10"), _YEAR_DAYS)
    assert intangible.amount == Decimal("80.00")


def test_rate_applies_to_the_basis_less_residual_value_and_is_capped_at_the_remaining_base() -> None:
    residual = lifecycle_revision(residual_value=Decimal("800"))
    nearly_amortized = lifecycle_revision(
        residual_value=Decimal("800"),
        opening_history=OpeningAmortizationHistory(
            status=OpeningHistoryStatus.KNOWN,
            accumulated_amount=Decimal("7100"),
            covered_through_tax_year=_TAX_YEAR,
        ),
    )

    charge = schedule_charge(
        residual,
        _authority(residual),
        covered_from=_YEAR_START,
        covered_until=_YEAR_END,
        history=_NO_HISTORY,
    )
    capped = schedule_charge(
        nearly_amortized,
        _authority(nearly_amortized),
        covered_from=_YEAR_START,
        covered_until=_YEAR_END,
        history=_NO_HISTORY,
    )

    # RIS art. 3.2: (8,000 - 800) x 10% = 720; 7,200 - 7,100 leaves 100 to amortize.
    assert charge.amount == Decimal("720.00")
    assert capped.amount == Decimal("100.00")
    assert {isleap(year) for year in filing_year_envelope().years} == {False, True}
    for year in filing_year_envelope().years:
        assert calendar_days_in_tax_year(year) == (366 if isleap(year) else 365), year


def test_contiguous_period_charges_sum_exactly_to_the_annual_figure() -> None:
    revision = lifecycle_revision(basis=_ordinary_basis(business_use_share=Decimal("1")))
    authority = _authority(revision, annual_rate=Decimal("0.12"))
    quarter_ends = (
        _YEAR_START,
        date(_TAX_YEAR, 4, 1),
        _MID_YEAR,
        date(_TAX_YEAR, 10, 1),
        _YEAR_END,
    )

    charges = [
        schedule_charge(revision, authority, covered_from=start, covered_until=end, history=_NO_HISTORY).amount
        for start, end in pairwise(quarter_ends)
    ]

    # 1,000 x 12% accrues day by day; each charge is the cumulative accrual rounded at the quarter
    # end less the one before, so the four charges sum exactly to the annual 120.00.
    accrued_at_ends = [_accrued(Decimal("1000"), Decimal("0.12"), (end - _YEAR_START).days) for end in quarter_ends[1:]]
    assert charges == [later - earlier for earlier, later in pairwise([Decimal("0"), *accrued_at_ends])]
    assert sum(charges) == Decimal("120.00")


def test_a_mid_year_start_splits_its_charge_without_a_rounding_gap() -> None:
    revision = lifecycle_revision(basis=_ordinary_basis(business_use_share=Decimal("1")), in_service_date=_MID_YEAR)
    authority = _authority(revision, annual_rate=Decimal("0.12"))

    def charged(start: date, end: date) -> Decimal:
        return schedule_charge(revision, authority, covered_from=start, covered_until=end, history=_NO_HISTORY).amount

    # The charge for the days in service is accrued once and each period carries the cumulative
    # rounding at its end, so the two quarters add up to the half-year figure.
    third_quarter_end = date(_TAX_YEAR, 10, 1)
    accrued_at_third_quarter_end = _accrued(Decimal("1000"), Decimal("0.12"), (third_quarter_end - _MID_YEAR).days)
    in_service_year = _accrued(Decimal("1000"), Decimal("0.12"), _SERVICE_DAYS_FROM_MID_YEAR)
    assert charged(_YEAR_START, _YEAR_END) == in_service_year
    assert charged(_MID_YEAR, third_quarter_end) == accrued_at_third_quarter_end
    assert charged(third_quarter_end, _YEAR_END) == in_service_year - accrued_at_third_quarter_end


def test_an_authority_resolved_for_another_election_is_refused() -> None:
    revision = lifecycle_revision()
    other = lifecycle_revision(amortization=_linear_election("otro-elemento"))

    with pytest.raises(ActividadAssetValidationError, match="schedule_authority_election_mismatch"):
        schedule_charge(
            revision,
            _authority(other),
            covered_from=_YEAR_START,
            covered_until=_YEAR_END,
            history=_NO_HISTORY,
        )


def test_non_deductible_iva_joins_the_cost_once_before_each_stage_allocation() -> None:
    ordinary = _ordinary_basis(non_deductible_iva=Decimal("210"))
    already_allocated = ActivityAssetBasis(
        stage=AssetBasisStage.BUSINESS_ALLOCATED,
        basis_amount=Decimal("800"),
        non_deductible_iva=Decimal("168"),
        prior_allocation_provenance="transaction allocation revision 4",
    )
    building = _property_basis(non_deductible_iva=Decimal("8000"))

    # (1,000 + 210) x 0.8, 800 + 168 already allocated, (80,000 + 8,000) x 0.5 x 20/100.
    assert ordinary.deductible_basis() == Decimal("968.0")
    assert already_allocated.deductible_basis() == Decimal("968")
    assert building.deductible_basis() == Decimal("8800")
    assert ordinary.acquisition_cost() == Decimal("1210")
    assert building.acquisition_cost() == Decimal("108000")
    # The price keeps its own field and the land stays outside the amortizable base.
    assert building.construction_cost is not None
    assert building.land_cost is not None
    assert building.basis_amount == building.construction_cost + building.land_cost


def test_non_deductible_iva_is_a_required_fact_and_zero_is_stated_explicitly() -> None:
    payload = _ordinary_basis().model_dump()
    del payload["non_deductible_iva"]
    with pytest.raises(ValidationError, match="non_deductible_iva"):
        ActivityAssetBasis.model_validate(payload)
    with pytest.raises(ValidationError, match="finite non-negative"):
        _ordinary_basis(non_deductible_iva=Decimal("-0.01"))
    assert _ordinary_basis(non_deductible_iva=Decimal("0")).deductible_basis() == Decimal("800.0")


def test_amortizable_basis_and_the_annual_charge_carry_the_non_deductible_iva() -> None:
    revision = lifecycle_revision(
        basis=_ordinary_basis(non_deductible_iva=Decimal("210")),
        residual_value=Decimal("68"),
    )

    charge = schedule_charge(
        revision,
        _authority(revision),
        covered_from=_YEAR_START,
        covered_until=_YEAR_END,
        history=_NO_HISTORY,
    )

    # 968 less residual 68 is 900 amortizable; 900 x 10% is 90.00.
    assert revision.amortizable_basis() == Decimal("900.0")
    assert charge.amount == Decimal("90.00")


def test_an_unexercised_financial_lease_is_refused_with_its_statutory_route() -> None:
    with pytest.raises(ValidationError, match="financial_lease_unexercised"):
        lifecycle_revision(acquisition_shape=AcquisitionShape.FINANCIAL_LEASE_UNEXERCISED)


def test_later_afectacion_amortizes_from_in_service_date_on_the_full_acquisition_value() -> None:
    # The element was bought and used privately before the mid-year in-service date; no private year
    # is deemed amortized.
    revision = lifecycle_revision(
        in_service_date=_MID_YEAR,
        basis=_ordinary_basis(business_use_share=Decimal("1")),
    )

    first_year = schedule_charge(
        revision,
        _authority(revision),
        covered_from=_YEAR_START,
        covered_until=_YEAR_END,
        history=_NO_HISTORY,
    )
    next_year = schedule_charge(
        revision,
        _authority(revision, tax_year=_TAX_YEAR + 1),
        covered_from=_YEAR_END,
        covered_until=date(_TAX_YEAR + 2, 1, 1),
        history=AssetScheduleHistory(accumulated_before_tax_year=first_year.amount),
    )

    # 1,000 x 10% x the days in service / the days of the year from 1 July; the next year is the full
    # 100.00 with only that charge deducted from the base, so nothing was taken for the private years.
    assert first_year.amount == _accrued(Decimal("1000"), Decimal("0.10"), _SERVICE_DAYS_FROM_MID_YEAR)
    assert next_year.amount == Decimal("100.00")
    assert revision.opening_history.accumulated_amount == Decimal("0")
    with pytest.raises(ActividadAssetUnsupportedError, match="covered_interval_without_service_days"):
        schedule_charge(
            revision,
            _authority(revision, tax_year=_TAX_YEAR - 1),
            covered_from=date(_TAX_YEAR - 1, 1, 1),
            covered_until=_YEAR_START,
            history=_NO_HISTORY,
        )
