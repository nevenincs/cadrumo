"""Low-value free-depreciation election, cap, replay, and correction contracts."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ..claims import AmortizationClaim, effective_free_depreciation_claims, record_claim
from ..errors import ActividadAssetClaimConflictError, ActividadAssetUnsupportedError, ActividadAssetValidationError
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
    AmortizationMethod,
    FreeDepreciationElection,
    ScheduleAuthority,
    schedule_charge,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _revision(asset_id: str = "low-value-tool", *, basis: Decimal = Decimal("300.00")) -> ActivityAssetRevision:
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
            prior_allocation_provenance="reviewed business allocation",
        ),
        in_service_date=date(2025, 1, 1),
        opening_history=OpeningAmortizationHistory(
            status=OpeningHistoryStatus.KNOWN,
            accumulated_amount=Decimal("0"),
        ),
    )


def _authority(
    *,
    requested: Decimal = Decimal("300.00"),
    cap: Decimal = Decimal("25000.00"),
) -> ScheduleAuthority:
    return ScheduleAuthority(
        asset_kind=AssetKind.MATERIAL,
        authority_generation="irpf-2025-published-test",
        source_reference="modelo-100:2025:low-value-free",
        method=AmortizationMethod.LOW_VALUE_FREE,
        free_depreciation_unit_threshold=Decimal("300.00"),
        free_depreciation_annual_cap=cap,
        free_depreciation_election=FreeDepreciationElection(
            election_reference="operator-election-1",
            new_material_evidence_reference="invoice-confirms-new-material-item",
            unit_acquisition_value=Decimal("300.00"),
            requested_amount=requested,
        ),
    )


def _schedule(
    revision: ActivityAssetRevision,
    *,
    authority: ScheduleAuthority | None = None,
    accumulated_free: Decimal = Decimal("0"),
):
    return schedule_charge(
        revision,
        authority or _authority(),
        covered_from=date(2025, 1, 1),
        covered_until=date(2026, 1, 1),
        accumulated_effective_free_depreciation_claims=accumulated_free,
    )


def _claim(
    asset_id: str,
    *,
    amount: Decimal,
    cap: Decimal = Decimal("500.00"),
    supersedes_claim_id: str | None = None,
) -> AmortizationClaim:
    revision = _revision(asset_id, basis=amount)
    schedule = _schedule(revision, authority=_authority(requested=amount, cap=cap))
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
    with pytest.raises(ActividadAssetUnsupportedError, match="unit acquisition value"):
        _schedule(
            revision,
            authority=_authority(requested=Decimal("300.00")).model_copy(
                update={
                    "free_depreciation_election": FreeDepreciationElection(
                        election_reference="over-threshold",
                        new_material_evidence_reference="new-item-evidence",
                        unit_acquisition_value=Decimal("300.01"),
                        requested_amount=Decimal("300.00"),
                    )
                },
            ),
        )
    with pytest.raises(ActividadAssetValidationError, match="remaining lawful basis"):
        _schedule(revision, authority=_authority(requested=Decimal("300.01")))
    late = revision.model_copy(update={"in_service_date": date(2024, 1, 1)})
    with pytest.raises(ActividadAssetUnsupportedError, match="placed in service"):
        _schedule(late)


def test_effective_claims_enforce_exact_cap_without_request_order_or_retry_consumption() -> None:
    first = _claim("asset-a", amount=Decimal("300.00"))
    second = _claim("asset-b", amount=Decimal("200.00"))
    excess = _claim("asset-c", amount=Decimal("0.01"))

    recorded = record_claim((), first)
    retried = record_claim(recorded.claims, first)
    exact_cap = record_claim(retried.claims, second)

    assert retried.reused_existing_claim is True
    assert sum((claim.amount for claim in effective_free_depreciation_claims(exact_cap.claims, tax_year=2025)), Decimal("0")) == Decimal("500.00")
    with pytest.raises(ActividadAssetClaimConflictError, match="annual cap"):
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
    assert sum((claim.amount for claim in effective_free_depreciation_claims(result.claims, tax_year=2025)), Decimal("0")) == Decimal("200.00")


def test_linear_fallback_is_a_separate_operator_selection_not_an_implicit_cap_allocation() -> None:
    revision = _revision()
    linear = ScheduleAuthority(
        asset_kind=AssetKind.MATERIAL,
        annual_rate=Decimal("0.10"),
        authority_generation="irpf-2025-published-test",
        source_reference="modelo-100:2025:linear",
    )

    charge = schedule_charge(
        revision,
        linear,
        covered_from=date(2025, 1, 1),
        covered_until=date(2026, 1, 1),
    )

    assert charge.method is AmortizationMethod.LINEAR
    assert charge.amount == Decimal("30.00")
