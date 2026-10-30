"""Low-value free-depreciation election, cap, replay, and correction contracts."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ..claims import AmortizationClaim, effective_free_depreciation_claims, record_claim
from ..election import (
    AcquiredCondition,
    ActivityAssetAmortizationElection,
    AmortizationMethod,
    DirectEstimationRegime,
    LowValueElection,
)
from ..errors import (
    ActividadAssetClaimConflictError,
    ActividadAssetIncompleteError,
    ActividadAssetUnsupportedError,
    ActividadAssetValidationError,
)
from ..lifecycle import (
    AcquisitionLineageReference,
    AcquisitionShape,
    ActivityAssetBasis,
    ActivityAssetRevision,
    AssetBasisStage,
    AssetKind,
    OpeningAmortizationHistory,
    OpeningHistoryStatus,
)
from ..schedule import (
    AssetScheduleHistory,
    ScheduleAuthority,
    ScheduledAmortizationCharge,
    parse_requested_free_amount,
    schedule_charge,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _election() -> ActivityAssetAmortizationElection:
    return ActivityAssetAmortizationElection(
        regime=DirectEstimationRegime.SIMPLIFIED,
        method=AmortizationMethod.LOW_VALUE_FREE,
        authority_class_key="util-herramienta",
        low_value=LowValueElection(
            election_reference="operator-election-1",
            new_material_evidence_reference="invoice-confirms-new-material-item",
        ),
    )


def _revision(
    asset_id: str = "low-value-tool",
    *,
    basis: Decimal = Decimal("300.00"),
    non_deductible_iva: Decimal = Decimal("0"),
    election: ActivityAssetAmortizationElection | None = None,
) -> ActivityAssetRevision:
    return ActivityAssetRevision(
        asset_id=asset_id,
        revision_number=1,
        acquisition=AcquisitionLineageReference(
            observed_transaction_id="a" * 64,
            invoice_evidence_id=f"invoice-{asset_id}",
            evidence_fingerprint="b" * 64,
        ),
        acquisition_shape=AcquisitionShape.PRIMARY_PURCHASE,
        asset_kind=AssetKind.MATERIAL,
        basis=ActivityAssetBasis(
            stage=AssetBasisStage.BUSINESS_ALLOCATED,
            basis_amount=basis,
            non_deductible_iva=non_deductible_iva,
            prior_allocation_provenance="reviewed business allocation",
        ),
        in_service_date=date(2025, 1, 1),
        opening_history=OpeningAmortizationHistory(
            status=OpeningHistoryStatus.KNOWN,
            accumulated_amount=Decimal("0"),
        ),
        acquired_condition=AcquiredCondition.NEW,
        amortization=election or _election(),
    )


def _authority(revision: ActivityAssetRevision, *, cap: Decimal = Decimal("25000.00")) -> ScheduleAuthority:
    low_value = revision.amortization.low_value
    return ScheduleAuthority(
        tax_year=2025,
        asset_kind=AssetKind.MATERIAL,
        method=AmortizationMethod.LOW_VALUE_FREE,
        election_fingerprint=revision.amortization.fingerprint,
        authority_generation="irpf-2025-published-test",
        source_reference="modelo-100:2025:low-value-free",
        free_depreciation_unit_threshold=Decimal("300.00"),
        free_depreciation_annual_cap=cap,
        low_value=low_value,
    )


def _schedule(
    revision: ActivityAssetRevision,
    *,
    requested: Decimal | None = Decimal("300.00"),
    cap: Decimal = Decimal("25000.00"),
    claimed_by_taxpayer: Decimal = Decimal("0"),
) -> ScheduledAmortizationCharge:
    return schedule_charge(
        revision,
        _authority(revision, cap=cap),
        covered_from=date(2025, 1, 1),
        covered_until=date(2026, 1, 1),
        history=AssetScheduleHistory(taxpayer_low_value_claimed_in_tax_year=claimed_by_taxpayer),
        requested_free_amount=requested,
    )


def _claim(
    asset_id: str,
    *,
    amount: Decimal,
    cap: Decimal = Decimal("500.00"),
    supersedes_claim_id: str | None = None,
) -> AmortizationClaim:
    revision = _revision(asset_id, basis=amount, election=_election())
    schedule = _schedule(revision, requested=amount, cap=cap)
    return AmortizationClaim.from_schedule(
        schedule,
        asset_kind=AssetKind.MATERIAL,
        creating_operation="test.low-value-free.claim",
        supersedes_claim_id=supersedes_claim_id,
    )


def test_explicit_election_preserves_evidence_and_forecast_does_not_consume_annual_cap() -> None:
    revision = _revision()

    first = _schedule(revision)
    second = _schedule(revision)

    assert first.amount == Decimal("300.00")
    assert second.amount == Decimal("300.00")
    assert first.free_depreciation_election_reference == "operator-election-1"
    assert first.free_depreciation_new_material_evidence_reference == "invoice-confirms-new-material-item"
    assert first.free_depreciation_unit_acquisition_value == Decimal("300.00")


def test_unit_threshold_new_material_and_explicit_amount_fail_closed() -> None:
    revision = _revision()
    with pytest.raises(ActividadAssetValidationError, match="free_amount_exceeds_remaining_basis"):
        _schedule(revision, requested=Decimal("300.01"))
    with pytest.raises(ActividadAssetIncompleteError, match="free_amount_required"):
        _schedule(revision, requested=None)
    with pytest.raises(ActividadAssetUnsupportedError, match="free_amount_exceeds_annual_cap"):
        _schedule(revision, cap=Decimal("500.00"), claimed_by_taxpayer=Decimal("200.01"))
    late = revision.model_copy(update={"in_service_date": date(2024, 1, 1)})
    with pytest.raises(ActividadAssetUnsupportedError, match="low_value_requires_entry_year"):
        _schedule(late)


def test_unit_value_is_price_plus_non_deductible_iva_against_the_300_euro_threshold() -> None:
    exactly_300 = _revision(basis=Decimal("300.00"), election=_election())
    assert _schedule(exactly_300).amount == Decimal("300.00")

    one_cent_over = _revision(basis=Decimal("300.01"), election=_election())
    with pytest.raises(ActividadAssetUnsupportedError, match="low_value_threshold_exceeded"):
        _schedule(one_cent_over, requested=Decimal("300.01"))

    # 280.00 price plus 25.00 non-deductible IVA is 305.00, above the threshold.
    price_plus_iva = _revision(
        basis=Decimal("280.00"),
        non_deductible_iva=Decimal("25.00"),
        election=_election(),
    )
    assert price_plus_iva.basis.acquisition_cost() == Decimal("305.00")
    with pytest.raises(ActividadAssetUnsupportedError, match="low_value_threshold_exceeded"):
        _schedule(price_plus_iva, requested=Decimal("305.00"))

    # 250.00 price plus 25.00 non-deductible IVA is 275.00, within the threshold.
    within = _revision(
        basis=Decimal("250.00"),
        non_deductible_iva=Decimal("25.00"),
        election=_election(),
    )
    assert _schedule(within, requested=Decimal("275.00")).amount == Decimal("275.00")


def test_effective_claims_enforce_exact_cap_without_request_order_or_retry_consumption() -> None:
    first = _claim("asset-a", amount=Decimal("300.00"))
    second = _claim("asset-b", amount=Decimal("200.00"))
    excess = _claim("asset-c", amount=Decimal("0.01"))

    recorded = record_claim((), first)
    retried = record_claim(recorded.claims, first)
    exact_cap = record_claim(retried.claims, second)

    assert retried.reused_existing_claim is True
    assert sum(
        (claim.amount for claim in effective_free_depreciation_claims(exact_cap.claims, tax_year=2025)), Decimal("0")
    ) == Decimal("500.00")
    with pytest.raises(ActividadAssetClaimConflictError, match="free_claims_exceed_annual_cap"):
        record_claim(exact_cap.claims, excess)


def test_correction_replaces_effective_free_claim_before_rechecking_cap() -> None:
    original = _claim("asset-a", amount=Decimal("300.00"))
    existing = record_claim((), original).claims
    corrected = _claim(
        "asset-a",
        amount=Decimal("200.00"),
        supersedes_claim_id=original.claim_id,
    )

    result = record_claim(existing, corrected)

    assert effective_free_depreciation_claims(result.claims, tax_year=2025) == (corrected,)
    assert sum(
        (claim.amount for claim in effective_free_depreciation_claims(result.claims, tax_year=2025)), Decimal("0")
    ) == Decimal("200.00")


def test_a_linear_election_is_a_separate_revision_not_an_implicit_cap_allocation() -> None:
    linear_revision = _revision(
        election=ActivityAssetAmortizationElection(
            regime=DirectEstimationRegime.SIMPLIFIED,
            method=AmortizationMethod.LINEAR,
            authority_class_key="util-herramienta",
        ),
    )
    linear = ScheduleAuthority(
        tax_year=2025,
        asset_kind=AssetKind.MATERIAL,
        method=AmortizationMethod.LINEAR,
        election_fingerprint=linear_revision.amortization.fingerprint,
        annual_rate=Decimal("0.10"),
        authority_generation="irpf-2025-published-test",
        source_reference="modelo-100:2025:linear",
    )

    charge = schedule_charge(
        linear_revision,
        linear,
        covered_from=date(2025, 1, 1),
        covered_until=date(2026, 1, 1),
        history=AssetScheduleHistory(),
    )

    assert charge.method is AmortizationMethod.LINEAR
    assert charge.amount == Decimal("30.00")
    with pytest.raises(ActividadAssetValidationError, match="free_amount_not_accepted"):
        schedule_charge(
            linear_revision,
            linear,
            covered_from=date(2025, 1, 1),
            covered_until=date(2026, 1, 1),
            history=AssetScheduleHistory(),
            requested_free_amount=Decimal("30.00"),
        )


def test_requested_free_amount_text_follows_the_canonical_decimal_grammar() -> None:
    assert parse_requested_free_amount(None) is None
    assert parse_requested_free_amount(" 250.00 ") == Decimal("250.00")
    # Sign and cent precision are the schedule's own refusal, not the reader's.
    assert parse_requested_free_amount("-1") == Decimal("-1")
    assert parse_requested_free_amount("0.125") == Decimal("0.125")
    for raw in ("", "NaN", "Infinity", "1e3", "+5", "1_000", "1.234", "1,5"):
        with pytest.raises(ActividadAssetValidationError, match="free_amount_not_decimal"):
            parse_requested_free_amount(raw)
