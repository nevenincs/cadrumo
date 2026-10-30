"""Contract tests for activity-asset claim identity and projections."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....core.period import Period
from ....calculations.registry.tests.published_authority import published_supported_filing_years
from ..claims import (
    AmortizationClaim,
    ClaimCoverageGap,
    effective_claims,
    project_m100,
    project_m130,
    record_claim,
    select_effective_claims,
    uncovered_claim_intervals,
)
from ..election import (
    AcquiredCondition,
    ActivityAssetAmortizationElection,
    AmortizationMethod,
    DirectEstimationRegime,
)
from ..errors import ActividadAssetClaimConflictError, ActividadAssetValidationError
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

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _supported_years() -> tuple[int, ...]:
    support = published_supported_filing_years()
    assert support is not None, "the published authority declares no support envelope"
    return support.years


_YEAR = _supported_years()[0]


def _claim(year: int = _YEAR, **overrides: object) -> AmortizationClaim:
    payload: dict[str, object] = {
        "asset_id": "office-computer",
        "asset_revision_id": "a" * 64,
        "asset_kind": AssetKind.MATERIAL,
        "tax_year": year,
        "covered_from": date(year, 1, 1),
        "covered_until": date(year, 4, 1),
        "amount": Decimal("200.00"),
        "schedule_fingerprint": "b" * 64,
        "authority_generation": "published-generation",
        "source_reference": "tabla-material",
        "creating_operation": "record-amortization",
    }
    payload.update(overrides)
    return AmortizationClaim.model_validate(payload)


def test_exact_retry_reuses_claim_and_changed_same_interval_refuses() -> None:
    original = _claim()
    recorded = record_claim((), original)
    replayed = record_claim(recorded.claims, original)

    assert replayed.reused_existing_claim
    assert replayed.claim.claim_id == original.claim_id
    with pytest.raises(ActividadAssetClaimConflictError, match="same asset"):
        record_claim(recorded.claims, _claim(amount=Decimal("201.00")))


def test_overlaps_refuse_but_supersession_allows_a_new_revision_of_same_asset() -> None:
    original = _claim()
    claims = record_claim((), original).claims
    with pytest.raises(ActividadAssetClaimConflictError, match="overlapping"):
        record_claim(
            claims,
            _claim(covered_from=date(_YEAR, 3, 1), covered_until=date(_YEAR, 5, 1)),
        )

    correction = _claim(
        asset_revision_id="d" * 64,
        amount=Decimal("199.99"),
        supersedes_claim_id=original.claim_id,
    )
    amended = record_claim(claims, correction).claims

    assert effective_claims(amended) == (correction,)
    assert correction.asset_id == original.asset_id
    assert correction.asset_revision_id != original.asset_revision_id


@pytest.mark.parametrize("year", _supported_years())
def test_m100_and_m130_reference_same_effective_claim_without_duplicate_basis_use(year: int) -> None:
    material = _claim(year)
    intangible = _claim(
        year,
        asset_revision_id="c" * 64,
        asset_kind=AssetKind.INTANGIBLE,
        covered_from=date(year, 4, 1),
        covered_until=date(year, 7, 1),
        amount=Decimal("300.00"),
    )
    claims = (material, intangible)

    material_m100 = project_m100(claims, asset_kind=AssetKind.MATERIAL, tax_year=year)
    intangible_m100 = project_m100(claims, asset_kind=AssetKind.INTANGIBLE, tax_year=year)
    material_m130 = project_m130(
        claims,
        period=Period.from_year_and_code(year, "1T"),
        asset_kind=AssetKind.MATERIAL,
    )

    assert material_m100.target_casilla_id == "0208"
    assert intangible_m100.target_casilla_id == "0227"
    assert material_m130.target_casilla_id == "02"
    assert material_m100.claim_ids == material_m130.claim_ids == (material.claim_id,)
    assert material_m100.amount == material_m130.amount == Decimal("200.00")


def _revision(*, in_service: date, out_of_service: date | None = None) -> ActivityAssetRevision:
    return ActivityAssetRevision(
        asset_id="office-computer",
        revision_number=1,
        acquisition=AcquisitionLineageReference(
            observed_transaction_id="a" * 64,
            invoice_evidence_id="invoice-gap-test",
            evidence_fingerprint="b" * 64,
        ),
        acquisition_shape=AcquisitionShape.PRIMARY_PURCHASE,
        asset_kind=AssetKind.MATERIAL,
        basis=ActivityAssetBasis(
            stage=AssetBasisStage.BUSINESS_ALLOCATED,
            basis_amount=Decimal("1000"),
            non_deductible_iva=Decimal("0"),
            prior_allocation_provenance="reviewed allocation record",
        ),
        in_service_date=in_service,
        out_of_service_date=out_of_service,
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


def _span_claim(start: date, end: date, **overrides: object) -> AmortizationClaim:
    return _claim(_YEAR, covered_from=start, covered_until=end, **overrides)


def _gaps(*pairs: tuple[date, date]) -> tuple[ClaimCoverageGap, ...]:
    return tuple(ClaimCoverageGap(covered_from=start, covered_until=end) for start, end in pairs)


_START = date(_YEAR, 1, 1)
_END = date(_YEAR + 1, 1, 1)


def test_gap_finder_reports_the_whole_window_without_claims() -> None:
    revision = _revision(in_service=_START)

    assert uncovered_claim_intervals(revision, (), start=_START, end=_END) == _gaps((_START, _END))


def test_gap_finder_reports_nothing_for_contiguous_claims() -> None:
    revision = _revision(in_service=_START)
    claims = (
        _span_claim(_START, date(_YEAR, 4, 1)),
        _span_claim(date(_YEAR, 4, 1), date(_YEAR, 7, 1), amount=Decimal("300.00")),
        _span_claim(date(_YEAR, 7, 1), _END, amount=Decimal("600.00")),
    )

    assert uncovered_claim_intervals(revision, claims, start=_START, end=_END) == ()


def test_gap_finder_reports_a_hole_and_the_trailing_remainder_in_order() -> None:
    revision = _revision(in_service=_START)
    claims = (
        _span_claim(date(_YEAR, 5, 1), date(_YEAR, 7, 1), amount=Decimal("50.00")),
        _span_claim(_START, date(_YEAR, 3, 1)),
    )

    assert uncovered_claim_intervals(revision, claims, start=_START, end=_END) == _gaps(
        (date(_YEAR, 3, 1), date(_YEAR, 5, 1)),
        (date(_YEAR, 7, 1), _END),
    )


def test_gap_finder_starts_at_a_mid_span_in_service_date() -> None:
    mid = date(_YEAR, 3, 15)
    revision = _revision(in_service=mid)

    assert uncovered_claim_intervals(revision, (), start=_START, end=_END) == _gaps((mid, _END))
    covered = (_span_claim(mid, date(_YEAR, 6, 1)),)
    assert uncovered_claim_intervals(revision, covered, start=_START, end=_END) == _gaps((date(_YEAR, 6, 1), _END))


def test_gap_finder_stops_at_the_out_of_service_date() -> None:
    revision = _revision(in_service=_START, out_of_service=date(_YEAR, 9, 1))
    claims = (_span_claim(_START, date(_YEAR, 6, 1)),)

    assert uncovered_claim_intervals(revision, claims, start=_START, end=_END) == _gaps(
        (date(_YEAR, 6, 1), date(_YEAR, 9, 1)),
    )


def test_gap_finder_returns_nothing_when_the_service_window_misses_the_span() -> None:
    revision = _revision(in_service=_START, out_of_service=date(_YEAR, 2, 1))
    later_span = (date(_YEAR, 6, 1), _END)

    assert uncovered_claim_intervals(revision, (), start=later_span[0], end=later_span[1]) == ()


def test_gap_finder_ignores_superseded_and_other_asset_claims() -> None:
    revision = _revision(in_service=_START)
    original = _span_claim(_START, date(_YEAR, 4, 1))
    replacement = _span_claim(
        _START,
        date(_YEAR, 4, 1),
        amount=Decimal("199.99"),
        supersedes_claim_id=original.claim_id,
    )
    other_asset = _span_claim(date(_YEAR, 4, 1), _END, asset_id="another-asset")

    assert uncovered_claim_intervals(revision, (original, replacement, other_asset), start=_START, end=_END) == _gaps(
        (date(_YEAR, 4, 1), _END),
    )


def test_gap_finder_refuses_an_empty_span() -> None:
    with pytest.raises(ActividadAssetValidationError, match="non-empty"):
        uncovered_claim_intervals(_revision(in_service=_START), (), start=_START, end=_START)


def test_select_effective_claims_applies_year_and_inclusive_cutoff() -> None:
    first = _span_claim(_START, date(_YEAR, 4, 1))
    second = _span_claim(date(_YEAR, 4, 1), date(_YEAR, 7, 1), amount=Decimal("300.00"))
    next_year = _claim(
        _YEAR + 1,
        covered_from=date(_YEAR + 1, 1, 1),
        covered_until=date(_YEAR + 1, 4, 1),
    )
    claims = (first, second, next_year)

    assert select_effective_claims(claims, tax_year=_YEAR) == (first, second)
    assert select_effective_claims(claims, tax_year=_YEAR, through=date(_YEAR, 3, 31)) == (first,)
    assert select_effective_claims(claims, tax_year=_YEAR, through=date(_YEAR, 3, 30)) == ()
